#!/usr/bin/env python
# coding: utf-8
#
# Copyright 2016 University of Oslo, Norway
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
""" Script to maintain accounts of students with aff STUDENT/ny. """
from __future__ import unicode_literals, absolute_import, print_function

import argparse
import datetime
import logging
import os.path
from collections import defaultdict

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.descriptors import lazy_property
from Cerebrum.Utils import Factory


SCRIPT_NAME = os.path.basename(__file__)

logger = logging.getLogger(__name__)


class NewStudentHelper(object):
    """ Helper utility to identify and maintain new student accounts.

    All personal accounts (owned by a person) are identified by `account type`,
    a reference to an affiliation. This script regards an account type as
    *real* if the affiliation (<person_id>, <affiliation>, <ou_id>) is also
    present on the owner (person). Non-real account_types are not actual
    affiliations, and will never have an affiliation status.

    This object classifies account types as:

    Student account
        A student account is an account where one of the account types is a
        STUDENT-affiliation.

    New student account
        A *new* student account is an account where at least one account type
        is a *real* STUDENT/ny affiliation.

    Active student account
        An *active* student account is an account where at least one account
        type is a *real* STUDENT affiliation, and is *not* a
        STUDENT/opptak-affiliation.

    Inactive student account
        An inactive student account is an account where *all* account types are
        *STUDENT/opptak* affiliations.

    In addition, this utility uses some unique properties to identify accounts:

    Locked account
        An account with a unique quarantine given by this utility.

    Tagged account
        An account with a unique trait given by this utility.
    """

    STAT_TAGGED = 'tagged'
    STAT_UNTAGGED = 'untagged'
    STAT_LOCKED = 'locked'
    STAT_UNLOCKED = 'unlocked'

    @lazy_property
    def db(self):
        db = Factory.get(b'Database')()
        db.cl_init(change_program=SCRIPT_NAME)
        return db

    @lazy_property
    def co(self):
        return Factory.get(b'Constants')(self.db)

    @lazy_property
    def trait(self):
        """ the trait used by this script. """
        return self.co.trait_tmp_student

    @lazy_property
    def quarantine(self):
        """ the quarantine used by this script. """
        return self.co.quarantine_auto_tmp_student

    @lazy_property
    def stats(self):
        return defaultdict(int)

    @lazy_property
    def operator(self):
        """ operator for db-changes """
        ac = Factory.get(b'Account')(self.db)
        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        return ac

    def get_account_type_affs(self, account):
        """ Returns the *real* affiliations tied in with an account. """
        if account.owner_type != self.co.entity_person:
            return []
        ac_types = {
            (row['affiliation'], row['ou_id'])
            for row in account.get_account_types()}
        pe = Factory.get(b'Person')(self.db)
        pe.find(account.owner_id)
        return [row for row in pe.get_affiliations()
                if (row['affiliation'], row['ou_id']) in ac_types]

    def is_new_account(self, account):
        """ Check if account is new.

        A new account is an account that has AT LEAST one 'STUDENT/ny' account
        type. Note that we only consider account types that are also present as
        affs on the owner (person).
        """
        # `any` returns `False` on an empty collection - just what we want!
        affs = self.get_account_type_affs(account)
        return (
            any(aff['affiliation'] == self.co.affiliation_student and
                aff['status'] == self.co.affiliation_status_student_ny
                for aff in affs) and
            all(aff['affiliation'] == self.co.affiliation_student and
                aff['status'] == self.co.affiliation_status_student_ny or
                aff['status'] == self.co.affiliation_status_student_opptak
                for aff in affs))

    def is_inactive_account(self, account):
        """ Check if account is inactive.

        An inactive account has EITHER only 'STUDENT/opptak' account types, OR
        no account types. Note that we only consider account types that are
        also present as affs on the owner (person).
        """
        # `all` returns `False` on an empty collection - just what we want!
        return all(
            aff['affiliation'] == self.co.affiliation_student
            and aff['status'] == self.co.affiliation_status_student_opptak
            for aff in self.get_account_type_affs(account))

    def list_new_accounts(self):
        """ Student accounts of students with status 'new' """
        ac_list = Factory.get(b'Account')(self.db)
        for row in ac_list.list_accounts_by_type(
                affiliation=self.co.affiliation_student,
                status=self.co.affiliation_status_student_ny,
                fetchall=False):
            account = Factory.get(b'Account')(self.db)
            account.find(row['account_id'])
            # The account has account_type STUDENT/ny, but it may just be
            # a leftover account type on an inactive account:
            if self.is_new_account(account):
                yield account

    def list_tagged_accounts(self):
        """ List tagged accounts. """
        ac_list = Factory.get(b'Account')(self.db)
        for row in ac_list.list_traits(code=self.trait):
            if row['entity_type'] != self.co.entity_account:
                continue
            ac = Factory.get(b'Account')(self.db)
            ac.find(row['entity_id'])
            yield ac

    def is_tagged_account(self, account):
        """ Check if account is tagged """
        return account.get_trait(self.trait) is not None

    def tag_account(self, account):
        """ Tag account as new account. """
        account.populate_trait(code=self.trait)
        account.write_db()
        self.stats[self.STAT_TAGGED] += 1

    def untag_account(self, account):
        """ Untag account. """
        account.delete_trait(self.trait)
        self.stats[self.STAT_UNTAGGED] += 1

    def list_locked_accounts(self):
        """ List accounts locked by this script. """
        ac_list = Factory.get(b'Account')(self.db)
        for row in ac_list.list_entity_quarantines(
                entity_types=self.co.entity_account,
                quarantine_types=self.quarantine):
            account = Factory.get(b'Account')(self.db)
            account.find(row['entity_id'])
            yield account

    def is_locked_account(self, account):
        """ Check if account has been locked. """
        return bool(
            account.get_entity_quarantine(
                qtype=self.quarantine,
                only_active=False,
                filter_disable_until=False))

    def lock_account(self, account):
        """ Lock an account. """
        account.add_entity_quarantine(
            self.quarantine,
            self.operator.entity_id,
            description="ny, inaktiv student",
            start=datetime.date.today())
        self.stats[self.STAT_LOCKED] += 1

    def unlock_account(self, account):
        """ Unlock an account. """
        account.delete_entity_quarantine(self.quarantine)
        self.stats[self.STAT_UNLOCKED] += 1


def tag_new_accounts(db_helper):
    """ Tag all new, untagged accounts. """
    for account in db_helper.list_new_accounts():
        if not db_helper.is_tagged_account(account):
            db_helper.tag_account(account)
            logger.debug("tagged account '%s'", account.account_name)


def process_tagged_accounts(db_helper):
    """ Untag and process all tagged accounts that aren't new. """
    for account in db_helper.list_tagged_accounts():
        logger.debug("account '%s' has trait", account.account_name)
        if db_helper.is_new_account(account):
            continue
        # not considered new anymore, must update
        db_helper.untag_account(account)
        logger.debug("account '%s' no longer new", account.account_name)
        if (db_helper.is_inactive_account(account)
                and not db_helper.is_locked_account(account)):
            db_helper.lock_account(account)
            logger.info("locked account '%s'", account.account_name)


def process_locked_accounts(db_helper):
    """ Unlock accounts that are not inactive. """
    for account in db_helper.list_locked_accounts():
        if not db_helper.is_inactive_account(account):
            db_helper.unlock_account(account)
            logger.info("unlocked account %s", account.account_name)


def print_new_students(db_helper):
    """ Print list of new accounts. """
    print("New accounts")
    for account in db_helper.list_new_accounts():
        print(" - {:s}".format(account.account_name))


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--list',
        action='store_true',
        help="List new accounts and exit",
    )

    db_args = parser.add_argument_group('Database')
    add_commit_args(db_args)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)
    logger.info("Start %s", parser.prog)
    logger.debug("args: %r", args)

    db_helper = NewStudentHelper()

    if args.list:
        print_new_students(db_helper)
        raise SystemExit(0)

    logger.info("unlock active accounts...")
    process_locked_accounts(db_helper)
    logger.info("process tagged accounts...")
    process_tagged_accounts(db_helper)
    logger.info("tag new accounts...")
    tag_new_accounts(db_helper)

    logger.info("Tagged %d accounts",
                db_helper.stats[db_helper.STAT_TAGGED])
    logger.info("Untagged %d accounts",
                db_helper.stats[db_helper.STAT_UNTAGGED])
    logger.info("Locked %d accounts",
                db_helper.stats[db_helper.STAT_LOCKED])
    logger.info("Unlocked %d accounts",
                db_helper.stats[db_helper.STAT_UNLOCKED])

    if args.commit:
        db_helper.db.commit()
        logger.info("Changes has been commited.")
    else:
        db_helper.db.rollback()
        logger.info("Changes has been rolled back.")

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
