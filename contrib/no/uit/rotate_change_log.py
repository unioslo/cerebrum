#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2004 - 2019 University of Oslo, Norway
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
"""Rotate_change_log removes entries from the change_log table.

    Note:
        One of --change_program and --change_type must be given.
        For historical reasons account_create and account_password
        entries will not be allowed deleted.
"""
from __future__ import unicode_literals

import argparse
import logging
import sys
import time
import cereconf
import os
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.Utils import Factory
from Cerebrum.Errors import ProgrammingError
import Cerebrum.logutils

logger = logging.getLogger(__name__)

ENCODING = 'latin-1'


class AccessLog(object):

    def __init__(self, file_dump, db, change_type_list=None):

        self.db = db
        self.cl_constants = Factory.get('CLConstants')(self.db)

        # no_touch_change_type_id contains a list over change_type_id's which
        # will not be deleted under any circumstances.
        self.no_touch_change_type_id = (
            int(self.cl_constants.account_create),
            int(self.cl_constants.account_password),
            int(self.cl_constants.quarantine_add),
            int(self.cl_constants.quarantine_del),
            int(self.cl_constants.person_create),
            int(self.cl_constants.entity_add),
            int(self.cl_constants.entity_ext_id_mod),
            int(self.cl_constants.entity_ext_id_add),
            int(self.cl_constants.group_create),
            int(self.cl_constants.group_add),
            int(self.cl_constants.ou_create)
        )

        try:
            for change_type in change_type_list:
                if int(change_type) in self.no_touch_change_type_id:
                    logger.error("%s is not a valid change_type.",
                                 int(change_type))
                    sys.exit(1)
        except TypeError:
            # no change_type given
            logger.debug("No change type given as parameter to program")
        if file_dump is not None:
            if not (os.path.isfile(file_dump)):
                self.file_handle = open(file_dump, "w")
                logger.debug("opening %s for writing", file_dump)
            else:
                # file already exists. concatenate data
                self.file_handle = open(file_dump, "a")
                logger.debug("opening %s for appending", file_dump)
        else:
            # no data will be stored in log files
            logger.debug("No dump file spesified")

    # get all change_ids we want to delete.
    def get_change_ids(self, date=None, change_program=None, change_type=None):
        # convert the type_list to a type_tuple
        type_tuple = change_type
        log_rows = self.get_old_log_events(sdate=date, types=type_tuple,
                                           change_program=change_program)
        return log_rows

    def delete_change_ids(self, id_list):
        try:
            # we've had some trouble deleting entries from the change_log table
            # when other scripts also tries to update it. adding a lock table
            # command to prevent this.
            self.db.query("lock table change_log")
            for row in id_list:
                line = "{},{},{},{},{},{},{},{}\n".format(
                    row['tstamp'], row['change_id'],
                    row['subject_entity'], row['change_type_id'],
                    row['dest_entity'], row['change_params'],
                    row['change_by'], row['change_program']
                ).encode(ENCODING)
                self.file_handle.write(line)
                self.db.remove_log_event(row['change_id'])
            self.file_handle.close()
        except AttributeError:
            logger.debug(
                "No dump file has been given. deleting withouth taking backup")
            # unable to write to file. no log file has been given
        self.db.commit()

    def get_old_log_events(self, start_id=0, max_id=None, types=None,
                           subject_entity=None, dest_entity=None,
                           any_entity=None, change_by=None, sdate=None,
                           change_program=None):
        if any_entity and (dest_entity or subject_entity):
            raise ProgrammingError("any_entity is mutually exclusive with"
                                   " dest_entity or subject_entity")
        where = ["change_id >= :start_id"]
        bind = {'start_id': int(start_id)}
        if subject_entity is not None:
            where.append("subject_entity=:subject_entity")
            bind['subject_entity'] = int(subject_entity)
        if dest_entity is not None:
            where.append("dest_entity=:dest_entity")
            bind['dest_entity'] = int(dest_entity)
        if any_entity is not None:
            where.append("subject_entity=:any_entity OR "
                         "dest_entity=:any_entity")
            bind['any_entity'] = int(any_entity)
        if change_by is not None:
            where.append("change_by=:change_by")
            bind['change_by'] = int(change_by)
        if max_id is not None:
            where.append("change_id <= :max_id")
            bind['max_id'] = int(max_id)
        if types is not None:
            where.append("change_type_id IN(" + ", ".join(
                ["%s" % x for x in types]) + ")")
        if change_program is not None:
            where.append("change_program IN('" + "','".join(
                ["%s" % x for x in change_program]) + "')")
        if self.no_touch_change_type_id is not None:
            where.append("change_type_id NOT IN(" + ",".join(
                ["%s" % x for x in self.no_touch_change_type_id]) + ")")
        if sdate is not None:
            where.append("tstamp < :sdate")
            bind['sdate'] = sdate
        where = "WHERE (" + ") AND (".join(where) + ")"
        logger.debug("WJHERE=%s", where)
        return self.db.query("""
        SELECT tstamp, change_id, subject_entity, change_type_id, dest_entity,
               change_params, change_by, change_program
        FROM [:table schema=cerebrum name=change_log] %s
        ORDER BY change_id""" % where, bind, fetchall=False)


def get_dump_file(date_tmp):
    date_today = "%02d%02d%02d" % (date_tmp[0], date_tmp[1], date_tmp[2])
    dump_file = os.path.join(sys.prefix, 'var', 'log', 'cerebrum',
                             'change_log_%s' % (date_today))
    return dump_file


def get_date(date_tmp):
    # threshold_date is used by rotate_change_log
    time_float = time.mktime(date_tmp) - (
                60 * 60 * 24 * 30)  # (60*60*24*30) => 1 month
    new_time = time.gmtime(time_float)
    nt_year = new_time[0]
    nt_month = new_time[1]
    nt_day = new_time[2]
    threshold_date = "%02d%02d%02d" % (nt_year, nt_month, nt_day)
    return threshold_date


def main():
    date_tmp = time.localtime()
    default_dump_file = get_dump_file(date_tmp)
    default_date = get_date(date_tmp)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-d', '--dump_file',
        default=default_dump_file,
        help='Removed data will be dumped into this file.'
    )
    parser.add_argument(
        '-D', '--date',
        default=default_date,
        help='All entries listed in change_program and change_type, older than'
             ' this date, will be deleted. format is: YYYY-MM-DD'
    )
    parser.add_argument(
        '-c', '--change_program',
        default=None,
        help='Comma sepparated list. All entries from these scripts will be '
             'deleted'
    )
    parser = add_commit_args(parser, default=True)

    args, _rest = parser.parse_known_args()
    parser.add_argument(
        '-C', '--change_type',
        required=args.change_program is None,
        default=None,
        help='Comma sepparated list. All entries of these change_types will be'
             ' deleted.'
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf("cronjob", args)

    change_type_list = None
    change_program_list = None
    db = Factory.get('Database')()

    if not args.commit:
        db.commit = db.rollback

    if args.change_type:
        change_type_list = args.change_type.split(",")
    if args.change_program:
        change_program_list = args.change_program.split(",")

    log = AccessLog(args.dump_file, db, change_type_list)
    id_list = log.get_change_ids(args.date, change_program_list,
                                 change_type_list)
    log.delete_change_ids(id_list)


if __name__ == '__main__':
    main()
