#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2024 University of Oslo, Norway
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
""" Import from a pbx in ldif-format. """

import argparse
import locale
import re
import six

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import LDIFutils


SOURCE_SYSTEM = 'PBX'

logger = Factory.get_logger("cronjob")


class ContactCache(dict):
    """ Cache of contact types and values from Cerebrum.

    > c = ContactCache(db)
    > c[<person_id>][<contact_type_intval>]
    [<contact_value>, ...]
    """

    def __init__(self, db, source_system=SOURCE_SYSTEM):
        person = Factory.get('Person')(db)
        co = Factory.get('Constants')(db)

        self._source = co.AuthoritativeSystem(source_system)

        for row in person.list_contact_info(source_system=self._source):
            db_key = int(row['entity_id'])
            cont_type = int(row['contact_type'])
            db_value = row['contact_value']

            self.setdefault(db_key, dict()).setdefault(cont_type, list())
            self[db_key][cont_type].append(db_value)
            self[db_key][cont_type].sort()

    def __repr__(self):
        return '<{!s} {!s}>'.format(self.__class__.__name__, self._source)


def get_person(db, person_id):
    person = Factory.get('Person')(db)
    person.find(person_id)
    return person


def get_account(db, account_name):
    account = Factory.get('Account')(db)
    account.find_by_name(account_name)
    return account


def get_ldif_info(db, stream):
    co = Factory.get('Constants')(db)
    fax, fax_num = co.contact_fax, 'facsimiletelephonenumber'
    phone, ph_num = co.contact_phone, 'internationalisdnnumber'
    mobile, mob_num = int(co.contact_mobile_phone), 'mobile'
    con_info = {}
    lt = LDIFutils.ldif_parser(stream)
    r = re.compile("^(\w+)@[uh]ia\.no(\/(\w+))?")
    for val in lt.parse().values():
        if 'uid' not in val:
            continue
        # check for syntax in 'uid'
        m = r.match(val['uid'][0])
        if not m:
            continue
        # Iff '/x' the 'x' has to be a digit
        if m.group(2) and not m.group(3).isdigit():
            continue
        uname = m.group(1)

        try:
            acc = get_account(db, uname)
            if not acc.owner_type == int(co.entity_person):
                logger.debug("Owner (%d) for '%s' is not a person" %
                             (acc.owner_id, uname))
                continue
            pers_id = acc.owner_id
        except Errors.NotFoundError:
            logger.debug("Could not find account: %s" % uname)
            continue

        if pers_id not in con_info:
            con_info[pers_id] = {}
        if ph_num not in val:
            con_info[pers_id].setdefault(phone, []).append(val[ph_num][0])
        if fax_num in val:
            con_info[pers_id][fax] = val[fax_num]
            con_info[pers_id][fax].sort()
        if mob_num in val:
            con_info[pers_id][mobile] = val[mob_num]
            con_info[pers_id][mobile].sort()
    return con_info


def sync_contact_info(db, contact_cache, contact_source):
    co = Factory.get('Constants')(db)

    # Insert missing contact info from source
    for pers_id, val in six.iteritems(contact_source):
        try:
            person = get_person(db, pers_id)
        except Errors.NotFoundError:
            logger.debug("Person not found. owner_id:%d" % pers_id)
            continue

        do_update = False
        for attr, info_l in val.items():
            try:
                if info_l != contact_cache[pers_id][attr]:
                    do_update = True
            except KeyError:
                do_update = True
        if not do_update:
            continue

        for attr, info_l in val.items():
            pref = 1
            for inf in info_l:
                person.populate_contact_info(co.AuthoritativeSystem('PBX'),
                                             type=attr,
                                             value=inf,
                                             contact_pref=pref)
                logger.info("Person(%s) contact info updated: %s %s" %
                            (pers_id, attr, inf))
                pref += 1
        person.write_db()

    # Clean up contact info missing in source
    for pers_id, types in six.iteritems(contact_cache):
        for c_type in types:
            if pers_id in contact_source and c_type in contact_source[pers_id]:
                continue
            person = get_person(pers_id)
            person.delete_contact_info(co.AuthoritativeSystem(SOURCE_SYSTEM),
                                       c_type)
            logger.info("Person(%s) contact info deleted: %s, %s" %
                        (pers_id, SOURCE_SYSTEM, c_type))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-l', '--ldif-file',
        required=True,
        type=argparse.FileType('r'),
        dest='ldif_stream',
        metavar='FILE',
        help='full path to ldif-file')
    parser.add_argument(
        '--commit',
        action='store_true',
        default=False,
        help='commit changes to db')
    args = parser.parse_args()

    db = Factory.get('Database')()

    # Parse LDIF
    source = get_ldif_info(db, args.ldif_stream)
    args.ldif_stream.close()

    # Fetch Cerebrum values
    cache = ContactCache(db)

    # Sync
    db.cl_init(change_program='import_pbx')
    sync_contact_info(db, cache, source)

    if args.commit():
        db.commit()
    else:
        db.rollback()


if __name__ == '__main__':
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))
    main()
