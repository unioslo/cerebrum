#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2022-2024 University of Oslo, Norway
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
Count number of active primary accounts by faculty.

Note that each personal account may be counted twice, if affiliated with
multiple org units, or multiple affiliation types.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Errors import NotFoundError
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.Stedkode import OuCache
from Cerebrum.modules.orgreg.constants import OrgregConstants
from Cerebrum.utils import csvutils
from Cerebrum.utils import file_stream


def generate_amounts_affiliations(db, affiliation_type):
    pe = Factory.get('Person')(db)
    ou = Factory.get('OU')(db)
    co = Factory.get('Constants')(db)
    amount_dict = {}
    affiliations = pe.list_affiliations(affiliation=affiliation_type)
    if affiliation_type == co.affiliation_tilknyttet:
        affiliations.extend(
            pe.list_affiliations(affiliation=co.affiliation_manuell))

    # TODO: Build up a list of active personal account owners, rather than
    # doing pe.find() + pe.get_accounts()
    for aff in affiliations:
        try:
            pe.find(aff['person_id'])
            if len(pe.get_accounts()) > 0:
                if amount_dict.get(aff['ou_id']) is None:
                    amount_dict[aff['ou_id']] = [aff['person_id']]
                else:
                    amount_dict[aff['ou_id']].append(aff['person_id'])
            pe.clear()
        except Exception:
            pass
    return condense_dict(amount_dict, ou, co)


def condense_dict(dict, ou, co):
    amount_dict = dict
    run = True
    # TODO: Build up a list of valid org units, and a map of (ou ->
    # faculty-level parent) to prevent this loop and repeated calls to
    # ou.find())
    while run:
        run = False
        for place in list(amount_dict):
            valid = True
            ou.find(place)
            quarantines = ou.get_entity_quarantine()
            for quarantine in quarantines:
                if quarantine[0] == co.quarantine_ou_notvalid:
                    amount_dict.pop(place)
                    valid = False
            if valid:
                try:
                    parent = ou.get_parent(OrgregConstants.perspective_orgreg)
                except NotFoundError:
                    parent = None
                if parent is not None and parent != 677:
                    run = True
                    if amount_dict.get(parent) is None:
                        amount_dict[parent] = amount_dict.pop(place)
                    else:
                        amount_dict[parent].extend(amount_dict.pop(place))
            ou.clear()
    for place in list(amount_dict):
        amount_dict[place] = len(set(amount_dict[place]))
    return amount_dict


CSV_FIELDS = [
    'ou_id',
    'seksjon',
    'antall ansattbrukere',
    'antall studentbrukere',
    'antall tilknyttetbrukere',
]


def csv_record(ou_id, name, n_employees, n_students, n_others):
    return dict(zip(CSV_FIELDS,
                    (ou_id, name, n_employees, n_students, n_others)))


def combine_numbers(db, ansatt_dict, student_dict, tilknyttet_dict):
    ou_cache = OuCache(db)

    for ou_id in list(ansatt_dict):
        ansatte = ansatt_dict.pop(ou_id)
        studenter = student_dict.pop(ou_id, 0)
        tilknyttede = tilknyttet_dict.pop(ou_id, 0)
        yield csv_record(
            ou_id=ou_id,
            name=ou_cache.get_name(ou_id),
            n_employees=ansatte,
            n_students=studenter,
            n_others=tilknyttede,
        )

    for ou_id in list(student_dict):
        studenter = student_dict.pop(ou_id)
        tilknyttede = tilknyttet_dict.pop(ou_id, 0)
        yield csv_record(
            ou_id=ou_id,
            name=ou_cache.get_name(ou_id),
            n_employees=0,
            n_students=studenter,
            n_others=tilknyttede,
        )

    for ou_id in list(tilknyttet_dict):
        tilknyttede = tilknyttet_dict.pop(ou_id)
        yield csv_record(
            ou_id=ou_id,
            name=ou_cache.get_name(ou_id),
            n_employees=0,
            n_students=0,
            n_others=tilknyttede,
        )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "filename",
        help='Filename for output-file',
    )
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(argv)

    Cerebrum.logutils.autoconf('console', args)
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    ansatt = generate_amounts_affiliations(db, co.affiliation_ansatt)
    student = generate_amounts_affiliations(db, co.affiliation_student)
    tilknyttet = generate_amounts_affiliations(db, co.affiliation_tilknyttet)
    records = list(combine_numbers(db, ansatt, student, tilknyttet))

    with file_stream.get_output_context(args.filename, encoding="utf-8") as f:
        writer = csvutils.UnicodeDictWriter(f, CSV_FIELDS)
        writer.writeheader()
        writer.writerows(records)


if __name__ == '__main__':
    main()
