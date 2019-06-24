#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006-2019 University of Oslo, Norway
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
Build an XML file with Cerebrum data for evalg 2.

This script generates an XML export with users for the evalg application.
Every person in Cerebrum is included, regardless of whether they have user
accounts or not.


Format
------
The XML document contains a single /data node, with zero or more /data/person
nodes.  Each person node will have some attributes with information about that
person.

::

    <?xml version="1.0" encoding="utf-8"?>
    <data>
      <person fnr="01017000000" first_name="Ola" last_name="Nordmann"
              uname="olan" email="olan@example.org"/>
    ...
    </data>


History
-------
This script was previously a part of the old cerebrum_config repository. It was
moved into the main Cerebrum repository, as it was currently in use by many
deployments of Cerebrum.

The original can be found in cerebrum_config.git, as
'bin/uio/fetch_valg_persons.py' at:

  commit: e83e053edc03dcd399775fadd9833101637757ef
  Merge: bef67be2 3bfbd8a2
  Date:  Wed Jun 19 16:07:06 2019 +0200
"""
from __future__ import unicode_literals

import argparse
import os
import sys

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.Utils import XMLHelper


def dump_person_info(args):
    fname = args.filename
    domain = args.domain
    usefeide = args.usefeide
    encoding = args.encoding
    exempt = args.exempt
    src_sys_order = dict(
        (getattr(co, b), a)
        for a, b in enumerate(cereconf.SYSTEM_LOOKUP_ORDER))

    def sort_by_source_system(item):
        return src_sys_order.get(int(item['source_system']), 99)

    def _fetch_exempt_list(arg):
        """
        Returns a list of person_id corresponding to arg

        :param arg: Filename or ,-separated list
        :type arg: str

        :return: List of person_id
        :rtype: list
        """
        elist = list()
        if not arg:
            return elist
        if os.path.isfile(arg):
            with open(arg) as fp:
                for line in fp:
                    try:
                        elist.append(int(line.strip()))
                    except ValueError:
                        continue
        else:
            # assume ,-separated list
            for token in arg.split(','):
                try:
                    elist.append(int(token.strip()))
                except ValueError:
                    continue
        return elist

    def _fetch_names(name_type):
        # Fetch persons full-name from most-significant source system
        ret = {}
        for row in person.get_names():
            # Retrieve all names first...
            if int(name_type) != row['name_variant']:
                # ... but skip those that aren't the type we're looking for
                continue
            pid = int(row['person_id'])
            ret.setdefault(pid, []).append(row)
        for pid, rows in ret.items():
            rows.sort(key=sort_by_source_system)
            ret[pid] = rows[0]
            assert int(name_type) == rows[0]['name_variant']
        return ret

    exempt_list = _fetch_exempt_list(exempt)
    # Fetch birth-no from most-significant source system
    pid2ext_ids = {}
    for row in person.search_external_ids(id_type=co.externalid_fodselsnr,
                                          fetchall=False):
        pid = int(row['entity_id'])
        pid2ext_ids.setdefault(pid, []).append(row)
    for pid, rows in pid2ext_ids.items():
        rows.sort(key=sort_by_source_system)
        pid2ext_ids[pid] = rows[0]

    pid2ac = {}
    pid2email = {}
    for row in ac.list_accounts_by_type(primary_only=True):
        pid = int(row['person_id'])
        assert pid not in pid2ac
        ac.find(row['account_id'])
        pid2ac[pid] = ('{}@{}'.format(ac.account_name, domain) if usefeide else
                       ac.account_name)
        try:
            pid2email[pid] = ac.get_primary_mailaddress()
        except:
            pass
        ac.clear()

    cols = ('fnr', 'first_name', 'last_name', 'uname', 'email')
    f = file(fname, "w")
    f.write(xml.xml_hdr + "<data>\n")
    for row in person.list_persons():
        pid = row['person_id']
        if pid in exempt_list:
            logger.info("Person %s is in the exempt list. Skipping", pid)
            continue
        person.clear()
        person.find(pid)
        # Person-API changed, so we need to retrive names for a
        # specific person, one at a time, not all at once
        pid2first_name = _fetch_names(co.name_first)
        pid2last_name = _fetch_names(co.name_last)

        if not (pid in pid2first_name and
                pid in pid2last_name):
            logger.info("Person %s does not have a name, "
                        "skipping", pid)
            continue
        row = dict(zip(cols, [None, None, None, None, None]))
        if pid in pid2ext_ids:
            row['fnr'] = pid2ext_ids[pid]['external_id']
        elif pid in pid2ac:
            # Use feide-id as fallback if fnr is lacking
            row['fnr'] = (pid2ac[pid] if usefeide else
                          '{}@{}'.format(pid2ac[pid], domain))
        else:
            logger.info("Person %s does not have fnr nor account, skipping",
                        pid)
            continue
        row['first_name'] = pid2first_name[pid]['name']
        row['last_name'] = pid2last_name[pid]['name']
        if pid in pid2ac:
            row['uname'] = pid2ac[pid]
            if pid in pid2email:
                row['email'] = pid2email[pid]
        else:
            logger.info("Person %s does not have any account", pid)
        f.write(
            (xml.xmlify_dbrow(row, cols, 'person') + "\n").encode(encoding))
    f.write("</data>\n")
    f.close()


if __name__ == '__main__':
    db = Factory.get('Database')()
    # db.cl_init(change_program="skeleton")
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    person = Factory.get('Person')(db)

    logger = Factory.get_logger("cronjob")
    p = argparse.ArgumentParser()
    p.add_argument(
        '-d',
        dest='domain',
        default='uio.no',
        action='store',
        required=False,
        help='feide domain name')
    p.add_argument(
        '-e', '--encoding',
        metavar='ENCODING',
        dest='encoding',
        default='utf-8',
        help='The XML encoding (default: utf-8)')
    p.add_argument(
        '-f',
        dest='usefeide',
        required=False,
        action='store_true',
        help='use feide id in username')
    p.add_argument(
        '-v',
        dest='filename',
        required=True,
        action='store',
        help='output file name')
    p.add_argument(
        '-x', '--exempt',
        metavar='FILE / LIST',
        dest='exempt',
        default='',
        help=('A file containing a list of person_id or '
              'a list of person_id separated by ","'))
    args = p.parse_args()
    xml = XMLHelper(encoding=args.encoding)
    try:
        dump_person_info(args)
    except:
        logger.exception("Unexpected exception, quitting")
        sys.exit(1)
