#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2016 University of Oslo, Norway
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

"""Database cleaner that can:
    - delete change_log entries based on change_type
    - delete change_log entries between two dates
    - filter on expired accounts

"""
from __future__ import unicode_literals

import sys
import time
import datetime
import os
from six import text_type
from datetime import date
from datetime import time
from datetime import datetime
from datetime import timedelta

try:
    import dbcl_conf
except ImportError:
    dbcl_conf = None
from Cerebrum.Utils import Factory
from Cerebrum.modules import default_dbcl_conf
from Cerebrum.utils import json
from Cerebrum import Errors

logger = Factory.get_logger("big_shortlived")


def get_db():
    db = Factory.get('Database')()
    db.cl_init(change_program="db_clean")
    return db


#
# if keep_last == True => remove last change_type for each subject from the
# list if only_expired == true => remove entries belonging to non-expired
# accounts if change_types != False => remove all change_types not in this list
# 
# Returns a list of changes to be deleted from the database
#
def filter_entries(keep_last, only_expired, change_types, changes, db):
    ac = Factory.get('Account')(db)
    entity = Factory.get('Entity')(db)
    const = Factory.get('Constants')(db)
    # account_list = []
    # account_expired_list = []
    # entity_list = []
    allowed_changes = [14, 708, 20, 19, 530, 531, 18, 17, 16, 15]
    account_expire = {}

    # Create a list of all change types to process (if it is not False)
    if change_types != False:
        change_type_list = change_types.split(",")
        # print change_type_list
        # convert from string to int
        change_type_list = map(int, change_type_list)

    # now filter the entries
    deleted_entries = []
    if only_expired == True:
        logger.debug("only process expired accounts")
    for k, v in changes.items():
        logger.debug("processing entry:%s" % k)
        entity_id = v['subject_entity']
        current_change = v['change_type_id']

        # check if we are to process expired accounts only.
        if only_expired == True:

            # only process account changes as defined in allowed_changes
            if current_change in allowed_changes:

                # add account id to account_expire dict if not alread there
                # also set value to true/false if account is expired (or not)
                if entity_id not in account_expire:
                    try:
                        ac.clear()
                        ac.find(entity_id)
                        account_expire[entity_id] = ac.is_expired()
                        logger.debug("adding account_expire[%s] = %s" % (
                        entity_id, account_expire[entity_id]))
                    except Errors.NotFoundError:
                        logger.debug(
                            "unable to find account entity_id:%s, but we know "
                            "its an account entry. Delete change entry:%s" % (
                                entity_id, k))
                        # add account to account_expire dict. this will speedup
                        # the search when more and more accounts are found in
                        # this dict
                        account_expire[
                            entity_id] = True

                # check if account is expired
                if account_expire[entity_id] == False:
                    # account is not expired. remove from list (that means do
                    # not delete changelog entries for this account)
                    if k not in deleted_entries:
                        logger.debug(
                            "account:%s is NOT expired. Do not delete change "
                            "entry:%s " % (
                            v['subject_entity'], k))
                        del changes[k]
                        deleted_entries.append(k)
                        continue
            else:
                # this is not an account. remove from list
                if k not in deleted_entries:
                    logger.debug(
                        "This is not an account. Do not delete change "
                        "entry:%s" % k)
                    del changes[k]
                    deleted_entries.append(k)
                    continue

            if change_types != False:
                if int(v['change_type_id']) in change_type_list:
                    if k not in deleted_entries:
                        logger.debug(
                            "change entry is of valid type:%s. Do not delete "
                            "change entry:%s" % (
                                current_change, k))
                        del changes[k]
                        deleted_entries.append(k)
                        continue

            # logger.debug("Delete change entry:%s" % k)
        else:
            logger.debug("processing all types")
            if change_types != False:
                logger.debug("look for change types:%s" % change_types)
                if int(v['change_type_id']) in change_type_list:
                    if k not in deleted_entries:
                        logger.debug(
                            "change type:%s is in list of valid change types. "
                            "Do not delete change entry:%s" % (
                                v['change_type_id'], k))
                        del changes[k]
                        deleted_entries.append(k)
                        continue
        logger.debug("Delete entry:%s" % k)
    return changes


#
# collect changelog entires and delete entires according to the rules given
# keep_last = keep last changelog type of each type
# only_expired = only process changetypes of expird accounts
# change_types = only process these change types
#
def collect_entries(from_date, to_date, out_file, db, keep_last, only_expired,
                    change_types, dryrun):
    if out_file != False:
        fh = open(out_file, "w")

    # get number of entries between the 2 dates.
    # split the workload to avoid memory issues
    # this we do be collecting changelog entries for a single day at a time.
    dateformat = "%Y-%m-%d"
    from_obj = datetime.strptime(from_date, dateformat)
    to_obj = datetime.strptime(to_date, dateformat)
    logger.debug("START:%s - END %s" % (from_obj, to_obj))
    modified_to_date = from_obj + timedelta(days=1)
    modified_from_date = from_obj

    # collect all changelog entires from a single date
    changes = {}
    changes_since_last_commit = 0
    while modified_to_date <= to_obj:
        logger.debug(
            "processing day: %s - %s" % (modified_from_date, modified_to_date))
        retval = db.get_log_events_date(sdate=modified_from_date,
                                        edate=modified_to_date)
        modified_from_date = modified_from_date + timedelta(days=1)
        modified_to_date = modified_to_date + timedelta(days=1)
        for item in retval:
            changes[item['change_id']] = {'tstamp': item['tstamp'],
                                          'subject_entity': item[
                                              'subject_entity'],
                                          'change_type_id': item[
                                              'change_type_id'],
                                          'dest_entity': item['dest_entity'],
                                          'change_params': item[
                                              'change_params'],
                                          'change_by': item['change_by'],
                                          'change_program': item[
                                              'change_program']}
        filtered_changes = filter_entries(keep_last, only_expired,
                                          change_types, changes, db)
        logger.debug("deleted: %s entries" % len(filtered_changes.keys()))
        changes_since_last_commit += len(filtered_changes.keys())
        for k, v in filtered_changes.items():
            db.remove_log_event(k)

            if out_file != False:
                fh.writelines("%s : %s\n" % (k, v))
        # commit changes if not dryrunning
        if dryrun == False:
            if changes_since_last_commit > 1000000:
                db.commit()  # commit after 1.000.000 changes
                logger.debug(
                    "commit after: %s changes" % changes_since_last_commit)
                changes_since_last_commit = 0

    # Close filehandler if writing to file
    if out_file != False:
        fh.close()


def main(args=None):
    """Main script runtime. Parses arguments. Starts tasks."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('--from',
                        required=True,
                        dest='from_date',
                        action='store',
                        help='remove entries from this date. '
                             'Format is YYYY-MM-DD')
    parser.add_argument('--to',
                        required=True,
                        action='store',
                        dest='to_date',
                        help='Remove entries to this date. '
                             'Format is YYYY-MM-DD')
    parser.add_argument('--out=',
                        dest='out_file',
                        action='store',
                        default=False,
                        help='Move deleted entries to this file')
    parser.add_argument('--dryrun',
                        dest='dryrun',
                        default=False,
                        action='store_true',
                        help='Do not Commit changes or write to file')
    parser.add_argument('--keep-last',
                        dest='keep_last',
                        action='store_true',
                        default=False,
                        help='Do not delete last entry of each change type '
                             '(NOT WORKING YET)')
    parser.add_argument('--only-expired-accounts',
                        dest='only_expired',
                        action='store_true',
                        default=False,
                        help='Only delete change entries belonging to expired '
                             'accounts')
    parser.add_argument('--change_types=',
                        dest='change_types',
                        action='store',
                        default=False,
                        help='Only delete change entries listed in change_'
                             'types attribute. format is comma separated list '
                             'with values as listed in change_type.change_'
                             'type_id in the database')

    args = parser.parse_args(args)

    logger.info("Starting %s with args: %s", parser.prog, args.__dict__)

    db = get_db()
    collect_entries(args.from_date, args.to_date, args.out_file, db,
                    args.keep_last, args.only_expired, args.change_types,
                    args.dryrun)

    #
    # dryrun, rollback database and delete out file (if it exists!)
    #
    if args.dryrun == True:
        print "dryrun: rollback all changes"
        db.rollback()
    else:
        db.commit()

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
