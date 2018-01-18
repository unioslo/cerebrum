#!/usr/bin/env python
# -*- coding: utf-8 -*-
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


from __future__ import unicode_literals


"""Fix double encoded constants.

Problem: Someone used non-ascii characters (e.g. norwegian letters) in
code_strs *and* the constant was in a utf-8 file. Since the database
layer expects latin1, this means the constants is double encoded.

This patch tries to fix this."""

import argparse
import locale
from Cerebrum.Utils import Factory
from Cerebrum.Constants import _CerebrumCode
import six


def main():
    locale.getpreferredencoding()
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('-c', '--commit', action='store_true', help='commit')
    config = p.parse_args()
    consts = Factory.get('Constants'.encode('ascii'))
    db = Factory.get('Database')(client_encoding='UTF-8')
    tables = set()
    for name in dir(consts):
        const = getattr(consts, name)
        if isinstance(const, _CerebrumCode):
            tables.add((const._lookup_table, const._lookup_code_column))
    for table, code in tables:
        print('fixing table {}'.format(table))
        rows = db.query('SELECT * FROM {}'.format(table))
        fixes = []
        for row in rows:
            fix = dict()
            for key in row.keys():
                if isinstance(row[key], six.text_type):
                    try:
                        new = row[key].encode('latin1').decode('utf-8')
                        if new != row[key]:
                            fix[key] = new
                    except UnicodeError:
                        pass
            if fix:
                fixes.append((row[code], fix))
        for key, fix in fixes:
            for row in rows:
                if any(row[k] == v for k, v in fix.items()):
                    print('Manual intervention may be needed.'
                          'Suspicious:\n\told = {}\n\tnew = {}={},'
                          '{}'.format(row, code, key, fix))
            sql = ('UPDATE {table} SET {fix} WHERE {code} = :fixargcode'
                   .format(table=table,
                           code=code,
                           fix=', '.join('{}=:{}'.format(x, x)
                                         for x in fix.keys())))
            print('Will update for {} = {}: {}'.format(
                code, key, ', '.join('{} = {}'.format(k, v) for k, v in
                                     fix.items())))
            fix['fixargcode'] = key
            try:
                db.execute(sql, fix)
                if config.commit:
                    db.commit()
                else:
                    db.rollback()
            except Exception as e:
                print('Manual intervention needed:')
                print(e)
                db.rollback()


if __name__ == '__main__':
    main()
