#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway
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
"""Delete old data from users."""

import collections
import functools


def clean_names(logger, person, constants, source_system):
    """Remove first, last and full name from person."""
    person.affect_names(source_system,
                        constants.name_first,
                        constants.name_last,
                        constants.name_full)
    try:
        person.write_db()
    except ValueError as e:
        if 'No cacheable name for' in str(e):
            return
        else:
            logger.warn(e)


def clean_addresses(person, source_system):
    """Remove all adresses from a source system for the given person."""
    for address in person.get_entity_address(source_system):
        person.delete_entity_address(source_system, address['address_type'])


def clean_contact_info(person, source_system):
    """Remove contact info from a given source system for the given person."""
    for contact in person.get_contact_info(source_system):
        person.delete_contact_info(source_system, contact['contact_type'])


def clean_titles(person, specs):
    """Remove titles from the given person according to the supplied spec."""
    for spec in specs:
        person.delete_name_with_language(*spec)


def update_person(logger, person, constants, source_system):
    """Remove general information from persons."""
    clean_names(logger, person, constants, source_system)
    clean_addresses(person, source_system)
    clean_contact_info(person, source_system)
    clean_titles(person, [(constants.work_title, constants.language_en),
                          (constants.work_title, constants.language_nb),
                          (constants.personal_title, constants.language_en),
                          (constants.personal_title, constants.language_nb)])


def perform(cleaner, committer, logger, person, constants, selection):
    """Call cleaner func for all persons in selection."""
    def _do_update(person_id, logger, person, constants, cleaner):
        person.clear()
        person.find(person_id)
        logger.info('Cleaning person_id:{}'.format(person_id))
        cleaner(logger, person, constants)
        person.write_db()

    updator = functools.partial(_do_update,
                                logger=logger,
                                person=person,
                                constants=constants,
                                cleaner=cleaner)

    for x in selection:
        updator(x)
        committer()


def _collect_candidates(collector, constants, source_system, (ss, attr)):
    candidates = collections.defaultdict(list)
    for row in collector(
            entity_type=constants.entity_person,
            source_system=source_system):
        candidates[row['entity_id']].append(
            (ss, row[attr]))
    return candidates


def select_by_stored_data(person, source_system, constants):
    """Look for persons applicable for deletion of information."""
    addresses = _collect_candidates(person.list_entity_addresses,
                                    constants,
                                    source_system,
                                    ('source_system',
                                     'address_type'))

    contact_info = _collect_candidates(person.list_contact_info,
                                       constants,
                                       source_system,
                                       ('source_system',
                                        'contact_type'))

    title_info = collections.defaultdict(list)
    for row in person.search_name_with_language(
            name_variant=[constants.work_title, constants.personal_title],
            name_language=[constants.language_nb,
                           constants.language_en],
            entity_type=constants.entity_person):
        title_info[row['entity_id']].append((row['name_variant'],
                                             row['name_language']))

    name_info = collections.defaultdict(list)
    for row in person.search_person_names(
            source_system=source_system,
            name_variant=[constants.name_first,
                          constants.name_last,
                          constants.name_full]):
        name_info[row['person_id']].append((source_system,
                                            row['name_variant']))

    return set(addresses.keys() +
               contact_info.keys() +
               title_info.keys() +
               name_info.keys())


def select_by_affiliation(person, source_system, grace=0):
    """Select persons that has had all their affiliations deleted."""
    import datetime

    grace_date = datetime.datetime.now() - datetime.timedelta(days=grace)
    cfd = collections.defaultdict(list)

    for r in person.list_affiliations(
            source_system=source_system,
            include_deleted=True):
        cfd[r['person_id']].append(r['deleted_date'])

    dont_alter = set()
    for (pid, dates) in cfd.iteritems():
        if any([(not date or date > grace_date) for date in dates]):
            dont_alter.add(pid)

    return set(cfd.keys()) - set(dont_alter)


def select(person, source_system, constants, grace):
    """Construct selection criteria for persons."""
    return (select_by_affiliation(person, source_system, grace) &
            select_by_stored_data(person, source_system, constants))


def clean_it(prog, commit, systems, commit_threshold=1):
    """Call funcs based on command line arguments."""
    class _Committer(object):
        """Commit changes upon reaching a threshold of N calls to commit()."""

        def __init__(self, database, commit_mode, commit_threshold=1):
            self.database = database
            self.mode = commit_mode
            self.commit_threshold = commit_threshold
            self.count = 0

        def commit(self):
            """Do a commit if commit_threshold is reached."""
            self.count += 1
            if self.count == self.commit_threshold:
                self._do_commit()
                self.count = 0

        def _do_commit(self):
            if self.mode:
                self.database.commit()
            else:
                self.database.rollback()

    from Cerebrum.Utils import Factory
    grace = 30
    logger = Factory.get_logger('cronjob')
    database = Factory.get('Database')(client_encoding='UTF-8')
    database.cl_init(change_program=prog)
    person = Factory.get('Person')(database)
    constants = Factory.get('Constants')(database)
    logger.info('Starting %s in %s mode',
                prog,
                ('commit' if commit else 'rollback'))

    committer = _Committer(database, commit, commit_threshold).commit

    for x in systems:
        system = constants.AuthoritativeSystem(x)
        logger.info("Starting to clean data from %s", system)
        cleaner = functools.partial(update_person, source_system=system)
        perform(cleaner,
                committer,
                logger,
                person,
                constants,
                select(person,
                       system,
                       constants,
                       grace))
        logger.info('Cleaned data from %s', system)

    logger.info('Stopping %s', prog)


def parse_it():
    """Argument parsing."""
    import argparse
    parser = argparse.ArgumentParser(
        description='Delete person data on grounds of originating source'
                    ' systems')
    parser.add_argument('--commit',
                        action='store_true',
                        help='Run in commit-mode (default: off)')
    parser.add_argument('--commit-threshold',
                        default=1,
                        type=int,
                        metavar='N',
                        help='Commit per N change (default: 1)')
    parser.add_argument('--systems',
                        nargs='+',
                        metavar='SYSTEM',
                        help='Systems that should be cleaned (e.g. SAP)')
    args = parser.parse_args()

    clean_it(parser.prog, args.commit, args.systems, args.commit_threshold)


if __name__ == '__main__':
    parse_it()
