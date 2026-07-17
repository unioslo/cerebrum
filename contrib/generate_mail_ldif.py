#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2025 University of Oslo, Norway
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
Write an email address ldif for email routing.

This script writes the mail-db.ldif file used for routing emails at the mail
exchange.

Configuration
-------------
This export is affected by the following settings in cereconf:

cereconf.LDAP_MAIL
    dn
        Distingushed name of the tree where objects are placed

    dump_dir
        Default location for LDAP-related export files.

    file
        Default filename to write export to. If filename is relative, it will
        be relative to dump_dir.

    spread
        Default value of spreads to include.
"""

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import contextlib
import logging
import six
from time import time as now

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.export.auth import AuthExporter
from Cerebrum.modules import Email
from Cerebrum.modules import LDIFutils
from Cerebrum.utils import date as date_utils

logger = logging.getLogger(__name__)
debug_log = logger.getChild("debug")
debug_log.propagate = 0

default_spam_level = 9999
default_spam_action = 0


# Why are we writing the ldif line-by-line, rather than using
# `LDIFutils.entry_string`?  This script should probably be re-implemented and
# use LDIFutils for building the LDAP object.


def dict_to_ldif_string(d):
    r"""
    Stringify a dict LDIF-style.

    Convert a dict with LDIF-attributes to a string that can be written
    directly to an LDIF file.

    :type d: dict[str, str|list]
    :param d:
        Attributes and values to stringify.

    :returns str:
        An ldap/ldif data 'chunk' (\n-separated bunch of lines) that can be
        written to an LDIF file directly. The resulting string is
        '\n'-terminated.
    """
    line_format = "%s: %s\n"
    result = []
    for key, value in sorted(six.iteritems(d)):
        if isinstance(value, (list, tuple, set)):
            result.extend(line_format % (key, tmp) for tmp in sorted(value))
        else:
            result.append(line_format % (key, value))
    return "".join(result)


@contextlib.contextmanager
def log_time(action, level=logging.DEBUG):
    logger.log(level, "start %s ...", action)
    start = date_utils.now()
    try:
        yield
    except Exception:
        raise
    else:
        time_used = date_utils.now() - start
        logger.log(level, "done %s in %ds", action, time_used.total_seconds())


def get_mail_targets(db):
    """ Get a list of candidate mail targets. """
    mail_targ = Email.EmailTarget(db)
    with log_time("get_mail_targets"):
        targets = sorted(
            (dict(row) for row in mail_targ.list_email_targets_ext()),
            key=lambda r: r['target_id'],
        )
    return targets


def write_ldif(db, ldap, auth, f, mail_dn):
    """
    Write matching mail-targets as LDAP objects to the given file.

    :type db: Cerebrum.database.Database
    :type ldap: Cerebrum.modules.EmailLDAP.EmailLDAP
    :type auth: Cerebrum.export.auth.AuthCache
    :param f: A file-like object to write objects to
    :param mail_dn: A DN string for this ldap tree
    """
    co = Factory.get('Constants')(db)
    counter = 0
    curr = now()
    ldap.read_pending_moves()

    f.write(LDIFutils.container_entry_string('MAIL'))

    for row in get_mail_targets(db):
        t = int(row['target_id'])
        debug_log.debug("Processing target id=%d", t)
        if t not in ldap.targ2addr:
            # There are no addresses for this target; hence, no mail
            # can reach it.  Move on.
            debug_log.debug("No addresses for target id=%s. Moving on.", t)
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
        if (counter % 5000) == 0:
            debug_log.debug("done %d list_email_targets(): %d sec.",
                            counter, now() - curr)

        target = ""
        uid = ""
        rest = ""

        # The structure is decided by what target-type the
        # target is (class EmailConstants in Email.py):
        tt = co.EmailTarget(int(tt))
        debug_log.debug("Target id=%s is of type %s", t, tt)

        # All of this would probably be cleaner if we move most of the
        # following code to a "create ldap entry" function, and use
        # entry_string to create the ldif text blob...

        if tt == co.email_target_account:
            # Target is the local delivery defined for the Account whose
            # account_id == email_target.target_entity_id.
            target = ""
            if et == co.entity_account:
                if ei in ldap.acc2name:
                    target = ldap.acc2name[ei]
                else:
                    logger.warning(
                        "Target id=%s (type %s): no user id=%s found",
                        t, tt, ei,
                    )
                    continue
            else:
                logger.warning(
                    "Target id=%s (type %s): wrong entity type: %s "
                    "(entity_id=%s)", t, tt, et, ei,
                )
                continue

            # Find quota-settings:
            if t in ldap.targ2quota:
                soft, hard = ldap.targ2quota[t]
                rest += "softQuota: %s\n" % soft
                rest += "hardQuota: %s\n" % hard

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
                logger.warning("Target id=%s (type %s) needs an alias_value",
                               t, tt)
                continue

            if run_as_id is not None:
                if run_as_id in ldap.acc2name:
                    uid = ldap.acc2name[run_as_id]
                else:
                    logger.warning(
                        "Target id=%s (type %s) no user id=%s found",
                        t, tt, ei,
                    )
                    continue

        elif tt == co.email_target_multi:
            # Target is the set of `account`-type targets corresponding to
            # the Accounts that are first-level members of the Group that
            # has group_id == email_target.target_entity_id.

            if et == co.entity_group:
                try:
                    addrs, missing = ldap.get_multi_target(
                        ei, ignore_missing=True)
                except ValueError as e:
                    logger.warning("Target id=%s (type %s): %s", t, tt, e)
                    continue
                for addr in sorted(addrs):
                    rest += "forwardDestination: %s\n" % addr
                for addr in missing:
                    logger.warning(
                        "Target id=%s (type %s): Multitarget group id %s: "
                        "account %s has no primary address",
                        t, tt, ei, addr,
                    )
            else:
                # A 'multi' target with no forwarding; seems odd.
                logger.warning("Target id=%s (type %s) no forwarding found",
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
            for addr in sorted(ldap.targ2forward[t]):
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
        for a in sorted(ldap.targ2filter[t]):
            f.write("mailFilter: %s\n" % a)

        # Populate auth-data:
        if auth is not None and tt == co.email_target_account:
            if ei in ldap.quarantined:
                passwd = '{crypt}*locked',
            else:
                try:
                    passwd = auth.get(ei)
                except LookupError:
                    logger.debug('No auth-data for account_id=%s, target=%s',
                                 repr(ei), repr(target))
                    passwd = '{crypt}*invalid',
            f.write("userPassword: %s\n" % passwd)

        f.write("\n")


def get_data(db, auth_cache, spread):
    """ Load the EmailLDAP module and cache all relevant data.  """

    with log_time('loading the EmailLDAP module'):
        ldap = Factory.get('EmailLDAP')(db)

    with log_time('read_prim()'):
        ldap.read_prim()

    with log_time('read_spam()'):
        ldap.read_spam()

    with log_time('read_target_filter()'):
        ldap.read_target_filter()

    with log_time('read_quota()'):
        ldap.read_quota()

    with log_time('read_addr()'):
        ldap.read_addr()

    with log_time('read_server()'):
        ldap.read_server(spread)

    with log_time('read_forward()'):
        ldap.read_forward()

    with log_time('read_local_delivery()'):
        ldap.read_local_delivery()

    # exchange-relatert-jazz
    # this wil, at UiO work fine as long as all Exchange-accounts
    # have NIS_user@uio as well. if UiO should decide to
    # allow pure AD-accounts/Exchange mailboxes they will not
    # be exported to LDAP. A solution could be to allow spread
    # to be None and export all accounts regardless of (Jazz, 2013-12)
    with log_time('read_accounts()'):
        ldap.read_accounts(spread)

    if auth_cache is not None:
        with log_time('read_quarantines()'):
            ldap.read_quarantines()

        # Maybe move the auth_data logic into the EmailLDAP module?
        with log_time('auth_cache.update_all()'):
            auth_cache.update_all()

    with log_time('read_multi_data()'):
        ldap.read_multi_data(ignore_missing=True)

    # ldap.read_misc_target() is by default empty. See EmailLDAP for details.
    with log_time('read_misc_target()'):
        ldap.read_misc_target()

    return ldap


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Generate a mail-db.ldif',
    )
    parser.add_argument(
        '-v', "--verbose",
        action="count",
        default=0,
        help='Show some statistics while running. ',
    )
    parser.add_argument(
        '-m', "--mail-file",
        help='Specify file to write to.',
    )
    parser.add_argument(
        '-s', "--spread",
        default=None,
        help='Targets printed found in spread.',
    )
    parser.add_argument(
        '-i', "--ignore-size",
        dest="max_change",
        action="store_const",
        const=100,
        help='Use file class instead of SimilarSizeWriter.',
    )
    parser.add_argument(
        '-a', "--no-auth-data",
        dest="auth",
        action="store_false",
        default=True,
        help="Don't populate userPassword.",
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf("cronjob", args)

    if args.verbose:
        debug_log.propagate = 1

    start = now()
    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))
    db = Factory.get("Database")()
    const = Factory.get("Constants")()

    # Build LdapConfig and check dn
    config = LDIFutils.get_ldap_config(["LDAP", "LDAP_MAIL"])
    dn = config.get_dn()

    spread = args.spread or config.get("spread", None)
    if spread is not None:
        spread = const.get_constant(const.Spread, spread)

    # Configure auth
    if args.auth:
        auth_attrs = config.get("auth_attr", {})
        user_password = AuthExporter.make_exporter(
            db, auth_attrs['userPassword'])
    else:
        user_password = None

    outfile = LDIFutils.ldif_outfile('MAIL', args.mail_file,
                                     max_change=args.max_change)
    logger.debug('writing data to %s', repr(outfile))

    with log_time('fetching data', level=logging.INFO):
        ldap = get_data(
            db,
            getattr(user_password, 'cache', None),
            spread)

    with log_time('generating ldif', level=logging.INFO):
        write_ldif(
            db,
            ldap,
            user_password,
            outfile,
            dn)

    LDIFutils.end_ldif_outfile('MAIL', outfile)

    logger.info("Wrote mail-db to %s", repr(outfile))
    logger.info("Total time: %ds" % (now() - start))
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
