#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009-2020 University of Oslo, Norway
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
Report affiliation counts.
"""
from __future__ import print_function

import argparse
import collections
import logging

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)


def get_aff_types(db):
    """ Get all valid PersonAffiliation types """
    co = Factory.get("Constants")(db)
    return tuple(co.fetch_constants(co.PersonAffiliation))


def get_aff_subtypes(db):
    """ Get all valid PersonAffStatus types """
    co = Factory.get("Constants")(db)
    return tuple(co.fetch_constants(co.PersonAffStatus))


def get_affiliations(db):
    """ Get all current person affiliations. """
    pe = Factory.get("Person")(db)

    types = {int(c): c for c in get_aff_types(db)}
    subtypes = {int(c): c for c in get_aff_subtypes(db)}

    for row in pe.list_affiliations():
        person_id = int(row['person_id'])
        aff = types[row['affiliation']]
        status = subtypes[row['status']]
        ou_id = int(row['ou_id'])

        yield person_id, aff, status, ou_id


class AffiliationStatistics(object):
    """ Organize persons by affiliation types and ous """

    def __init__(self, affiliations):
        """
        :param affiliations:
            iterable of (person_id, affiliation, status, ou_id) tuples
        """

        # observed ous, affs
        affs = set()
        stat = set()
        ous = set()

        data = collections.defaultdict(list)

        for person_id, aff, status, ou_id in affiliations:
            affs.add(aff)
            stat.add(status)
            ous.add(ou_id)

            # record person by aff, status, ou
            for key in (
                (None,  None,       None),
                (aff,   None,       None),
                (None,  status,     None),
                (None,  None,       ou_id),
                (aff,   None,       ou_id),
                (None,  status,     ou_id),
            ):
                data[key].append(person_id)

        self._data = dict(data)
        self.ous = ous
        self.types = tuple(sorted(affs))
        self.subtypes = tuple(sorted(stat))

    def count(self, affiliation=None, status=None, ou=None):
        return len(self._data[affiliation, status, ou])

    def count_unique(self, affiliation=None, status=None, ou=None):
        return len(set(self._data[affiliation, status, ou]))


def print_affiliation_summary(stats):

    status_by_aff = collections.defaultdict(set)

    for s in stats.subtypes:
        status_by_aff[s.affiliation].add(s)

    entry = "{key:29} {persons:>9} {affs:>9}"

    print(entry.format(key='', persons='#persons', affs='#affs'))
    print(entry.format(key='total',
                       persons=stats.count_unique(),
                       affs=stats.count()))
    for a in stats.types:
        print(entry.format(key=six.text_type(a),
                           persons=stats.count_unique(affiliation=a),
                           affs=stats.count(affiliation=a)))
        for s in status_by_aff.get(a, []):
            print(entry.format(key=six.text_type(s),
                               persons=stats.count_unique(status=s),
                               affs=stats.count(status=s)))


default_logger_preset = 'console'
default_logger_level = logging.WARNING


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Count affiliations by type',
    )

    Cerebrum.logutils.options.install_subparser(parser)
    parser.set_defaults(**{
        Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: default_logger_level,
    })

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf(default_logger_preset, args)

    db = Factory.get("Database")()
    stats = AffiliationStatistics(get_affiliations(db))
    print_affiliation_summary(stats)


if __name__ == '__main__':
    main()
