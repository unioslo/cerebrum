#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2013-2021 University of Oslo, Norway
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
""" Process users that are exported to or retained from LDAP.

This script can run an assortment of functions on users as they are 'created'
or 'deleted' in the associated WebID LDAP tree.  We calculate if users *should*
exist in LDAP, look up if they *actually do* exist in LDAP, and if we've
notified users about a change in this state before
(Constants.trait_user_notified).

If this state changes for the first time, we run a series of callbacks for that
user account.  Currently, only one type of callback is implemented;  We notify
users if they are member of a group with a Constants.trait_group_forward trait,
with an email that explains that their account is now active, and ready to be
used with the associated webapp.

NOTE: This script requires special commit handling! The notifier will commit
changes to the retained-trait after running `update_retained_trait()'.

When running `run_callbacks()', we pass Account-objects to the callback
functions, re-using a single Database-transaction. The callback function must
commit/rollback any changes according to the `dryrun` flag.

cereconf
--------
``LDAP_URL``
    The LDAP user lookup connects to the ldap server given in ``LDAP_URL``.

``LDAP_USER``
    The LDAP user lookup does a subtree search in the base-dn given by
    ``LDAP_USER['dn']``.

``USER_NOTIFIED_LIMIT``
    Notification limits for this script - a dict with two values, *num* and
    *days*.  A given user account can only be notified up to *num* times in
    *days* days.

``EXPORT_MESSAGE``
    Message template for notifications - a dict with values *sender*,
    *subject*, *body*, and *item_fmt*.

    *sender* and *subject* are the *From* and *Subject* fields of a
    notification email.

    *body* is a template which gets rendered with old-style string formatting,
    while *item_tpl* is a template for individual group memberships/webapps to
    notify the user about:

    ::

        EXPORT_MESSAGE['body'] % {
            'account_name': 'example@realm',
            'items': "\n".join(
                EXPORT_MESSAGE['item_fmt'] % {'name': name, 'url': url}
                for name, url in ...
            ),
        }
"""
import argparse
import datetime
import ldap
import logging
import smtplib
import textwrap
from time import time

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils import date_compat
from Cerebrum.utils.email import sendmail
from Cerebrum.modules.virthome.LDIFHelper import LDIFHelper

# Some defaults
DEFAULT_LOGGER = 'cronjob'
CHANGELOG_PROGRAM = 'ldap_notifier'

logger = logging.getLogger(__name__)


def get_config(name):
    """ Fetch a constant from cereconf. """
    if not hasattr(cereconf, name):
        raise RuntimeError("Variable '%s' is not defined in cereconf" %
                           str(name))
    return getattr(cereconf, name)


def get_trait(entity, trait_const, val=None):
    """ Get trait or a given trait attribute

    :type entity: Cerebrum.Entity
    :param entity: The entity we're looking up trait for

    :type trait_const: EntityTraitCode
    :param trait_const: The type of trait

    :type val: str, NoneType
    :param val: The trait attribute to get, or None to get the trait dict

    :rtype: mixed
    :return:
        The trait or given trait value L{val}, if it exists. Otherwise None
    """
    assert hasattr(entity, 'entity_id') and hasattr(entity, 'get_trait')
    try:
        trait = entity.get_trait(trait_const)
        if not val:
            return trait
        return trait.get(val, None)
    except AttributeError:
        pass
    return None


class Notifier(object):
    """ Notifier, runs a dummy LDAP export to see which users are eligible for
    export to LDAP. We compare this set with all users in the database, and all
    users previously marked as retained/'not exported'.

    We can then register callbacks that should be called for different groups
    of users (exported, not exported)
    """

    def __init__(self, logger, dryrun=True):
        """ Initialize the notifier with a db connection, logger and dryrun
        option

        :type db: Cerebrum.database.Database
        :type logger: logging.Logger
        :param bool dryrun: If we should revert any changes to the database
        """
        self.db = Factory.get('Database')()
        self.db.cl_init(change_program=CHANGELOG_PROGRAM)
        self.logger = logger
        self.dryrun = dryrun

        self.all_exported = set()  # All users exported to LDAP
        self.not_exported = set()  # All users NOT exported to LDAP
        self.now_exported = set()  # Users recently exported to LDAP
        self.now_retained = set()  # Users recently marked as 'retained'

        # Callback functions for the now_exported / now_retained groups
        self.exported_callbacks = []
        self.retained_callbacks = []

    def add_export_cb(self, cb):
        """ Adds a callback that will be called for every (newly) exported
        account.

        @type cb: function
        @param cb: A (static) function. The function is called with two
                   arguments: A populated Cerebrum.Account object, and dryrun
                   setting
        """
        self.exported_callbacks.append(cb)

    def add_retain_cb(self, cb):
        """ Adds a callback that will be called for every (newly) retained
        account.

        @type cb: function
        @param cb: A (static) function. The function is called with two
                   arguments: A populated Cerebrum.Account object, and dryrun
                   setting
        """
        self.retained_callbacks.append(cb)

    def update_retained_trait(self):
        """ Finds and returns users that have either been retained from or
        exported to LDAP since the last run.

        Uses the LDIFHelper from ldap_notifier to figure out which users
        are eligible for export, then compares this to account traits and
        actual LDAP state.

        Prepares four sets of account_ids:
            all_exported - All users eligible for LDAP export
            not_exported - All users NOT eligible for LDAP export
            now_exported - Users that
                1. are eligible for LDAP export
                2. does have trait 'retained' (NOT previously exported)
                3. currently exists in LDAP
            now_retained - Users that
                1. are NOT eligible for LDAP export
                2. does NOT have trait 'retained' (previously exported)
                3. currently NOT in LDAP
        """
        co = Factory.get('Constants')(self.db)
        ac = Factory.get('Account')(self.db)

        # For DEBUG - log timing
        debug_times = [time(), ]

        def _add_debug_time(text):
            debug_times.append(time())
            if text:
                self.logger.debug("Time (%0.2f s) %s",
                                  debug_times[-1] - debug_times[-2], text)

        # First we need to find all the changes
        helper = LDIFHelper(self.logger)
        exported_names = set([user['uid'][0] for user in helper.yield_users()])
        _add_debug_time('Dummy LDAP export')

        all_accounts = ac.list_names(co.account_namespace)
        _add_debug_time("Fetched all accounts")

        has_trait = set(t['entity_id'] for t in
                        ac.list_traits(code=co.trait_user_retained,
                                       fetchall=True))

        # New exports: Was exported, and has 'retained' trait
        self.all_exported = set(a['entity_id']
                                for a in all_accounts
                                if a['entity_name'] in exported_names)
        new_exports = self.all_exported.intersection(has_trait)
        self.now_exported = set()

        # New retainees, wasn't exported, and doesn't have trait
        self.not_exported = set(
            a['entity_id']
            for a in all_accounts).difference(self.all_exported)
        new_retainees = self.not_exported.difference(has_trait)
        self.now_retained = set()

        _add_debug_time('Prepared sets')

        # THEN we need to verify their state against LDAP, and mirror that
        # state in Cerebrum
        for account_id in new_exports:
            ac.clear()
            ac.find(account_id)
            if self.verify_ldap(ac.account_name):
                ac.delete_trait(co.trait_user_retained)
                self.now_exported.add(account_id)
            # Else, user won't be in (verified) new export set, will retry next
            # time the script runs
        _add_debug_time("Verified new exports with LDAP")
        self.logger.debug("%d of the %d exported users were"
                          " previously retained",
                          len(self.now_exported),
                          len(self.all_exported))

        for account_id in new_retainees:
            ac.clear()
            ac.find(account_id)
            verify = self.verify_ldap(ac.account_name)
            if verify is False:
                ac.populate_trait(co.trait_user_retained, numval=0)
                ac.write_db()
                self.now_retained.add(account_id)
            # Else, user won't be in (verified) new retainee set, will retry
            # next time the script runs
        _add_debug_time("Verified new retainees with LDAP")
        self.logger.debug("%d of the %d retained users were"
                          " previously exported",
                          len(self.now_retained), len(self.not_exported))

        if self.dryrun:
            self.db.rollback()
        else:
            self.db.commit()

    def verify_ldap(self, uid):
        """ Verify that a username, L{uid} exists in the virthome LDAP tree

        @type uid: basestring
        @param uid: The UID/username to look for

        @rtype: bool or None
        @return: True if the user is found in the LDAP tree, False if not. None
                 on errors
        """
        filter = "uid=%s" % uid
        user_dn = get_config('LDAP_USER')['dn']
        webid = ldap.initialize(get_config('LDAP_URL'))

        try:
            result = webid.search_s(user_dn, ldap.SCOPE_SUBTREE,
                                    filterstr=filter)
        except ldap.LDAPError as e:
            self.logger.info("Could not check if %r in ldap: %s", uid, str(e))
            return None

        if not isinstance(result, list):
            return None

        return len(result) == 1

    def run_callbacks(self, dryrun=True):
        """ Run all registered callbacks for newly exported accounts and newly
        retained accounts.
        """
        ac = Factory.get('Account')(self.db)

        for account_id in self.now_exported:
            ac.clear()
            ac.find(account_id)
            for callback in self.exported_callbacks:
                callback(ac, dryrun)

        for account_id in self.now_retained:
            ac.clear()
            ac.find(account_id)
            for callback in self.retained_callbacks:
                callback(ac, dryrun)


class AccountEmailer(object):
    """ A simple emailer that can send emails to an address associated with an
    account, and prevent spamming if anything should fail.

    NOTE: No other database-operations should happen in the lifetime of this
    object, as is calles commit/rollback after each email sent!
    """
    # TODO: Build in spam prevention

    def __init__(self, ac, logger, sender, dryrun=True, today=None):
        """ If account L{ac} is a member of at least one group with trait
        'forward_url', send an email notification to the email address
        associated with the account.
        """
        assert hasattr(ac, 'entity_id')
        self.dryrun = dryrun
        self.logger = logger
        self.ac = ac
        self.co = Factory.get('Constants')(ac._db)
        self.sender = sender
        self.address = None
        self.max_num = int(get_config('USER_NOTIFIED_LIMIT')['num'])
        self.days_reset = datetime.timedelta(
            days=int(get_config('USER_NOTIFIED_LIMIT')['days']),
        )
        self.today = today or datetime.date.today()

    def _needs_reset(self, last_reset):
        """Check if a trait needs to be reset, according to its date value."""
        # Note: traits contains TIMESTAMP values, but we really only care about
        # the date component
        last_reset = date_compat.get_date(last_reset)
        if not last_reset:
            return True
        return self.today - last_reset > self.days_reset

    def get_address(self):
        """ Lazy fetching of account email address """
        if not self.address:
            self.address = self.ac.get_email_address()
        return self.address

    def trait_allows(self):
        """ Check if the trait 'trait_user_notified' will allow us to send
        email. We can send if any of the following is true:
          - The trait date attribute is older than max_num
          - The trait numval attribute is less than max_num
        """
        trait = self.ac.get_trait(self.co.trait_user_notified)
        if not trait:
            logger.debug("No trait '%s' for '%s'",
                         self.co.trait_user_notified, self.ac.account_name)
            return True

        logger.debug("Trait '%s' for '%s': numval=%r, date=%r",
                     self.co.trait_user_notified, self.ac.account_name,
                     trait['numval'], trait['date'])
        if self._needs_reset(trait['date']):
            return True
        if self.max_num >= (trait['numval'] or 0):
            return True
        return False

    def update_trait(self):
        """ Update the 'trait_user_notified' trait by:
          1. Creating it, if it doesn't exist
          2. Resetting it if the date attribute is more than
             days_reset days old.
          3. Incrementing the numval attribute.
        """
        # Initial values for new trait
        trait = self.ac.get_trait(self.co.trait_user_notified)

        if (trait and not self._needs_reset(trait['date'])):
            # Trait date exists, and is not older than days_reset old
            last_reset = date_compat.get_date(trait['date'])
            num_sent = trait['numval'] or 0
        else:
            last_reset = self.today
            num_sent = 0

        # Increment and write the updated trait values
        num_sent += 1

        self.ac.populate_trait(self.co.trait_user_notified,
                               numval=num_sent,
                               date=last_reset)
        self.ac.write_db()

        if self.dryrun:
            self.logger.warn("Dryrun, not writing trait '%s' for user '%s",
                             str(self.co.trait_user_notified),
                             self.ac.account_name)
            self.ac._db.rollback()
        else:
            self.ac._db.commit()

    def send_email(self, subject, message):
        """ Send an email to the email address associated with the account

        """
        to_addr = self.get_address()
        if not self.trait_allows():
            self.logger.warn("Account flooded, will not mail %r", to_addr)
        elif not self.dryrun:
            try:
                sendmail(to_addr, self.sender, subject, message)
                self.logger.debug("Sent message to %r", to_addr)
            except smtplib.SMTPRecipientsRefused as e:
                error = e.recipients.get(to_addr)
                self.logger.warn("Failed to send message to %s (SMTP %d: %s)",
                                 to_addr, error[0], error[1])
            except smtplib.SMTPException:
                self.logger.exception("Failed to send message to %s", to_addr)
        else:
            self.logger.debug("Dryrun - Would send message for %s", to_addr)
        # Update attempt count
        self.update_trait()


def callback_test(ac, dryrun=False):
    logger.debug("Callback for account '%s'", ac.account_name)


def callback_notify_forward(ac, dryrun=False):
    """ If account L{ac} is a member of at least one group with trait
    'forward_url', send an email notification to the email address associated
    with the account.
    """
    assert hasattr(ac, 'entity_id')

    # Config
    sender = get_config('EXPORT_MESSAGE')['sender']
    subject = get_config('EXPORT_MESSAGE')['subject']
    body = get_config('EXPORT_MESSAGE')['body']
    item_fmt = get_config('EXPORT_MESSAGE')['item_fmt']

    co = Factory.get('Constants')(ac._db)
    gr = Factory.get('Group')(ac._db)

    mailer = AccountEmailer(ac, logger, sender, dryrun)
    external_apps = set()  # tuples (name/description, forward_url)

    # Look up group memberships in groups with forward trait
    for g in gr.search(member_id=ac.entity_id):
        gr.clear()
        gr.find(g['group_id'])
        forward = get_trait(gr, co.trait_group_forward, val='strval')
        if forward:
            # Only unique
            external_apps.add((g['description'] or g['name'], forward))

    # Send email if such group memberships exists.
    if len(external_apps) > 0:
        items = "\n".join([item_fmt % {'name': name, 'url': url}
                           for name, url in external_apps])
        logger.info("Will inform '%s' (%s) about access to %d external apps",
                    ac.account_name, mailer.get_address(), len(external_apps))

        message = body % {
            'account_name': ac.account_name,
            'items': items}
        mailer.send_email(subject, message)


dryrun_callback_error_msg = """
Running callbacks without commiting would cause users to be
notified multiple times about the same change.

Commiting without running callbacks would cause users NOT to get
notified about changes.

If debugging, or running first time, use -f to force this action.
""".lstrip()


def main(inargs=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """
            This script keeps track on which users are exported to LDAP and
            removed from LDAP.
            It can also run a series of operations for new users in LDAP (as
            well as users that are deleted from LDAP.

            Configured operations:
              * NEW users in LDAP, that are members of a group with
              'forward_url' trait will receive an email notification.
            """
        )
    )

    # --commit / --dryrun
    commit_mutex = parser.add_mutually_exclusive_group()
    commit_mutex.add_argument(
        '-c', '--commit',
        dest='commit',
        action='store_true',
        help='commit changes')
    commit_mutex.add_argument(
        '--dryrun',
        dest='commit',
        action='store_false',
        help='dry run (do not commit -- this is the default)')
    commit_mutex.set_defaults(commit=False)

    parser.add_argument(
        '-r', '--run_callbacks',
        action='store_true',
        default=False,
        help='Run operations that are associated with export state.'
             ' It is an error to use this option without commit!'
    )
    parser.add_argument(
        '-f', '--force',
        action='store_true',
        default=False,
        help='Force run callbacks (-r) in dryrun'
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf(DEFAULT_LOGGER, args)

    logger.info('Start %s', parser.prog)
    logger.debug("args: %r", args)

    if args.run_callbacks and not (args.commit or args.force):
        raise RuntimeError(dryrun_callback_error_msg)

    noti = Notifier(logger, dryrun=not args.commit)

    # For new exports, notify if member of group with forward_url trait
    noti.add_export_cb(callback_notify_forward)

    noti.update_retained_trait()

    if args.run_callbacks:
        noti.run_callbacks(not args.commit)

    logger.info('Done %s', parser.prog)


if __name__ == "__main__":
    main()
