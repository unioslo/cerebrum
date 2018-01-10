#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# Copyright 2013-2018 University of Oslo, Norway
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

""" This is a generic script that can operate on users that are created
(exported) or removed (retained) in LDAP exports.

NOTE: This script requires special commit handling! The notifier will commit
changes to the retained-trait after running `update_retained_trait()'.

When running `run_callbacks()', we pass Account-objects to the callback
functions, re-using the same Database-object. The callback function must take
care of and commit/rollback any changes it writes.
"""
import cerebrum_path
import cereconf

import sys
from getopt import getopt, GetoptError
import ldap
import smtplib
from time import time
from os.path import basename

from Cerebrum.Utils import Factory
from Cerebrum.Utils import sendmail
from Cerebrum.modules.virthome.LDIFHelper import LDIFHelper
from mx.DateTime import now

# Some defaults
DEFAULT_LOGGER = 'cronjob'
CHANGELOG_PROGRAM = 'ldap_notifier'

def get_config(name):
    """ Fetch a constant from cereconf. """
    if not hasattr(cereconf, name):
        raise RuntimeError("Variable '%s' is not defined in cereconf" %
                           str(name))
    return getattr(cereconf, name)


def get_trait(entity, trait_const, val=None):
    """ Get trait or a given trait attribute
    
    @type entity: Cerebrum.Entity
    @param entity: The entity we're looking up trait for

    @type trait_const: EntityTraitCode
    @param trait_const: The type of trait

    @type val: str, NoneType
    @param val: The trait attribute to get, or None to get the trait dict

    @rtype: mixed
    @return: The trait or given trait value L{val}, if it exists. Otherwise
             None
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


class Notifier:
    """ Notifier, runs a dummy LDAP export to see which users are eligible for
    export to LDAP. We compare this set with all users in the database, and all
    users previously marked as retained/'not exported'.

    We can then register callbacks that should be called for different groups of
    users (exported, not exported)
    """

    def __init__(self, logger, dryrun=True):
        """ Initialize the notifier with a db connection, logger and dryrun
        option

        @type db: Cerebrum.database.Database
        @param db: A database connection

        @type logger: Cerebrum.modules.cerelog
        @param logger: A logger

        @type dryrun: bool
        @param dryrun: If we should revert any changes to the database
        """
        self.db = Factory.get('Database')()
        self.db.cl_init(change_program=CHANGELOG_PROGRAM)
        self.logger = logger
        self.dryrun = dryrun

        self.all_exported = set() # All users exported to LDAP
        self.not_exported = set() # All users NOT exported to LDAP
        self.now_exported = set() # Users recently exported to LDAP
        self.now_retained = set() # Users recently marked as 'retained'

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
        are eligible for export, then compares this to account traits and actual
        LDAP state.

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
                self.logger.debug("Time (%0.2f s) %s" % (debug_times[-1] - debug_times[-2], text))

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
        self.all_exported = set(a['entity_id'] for a in all_accounts if a['entity_name'] in
                       exported_names)
        new_exports = self.all_exported.intersection(has_trait)
        self.now_exported = set()

        # New retainees, wasn't exported, and doesn't have trait
        self.not_exported = set(a['entity_id'] for a in
                all_accounts).difference(self.all_exported)
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
        self.logger.debug("%d of the %d exported users were previously retained" %
                     (len(self.now_exported), len(self.all_exported)))

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
        self.logger.debug("%d of the %d retained users were previously exported" %
                     (len(self.now_retained), len(self.not_exported)))

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
            result = webid.search_s(user_dn, ldap.SCOPE_SUBTREE, filterstr=filter)
        except ldap.LDAPError, e:
            self.logger.info("Could not check if '%s' in ldap: %s" % (uid, str(e)))
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

class AccountEmailer:
    """ A simple emailer that can send emails to an address associated with an
    account, and prevent spamming if anything should fail.

    NOTE: No other database-operations should happen in the lifetime of this
    object, as is calles commit/rollback after each email sent!
    """
    # TODO: Build in spam prevention

    def __init__(self, ac, logger, sender, dryrun=True):
        """ If account L{ac} is a member of at least one group with trait
        'forward_url', send an email notification to the email address associated
        with the account.
        """
        assert hasattr(ac, 'entity_id')
        self.dryrun = dryrun
        self.logger = logger
        self.ac = ac
        self.co = Factory.get('Constants')(ac._db)
        self.sender = sender
        self.address = None
        self.max_num = get_config('USER_NOTIFIED_LIMIT')['num']
        self.days_reset = get_config('USER_NOTIFIED_LIMIT')['days']

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
            logger.debug("No trait '%s' for '%s'" %
                    (self.co.trait_user_notified, self.ac.account_name))
            return True
        else:
            logger.debug("Trait '%s' for '%s': numval(%d) date(%s)" %
                    (self.co.trait_user_notified, self.ac.account_name,
                     trait.get('numval', 0), trait.get('date')))
        if (now() - self.days_reset) > trait.get('date'):
            return True
        if self.max_num >= trait.get('numval'):
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
        last_reset = now()
        num_sent = 0
        trait = self.ac.get_trait(self.co.trait_user_notified)

        # Trait date exists, and is not older than days_reset old.
        if trait and (last_reset - self.days_reset) < trait.get('date'):
            last_reset = trait.get('date')
            num_sent = trait.get('numval') or 0
        # Else, reset trait
        
        # Increment and write the updated trait values
        num_sent += 1

        self.ac.populate_trait(self.co.trait_user_notified, numval=num_sent,
                date=last_reset)
        self.ac.write_db()

        if self.dryrun:
            self.logger.warn("Dryrun, not writing trait '%s' for user '%s" %
                    (str(self.co.trait_user_notified), self.ac.account_name))
            self.ac._db.rollback()
        else:
            self.ac._db.commit()


    def send_email(self, subject, message):
        """ Send an email to the email address associated with the account

        """
        to_addr = self.get_address()
        if not self.trait_allows():
            self.logger.warn("Account flooded, will not mail %s" % to_addr)
        elif not self.dryrun:
            try:
                sendmail(to_addr, self.sender, subject, message)
                self.logger.debug("Sent message to %s" % to_addr)
            except smtplib.SMTPRecipientsRefused, e:
                error = e.recipients.get(to_addr)
                self.logger.warn("Failed to send message to %s (SMTP %d: %s)",
                            to_addr, error[0], error[1])
            except smtplib.SMTPException:
                self.logger.exception("Failed to send message to %s", to_addr)
        else:
            self.logger.debug("Dryrun - Would send message for %s" % to_addr)
        
        # Update attempt count
        self.update_trait()


def callback_test(ac, dryrun=False):
    logger.debug("Callback for acocunt '%s'" % ac.account_name)


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
    external_apps = set() # tuples (name/description, forward_url)

    # Look up group memberships in groups with forward trait
    for g in gr.search(member_id=ac.entity_id):
        gr.clear()
        gr.find(g['group_id'])
        forward = get_trait(gr, co.trait_group_forward, val='strval')
        if forward:
            external_apps.add((g['description'] or g['name'], forward)) # Only unique

    # Send email if such group memberships exists.
    if len(external_apps) > 0:
        items = "\n".join([item_fmt % {'name': name, 'url': url} for name, url
            in external_apps])
        logger.info("Will inform '%s' (%s) about access to %d external apps" %
                (ac.account_name, mailer.get_address(), len(external_apps)))

        message = body % {
            'account_name': ac.account_name,
            'items': items}
        mailer.send_email(subject, message)


def usage(exitcode=0):
    """ Prints script usage, and exits with C{exitcode}.
    """
    print """ Usage: %(name)s [options]

    This script keeps track on which users are exported to LDAP and removed from
    LDAP. 
    It can also run a series of operations for new users in LDAP (as well as
    users that are deleted from LDAP.

    Configured operations:
      * NEW users in LDAP, that are members of a group with 'forward_url' trait
        will receive an email notification.

    Options:
      -c, --commit               Commit changes to cerebrum -- this causes the
                                 script to update the state of users exported to
                                 LDAP.
      -r, --run_callbacks        Run operations that are associated with export
                                 state. It is an error to use this option
                                 without commit!
      -f. --force                Cannot normally run callbacks (-r) without
                                 commiting (-c), as that would cause callbacks
                                 to be runned multiple times for a given user.
                                 The -f flag makes this possible.
      -h, --help                 Show this help text.
    """ % {'name': basename(sys.argv[0])}

    sys.exit(exitcode)


def main(argv):
    try:
        opts, junk = getopt(argv[1:], 'hcrf', ('help', 'commit',
            'run_callbacks', 'force'))
    except GetoptError, e:
        print e
        usage(1)

    dryrun = True
    force = False
    run_callbacks = False

    for option, value in opts:
        if option in ('-h', '--help'):
            usage(0)
        elif option in ('-c', '--commit'):
            dryrun = False
        elif option in ('-r', '--run_callbacks'):
            run_callbacks = True
        elif option in ('-f', '--force'):
            force = True

    # Logical xor - must have (dryryn, not run_callbacks) or (not dryrun,
    # run_callbacks)
    assert force or (run_callbacks != dryrun), """Running callbacks without
    commiting would cause users to be notified multiple times about the same
    change. Commiting without running callbacks would cause users NOT to get
    notified about changes. If debugging, or running first time, use -f to force
    this action"""

    noti = Notifier(logger, dryrun=dryrun)

    # For new exports, notify if member of group with forward_url trait
    noti.add_export_cb(callback_notify_forward)

    noti.update_retained_trait()

    if run_callbacks:
        noti.run_callbacks(dryrun)

logger = Factory.get_logger(DEFAULT_LOGGER)
if __name__ == "__main__":
    main(sys.argv[:])
