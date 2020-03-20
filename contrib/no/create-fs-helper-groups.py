#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
Create and update groups for students and lecturers in each individual subject.

This script creates the following groups:

- student-emne-<s>[v<v>]-<term>[_<n>]
- fagansvar-emne-<s>[v<v>]-<term>[_<n>]

where

 - <s> is the subject id (emnekode)
 - <v> is the subject version (versjonskode)
 - <term> is a shortname for the subject term (terminkode) (h, v, vi, so)
 - <n> is the term number (terminnr)

The groups are populated with "fronter" groups (see populate_fronter_groups.py)
"""
from __future__ import absolute_import, print_function, unicode_literals

import argparse
import collections
import datetime
import logging
import os
import random
import re
import six

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.transliterate import to_ascii
from Cerebrum.Utils import Factory
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.xmlutils.fsxml2object import EduDataGetter


logger = logging.getLogger(__name__)


class UndervisningsEnhet(collections.Mapping):
    """ Educational unit. """
    __slots__ = ('raw',)

    __require__ = ('emnenavn_bokmal',)

    __key__ = (
        'emnekode',
        'versjonskode',
        'terminkode',
        'arstall',
        'terminnr',
    )

    def __init__(self, data):
        missing = set(f for f in self.__key__ + self.__require__
                      if f not in data)
        if missing:
            raise ValueError('Missing required field(s) %r' % (missing,))
        self.raw = data

    def __len__(self):
        return len(self.raw)

    def __iter__(self):
        return iter(self.raw)

    def __getitem__(self, item):
        return self.raw[item]

    @property
    def key(self):
        return ':'.join(six.text_type(self[f]).lower()
                        for f in self.__key__)

    def __repr__(self):
        key = self.key
        name = type(self).__name__
        if key:
            return '<{} {}>'.format(name, key)
        else:
            return '<{}>'.format(name)

    def is_relevant(self, date):
        start, end = self.get_date_range()
        return date > start and date < end

    def get_date_range(self):
        """
        Make a reasonable guess for the time period where we are interested in
        maintaining a given edu object.

        - Any edu object that has not yet met its start date will not be
            created
        - Any edu object that has passed its end date will no longer be
            maintained.

        An unmaintained group will eventually reach its expire_date and be
        removed.  Ideally, FS should be able to provide us with a duration for
        a given subject.
        """
        term = self['terminkode']
        year = int(self['arstall'])
        start = datetime.date(year, 1, 1)
        end = datetime.date(year, 12, 31)

        if term == 'VÅR':
            end = datetime.date(year, 6, 30)
        elif term == 'HØST':
            start = datetime.date(year, 7, 1)

        # TODO: How about the other terms? SOMMER/VINTER -- should we have any
        # sort of info on that?
        return start, end

    @property
    def term_key(self):
        term = self['terminkode']
        if term == 'VÅR':
            return 'var'
        elif term == 'HØST':
            return 'host'
        else:
            return to_ascii(term.lower())

    @property
    def description(self):
        return '{}: {} ({} {})'.format(
            self['emnekode'], self['emnenavn_bokmal'],
            self['terminkode'].lower(), self['arstall'])


def get_edu_units(filename, date=None):
    """
    undervisningenheter.xml

      <enhet
        emnekode="TEOL2301"
        versjonskode="1"
        terminkode="HØST"
        arstall="2020"
        terminnr="1"
        emnenavn_bokmal="Tekster fra Deuteronomium"
        emnenavnfork="Tekster fra Deuteron"
        ...>
    """
    logger.debug('reading edu units from %r', filename)
    getter = EduDataGetter(filename, logger.getChild('get_edu_units'))
    stats = collections.Counter({'ok': 0, 'skip': 0})
    seen = set()
    for entry in getter.iter_undenh():
        unit = UndervisningsEnhet(entry)
        if date and not unit.is_relevant(date):
            stats['skip'] += 1
            continue
        stats['ok'] += 1
        unit_id = unit.key
        if unit_id in seen:
            raise ValueError("Duplicate edu unit: <%s>" % unit_id)
        yield unit_id, unit
    logger.info("found %(ok)d units (skipped %(skip)d)", stats)


def create_group_ident(unit, use_version, use_termno):
    name = unit['emnekode'].lower()
    if use_version:
        name += 'v' + unit['versjonskode']
    name += '-' + unit.term_key
    if use_termno:
        name += '_' + unit['terminnr']
    return name


def build_group_names(units):
    """ Create group names for a collection of units. """
    seen = set()
    groups = {}
    multi_term = {}

    def add_multi(unit):
        ident = create_group_ident(unit, True, True)
        if ident in multi_term:
            existing_unit = multi_term[ident]
            raise ValueError('Group name collision: %r (%s, %s)' %
                             (ident, existing_unit, unit))
        multi_term[ident] = unit

    for unit_id, unit in units.items():
        ident = create_group_ident(unit, False, False)
        if ident in seen:
            if ident in groups:
                other_unit = groups.pop(ident)
                add_multi(other_unit)
            add_multi(unit)
        else:
            groups[ident] = unit
        seen.add(ident)
    groups.update(multi_term)
    return groups


def filter_groups(results, roles):
    """
    get candidate group member names for edu unit student group

    :param results:
        gr.search() results with fronter groups.

    :return:
        Returns results that matches the given roles.
    """
    for result in results:
        for role in roles:
            if any(result['name'].endswith(suffix)
                   for suffix in (':' + role, ':' + role + '-sek')):
                yield result
            elif any(role_part in result['name']
                     for role_part in (':' + role + ':',
                                       ':' + role + '-sek:')):
                yield result


def get_group_by_name(db, group_name):
    gr = Factory.get('Group')(db)
    gr.find_by_name(group_name)
    return gr


def get_account_by_name(db, account_name):
    ac = Factory.get('Account')(db)
    ac.find_by_name(account_name)
    return ac


class GroupUtil(object):

    # Expire N days after the unit is no longer "relevant"
    expire = datetime.timedelta(days=15)

    fs_prefix = '*:fs:kurs:*'

    student_roles = (
        'student',
    )

    # roles from populate_fronter_groups
    educator_roles = (
        "admin", "dlo", "fagansvar", "foreleser", "gjestefore",
        "gruppelære", "hovedlærer", "it-ansvarl", "lærer", "sensor",
        "studiekons", "tolk", "tilsyn"
    )

    def __init__(self, db):
        self._db = db

    @property
    def creator(self):
        """ Creator account for new groups. """
        try:
            self._creator
        except AttributeError:
            self._creator = get_account_by_name(
                self._db,
                cereconf.INITIAL_ACCOUNTNAME).entity_id
        return self._creator

    def sync_edu_group_students(self, name, unit):
        group_name = '-'.join(('student', 'emne', name))
        group_desc = 'Studenter ved ' + unit.description
        expire_date = unit.get_date_range()[1] + self.expire
        gr = self._assert_group(group_name, group_desc, expire_date)

        # Sync group members
        candidates_pattern = self.fs_prefix + ':' + unit.key + ':*'
        needs_members = set(
            r['group_id']
            for r in filter_groups(gr.search(name=candidates_pattern),
                                   self.student_roles))
        self._sync_members(gr, needs_members)
        logger.info('group: %s, members: %s', name, len(needs_members))

    def sync_edu_group_educators(self, name, unit):
        group_name = '-'.join(('fagansvar', 'emne', name))
        group_desc = 'Fagansvarlige for ' + unit.description
        expire_date = unit.get_date_range()[1] + self.expire
        gr = self._assert_group(group_name, group_desc, expire_date)

        # Sync group members
        candidates_pattern = self.fs_prefix + ':' + unit.key + ':*'
        needs_members = set(
            r['group_id']
            for r in filter_groups(gr.search(name=candidates_pattern),
                                   self.educator_roles))

        self._sync_members(gr, needs_members)
        logger.info('group: %s, members: %s', name, len(needs_members))

    def _sync_members(self, group, needs_members):
        current_members = set(
            r['member_id']
            for r in group.search_members(group_id=group.entity_id))
        to_remove = current_members - needs_members
        to_add = needs_members - current_members

        for member_id in to_remove:
            group.remove_member(member_id)
        for member_id in to_add:
            group.add_member(member_id)

        if to_add or to_remove:
            logger.info('group=%r, added=%d, removed=%d',
                        group.group_name, len(to_add), len(to_remove))

    def _assert_group(self, name, description, expire_date):
        try:
            gr = get_group_by_name(self._db, name)
            logger.debug('updating %r', name)
            self._update_group(gr, description)
        except NotFoundError:
            logger.info('creating %r', name)
            gr = self._create_group(name, description)

        if not gr.expire_date or gr.expire_date < expire_date:
            gr.expire_date = expire_date
            logger.info('group=%r, new expire_date=%r',
                        gr.group_name, gr.expire_date)
            gr.write_db()
        return gr

    def _update_group(self, group, description):
        # TODO: Create new type
        group.group_type = group.const.group_type_edu_meta
        group.visibility = group.const.group_visibility_all
        group.description = description
        group.write_db()

    def _create_group(self, name, description):
        # TODO: Create new type
        group = Factory.get('Group')(self._db)
        group_type = group.const.group_type_edu_meta
        group.populate(
            creator_id=self.creator,
            visibility=group.const.group_visibility_all,
            name=name,
            description=description,
            group_type=group_type,
        )
        group.write_db()
        return group


def sync_unit_groups(db, units):
    group_names = build_group_names(units)

    util = GroupUtil(db)

    for basename, unit in group_names.items():
        util.sync_edu_group_students(basename, unit)
        util.sync_edu_group_educators(basename, unit)


def sample(iterable, n=5, text='iterable'):
    print('%s of len=%d:' % (text, len(iterable)))
    for s in random.sample(iterable, min(n, len(iterable))):
        print(' -', s)


DEFAULT_LOG_PRESET = 'console'
DEFAULT_LOG_LEVEL = logging.DEBUG


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Sync student subject groups",
    )
    parser.add_argument(
        '--include',
        type=re.compile,
        action='append',
        help='only create groups for edu units that match the given regex',
    )
    parser.add_argument(
        'unit_file',
        help='a undervisningenheter.xml file',
    )

    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)
    parser.set_defaults(logger_level=DEFAULT_LOG_LEVEL)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf(DEFAULT_LOG_PRESET, args)

    logger.info('Start of script %s', parser.prog)
    logger.debug('args: %r', args)

    today = datetime.date.today()
    all_units = dict(get_edu_units(args.unit_file, date=today))

    if args.include:
        units = {}
        for k in all_units:
            if any(regex.match(k) for regex in args.include):
                units[k] = all_units[k]
    else:
        units = all_units

    db = Factory.get("Database")()
    db.cl_init(change_program=parser.prog)

    logger.info('Syncing groups for %d units', len(units))

    sync_unit_groups(db, units)

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        logger.info('Rolling back changes')
        db.rollback()

    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
