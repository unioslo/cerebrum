#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2019 University of Oslo, Norway
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
"""This module contains functionality for maintaining fs groups

It is the result of a refactoring of populate_fronter_groups.py and
fs_group_stats.py.
"""

from __future__ import unicode_literals
import re
import datetime
import collections
import logging

import cereconf

from Cerebrum.Utils import Factory, NotSet

logger = logging.getLogger(__name__)

TODAY = datetime.date.today()
EXPIRE_YEAR = 2016

org_regex = r'(?P<org>[^:]+):fs'

kurs = ':'.join((
    org_regex,
    r'(?P<type>kurs)',
    r'(?P<emne>[^:]+)',
))

kurs_unit = ':'.join((
    org_regex,
    r'(?P<type>kurs)',
    r'(?P<institusjon>\d+)',
    r'(?P<emne>[^:]+)',
    r'(?P<ver>\d+)',
    r'(?P<sem>[^:]+)',
    r'(?P<year>\d+)',
))

kurs_unit_id = ':'.join((
    org_regex,
    r'(?P<type>kurs)',
    r'(?P<institusjon>\d+)',
    r'(?P<emne>[^:]+)',
    r'(?P<ver>\d+)',
    r'(?P<sem>[^:]+)',
    r'(?P<year>\d+)',
    r'(?P<n>\d+)',
))

evu = ':'.join((org_regex, r'(?P<type>evu)', r'(?P<kurs>[^:]+)',))
evu_unit = ':'.join((evu, r'(?P<kurstid>[^:]+)',))

kull = ':'.join((org_regex, r'(?P<type>kull)', '(?P<prog>[^:]+)'))
kull_unit = ':'.join((kull, '(?P<termin>[^:]+)', r'(?P<year>\d+)'))

role = r'(?P<role>[^:]+)'
subrole = ':'.join((role, r'(?P<akt>[^:]+)'))

evu_year = re.compile(r'(?P<year>\d{4})')


def make_internal(*args):
    return re.compile('^internal:' + ':'.join(args) + '$')


def make_external(*args):
    return re.compile('^' + ':'.join(args) + '$')


def _date_or_none(d):
    if d is None:
        return None
    return d.pydate()


def get_groups(db):
    gr = Factory.get('Group')(db)
    # co = Factory.get('Constants')(db)
    for row in gr.search(name='%{}%'.format(cereconf.FS_GROUP_PREFIX)):
        yield {
            # 'id': int(row['group_id']),
            'name': row['name'],
            # 'visibility': co.GroupVisibility(row['visibility']),
            # 'description': row['description'],
            'expire_date': _date_or_none(row['expire_date']),
        }


def get_year(cat, match):
    try:
        if cat in ('evu-ue', 'evu-role', 'evu-role-sub'):
            year = int(evu_year.findall(match.group('kurstid'))[-1])
        else:
            year = int(match.group('year'))
    except IndexError:
        year = None
    except ValueError:
        year = None
        logger.error('Non-numeric year!')
    return year


class FsGroupCategorizer(object):
    def __init__(self, db):
        self.categories = (
            ('super', make_internal(org_regex, '{supergroup}')),
            ('auto', make_internal(org_regex, '{autogroup}')),
            ('ifi_auto_fg', make_internal(org_regex, '{ifi_auto_fg}')),
            # fs:kurs
            ('kurs', make_internal(kurs)),
            ('kurs-ue', make_internal(kurs_unit)),
            ('kurs-role', make_external(kurs_unit_id, role)),
            ('kurs-role-sub', make_external(kurs_unit_id, subrole)),
            # fs:evu
            ('evu', make_internal(evu)),
            ('evu-ue', make_internal(evu_unit)),
            ('evu-role', make_external(evu_unit, role)),
            ('evu-role-sub', make_external(evu_unit, subrole)),
            # fs:kull
            ('kull-ue', make_internal(kull)),
            ('kull-ua', make_internal(kull_unit)),
            ('kull-role', make_external(kull_unit, role)),
        )
        self.groups = get_groups(db)

    def get_category(self, group_name):
        for cat, regex in self.categories:
            match = regex.match(group_name)
            if match:
                return cat, match
        raise LookupError('No category for %r' % (group_name,))

    def categorize(self, expire_year=EXPIRE_YEAR):
        specific_stats = collections.defaultdict(
            lambda: collections.defaultdict(int)
        )
        general_stats = collections.defaultdict(int)
        new_expire_dates = {}

        for group in self.groups:
            try:
                cat, match = self.get_category(group['name'])
                specific_stats[cat]['count'] += 1
            except LookupError:
                logger.warning('No category for %s', group['name'])
                general_stats['errors'] += 1
                continue

            year = get_year(cat, match)

            if not group['expire_date']:
                if year:
                    if year <= expire_year:
                        new_expire_dates[match.string] = TODAY
                        specific_stats[cat]['should-expire-now'] += 1
                    else:
                        years_until_expiration = (
                                year + cereconf.FS_GROUP_LIFETIMES[
                            cat] + 1 -
                                TODAY.year)

                        if years_until_expiration <= 0:
                            new_expire_dates[match.string] = TODAY
                            specific_stats[cat]['should-expire-now'] += 1
                        else:
                            expire_date = TODAY + datetime.timedelta(
                                days=years_until_expiration * 365)
                            new_expire_dates[match.string] = expire_date
                            specific_stats[cat]['should-set-expire-date'] += 1
                elif cat in ('super', 'auto', 'ifi_auto_fg'):
                    specific_stats[cat]['should-do-nothing'] += 1
                else:
                    expire_date = TODAY + datetime.timedelta(
                        days=cereconf.FS_GROUP_LIFETIMES[cat] * 365)
                    new_expire_dates[match.string] = expire_date
                    specific_stats[cat]['should-set-expire-date'] += 1
            else:
                specific_stats[cat]['should-do-nothing'] += 1

        for k, v in specific_stats.items():
            for stat, value in v.items():
                general_stats[stat] += value
            specific_stats[k] = dict(v)
        return dict(general_stats), dict(specific_stats), new_expire_dates
