#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003-2009 University of Oslo, Norway
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

"""Usage: generate_mail_ldif.py [options]

Write e-mail information for use by the mail system to an LDIF file,
which can then be loaded into LDAP.

Options:
  -s | --spread <spread>:  Targets printed found in spread.
  -v | --verbose:          Show some statistics while running.
                           Repeat the option for more verbosity.
  -m | --mail-file <file>: Specify file to write to.
  -i | --ignore-size:      Use file class instead of SimilarSizeWriter.
  -a | --no-auth-data:     Don't populate userPassword.
  -h | --help:             This message."""

import sys
import base64
import getopt
from time import time as now

import cereconf
import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.LDIFutils import \
     ldapconf,map_spreads,ldif_outfile,end_ldif_outfile,container_entry_string
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
# end dict_to_ldif_string
    


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
        if not ldap.targ2addr.has_key(t):
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
            home = ""
            if et == co.entity_account:
                if ldap.acc2name.has_key(ei):
                    target, home = ldap.acc2name[ei]
                else:
                    logger.warn("Target id=%s (type %s): no user id=%s found",
                                t, tt, ei)
                    continue
            else:
                logger.warn("Target id=%s (type %s): wrong entity type: %s "
                            "(entity_id=%s)", t, tt, et, ei)
                continue
            
            # Find quota-settings:
            if ldap.targ2quota.has_key(t):
                soft, hard = ldap.targ2quota[t]
                rest += "softQuota: %s\n" % soft
                rest += "hardQuota: %s\n" % hard

            # Find vacations-settings:
            if ldap.targ2vacation.has_key(t):
                txt, start, end, enable = ldap.targ2vacation[t]
                rest += "tripnote:: %s\n" % \
                        base64.encodestring(txt or "<No message>\n"
                                            ).replace("\n", "")
                if enable:
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

            # Does the event log have an unprocessed primary email change for this email target?
            # pending_primary_email is populated by EmailLDAPUiOMixin
            if hasattr(ldap, 'pending_primary_email') and t in ldap.pending_primary_email:
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
                if ldap.acc2name.has_key(ei):
                    target = ldap.acc2name[ei][0]
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
                    co.email_target_file, co.email_target_Mailman,
                    co.email_target_Sympa):

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
            # Target is a Mailman or Sympa mailing list. The command (and args)
            # to pipe mail into is gathered from email_target.alias_value.
            # Iff email_target.target_entity_id is set and belongs to an
            # Account, deliveries to this target will be run as that
            # account.
            if alias == None:
                logger.warn("Target id=%s (type %s) needs an alias_value",
                            t, tt)
                continue

            if run_as_id is not None:
                if ldap.acc2name.has_key(run_as_id):
                    uid = ldap.acc2name[run_as_id][0]
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
                    addrs = ldap.read_multi_target(ei)
                except ValueError:
                    logger.warn("Target id=%s (type %s)", t, tt)
                    continue
                for addr in addrs:
                    rest += "forwardDestination: %s\n" % addr
            else:
                # A 'multi' target with no forwarding; seems odd.
                logger.warn("Target id=%s (type %s) no forwarding found", t, tt)
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
        if ldap.targ2prim.has_key(t):
            if ldap.aid2addr.has_key(ldap.targ2prim[t]):
                f.write("defaultMailAddress: %s\n" % ldap.aid2addr[ldap.targ2prim[t]])
            else:
                logger.debug("Strange: target id=%d, targ2prim[t]: %d, but no aid2addr",
                             t, ldap.targ2prim[t])
            
        # Find addresses for target:
        for a in ldap.targ2addr[t]:
            f.write("mail: %s\n" % a)

        # Find forward-settings:
        if ldap.targ2forward.has_key(t):
            for addr,enable in ldap.targ2forward[t]:
                # Skip local forward addresses when the account is deleted, else
                # they will create an unnecessary bounce message.
                if tt == co.email_target_deleted and addr in ldap.targ2addr[t]:
                    continue
                if enable == 'T':
                    f.write("forwardDestination: %s\n" % addr)

        # Find spam-settings:
        if ldap.targ2spam.has_key(t):
            level, action = ldap.targ2spam[t]
            f.write("spamLevel: %s\n" % level)
            f.write("spamAction: %s\n" % action)
        else:
            # Set default-settings.
            f.write("spamLevel: %s\n" % default_spam_level)
            f.write("spamAction: %s\n" % default_spam_action)

        # Filters
        if ldap.targ2filter.has_key(t):
            for a in ldap.targ2filter[t]:
                f.write("mailFilter: %s\n" % a)
            
        # Find virus-setting:
        if ldap.targ2virus.has_key(t):
            found, rem, enable = ldap.targ2virus[t]
            f.write("virusFound: %s\n" % found)
            f.write("virusRemoved: %s\n" % rem)
            if enable == 'T':
                f.write("virusScanning: TRUE\n")
            else:
                f.write("virusScanning: FALSE\n")
        else:
            # Set default-settings.
            f.write("virusScanning: TRUE\n")
            f.write("virusFound: 1\n")
            f.write("virusRemoved: 1\n")

        # Populate auth-data:
        if auth and tt == co.email_target_account:
            if ldap.e_id2passwd.has_key(ei):
                uname, passwd = ldap.e_id2passwd[ei]
                if not passwd:
                    passwd = "*invalid"
                f.write("userPassword: {crypt}%s\n" % passwd)
            else:
                txt = "No auth-data for user: %s\n" % (target or ei)
                logger.error(txt)

        misc = ldap.get_misc(row)
        if misc:
            f.write("%s\n" % misc)
        f.write("\n")


def get_data(spread):
    start = now()

    if verbose:
        logger.debug("Starting read_prim()...")
        curr = now()
    ldap.read_prim()
    if verbose:
        logger.debug("  done in %d sec." % (now() - curr))
        logger.debug("Starting read_virus()...")
        curr = now()
    ldap.read_virus()
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
        logger.debug("Starting read_account()...")
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
        logger.debug("Starting read_misc()...")
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
    global verbose, f, db, co, ldap, auth
    try:
        opts, args = getopt.getopt(sys.argv[1:], "vm:s:iha",
                                   ("verbose", "mail-file=", "spread=",
                                    "ignore-size", "help", "no-auth-data"))
    except getopt.GetoptError, e:
        usage(str(e))
    if args:
        usage("Invalid arguments: " + " ".join(args))

    verbose = 0
    mail_file = None
    spread = ldapconf('MAIL', 'spread', None)
    max_change = None
    auth = True
    for opt, val in opts:
        if opt in ("-v", "--verbose"):
            verbose += 1
        elif opt in ("-m", "--mail-file"):
            mail_file = val
        elif opt in ("-s", "--spread"):
            spread = val
        elif opt in ("-i", "--ignore-size"):
            max_change = 100
        elif opt in ("-h", "--help"):
            usage()
        elif opt in ("-a", "--no-auth-data"):
            auth = False

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    if verbose:
        logger.debug("Loading the EmailLDAP module...")
    ldap = Factory.get('EmailLDAP')(db)

    if spread is not None:
        spread = map_spreads(spread, int)

    f = ldif_outfile('MAIL', mail_file, max_change=max_change)
    get_data(spread)
    end_ldif_outfile('MAIL', f)
# end main


def usage(err=0):
    if err:
        logger.error("%s", err)

    logger.error(__doc__)
    sys.exit(bool(err))
# end usage


if __name__ == '__main__':
    main()
