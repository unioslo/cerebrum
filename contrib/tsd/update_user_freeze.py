#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2015-2018 University of Oslo, Norway
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
This script is used to set / remove user auto-freeze on users that are
members of projects that have been frozen.
"""

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory

logger = Factory.get_logger('cronjob')


def auto_freeze_project_accounts(db,
                                 account_ids,
                                 auto_freeze_datetime,
                                 default_creator_id):
    """
    Sets quarantine with type auto_frozen and with start_date
    = `auto_freeze_datetime` to all
    accounts corresponding to the given `account_ids`

    All accounts will be processed as following:
        - if an account doesn't have an auto_frozen quarantine from before
          a new one will be created
        - if an account has an auto_frozen quarantine from before but its
          start_date is not the same as `auto_freeze_datetime`,
          the account's auto_frozen quarantine will be removed
          before a new one is added
        - no changes will be made to the account in all other cases

    :type db: Cerebrum.database.Database
    :param db: The database connection-object

    :type account_ids: list
    :param project: The list of account ids for the accounts to be auto-frozen

    :type auto_freeze_datetime: mx.DateTime or None
    :param auto_freeze_datetime: The start_time for all new quarantines

    :type default_creator_id: int or long
    :param default_creator_id: the entity_id of the "creator" account
    """
    account = Factory.get('Account')(db)
    for account_id in account_ids:
        account.clear()
        account.find(account_id)
        logger.debug('Processing account %s (entity_id=%d)',
                     account.account_name,
                     account.entity_id)
        if account.has_autofreeze_quarantine:
            if auto_freeze_datetime != account.autofreeze_quarantine_start:
                # autofreeze quarantine exists for this account
                # but its start_date is not the same as the one for the
                # project's freeze quarantine.
                # Remove the existing quarantine before adding a new one
                account.remove_autofreeze_quarantine()
                logger.debug(
                    'Removed auto freeze quarantine from Account %s '
                    '(entity_id=%d)',
                    account.account_name,
                    account.entity_id)
            else:
                # autofreeze quarantine exists for this account
                # and its start_date is the same as the one for the
                # project's freeze quarantine. No need to do anything
                logger.debug(
                    'Account %s (entity_id=%d) already has a valid '
                    'auto freeze quarantine. Nothing to be done',
                    account.account_name,
                    account.entity_id)
                continue
        # add new quarantine using the peoject's freeze-start_date
        account.add_autofreeze_quarantine(
            creator=default_creator_id,
            description='Auto set due to project-freeze',
            start=auto_freeze_datetime
        )
        logger.info(
            'Added auto freeze quarantine to Account %s (entity_id=%d)',
            account.account_name,
            account.entity_id)


def remove_auto_freeze_from_project_accounts(db, account_ids):
    """
    Removes quarantine with type auto_frozen from all
    accounts corresponding to the given `account_ids`

    :type db: Cerebrum.database.Database db
    :param db: The database connection-object

    :type account_ids: list
    :param project: The list of account ids for the accounts to be "unfrozen"
    """
    account = Factory.get('Account')(db)
    for account_id in account_ids:
        account.clear()
        account.find(account_id)
        logger.debug('Processing account %s (entity_id=%d)',
                     account.account_name,
                     account.entity_id)
        if account.has_autofreeze_quarantine:
            account.remove_autofreeze_quarantine()
            logger.info(
                'Removed auto freeze quarantine from Account %s '
                '(entity_id=%d)',
                account.account_name,
                account.entity_id)


def update_user_freeze(db, dryrun):
    """
    Sets / unsets auto-freeze quarantine for accounts belonging to
    projects with set / unset freeze quarantine

    :type db: Cerebrum.database.Database db
    :param db: The database connection-object

    :type dryrun: bool
    :param dryrun: If True, do not actually commit DB changes
    """
    try:  # all or nothing policy
        if dryrun:
            logger.info('DRYRUN: Rolling back all changes')
        constants = Factory.get('Constants')(db)
        project = Factory.get('OU')(db)
        account = Factory.get('Account')(db)
        account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        default_creator_id = account.entity_id
        # create ou_id -> accounts mappings in order to minimize db-load
        ou2accounts = dict()
        account_rows = account.list_accounts_by_type(
            affiliation=constants.affiliation_project,
            filter_expired=True,
            account_spread=constants.spread_gateway_account)
        for account_row in account_rows:
            if account_row['ou_id'] not in ou2accounts:
                # the first element for this ou_id
                ou2accounts[account_row['ou_id']] = list()
            ou2accounts[account_row['ou_id']].append(
                account_row['account_id'])
        logger.debug('Found %d projects connected with account(s)',
                     len(ou2accounts))
        # process all projects
        project_rows = project.search()
        logger.debug('Processing a total of %d projects', len(project_rows))
        for project_row in project_rows:
            project.clear()
            project.find(project_row['ou_id'])
            if project_row['ou_id'] not in ou2accounts:
                logger.debug(
                    'Project %s (entity_id=%d) has no affiliated accounts. '
                    'Skipping',
                    project.get_project_name(),
                    project.entity_id)
                continue  # no accounts found
            if project.has_freeze_quarantine:
                # auto-freeze all accounts affiliated with this project
                logger.debug(
                    'Auto-freezing accounts for project %s (entity_id=%d)',
                    project.get_project_name(),
                    project.entity_id)
                auto_freeze_project_accounts(db,
                                             ou2accounts[project_row['ou_id']],
                                             project.freeze_quarantine_start,
                                             default_creator_id)
            else:
                # remove all auto_frozen-quarantines from all accounts
                # affiliated with this project
                logger.debug(
                    'Auto-unfreezing accounts for project %s (entity_id=%d)',
                    project.get_project_name(),
                    project.entity_id)
                remove_auto_freeze_from_project_accounts(
                    db,
                    ou2accounts[project_row['ou_id']])
        if dryrun:
            db.rollback()
        else:
            db.commit()
    except Exception, e:
        logger.critical('Unexpected exception: %s' % (str(e)), exc_info=True)
        db.rollback()
        raise


def main(args=None):
    """
    """
    try:
        import argparse
    except ImportError:
        from Cerebrum.extlib import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-d', '--dryrun',
        action='store_true',
        dest='dryrun',
        default=False,
        help='Do not actually remove the groups '
        '(default: All matching groups will be removed)'
    )
    logger.info('START %s', parser.prog)
    args = parser.parse_args(args)
    db = Factory.get('Database')()
    db.cl_init(change_program='update_user_freeze.py')
    update_user_freeze(db, args.dryrun)
    logger.info('DONE %s', parser.prog)


if __name__ == '__main__':
    main()
