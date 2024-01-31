#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2023 University of Oslo, Norway
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
Combine, remove or modify changelog records

This is script can be used to:

- Remove records of a given type if older than a given limit
- Clean up successive records
- Remove passwords from change_params

Default configuration lives in :mod:`Cerebrum.modules.default_dbcl_conf`.
Configuration that extends and/or overrides the defaults should be in a
`dbcl_conf` module.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import datetime
import logging

from six import text_type

try:
    import dbcl_conf
except ImportError:
    dbcl_conf = None

import Cerebrum.logutils
from Cerebrum.modules import default_dbcl_conf
from Cerebrum.Utils import Factory
from Cerebrum.utils import json
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import date_compat

logger = logging.getLogger(__name__)


def get_db():
    db = Factory.get('Database')()
    db.cl_init(change_program="db_clean")
    return db


def maybe_commit(cls):
    if cls.commit:
        logger.info("Committing changes")
        cls.db.commit()
    else:
        logger.info("Rolled back changes")
        cls.db.rollback()


class CleanChangeLog(object):

    def __init__(self, commit=False):
        self.commit = commit
        self.db = get_db()
        self.co = Factory.get('Constants')(self.db)
        self.clconst = Factory.get('CLConstants')(self.db)

        self.forever = default_dbcl_conf.forever

        if dbcl_conf:
            logger.info("Found instance specific configuration: %s", dbcl_conf)
        else:
            logger.info("No instance specific configuration found")

        # Importing the instance specific changelog cleaning rules, if any
        self.default_age = getattr(dbcl_conf, 'default_age',
                                   default_dbcl_conf.default_age)
        self.minimum_age = getattr(dbcl_conf, 'minimum_age',
                                   default_dbcl_conf.minimum_age)

        # Update max ages
        self.max_ages = default_dbcl_conf.max_ages
        if hasattr(dbcl_conf, 'max_ages'):
            self.max_ages.update(dbcl_conf.max_ages)

        # Extend togglers
        self.togglers = default_dbcl_conf.togglers
        if hasattr(dbcl_conf, 'togglers'):
            for i in dbcl_conf.togglers:
                found = False
                for j in self.togglers:
                    if i['triggers'] == j['triggers']:
                        found = True
                        if ('togglable' in i and 'togglable' in j
                                and i['togglable'] == j['togglable']):
                            logger.info(
                                "Custom trigger %s with default settings,"
                                " skipping",
                                j['triggers'])
                        else:
                            j['togglable'] = i['togglable']
                            logger.info(
                                "Updated following trigger %s to "
                                " 'togglable': %s",
                                j['triggers'], i['togglable'])
                        break
                if not found:
                    self.togglers.append(i)

    def int_or_none(self, i):
        if i is not None:
            return int(i)
        return i

    def format_for_logging(self, e):
        is_pwd = int(e['change_type_id']) == int(self.clconst.account_password)
        return (
            e['tstamp'].strftime('%Y-%m-%d'),
            int(e['change_id']),
            text_type(self.clconst.map_const(int(e['change_type_id']))),
            self.int_or_none(e['subject_entity']),
            self.int_or_none(e['dest_entity']),
            'password' if is_pwd else e['change_params'],
        )

    def process_log(self):
        start = date_utils.now()
        last_seen = {}
        unknown_type = {}
        processed = aged = toggled = 0

        logger.info("Fetching change log...")
        # Use a separate cursor for fetching
        db2 = get_db()

        for e in db2.get_log_events():
            processed += 1
            if (processed % 100000) == 0:
                logger.debug('processed = %s', processed)
            change_type = int(e['change_type_id'])

            # Skip unknown change types
            if change_type not in self.trigger_map:
                unknown_type.setdefault(change_type, 0)
                unknown_type[change_type] += 1
                continue

            # Keep all data newer than minimum_age
            age = (start -
                   date_compat.get_datetime_tz(e['tstamp'])).total_seconds()
            if age < self.minimum_age:
                continue

            # logger.debug('Changelog entry: {!r}'.format(
            #     self.format_for_logging(e)))

            max_age = self.max_ages.get(change_type, self.default_age)
            if max_age != self.forever and age > max_age:
                logger.info("Removed due to age: %s",
                            repr(self.format_for_logging(e)))
                aged += 1
                if self.commit:
                    self.db.remove_log_event(e['change_id'])

            # Determine a unique key for this event to check togglability
            toggler = self.trigger_map[change_type]
            if toggler is None:
                continue
            key = ["{:d}".format(toggler['id'])]
            for column in toggler['columns']:
                key.append("{:d}".format(e[column]))
            if 'change_params' in toggler:
                if e['change_params']:
                    data = json.loads(e['change_params'])
                else:
                    data = {}
                for c in toggler['change_params']:
                    key.append("{}".format(data.get(c)))
            key = "-".join(key)

            # Has something been toggled?
            if key in last_seen:
                logger.info("Removed toggle %s, %s toggled by %s",
                            repr(key), repr(last_seen[key]),
                            repr(self.format_for_logging(e)))
                toggled += 1
                if self.commit:
                    self.db.remove_log_event(last_seen[key])
            last_seen[key] = int(e['change_id'])

            if self.commit and (processed % 1000) == 0:
                self.db.commit()

        for change_type, num in unknown_type.items():
            logger.warn("Unknown change type id:%s (%s) for %s entries",
                        change_type,
                        text_type(self.clconst.human2constant(change_type)),
                        num)

        maybe_commit(self)

        logger.info("Entries processed: %s", processed)
        logger.info("Entries removed due to age: %s", aged)
        logger.info("Entries removed due to being toggled: %s", toggled)
        logger.info("Spent %s", date_utils.now() - start)

    def parse_config(self):
        logger.info("Default age: %s seconds", self.default_age)
        logger.info("Minimum age: %s seconds", self.minimum_age)
        logger.info("Parsing max ages...")

        for human_change_type, age in self.max_ages.items():
            change_type = self.clconst.human2constant(human_change_type)
            if change_type is None:
                logger.info("Unknown change type %s ignored",
                            repr(human_change_type))
                del self.max_ages[human_change_type]
                continue
            assert isinstance(change_type, self.clconst.ChangeType)
            self.max_ages[int(change_type)] = age
            del self.max_ages[human_change_type]

        logger.info("Max age overrides: %d", len(self.max_ages))

        togglable_stats = {True: 0, False: 0}
        self.trigger_map = {}
        logger.info("Parsing togglers...")

        for toggler_id, data in enumerate(self.togglers):
            data['id'] = toggler_id
            triggers = []

            # Verify and convert change types
            for trigger in data['triggers']:
                change_type = self.clconst.human2constant(trigger)
                if change_type is None:
                    logger.info("Unknown change type %s ignored", trigger)
                    continue
                if not isinstance(change_type, self.clconst.ChangeType):
                    logger.info("%s is not a change type", repr(trigger))
                    continue
                triggers.append(int(change_type))

            # Skip toggler if a change type is unknown
            if len(triggers) != len(data['triggers']):
                logger.info("One or more unknown triggers, ignoring: %s",
                            repr(data))
                continue

            data['triggers'] = triggers
            togglable = data.get('togglable', True)
            togglable_stats[togglable] += 1

            # Add to map
            for trigger in triggers:
                if trigger in self.trigger_map:
                    raise ValueError("{} is not a unique trigger".format(
                        self.clconst.ChangeType(trigger)))
                self.trigger_map[trigger] = data if togglable else None

        logger.info("Unique toggler rules: %d", len(self.togglers))
        logger.info("Active toggler rules: %s", togglable_stats[True])
        logger.info("Inactive toggler rules: %s", togglable_stats[False])

    def run(self):
        self.parse_config()
        self.process_log()


class CleanPasswords(object):

    def __init__(self, password_age, commit=False):
        self.commit = commit
        self.password_age = password_age
        self.db = get_db()
        self.co = Factory.get('Constants')(self.db)
        self.clconst = Factory.get('CLConstants')(self.db)

    def remove_plaintext_passwords(self):
        """Removes plaintext passwords."""
        today = datetime.date.today()
        delta = datetime.timedelta(days=self.password_age)
        cutoff = today - delta

        start = date_utils.now()

        removed = 0
        logger.info("Fetching password change log entries...")
        for e in self.db.get_log_events_date(
                type=int(self.clconst.account_password),
                edate=cutoff):
            if not e['change_params']:
                # Nothing to remove
                continue
            data = json.loads(e['change_params'])
            if 'password' in data:
                del data['password']
                if self.commit:
                    self.db.update_log_event(e['change_id'], data)
                logger.info("Removed password for id:%d", e['subject_entity'])
                removed += 1

        logger.info("Spent %s", date_utils.now() - start)
        logger.info("Removed %s passwords older than %s", removed, cutoff)

        maybe_commit(self)

    def run(self):
        self.remove_plaintext_passwords()


def main(args=None):
    """Main script runtime. Parses arguments. Starts tasks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plaintext-passwords',
                        default=False,
                        action='store_true',
                        dest='remove_plaintext',
                        help='Remove plaintext passwords')
    parser.add_argument('--password-age-days',
                        dest='password_age_days',
                        type=int,
                        default=30,
                        metavar='<days>',
                        help='Remove passwords older than this')
    parser.add_argument('--changelog',
                        default=False,
                        action='store_true',
                        dest='clean_changelog',
                        help='Clean changelog entries')

    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(args)
    Cerebrum.logutils.autoconf("big_shortlived", args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    if args.remove_plaintext:
        CleanPasswords(
            password_age=args.password_age_days,
            commit=args.commit).run()

    if args.clean_changelog:
        CleanChangeLog(commit=args.commit).run()

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
