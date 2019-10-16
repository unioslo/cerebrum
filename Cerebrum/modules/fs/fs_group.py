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

from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)

org_regex = r'(?:internal:)?(?P<org>[^:]+):fs'

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
    r'(?P<ver>[^:]+)',
    r'(?P<sem>[^:]+)',
    r'(?P<year>\d{4})',
))

kurs_unit_id = ':'.join((
    org_regex,
    r'(?P<type>kurs)',
    r'(?P<institusjon>\d+)',
    r'(?P<emne>[^:]+)',
    r'(?P<ver>[^:]+)',
    r'(?P<sem>[^:]+)',
    r'(?P<year>\d{4})',
    r'(?P<n>\d+)',
))

undenh = ':'.join((
    org_regex,
    r'(?P<institusjon>\d+)',
    r'(?P<type>undenh)',
    r'(?P<year>\d{4})',
    r'(?P<sem>[^:]+)',
    r'(?P<emne>[^:]+)',
    r'(?P<ver>[^:]+)',
    r'(?P<n>[^:]+)',
))

sp = ':'.join((
    org_regex,
    r'(?P<institusjon>\d+)',
    r'(?P<type>studieprogram)',
    r'(?P<prog>[^:]+)',

))

sp_kull_type = ':'.join((
    sp,
    r'(?P<kull>(studiekull|rolle-kull){1})',
))

sp_rolle_type = ':'.join((
    sp,
    r'(?P<rolle>(rolle-program|rolle){1})',
))

sp_kull = ':'.join((
    sp_kull_type,
    r'(?P<year>\d{4})',
    r'(?P<sem>[^:]+)',
))

evu = ':'.join((org_regex, r'(?P<type>evu)', r'(?P<kurs>[^:]+)',))
evu_unit = ':'.join((evu, r'(?P<kurstid>[^:]+)',))

kull = ':'.join((org_regex, r'(?P<type>kull)', '(?P<prog>[^:]+)'))
kull_unit = ':'.join((kull, '(?P<termin>[^:]+)', r'(?P<year>\d+)'))

role = r'(?P<role>[^:]+)'
subrole = ':'.join((role, r'(?P<akt>[^:]+)'))

evu_year = re.compile(r'(?P<year>\d{4})')


def make_regex(*args):
    return re.compile('^' + ':'.join(args) + '$')


def _date_or_none(d):
    if d is None:
        return None
    return d.pydate()


def get_year(cat, match):
    try:
        if cat in ('evu-ue', 'evu-role', 'evu-role-sub'):
            year = max(int(year) for year in evu_year.findall(
                match.group('kurstid')
            ))
        else:
            year = int(match.group('year'))
    except IndexError:
        year = None
    except ValueError:
        year = None
        logger.error('Non-numeric year!')
    return year


class FsGroupCategorizer(object):
    def __init__(self, db, fs_group_prefix=None):
        self.db = db
        self.fs_group_prefix = fs_group_prefix or cereconf.FS_GROUP_PREFIX
        if self.fs_group_prefix is None:
            raise Exception('No prefix given')
        # The elements of categories are tuples of category, regex and lifetime
        self.categories = (
            ('super', make_regex(org_regex, '{supergroup}'), None),
            ('auto', make_regex(org_regex, '{autogroup}'), None),
            ('ifi_auto_fg', make_regex(org_regex, '{ifi_auto_fg}'), None),
            # fs:kurs
            ('kurs', make_regex(kurs), 3),
            ('kurs-ue', make_regex(kurs_unit), 2),
            ('kurs-role', make_regex(kurs_unit_id, role), 2),
            ('kurs-role-sub', make_regex(kurs_unit_id, subrole), 2),
            # fs:evu
            ('evu', make_regex(evu), 3),
            ('evu-ue', make_regex(evu_unit), 2),
            ('evu-role', make_regex(evu_unit, role), 2),
            ('evu-role-sub', make_regex(evu_unit, subrole), 2),
            # fs:kull
            ('kull-ue', make_regex(kull), 6),
            ('kull-ua', make_regex(kull_unit), 6),
            ('kull-role', make_regex(kull_unit, role), 6),

            # Non uio types:
            # fs:<institusjon>:undenh
            ('undenh', make_regex(undenh), 3),
            ('undenh-role', make_regex(undenh, role), 2),
            ('undenh-role-sub', make_regex(undenh, subrole),
             2),
            # fs:<institusjon>:studieprogram
            ('sp', make_regex(sp), 3),

            ('sp-kull-type', make_regex(sp_kull_type), 6),
            ('sp-kull-role', make_regex(sp_kull, role), 6),
            ('sp-kull-role-sub', make_regex(sp_kull, subrole), 6),

            ('sp-rolle-type', make_regex(sp_rolle_type), 3),
            ('sp-rolle', make_regex(sp_rolle_type, role), 3),
        )

    def get_groups(self):
        gr = Factory.get('Group')(self.db)
        # co = Factory.get('Constants')(db)
        for row in gr.search(name='%{}%'.format(self.fs_group_prefix)):
            yield {
                'id': int(row['group_id']),
                'name': row['name'],
                # 'visibility': co.GroupVisibility(row['visibility']),
                # 'description': row['description'],
                'expire_date': _date_or_none(row['expire_date']),
            }

    def get_group_category(self, group_name):
        category = match = lifetime = None
        for cat, regex, l in self.categories:
            m = regex.match(group_name)
            if m:
                if not category:
                    category = cat
                    match = m
                    lifetime = l
                else:
                    raise LookupError('Multiple categories for %s', group_name)

        if category:
            return category, match, lifetime
        raise LookupError('No category for %s', group_name)

    @staticmethod
    def get_expire_date(lifetime, year, group_name):
        if not lifetime:
            return None
        today = datetime.date.today()
        if not year:
            return today + datetime.timedelta(days=lifetime * 365)
        if not today.year + 5 > year > 1990:
            logger.warning('Year %s not in allowed range, %s',
                           year,
                           group_name)
            return today + datetime.timedelta(days=lifetime * 365)

        years_until_expiration = year + lifetime + 1 - today.year
        if years_until_expiration <= 0:
            return (today +
                    datetime.timedelta(days=cereconf.FS_GROUP_GRACE_PERIOD))
        return today + datetime.timedelta(days=years_until_expiration * 365)

    def categorize_groups(self):
        specific_stats = collections.defaultdict(
            lambda: collections.defaultdict(int)
        )
        general_stats = collections.defaultdict(int)
        new_expire_dates = {}

        for group in self.get_groups():
            try:
                cat, match, lifetime = self.get_group_category(group['name'])
            except LookupError as e:
                logger.warning(e)
                general_stats['errors'] += 1
                continue

            specific_stats[cat]['count'] += 1

            year = get_year(cat, match)

            if group['expire_date']:
                specific_stats[cat]['should-do-nothing'] += 1
            else:
                expire_date = self.get_expire_date(lifetime,
                                                   year,
                                                   group['name'])
                if expire_date:
                    new_expire_dates[group['id']] = expire_date
                    specific_stats[cat][
                        'should-expire-{}'.format(expire_date.year)] += 1
                else:
                    specific_stats[cat]['should-do-nothing'] += 1

        for key, stats in specific_stats.items():
            for stat, value in stats.items():
                general_stats[stat] += value
            specific_stats[key] = dict(stats)
        return dict(general_stats), dict(specific_stats), new_expire_dates

    def set_expire_dates(self, new_expire_dates):
        gr = Factory.get('Group')(self.db)
        for group_id, expire_date in new_expire_dates.items():
            gr.clear()
            gr.find(group_id)
            gr.expire_date = expire_date
            gr.write_db()
            logger.debug('Set expire_date %s for group %s with name %s',
                         expire_date,
                         group_id,
                         gr.group_name)
