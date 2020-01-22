#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build an XML file with Cerebrum data for evalg 2.

This script generates an XML export with users for the evalg application.
Every person in Cerebrum is included, regardless of whether they have user
accounts or not.

TODO: Do we really need a separate version for UiT? The major differences are:

- Hard coded SYSTEM_LOOKUP_ORDER in script, different from the real uit
  SYSTEM_LOOKUP_ORDER. System lookup order is used to select prioritized value
  for attributes 'fnr', 'names'
- Exports a 'bdate' attribute
- Does not export an 'email' attribute


"""
from __future__ import unicode_literals

import argparse
import io
import logging

import Cerebrum.logutils

from Cerebrum.Utils import Factory
from Cerebrum.Utils import XMLHelper


logger = logging.getLogger(__name__)


def dump_person_info(db, fname):
    xml = XMLHelper()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    person = Factory.get('Person')(db)

    src_sys_order = {
        int(co.system_fs): 1,
        int(co.system_x): 2,
    }

    def source_system_key(row):
        return src_sys_order.get(int(row['source_system']), 99)

    def _fetch_names(name_type):
        # Fetch persons full-name from most-significant source system
        ret = {}
        for row in person.list_names(variant=name_type):
            pid = int(row['person_id'])
            ret.setdefault(pid, []).append(row)
        for pid, rows in ret.items():
            rows.sort(key=source_system_key)
            ret[pid] = rows[0]
            assert int(name_type) == rows[0]['name_variant']
        return ret

    # Fetch persons full-name from most-significant source system
    # pid2names = _fetch_names(co.name_full)
    pid2first_name = _fetch_names(co.name_first)
    pid2last_name = _fetch_names(co.name_last)

    # Fetch birth-no from most-significant source system
    pid2ext_ids = {}
    for row in person.search_external_ids(id_type=co.externalid_fodselsnr):
        pid = int(row['entity_id'])
        pid2ext_ids.setdefault(pid, []).append(row)
    for pid, rows in pid2ext_ids.items():
        rows.sort(key=source_system_key)
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
        assert pid not in pid2ac
        pid2ac[pid] = _acid2uname[int(row['account_id'])]

    cols = ('fnr', 'first_name', 'last_name', 'uname', 'bdate')
    f = io.open(fname, "wt", encoding='utf-8')
    f.write(xml.xml_hdr + u"<data>\n")
    for pid, birth in pid2birth.items():
        if ((pid not in pid2ext_ids) or
                (not (pid in pid2first_name or
                      pid in pid2last_name))):
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
        if pid in pid2ac:
            row['uname'] = pid2ac[pid]
        row['bdate'] = pid2birth[pid]
        f.write(xml.xmlify_dbrow(row, cols, 'person'))  # .encode('utf-8'))
        f.write(u'\n')

    f.write(u"</data>\n")
    f.close()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-v',
        dest='filename',
        required=True,
        help='Write evalg data to %(metavar)s',
        metavar='<filename>',
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args=%r', args)

    db = Factory.get('Database')()
    output_file = args.filename
    dump_person_info(db, output_file)

    logger.info('Wrote evalg data to %r', output_file)
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
