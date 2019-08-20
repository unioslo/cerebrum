#!/usr/bin/env python
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
""" Dump affiliation count. """
from __future__ import print_function

from Cerebrum.Utils import Factory
from collections import defaultdict

from six import text_type


class AffiliationStatistics(object):
    """ Cache person affiliation by type/ou. """

    def __init__(self, db):
        co = Factory.get("Constants")(db)
        pe = Factory.get("Person")(db)

        # observed ous, affs
        affs = set()
        stat = set()
        ous = set()

        data = defaultdict(list)

        for row in pe.list_affiliations():
            affs.add(row['affiliation'])
            stat.add(row['status'])
            ous.add(row['ou_id'])

            # record person by aff, status, ou
            for key in (
                (None,               None,          None),
                (row['affiliation'], None,          None),
                (None,               row['status'], None),
                (None,               None,          row['ou_id']),
                (row['affiliation'], None,          row['ou_id']),
                (None,               row['status'], row['ou_id']),
            ):
                data[key].append(row['person_id'])

        self._data = dict(data)
        self.ous = ous
        self.types = tuple((co.PersonAffiliation(a) for a in affs))
        self.subtypes = tuple((co.PersonAffStatus(s) for s in stat))

    def count(self, affiliation=None, status=None, ou=None):
        return len(self._data[affiliation, status, ou])

    def count_unique(self, affiliation=None, status=None, ou=None):
        return len(set(self._data[affiliation, status, ou]))


def print_affiliation_summary(stats):

    status_by_aff = defaultdict(set)

    for s in stats.subtypes:
        status_by_aff[s.affiliation].add(s)

    entry = "{key:29} {persons:>9} {affs:>9}"

    print(entry.format(key='', persons='#persons', affs='#affs'))
    print(entry.format(key='total',
                       persons=stats.count_unique(),
                       affs=stats.count()))
    for a in stats.types:
        print(entry.format(key=text_type(a),
                           persons=stats.count_unique(affiliation=a),
                           affs=stats.count(affiliation=a)))
        for s in status_by_aff.get(a, []):
            print(entry.format(key=text_type(s),
                               persons=stats.count_unique(status=s),
                               affs=stats.count(status=s)))


def main():
    db = Factory.get("Database")()
    stats = AffiliationStatistics(db)
    print_affiliation_summary(stats)


if __name__ == '__main__':
    main()
