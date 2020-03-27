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
import contextlib
import datetime
import logging
import re
import six
import time

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.transliterate import to_ascii
from Cerebrum.Utils import Factory
from Cerebrum.modules.xmlutils.fsxml2object import EduDataGetter


logger = logging.getLogger(__name__)


@contextlib.contextmanager
def timer(msg, level=logging.DEBUG):
    logger.log(level, 'start %s ...', msg)
    start = time.time()
    try:
        yield
    except Exception:
        logger.log(level, 'failed %s after %.1f s', msg, time.time() - start)
        raise
    else:
        logger.log(level, 'done %s after %.1f s', msg, time.time() - start)


class FsObject(collections.Mapping):

    __slots__ = ('raw',)
    __key__ = ()

    def __init__(self, data):
        missing = set(f for f in self.__key__ if f not in data)
        if missing:
            raise ValueError('Missing required field(s): %r' % (missing,))
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
        key = repr(self.key)
        name = type(self).__name__
        if key:
            return '<{} {}>'.format(name, key)
        else:
            return '<{}>'.format(name)


class FsObjectDateMixin(FsObject):
    """
    Year (arstall) and term (terminkode, terminno) related methods.
    """

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


class UndervisningsEnhet(FsObjectDateMixin):
    """ Educational unit. """

    __slots__ = ('activities',)

    __key__ = (
        'emnekode',
        'versjonskode',
        'terminkode',
        'arstall',
        'terminnr',
    )

    def __init__(self, data):
        super(UndervisningsEnhet, self).__init__(data)
        self.activities = {}

    @property
    def description(self):
        return '{}: {} ({} {})'.format(
            self['emnekode'], self.get('emnenavn_bokmal', ''),
            self['terminkode'].lower(), self['arstall'])


class UndervisningsAktivitet(UndervisningsEnhet):

    __key__ = (
        'emnekode',
        'versjonskode',
        'terminkode',
        'arstall',
        'terminnr',
        'aktivitetkode',
    )

    @property
    def unit(self):
        return UndervisningsEnhet(self.raw)

    @property
    def activity_id(self):
        return self['aktivitetkode'].lower()

    @property
    def description(self):
        return '{} ({}): {} ({} {})'.format(
            self['emnekode'], self['aktivitetkode'],
            self.get('aktivitetsnavn', ''),
            self['terminkode'].lower(), self['arstall'])


def read_edu_units(filename, date=None):
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
    getter = EduDataGetter(filename, logger.getChild('read_edu_units'))
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
        seen.add(unit_id)
    logger.debug("found %(ok)d units (skipped %(skip)d)", stats)


def read_edu_activities(filename, date=None):
    """
    undervisningsaktiviteter.xml

      <aktivitet
        emnekode="PSYC4401"
        versjonskode="1"
        terminkode="VÅR"
        arstall="2020"
        terminnr="1"
        aktivitetkode="2-1-9"
        undpartilopenr="9"
        disiplinkode="PRA"
        undformkode="PRAKSIS"
        aktivitetsnavn="Bydel Søndre Nordstrand Rask Psykisk Helsehjelp"
        ...>
    """
    logger.debug('reading edu activities from %r', filename)
    getter = EduDataGetter(filename, logger.getChild('read_edu_activities'))
    stats = collections.Counter({'ok': 0, 'skip': 0})
    seen = set()
    for entry in getter.iter_undakt():
        act = UndervisningsAktivitet(entry)
        if date and not act.is_relevant(date):
            stats['skip'] += 1
            continue
        stats['ok'] += 1
        act_id = act.key
        if act_id in seen:
            raise ValueError("Duplicate edu activity: <%s>" % (act_id, ))
        yield act_id, act
        seen.add(act_id)
    logger.debug("found %(ok)d activities (skipped %(skip)d)", stats)


def create_group_ident(unit, use_version, use_termno):
    name = unit['emnekode'].lower()
    if use_version:
        name += 'v' + unit['versjonskode']
    name += '-' + unit.term_key
    if use_termno:
        name += '_' + unit['terminnr']
    return name


def build_group_idents(units):
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


def filter_groups(results, roles, sub=True):
    """
    get candidate group member names for edu unit student group

    :param results:
        gr.search() results with fronter groups.

    :param sub:
        Include *sub groups* (edu activities) in the output
        (i.e. <edu-unit>:<role>:<edu-activity>, as opposed to only
        <edu-unit>:<role>).

    :return:
        Returns results that matches the given roles.
    """
    for result in results:
        for role in roles:
            if any(result['name'].endswith(suffix)
                   for suffix in (':' + role, ':' + role + '-sek')):
                yield result
            elif sub and any(role_part in result['name']
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


def _pydate(obj):
    if obj is None:
        return obj
    # otherwise assume mx.DateTime
    return obj.pydate()


def get_groups(db):
    gr = Factory.get('Group')(db)
    g_vis = {int(c): c
             for c in gr.const.fetch_constants(gr.const.GroupVisibility)}
    g_typ = {int(c): c
             for c in gr.const.fetch_constants(gr.const.GroupType)}
    for row in gr.search():
        yield {
            'id': row['group_id'],
            'name': row['name'],
            'group_type': g_typ[row['group_type']],
            'visibility': g_vis[row['visibility']],
            'expire_date': _pydate(row['expire_date']),
            'description': row['description'],
        }


def get_memberships(db):
    """ Fetch group-in-group memberships. """
    # Note: Since we only ever consider groups-in-groups, we end up ignoring
    #       all other members. I.e. if a person or account is added to a edu
    #       group, it will remain there until manually removed.
    gr = Factory.get('Group')(db)
    for row in gr.search_members(member_type=gr.const.entity_group):
        yield row['group_id'], row['member_id']


class GroupCache(object):

    def __init__(self, db):
        self._db = db
        self.groups = {}
        self.names = {}
        self.members = collections.defaultdict(set)

        const = Factory.get('Constants')(db)
        self.group_type = const.group_type_edu_meta
        self.group_visibility = const.group_visibility_all

    def cache(self):
        """ Cache (relevant) groups and group memberhips. """
        with timer('caching groups'):
            for group in get_groups(self._db):
                self.groups[group['id']] = group
                self.names[group['name']] = group['id']
            logger.info('cached %d groups', len(self.groups))

        with timer('caching group memberships'):
            for group_id, member_id in get_memberships(self._db):
                self.members[group_id].add(member_id)
            logger.info('cached %d memberships in %d groups',
                        sum(len(m) for m in self.members.values()),
                        len(self.members))

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

    def create_group(self, name, description):
        """
        Create a new group
        """
        group = Factory.get('Group')(self._db)
        g_type = self.group_type
        g_vis = self.group_visibility
        group.populate(
            creator_id=self.creator,
            visibility=g_vis,
            name=name,
            description=description,
            group_type=g_type,
        )
        group.write_db()
        self.groups[group.entity_id] = {
            'id': group.entity_id,
            'name': group.group_name,
            'group_type': g_type,
            'visibility': g_vis,
            'expire_date': None,
            'description': group.description,
        }
        self.names[group.group_name] = group.entity_id
        self.members[group.entity_id] = set()
        logger.info('group %r created', group.group_name)
        return group

    def update_group(self, group, description):
        wants = {
            'group_type': self.group_type,
            'visibility': self.group_visibility,
            'description': description,
        }

        update = False
        for k, v in wants.items():
            if getattr(group, k) != v:
                setattr(group, k, v)
                update = True

        if update:
            self.groups[group.entity_id].update(wants)
            group.write_db()
            logger.info('group %r updated', group.group_name)

    def sync_members(self, group, needs_members):
        current_members = self.members.get(group.entity_id, set())
        to_remove = current_members - needs_members
        to_add = needs_members - current_members

        if to_add or to_remove:
            for member_id in to_remove:
                group.remove_member(member_id)
            for member_id in to_add:
                group.add_member(member_id)
            self.members[group.entity_id] = needs_members
            logger.info('group=%r, added=%d, removed=%d',
                        group.group_name, len(to_add), len(to_remove))

    def update_expire_date(self, group, expire_date):
        if not group.expire_date or group.expire_date < expire_date:
            group.expire_date = expire_date
            group.write_db()
            self.groups[group.entity_id]['expire_date'] = expire_date
            logger.info('group=%r, new expire_date=%r',
                        group.group_name, group.expire_date)

    def assert_group(self, name, description, expire_date):
        if name in self.names:
            gr = get_group_by_name(self._db, name)
            self.update_group(gr, description)
        else:
            gr = self.create_group(name, description)

        self.update_expire_date(gr, expire_date)
        return gr


class EduGroupBuilder(object):

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

    # TODO: This would be a lot more effective if we tried a bit harder to use
    #       the cache before actually looking up the group.
    #       If everything is already in sync, we shouldn't have to ever have to
    #       get_group_by_name

    def __init__(self, db, nested=False):
        self._db = db
        self._gr = Factory.get('Group')(db)
        self.cache = GroupCache(db)
        self.cache.cache()
        self.nested = nested

    def get_expire_date(self, fsobj):
        return fsobj.get_date_range()[1] + self.expire

    def get_unit_members(self, unit, roles):
        name_pattern = self.fs_prefix + ':' + unit.key + ':*'
        return set(
            r['group_id']
            for r in filter_groups(self._gr.search(name=name_pattern),
                                   roles, sub=not self.nested))

    def get_act_members(self, activity, roles):
        unit_key = activity.unit.key
        act_id = activity.activity_id
        name_pattern = self.fs_prefix + ':' + unit_key + ':*:' + act_id
        return set(
            r['group_id']
            for r in filter_groups(self._gr.search(name=name_pattern),
                                   roles, sub=True))

    def _sync_activity_group(self, activity, roles, group_name, group_desc):
        expire_date = self.get_expire_date(activity)
        gr = self.cache.assert_group(group_name, group_desc, expire_date)
        needs_members = self.get_act_members(activity, roles)
        self.cache.sync_members(gr, needs_members)
        return gr

    def sync_edu_group_student_act(self, name, activity):
        group_name = '-'.join(('student', 'emne', name, activity.activity_id))
        group_desc = 'Deltakere i ' + activity.description
        gr = self._sync_activity_group(activity, self.student_roles,
                                       group_name, group_desc)
        return gr.entity_id

    def sync_edu_group_educators_act(self, name, activity):
        group_name = '-'.join(('fagansvar', 'emne', name,
                               activity.activity_id))
        group_desc = 'Fagansvarlige i ' + activity.description
        gr = self._sync_activity_group(activity, self.educator_roles,
                                       group_name, group_desc)
        return gr.entity_id

    def sync_edu_group_students(self, name, unit):
        group_name = '-'.join(('student', 'emne', name))
        group_desc = 'Studenter ved ' + unit.description
        expire_date = self.get_expire_date(unit)
        gr = self.cache.assert_group(group_name, group_desc, expire_date)

        needs_members = self.get_unit_members(unit, self.student_roles)
        if self.nested:
            for act_id, act in unit.activities.items():
                needs_members.add(
                    self.sync_edu_group_student_act(name, act))

        self.cache.sync_members(gr, needs_members)
        return gr.entity_id

    def sync_edu_group_educators(self, name, unit):
        group_name = '-'.join(('fagansvar', 'emne', name))
        group_desc = 'Fagansvarlige for ' + unit.description
        expire_date = self.get_expire_date(unit)
        gr = self.cache.assert_group(group_name, group_desc, expire_date)

        needs_members = self.get_unit_members(unit, self.educator_roles)
        if self.nested:
            for act_id, act in unit.activities.items():
                needs_members.add(
                    self.sync_edu_group_educators_act(name, act))

        self.cache.sync_members(gr, needs_members)
        return gr.entity_id


def get_units(unit_file, activity_file=None, filter_units=None, date=None):
    """ Fetch all edu units required to build groups. """
    date = date or datetime.date.today()
    filter_units = filter_units or ()

    all_units = dict(read_edu_units(unit_file, date=date))

    if filter_units:
        units = {}
        for k in all_units:
            if any(regex.match(k) for regex in filter_units):
                units[k] = all_units[k]
    else:
        units = all_units

    if activity_file:
        all_acts = dict(read_edu_activities(activity_file, date=date))
    else:
        all_acts = {}

    # update edu units with edu activities
    for act in all_acts.values():
        if act.unit.key not in units:
            continue
        units[act.unit.key].activities[act.activity_id] = act

    n_activities = sum(len(u.activities) for u in units.values())
    logger.info('Found %d units and %d activities',
                len(units), n_activities)

    return units


DEFAULT_LOG_PRESET = 'cronjob'
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
        '--activity-groups',
        dest='act_file',
        help='build activity sub-groups from a '
             'undervisningsaktiviteter.xml file',
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

    with timer('reading FS data', logging.INFO):
        units = get_units(args.unit_file,
                          activity_file=args.act_file,
                          filter_units=args.include)
        nested = bool(args.act_file)
        edu_groups = build_group_idents(units)

    with timer('preparing Cerebrum data', logging.INFO):
        db = Factory.get("Database")()
        db.cl_init(change_program=parser.prog)
        builder = EduGroupBuilder(db, nested)

    total = len(edu_groups)
    with timer('updating groups', logging.INFO):
        for n, ident in enumerate(sorted(edu_groups), 1):
            unit = edu_groups[ident]
            logger.debug('processing groups for %s %r', ident, unit)
            builder.sync_edu_group_students(ident, unit)
            builder.sync_edu_group_educators(ident, unit)
            if n % 100 == 0:
                logger.debug('processed %d/%d units', n, total)

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        logger.info('Rolling back changes')
        db.rollback()

    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
