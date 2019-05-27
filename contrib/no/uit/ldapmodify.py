#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2002-2019 University of Oslo, Norway
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
Update LDAP from ldif-file.

This script does an ldap modify towards the ldap server and then updates the
local ldif file to reflect the status on the server.

Copied from Leetah
"""
import argparse
import datetime
import logging
import os

import cereconf
from Cerebrum.modules.LDIFutils import ldapconf

import Cerebrum.logutils
import Cerebrum.logutils.options

logger = logging.getLogger(__name__)


def main(inargs=None):
    parser = argparse.ArgumentParser(description="Update LDAP")
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    today = datetime.date.today().strftime('%Y%m%d')

    ldap_server = cereconf.LDAP['server']
    user = cereconf.LDAP['user']
    password = cereconf.LDAP['password']

    ldap_dump_dir = ldapconf(None, 'dump_dir')
    infile = os.path.join(ldap_dump_dir, 'uit_diff_%s' % (today, ))
    ldap_temp_file = os.path.join(ldap_dump_dir, "temp_uit_ldif")
    ldap_diff = os.path.join(ldap_dump_dir, "uit_ldif")

    ret = 0
    ret = os.system(
        ' '.join((
            '/usr/bin/ldapmodify',
            '-x',
            '-H', 'ldaps://%s' % (ldap_server, ),
            '-D', '"cn=%s,dc=uit,dc=no"' % (user, ),
            '-w', password,
            '-f', infile,
        )))

    if ret != 0:
        logger.error("Unable to update ldap server")
        raise SystemExit(1)

    ret = os.system("mv %s %s" % (ldap_temp_file, ldap_diff))
    if ret != 0:
        logger.error("Unable to copy tempfile")
        raise SystemExit(1)


if __name__ == '__main__':
    main()
