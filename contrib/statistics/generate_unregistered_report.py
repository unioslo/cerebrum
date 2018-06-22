#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009-2018 University of Oslo, Norway
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
""" Generate a plaintext report on persons not in authotitative systems.

The report will include persons that are not registered in an authoritative
system (e.g. SAP or FS), but still has an active account.  An active account is
simply an account that is not expired, regardless of home is set.

The script is sorting the persons by OUs. It can work at fakultet, institutt
and avdeling level. Those that does not even have a manual affiliation are
sorted as 'unregistered'.

Example of use:

    generate_unregistered_report.py -f /tmp/unregistered_report.txt \
            --ignore-students --ignore-sko 78,79
"""

import argparse
import logging
import sys
from collections import defaultdict

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.utils.argutils import codec_type

logger = logging.getLogger(__name__)


def make_name_cache(db):
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)

    @memoize
    def get_name(person_id):
        res = pe.search_person_names(
            person_id=person_id,
            source_system=co.system_cached,
            name_variant=co.name_full)
        return (res or [{'name': None}])[0]['name']
    return get_name


def make_ou_name_cache(db):
    ou = Factory.get('OU')(db)
    co = Factory.get('Constants')(db)

    names = dict(
        (row['entity_id'], row['name'])
        for row in ou.search_name_with_language(
            name_variant=co.ou_name,
            name_language=co.language_nb))
    logger.debug('make_ou_name_cache: %d ou names', len(names))

    def get_ou_name(ou_id):
        return names.get(ou_id)
    return get_ou_name


def make_ou_filter(db, ou_level, filters=None):
    ou = Factory.get('OU')(db)
    filters = set(filters or ())

    # Get a list of all OUs we want to search through on the form
    # ((ou_id, stedkode), (ou_id, stedkode), ...)
    all_ous = set((row['ou_id'], "%02d%02d%02d" % (row['fakultet'],
                                                   row['institutt'],
                                                   row['avdeling']))
                  for row in ou.get_stedkoder(
                          institutt=0 if ou_level >= 1 else None,
                          avdeling=0 if ou_level >= 2 else None))
    logger.debug('make_ou_filter: %d ous at level %d', len(all_ous), ou_level)

    # Create a dict of the ous and skos, but without those specified in
    # ignore_sko (if any):
    ous = dict((ou_id, sko) for ou_id, sko in all_ous
               if not any(sko.startswith(f) for f in filters))
    logger.debug('make_ou_filter: %d not matching filters %r',
                 len(ous), filters)
    return ous


def make_account_type_cache(db):
    ac = Factory.get('Account')(db)

    cache = defaultdict(set)
    for row in ac.list_accounts_by_type():
        cache[row['account_id']].add(row['affiliation'])
    logger.debug("make_account_type_cache: %d accounts with account_types",
                 len(cache))

    def get_account_types(account_id):
        """ set with account_type affiliations. """
        return cache[account_id]
    return get_account_types


def make_quarantine_check(db):
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)

    cache = set(
        row['entity_id'] for row
        in ac.list_entity_quarantines(
            entity_types=co.entity_account,
            only_active=True))
    logger.debug("make_quarantine_check: %d accounts with quarantines",
                 len(cache))

    def is_quarantined(account_id):
        return account_id in cache
    return is_quarantined


def make_homedir_check(db):
    ac = Factory.get('Account')(db)

    cache = set(
        row['account_id'] for row in ac.list_account_home())
    logger.debug("make_homedir_check: %d accounts with homedir",
                 len(cache))

    def has_home(account_id):
        return account_id in cache
    return has_home


def make_account_caches(db):
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)

    cache = dict()
    pe2acc = defaultdict(set)

    for row in ac.search(owner_type=co.entity_person):
        data = dict(row)
        cache[row['account_id']] = data
        pe2acc[row['owner_id']].add(row['account_id'])
    logger.debug("make_account_caches: %d persons with %d accounts",
                 len(pe2acc), len(cache))

    def get_account(account_id):
        return cache[account_id]

    def list_account_ids(person_id):
        return pe2acc[person_id]

    return get_account, list_account_ids


def make_affiliation_cache(db):
    pe = Factory.get(b'Person')(db)
    co = Factory.get('Constants')(db)

    cache = defaultdict(set)
    for row in pe.list_affiliations():
        data = tuple((
            co.AuthoritativeSystem(row['source_system']),
            row['ou_id'],
        ))
        cache[row['person_id']].add(data)
    logger.debug('make_affiliation_cache: %d persons with affs', len(cache))

    @memoize
    def get_affiliations(person_id):
        return tuple(cache[person_id])
    return get_affiliations


def get_persons(
        db,
        auth_sources,
        ou_level=0,
        ignore_sko=None,
        ignore_students=False,
        ignore_quarantined=False,
        stats=None):
    """ Get persons and affs to report. """
    logger.info("Generating report on persons not registered in %r",
                auth_sources)
    ignore_sko = tuple(ignore_sko or [])
    stats = {} if stats is None else stats

    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)

    all_persons = pe.list_persons()
    logger.debug("%d persons found", len(all_persons))

    stats.update({
        'num-has-acc': 0,
        'num-manual-aff': 0,
        'num-no-aff': 0,
        'num-persons': len(all_persons),
    })

    if ignore_students:
        get_account_types = make_account_type_cache(db)

    if ignore_quarantined:
        has_quarantine = make_quarantine_check(db)

    get_person_name = make_name_cache(db)
    has_homedir = make_homedir_check(db)
    get_account, list_account_ids = make_account_caches(db)
    get_person_affiliations = make_affiliation_cache(db)
    sko_map = make_ou_filter(db, ou_level, ignore_sko)
    get_ou_name = make_ou_name_cache(db)

    def make_item(person_id, accounts, sko, ou_name):

        def _u(db_value):
            if isinstance(db_value, bytes):
                return db_value.decode(db.encoding)
            return db_value

        return {
            'person_id': person_id,
            'person_name': _u(get_person_name(person_id)),
            'accounts': [
                dict(account_name=_u(get_account(account_id)['name']),
                     has_homedir=bool(has_homedir(account_id)))
                for account_id in accounts],
            'sko': _u(sko),
            'ou_name': _u(ou_name),
        }

    for cnt, row in enumerate(all_persons):
        person_id = row['person_id']

        if cnt and cnt % 10000 == 0:
            logger.debug('... processed %d persons (reported %d)', cnt,
                         stats['num-no-aff'] + stats['num-manual-aff'])

        accs = list_account_ids(person_id)

        if len(accs) == 0:
            continue

        stats['num-has-acc'] += 1

        # Check for authoritative systems, skipping person if found
        affs = get_person_affiliations(person_id)
        if any(aff[0] in auth_sources for aff in affs):
            continue

        # Students should only have _one_ account, so if a student
        # has several accounts he/she should still be listed
        if (ignore_students and len(accs) == 1 and
                co.affiliation_student in get_account_types(accs[0])):
            continue

        if ignore_quarantined and all(has_quarantine(a) for a in accs):
            continue

        if len(affs) == 0:
            yield make_item(person_id, accs, u'Unregistered persons',
                            u'no affiliations')
            stats['num-no-aff'] += 1
            continue

        stats['num-manual-aff'] += 1

        for ou_id in (aff[1] for aff in affs):
            if ou_id not in sko_map:
                continue
            yield make_item(person_id, accs, sko_map.get(ou_id),
                            get_ou_name(ou_id))


def write_header(stream, stats, filters):
    filters = filters or []
    stats = defaultdict(int, stats)

    stream.write("===== Summary =====\n")
    stream.write("Persons found:                %(num-persons)8d\n" % stats)
    stream.write("Persons with accounts:        %(num-has-acc)8d\n" % stats)
    stream.write(" - With manual affiliations:  %(num-manual-aff)8d\n" % stats)
    stream.write(" - Without any affiliation:   %(num-no-aff)8d\n" % stats)
    stream.write("\n")

    if filters:
        for f in filters:
            stream.write('Filter: %s\n' % (f, ))
        stream.write("\n")


def write_short_report(stream, results):
    unregistered = results or {}

    stream.write("===== Manual registrations =====\n")
    for sko in sorted(unregistered):
        num_affs = sum(len(affs) for persons in unregistered[sko].values() for
                       affs in persons)
        if len(unregistered[sko]) > 0:
            stream.write(" %8d affiliations on %s\n" % (num_affs, sko))


def write_report(stream, results):
    unregistered = results or {}

    homedir_suffix = defaultdict(str, {False: ' (NOHOME)'})

    stream.write("===== Manual registrations =====\n")
    for sko in sorted(unregistered):
        stream.write("\n---- %s ----\n" % (sko, ))
        for pid in sorted(unregistered[sko]):
            for aff_data in unregistered[sko][pid]:
                accounts = []
                for account in aff_data['accounts']:
                    accounts.append(
                        account['account_name'] +
                        homedir_suffix[account['has_homedir']])

                stream.write("%d - %s - accounts: %s\n" %
                             (aff_data['person_id'],
                              aff_data['person_name'],
                              ', '.join(accounts)))


def aggregate(iterable, *keys):
    if len(keys) < 1:
        raise TypeError("aggregate takes at least two arguments (1 given)")

    root = dict()
    group_defaults = tuple(zip(keys, [dict] * (len(keys) - 1) + [list]))

    for item in iterable:
        group = root
        for key, default in group_defaults:
            group_name = key % item
            group = group.setdefault(group_name, default())
        group.append(item)
    return root


DEFAULT_ENCODING = 'utf-8'


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Generate a report of persons not in a source system")

    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        type=argparse.FileType('w'),
        default='-',
        help='Output file for report, defaults to stdout')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="Output file encoding, defaults to %(default)s")

    parser.add_argument(
        '--summary',
        dest='write_report',
        action='store_const',
        const=write_short_report,
        default=write_report,
        help='Only print a summary with number of results')

    level_arg = parser.add_mutually_exclusive_group()
    level_arg.add_argument(
        '--faculties',
        dest='ou_level',
        action='store_const',
        const=2,
        help='Only the faculty level of OUs are being searched')
    level_arg.add_argument(
        '--institutes',
        dest='ou_level',
        action='store_const',
        const=1,
        help='Only the faculty and institute level of OUs are being searched')
    parser.set_defaults(ou_level=0)

    parser.add_argument(
        '--ignore-students',
        action='store_true',
        default=False,
        help="Since a lot of students are unregistered before they're"
             " disabled, this option can be used to ignore these persons")
    parser.add_argument(
        '--ignore-quarantined',
        action='store_true',
        default=False,
        help='')
    parser.add_argument(
        '--ignore-sko',
        type=lambda x: [sko.strip() for sko in x.split(',')],
        default=[],
        help="If some OUs are to be ignored. Can be a commaseparated"
             " list of stedkoder. Can add sub-OUs by only adding the first"
             " digits in the sko. E.g. '33' gives all OUs at USIT.")

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    # List of the authoritative systems
    auth_sources = filter(
        None,
        (co.human2constant(x, co.AuthoritativeSystem)
         for x in getattr(cereconf, "BOFHD_AUTH_SYSTEMS", ())))

    stats = dict()
    results = get_persons(
        db,
        auth_sources,
        ou_level=args.ou_level,
        ignore_students=args.ignore_students,
        ignore_quarantined=args.ignore_quarantined,
        ignore_sko=args.ignore_sko,
        stats=stats)

    results = aggregate(results, '%(sko)s (%(ou_name)s)', '%(person_id)d')

    filters = []
    if args.ignore_students:
        filters.append("Ignoring students")
    if args.ignore_quarantined:
        filters.append("Ignoring quarantined")
    if args.ignore_sko:
        filters.append("Ignoring sko(prefix): %r" % (args.ignore_sko, ))

    output = args.codec.streamwriter(args.output)
    write_header(output, stats, filters)
    args.write_report(output, results)

    args.output.flush()
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
