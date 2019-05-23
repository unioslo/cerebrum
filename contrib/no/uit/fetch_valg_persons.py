#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Lager XML fil med person-info for import i valg-applikasjonen.
Henter informasjon om alle personer kjent i cerebrum, ogs� de som ikke
har brukere.

Usage: fetch-valg_persons.py [options]
  -v outfile.xml : write persons to xml file
"""
# from __future__ import unicode_literals
import getopt
import io
import sys

from Cerebrum.Utils import Factory
from Cerebrum.Utils import XMLHelper

xml = XMLHelper()

db = Factory.get('Database')()
# db.cl_init(change_program="skeleton")
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
person = Factory.get('Person')(db)

logger = Factory.get_logger("console")


def dump_person_info(fname):
    src_sys_order = {
        int(co.system_lt): 1,
        int(co.system_fs): 2,
        int(co.system_x): 3,
    }

    def sort_by_source_system(a, b):
        return cmp(src_sys_order.get(int(a['source_system']), 99),
                   src_sys_order.get(int(b['source_system']), 99))

    def _fetch_names(name_type):
        # Fetch persons full-name from most-significant source system
        ret = {}
        for row in person.list_names(name_type=name_type):
            pid = int(row['person_id'])
            ret.setdefault(pid, []).append(row)
        for pid, rows in ret.items():
            rows.sort(sort_by_source_system)
            ret[pid] = rows[0]
            assert int(name_type) == rows[0]['name_variant']
        return ret

    # Fetch persons full-name from most-significant source system
    # pid2names = _fetch_names(co.name_full)
    pid2first_name = _fetch_names(co.name_first)
    pid2last_name = _fetch_names(co.name_last)

    # Fetch birth-no from most-significant source system
    pid2ext_ids = {}
    for row in person.list_external_ids(id_type=co.externalid_fodselsnr):
        pid = int(row['entity_id'])
        pid2ext_ids.setdefault(pid, []).append(row)
    for pid, rows in pid2ext_ids.items():
        rows.sort(sort_by_source_system)
        pid2ext_ids[pid] = rows[0]

    # Fetch birth-date
    pid2birth = {}
    for row in person.list_persons():
        pid = int(row['person_id'])
        if not row['birth_date']:
            continue
        pid2birth[pid] = row['birth_date'].strftime('%Y-%m-%d')

    pid2ac = {}
    _acid2uname = {}
    # Fetch primary account
    for row in ac.search():
        _acid2uname[int(row['account_id'])] = row['name']
    for row in ac.list_accounts_by_type(primary_only=True):
        pid = int(row['person_id'])
        assert not pid2ac.has_key(pid)
        pid2ac[pid] = _acid2uname[int(row['account_id'])]

    cols = ('fnr', 'first_name', 'last_name', 'uname', 'bdate')
    f = io.open(fname, "wt", encoding='utf-8')
    f.write(xml.xml_hdr + u"<data>\n")
    for pid, birth in pid2birth.items():
        if ((not pid2ext_ids.has_key(pid)) or
                (not (pid2first_name.has_key(pid) or
                      pid2last_name.has_key(pid)))):
            continue

        row = {}
        row['fnr'] = None
        row['first_name'] = None
        row['last_name'] = None
        row['uname'] = None
        row['bdate'] = None

        row['fnr'] = pid2ext_ids[pid]['external_id']
        row['first_name'] = pid2first_name[pid]['name']
        row['last_name'] = pid2last_name[pid]['name']
        if pid2ac.has_key(pid):
            row['uname'] = pid2ac[pid]
        row['bdate'] = pid2birth[pid]
        f.write(xml.xmlify_dbrow(row, cols, 'person'))  # .encode('utf-8'))
        f.write(u'\n')

    f.write(u"</data>\n")
    f.close()


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'v:', ['help'])
    except getopt.GetoptError:
        usage(1)

    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-v',):
            valg_fname = val
    if not opts:
        usage(1)
    dump_person_info(valg_fname)


def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
