#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2003-2018 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""
Write e-mail information for use by the mail system to an LDIF file,
which can then be loaded into LDAP.

"""

from __future__ import unicode_literals

import base64
import argparse
from time import time as now

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.LDIFutils import ldapconf, map_spreads, ldif_outfile, \
    end_ldif_outfile, container_entry_string
from Cerebrum import Errors

logger = Factory.get_logger("cronjob")
default_spam_level = 9999
default_spam_action = 0
mail_dn = ldapconf('MAIL', 'dn')


def dict_to_ldif_string(d):
    """Stringify a dict LDIF-style.

    FIXME: Should this be moved to LDIFutils.py?

    Convert a dict with LDIF-attributes to a string that can be written
    directly to an LDIF file.

    @type d: dict (basestring to basestring/sequence of basestring)
    @param d:
      A dictionary with key,value pairs containing the attributes for some
      LDAP object. value-part can be either a scalar (a basestring) OR a
      sequence (list, tuple or set) thereof

    @rtype: basestring
    @return:
      A data 'chunk' (\n-separated bunch of lines) that can be written to an
      LDIF file directly. The resulting string is '\n'-terminated.
    """

    format = "%s: %s\n"
    result = list()
    for key, value in d.iteritems():
        if isinstance(value, (list, tuple, set)):
            result.extend(format % (key, tmp) for tmp in value)
        else:
            result.append(format % (key, value))

    return "".join(result)


def write_ldif():
    mail_targ = Email.EmailTarget(db)
    counter = 0
    curr = now()
    ldap.read_pending_moves()

    f.write(container_entry_string('MAIL'))

    for row in mail_targ.list_email_targets_ext():
        t = int(row['target_id'])
        if verbose > 1:
            logger.debug("Processing target id=%d", t)
        if t not in ldap.targ2addr:
            # There are no addresses for this target; hence, no mail
            # can reach it.  Move on.
            if verbose > 1:
                logger.debug("No addresses for target id=%s. Moving on.", t)
            continue

        tt = int(row['target_type'])
        et = row['target_entity_type']
        if et is not None:
            et = int(et)
        ei = row['target_entity_id']
        if ei is not None:
            ei = int(ei)
        alias = row['alias_value']
        run_as_id = row['using_uid']
        if run_as_id is not None:
            run_as_id = int(run_as_id)

        counter += 1
        if verbose and (counter % 5000) == 0:
            logger.debug("done %d list_email_targets(): %d sec.",
                         counter, now() - curr)

        target = ""
        uid = ""
        rest = ""

        # The structure is decided by what target-type the
        # target is (class EmailConstants in Email.py):
        tt = co.EmailTarget(int(tt))
        if verbose > 1:
            logger.debug("Target id=%s is of type %s", t, tt)

        if tt == co.email_target_account:
            # Target is the local delivery defined for the Account whose
            # account_id == email_target.target_entity_id.
            target = ""
            if et == co.entity_account:
                if ei in ldap.acc2name:
                    target = ldap.acc2name[ei]
                else:
                    logger.warn("Target id=%s (type %s): no user id=%s found",
                                t, tt, ei)
                    continue
            else:
                logger.warn("Target id=%s (type %s): wrong entity type: %s "
                            "(entity_id=%s)", t, tt, et, ei)
                continue

            # Find quota-settings:
            if t in ldap.targ2quota:
                soft, hard = ldap.targ2quota[t]
                rest += "softQuota: %s\n" % soft
                rest += "hardQuota: %s\n" % hard

            # Find vacations-settings:
            if t in ldap.targ2vacation:
                txt, start, end = ldap.targ2vacation[t]
                note = (txt or '<No message>').encode('utf-8')
                rest += "tripnote:: {}\n".format(base64.b64encode(note))
                rest += "tripnoteActive: TRUE\n"

            # See if e-mail delivery should be suspended.
            # We do try/raise/except to support what might be implemented
            # at other institutions.
            try:
                if cereconf.LDAP_INST != "uio":
                    raise AttributeError
            except AttributeError:
                if ei in ldap.pending:
                    rest += "mailPause: TRUE\n"

            # Does the event log have an unprocessed primary email change for
            # this email target?
            # pending_primary_email is populated by EmailLDAPUiOMixin
            if (hasattr(ldap, 'pending_primary_email') and
                    t in ldap.pending_primary_email):
                # maybe the event has been processed by now?
                pending_event = False

                for event_id in ldap.pending_primary_email[t]:
                    try:
                        db.get_event(event_id=event_id)
                        pending_event = True
                    except Errors.NotFoundError:
                        continue

                if pending_event:
                    rest += "mailPausePendingEvent: TRUE\n"

            # Any server info?
            rest += dict_to_ldif_string(ldap.get_server_info(row))

        elif tt == co.email_target_deleted:
            # Target type for addresses that are no longer working, but
            # for which it is useful to include of a short custom text in
            # the error message returned to the sender.  The text
            # is taken from email_target.alias_value
            if et == co.entity_account:
                if ei in ldap.acc2name:
                    target = ldap.acc2name[ei]
            if alias:
                rest += "forwardDestination: %s\n" % alias

        elif tt == co.email_target_forward:
            # Target is a pure forwarding mechanism; local deliveries
            # will only occur as indirect deliveries to the addresses
            # forwarded to.  Both email_target.target_entity_id and
            # email_target.alias_value should be NULL, as they are
            # ignored.  The email address(es) to forward to is taken
            # from table email_forward.
            pass

        elif tt in (co.email_target_pipe, co.email_target_RT,
                    co.email_target_file, co.email_target_Sympa):

            # Target is a shell pipe. The command (and args) to pipe mail
            # into is gathered from email_target.alias_value.  Iff
            # email_target.target_entity_id is set and belongs to an Account,
            # deliveries to this target will be run as that account.
            #   or
            # Target is a file. The absolute path of the file is gathered
            # from email_target.alias_value.  Iff email_target.target_entity_id
            # is set and belongs to an Account, deliveries to this target
            # will be run as that account.
            #   or
            # Target is a Sympa mailing list. The command (and args)
            # to pipe mail into is gathered from email_target.alias_value.
            # Iff email_target.target_entity_id is set and belongs to an
            # Account, deliveries to this target will be run as that
            # account.
            if alias is None:
                logger.warn("Target id=%s (type %s) needs an alias_value",
                            t, tt)
                continue

            if run_as_id is not None:
                if run_as_id in ldap.acc2name:
                    uid = ldap.acc2name[run_as_id]
                else:
                    logger.warn("Target id=%s (type %s) no user id=%s found",
                                t, tt, ei)
                    continue

        elif tt == co.email_target_multi:
            # Target is the set of `account`-type targets corresponding to
            # the Accounts that are first-level members of the Group that
            # has group_id == email_target.target_entity_id.

            if et == co.entity_group:
                try:
                    addrs, missing = ldap.get_multi_target(
                        ei, ignore_missing=True)
                except ValueError, e:
                    logger.warn("Target id=%s (type %s): %s", t, tt, e)
                    continue
                for addr in addrs:
                    rest += "forwardDestination: %s\n" % addr
                for addr in missing:
                    logger.warn("Target id=%s (type %s): "
                                "Multitarget group id %s: "
                                "account %s has no primary address",
                                t, tt, ei, addr)
            else:
                # A 'multi' target with no forwarding; seems odd.
                logger.warn("Target id=%s (type %s) no forwarding found",
                            t, tt)
                continue
        else:
            # We don't want to log errors for distributiong groups.
            # This is really a bad hack. This LDIF generator should
            # be re-written in a way that lets us define desired functionality
            # in a non-hackis-way.
            try:
                if tt == co.email_target_dl_group:
                    continue
            except AttributeError:
                pass
            # The target-type isn't known to this script.
            logger.error("Wrong target-type in target id=%s: %s", t, tt)
            continue

        f.write("dn: cn=d%s,%s\n" % (t, mail_dn))
        f.write("objectClass: mailAddr\n")
        f.write("cn: d%s\n" % t)
        f.write(dict_to_ldif_string(ldap.get_target_info(row)))
        if uid:
            f.write("uid: %s\n" % uid)
        if rest:
            f.write(rest)

        # Find primary mail-address:
        primary_address = None
        if t in ldap.targ2prim:
            if ldap.targ2prim[t] in ldap.aid2addr:
                primary_address = ldap.aid2addr[ldap.targ2prim[t]]
                f.write("defaultMailAddress: %s\n" % primary_address)
            else:
                logger.warning(
                    "Strange: target id=%d, targ2prim[t]: %d, but no aid2addr",
                    t, ldap.targ2prim[t])

        # Find addresses for target:
        for a in sorted(ldap.targ2addr[t]):
            f.write("mail: %s\n" % a)

        # Find forward-settings:
        if t in ldap.targ2forward:
            if tt == co.email_target_account and t in ldap.targ2localdelivery:
                if primary_address:
                    f.write("forwardDestination: %s\n" % primary_address)
                else:
                    logger.warning(
                        "Missing primary address when setting local delivery "
                        "for account_id:%s target_id:%s",
                        ldap.targ2prim.get(t), t)
            for addr in ldap.targ2forward[t]:
                # Skip local forward addresses when the account is deleted,
                # else they will create an unnecessary bounce message.
                if tt == co.email_target_deleted and addr in ldap.targ2addr[t]:
                    continue
                f.write("forwardDestination: %s\n" % addr)

        # Find spam-settings:
        if t in ldap.targ2spam:
            level, action = ldap.targ2spam[t]
            f.write("spamLevel: %s\n" % level)
            f.write("spamAction: %s\n" % action)
        else:
            # Set default-settings.
            f.write("spamLevel: %s\n" % default_spam_level)
            f.write("spamAction: %s\n" % default_spam_action)

        # Filters
        for a in ldap.targ2filter[t]:
            f.write("mailFilter: %s\n" % a)

        # Populate auth-data:
        if auth and tt == co.email_target_account:
            if ei in ldap.e_id2passwd:
                passwd = ldap.e_id2passwd[ei]
                if not passwd:
                    passwd = "*invalid"
                f.write("userPassword: {crypt}%s\n" % passwd)
            else:
                logger.error("No auth-data for user: %s\n" % (target or ei))

        misc = ldap.get_misc(row)
        if misc:
            f.write("%s\n" % misc)
        f.write("\n")


def get_data(spread):
    if verbose:
        logger.debug("Starting read_prim()...")
        curr = now()
    ldap.read_prim()
    if verbose:
        logger.debug("  done in %d sec." % (now() - curr))
        logger.debug("Starting read_spam()...")
        curr = now()
    ldap.read_spam()
    if verbose:
        logger.debug("  done in %d sec." % (now() - curr))
        logger.debug("Starting read_target_filter()...")
        curr = now()
    ldap.read_target_filter()
    if verbose:
        logger.debug("  done in %d sec." % (now() - curr))
        logger.debug("Starting read_quota()...")
        curr = now()
    ldap.read_quota()
    if verbose:
        logger.debug("  done in %d sec." % (now() - curr))
        logger.debug("Starting read_addr()...")
        curr = now()
    ldap.read_addr()
    if verbose:
        logger.debug("  done in %d sec." % (now() - curr))
        logger.debug("Starting read_server()...")
        curr = now()
    ldap.read_server(spread)
    if verbose:
        logger.debug("  done in %d sec." % (now() - curr))
        logger.debug("Starting read_vacation()...")
        curr = now()
    ldap.read_vacation()
    if verbose:
        logger.debug("  done in %d sec." % (now() - curr))
        logger.debug("Starting read_forward()...")
        curr = now()
    ldap.read_forward()
    if verbose:
        logger.debug("  done in %d sec." % (now() - curr))
        logger.debug("Starting read_local_delivery()...")
        curr = now()
    ldap.read_local_delivery()
    if verbose:
        logger.debug("  done in %d sec." % (now() - curr))
        logger.debug("Starting read_accounts()...")
        curr = now()
    # exchange-relatert-jazz
    # this wil, at UiO work fine as long as all Exchange-accounts
    # have NIS_user@uio as well. if UiO should decide to
    # allow pure AD-accounts/Exchange mailboxes they will not
    # be exported to LDAP. A solution could be to allow spread
    # to be None and export all accounts regardless of (Jazz, 2013-12)
    ldap.read_accounts(spread)
    if verbose:
        logger.debug("  done in %d sec." % (now() - curr))
    if auth:
        if verbose:
            logger.debug("Starting read_target_auth_data()...")
            curr = now()
        ldap.read_target_auth_data()
        if verbose:
            logger.debug("  done in %d sec." % (now() - curr))
    if verbose:
        logger.debug("Starting read_multi_data()...")
        curr = now()
    ldap.read_multi_data(ignore_missing=True)
    if verbose:
        logger.debug("  done in %d sec." % (now() - curr))
        logger.debug("Starting read_misc_target()...")
        curr = now()
    # ldap.read_misc_target() is by default empty. See EmailLDAP for details.
    ldap.read_misc_target()
    if verbose:
        logger.debug("  done in %d sec." % (now() - curr))
        logger.debug("Starting write_ldif()...")
        curr = now()
    write_ldif()
    if verbose:
        logger.debug("  done in %d sec." % (now() - curr))
        logger.debug("Total time: %d" % (now() - start))


def main():
    global verbose, f, db, co, ldap, auth, start

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-v', "--verbose",
                        action="count",
                        default=0,
                        help='Show some statistics while running. '
                             'Repeat the option for more verbosity.')
    parser.add_argument('-m', "--mail-file",
                        help='Specify file to write to.')
    parser.add_argument('-s', "--spread",
                        default=ldapconf('MAIL', 'spread', None),
                        help='Targets printed found in spread.')
    parser.add_argument('-i', "--ignore-size",
                        dest="max_change",
                        action="store_const",
                        const=100,
                        help='Use file class instead of SimilarSizeWriter.')
    parser.add_argument('-a', "--no-auth-data",
                        dest="auth",
                        action="store_false",
                        default=True,
                        help="Don't populate userPassword.")
    args = parser.parse_args()

    verbose = args.verbose
    auth = args.auth

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    start = now()
    curr = now()

    if verbose:
        logger.debug("Loading the EmailLDAP module...")
    ldap = Factory.get('EmailLDAP')(db)
    if verbose:
        logger.debug("  done in %d sec." % (now() - curr))

    spread = args.spread
    if spread is not None:
        spread = map_spreads(spread, int)

    f = ldif_outfile('MAIL', args.mail_file, max_change=args.max_change)
    get_data(spread)
    end_ldif_outfile('MAIL', f)

if __name__ == '__main__':
    main()
