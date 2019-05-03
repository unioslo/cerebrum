#!/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003, 2004, 2019 University of Oslo, Norway
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


import os
import time
import sys
import getopt

import cereconf

from Cerebrum.extlib import xmlprinter
from Cerebrum.Utils import XMLHelper
from Cerebrum.utils.atomicfile import MinimumSizeWriter
from Cerebrum.modules.no.uit.access_SYSY import SystemY

default_role_file = os.path.join(cereconf.DUMPDIR,
                                 'sysY',
                                 'sysY_%s.xml' % (time.strftime("%Y%m%d")))

xml = XMLHelper()

sys_y = None
KiB = 1024


def write_role_info(outfile):
    stream = MinimumSizeWriter(outfile)
    stream.min_size = 2 * KiB
    write_roles(stream, sys_y.list_roles())
    stream.close()


def write_roles(stream, items):
    xml_data = {}
    for data in items:
        current = xml_data.get(data['gname'])
        if current:
            xml_data[data['gname']].append(data['uname'])
        else:
            xml_data[data['gname']] = [data['uname']]
    keys = xml_data.keys()
    keys.sort()

    writer = xmlprinter.xmlprinter(stream,
                                   indent_level=2,
                                   data_mode=True,
                                   input_encoding="iso-8859-1")
    writer.startDocument(encoding="iso-8859-1")
    writer.startElement("roles")
    for data in keys:
        admin = 'no'
        if data.find('admin') >= 0:
            admin = 'yes'
        writer.startElement("role", {"name": data, "admin": admin})
        xml_list = xml_data.get(data)
        for x in xml_list:
            writer.dataElement("member", x)
        writer.endElement("role")

    writer.endElement("roles")
    writer.endDocument()


def assert_connected(user=None, service=None, host=None):
    global sys_y
    if sys_y is None:
        sys_y = SystemY(user=user, database=service, host=host)


def usage(exit_code=0, msg=None):
    if msg:
        print(msg)

    print(""" CREATE DOCSTRING""")
    sys.exit(exit_code)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "r",
                                   ["role-file",
                                    "db-user=",
                                    "db-service=",
                                    "db-host="])
    except getopt.GetoptError as m:
        usage(1, m)

    role_file = default_role_file
    db_user = cereconf.SYS_Y['db_user']
    db_service = cereconf.SYS_Y['db_service']
    db_host = cereconf.SYS_Y['db_host']
    for o, val in opts:
        if o in ('--role-file',):
            role_file = val
        elif o in ('--db-user',):
            db_user = val
        elif o in ('--db-host',):
            db_host = val
        elif o in ('--db-service',):
            db_service = val
    assert_connected(user=db_user, service=db_service, host=db_host)
    for o, val in opts:
        if o in ('-r',):
            write_role_info(role_file)


if __name__ == '__main__':
    main()
