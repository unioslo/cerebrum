#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011, 2012, 2014 University of Oslo, Norway
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

"""Deactivate accounts with a given quarantine.

This script checks all accounts for a given type of quarantine. If such
quarantine exists and it has been created before the date implied by the
since-parameter the account is deactivated. Only active quarantines are
considered.

Note that this script depends on Account.deactivate() for removal of spreads,
home directory etc. depending on what the institution needs. The deactivate
method must be implemented in the institution specific account mixin -
Cerebrum/modules/no/INST/Account.py - before this script would work.

The script also supports deleting (nuking) accounts instead of just deactivating
them.  You should be absolutely sure before you run it with nuking, as this
deletes all the details around the user accounts, even its change log.

Note: If a quarantine has been temporarily disabled, it would not be found by
this script. This would make it possible to let accounts live for prolonged
periods, without getting deactivated. This is a problem which should be solved
in other ways, and not by this script.

"""

import sys
import getopt

import time
import mx.DateTime as dt

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory

logger = Factory.get_logger("cronjob")
database = Factory.get("Database")()
database.cl_init(change_program="deactivate-qua")
constants = Factory.get("Constants")(database)
# we could probably generalise and use entity here, but for now we
# need only look at accounts
account = Factory.get("Account")(database)
today = dt.today()


def fetch_all_relevant_accounts(qua_type, since):
    """Fetch all accounts that matches the criterias for deactivation.

    :param QuarantineCode qua_type:
        The quarantine that the accounts must have to be targeted.

    :param int since:
        The number of days a quarantine must have been active for the account to
        be targeted.

    :rtype: set
    :returns: The `entity_id` for all the accounts that match the criterias.

    """
    max_date = dt.now() - since
    logger.debug("Search quarantines older than %s days, i.e. before %s", since,
                 max_date.strftime('%Y-%m-%d'))
    quarantined = set(row['entity_id'] for row in
                      account.list_entity_quarantines(
                            entity_types=constants.entity_account,
                            quarantine_types=qua_type, only_active=True)
                      if row['start_date'] <= max_date)
    logger.debug("Found %d quarantine targets", len(quarantined))

    # TODO: Check person affiliations

    return quarantined

def process_account(account, delete=False):
    """Deactivate the given account.

    :param Cerebrum.Account: The account that should get deactivated.

    :param bool delete:
        If True, the account will be totally deleted instead of just
        deactivated.

    :rtype: bool
    :returns: If the account really got deactivated/deleted.

    """
    if delete:
        logger.info("Terminating account: %s", account.account_name)
        account.terminate()
        return True
    if account.is_deleted():
        logger.debug2("Account %s already deleted", account.account_name)
        return False
    account.deactivate()
    logger.info("Deactivated account: %s", account.account_name)
    return True

def usage(exitcode=0):
    print """Usage: deactivate_quarantined_accounts.py -q quarantine_type -s #days [-d]

Deactivate all accounts where given quarantine has been set for at least #days.

%s

    -q, --quarantine QUAR   Quarantine type. Default: generell

    -s, --since DAYS        Number of days since quarantine started. Default: 30

    -l, --limit LIMIT       Limit the number of deactivations by the script.
                            This is to prevent too much changes in the system,
                            as archiving could take time. Defaults to no limit.

    -d, --dryrun            Do not commit changes to the database

        --terminate         *Delete* the account instead of just deactivating
                            it. Warning: This deletes *everything* about the
                            accounts with active quarantines, even their logs.
                            This can not be undone, so use with care!

    -h, --help              show this and quit.
    """ % __doc__
    sys.exit(exitcode)

def main():
    options, junk = getopt.getopt(sys.argv[1:],
                                  "q:s:dh",
                                  ("quarantine=",
                                   "dryrun",
                                   "help",
                                   "terminate",
                                   "since=",))
    dryrun = False
    limit = None
    # default quarantine type
    quarantine = int(constants.quarantine_generell)
    # number of days since quarantine has started
    since = 30
    delete = False

    for option, value in options:
        if option in ("-q", "--quarantine"):
            quarantine = int(constants.Quarantine(value))
        elif option in ("-d", "--dryrun"):
            dryrun = True
        elif option in ("-s", "--since"):
            since = value
        elif option in ("-l", "--limit"):
            limit = int(value)
        elif option in ("--terminate",):
            logger.info('Set to delete accounts and not just deactivating!')
            delete = True
        elif option in ("-h", "--help"):
            usage()
        else:
            print "Unknown argument: %s" % option
            usage(1)

    logger.info("Start deactivate_quarantined_accounts")
    logger.info("Fetching relevant accounts")
    rel_accounts = fetch_all_relevant_accounts(quarantine, since)
    logger.info("Got %s accounts to process", len(rel_accounts))

    i = 0
    for a in rel_accounts:
        if limit and i >= limit:
            logger.debug("Limit of deactivations reached (%d), stopping", limit)
            break
        account.clear()
        try:
            account.find(int(a))
        except Errors.NotFoundError:
            logger.warn("Could not find account_id %s, skipping", a)
            continue
        logger.debug('Processing account %s (%s)', account.account_name,
                     account.entity_id)
        try:
            process_account(account, delete)
            i += 1
        except Exception, e:
            # Add debug info
            logger.warn("Failed processing account: %s" % account.account_name)
            raise

    if dryrun:
        database.rollback()
        logger.info("rolled back all changes")
    else:
        database.commit()
        logger.info("changes commited")
    logger.info("Done deactivate_quarantined_accounts")

if __name__ == '__main__':
    main()
