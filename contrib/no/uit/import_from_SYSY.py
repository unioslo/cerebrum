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


import argparse
import logging
import os
import time

import cereconf
from Cerebrum import logutils
from Cerebrum.extlib import xmlprinter
from Cerebrum.modules.no.uit.access_SYSY import SystemY
from Cerebrum.utils.atomicfile import MinimumSizeWriter

default_role_file = os.path.join(cereconf.DUMPDIR,
                                 'sysY',
                                 'sysY_%s.xml' % (time.strftime("%Y%m%d")))

KiB = 1024
logger = logging.getLogger(__name__)


def write_role_info(sys_y, outfile):
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
    # TODO: Do we want to change the encoding here?
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


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('-r',
                        action='store_true',
                        default=False,
                        dest='write_roles',
                        help='write role info file')

    parser.add_argument('--role-file',
                        required=False,
                        metavar='filename',
                        default=default_role_file)
    parser.add_argument('--db-user',
                        default=cereconf.SYS_Y['db_user'])
    parser.add_argument('--db-host',
                        default=cereconf.SYS_Y['db_host'])
    parser.add_argument('--db-service',
                        default=cereconf.SYS_Y['db_service'])

    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)

    sys_y = SystemY(user=args.db_user, database=args.db_service,
                    host=args.db_host)

    if args.write_roles:
        write_role_info(sys_y, args.role_file)


if __name__ == '__main__':
    main()
