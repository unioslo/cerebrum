#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2016 University of Oslo, Norway
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
This script is invoked by Zabbbix and aims to determine whether the bofhd
server is running.
The script acts as an independent client and requires only Python 2.7.
The script exits with code 0 if the bofhd server is running.
"""

import argparse
import errno
import os
import socket
import sys
import xmlrpclib


def main():
    parser = argparse.ArgumentParser(
        description='The following options are available')
    parser.add_argument(
        '--url',
        dest='url',
        metavar='<url>',
        type=str,
        required=True,
        help='bofhd server URL')
    args = parser.parse_args()
    try:
        server = xmlrpclib.ServerProxy(args.url)
        motd = server.get_motds(u'ZabbixTest', 1)
        # print('MOTD: {}'.format(motd))
        sys.exit(0)
    except socket.gaierror:
        err = errno.ENOSYS
    except socket.error:
        err = errno.ECONNREFUSED
    except xmlrpclib.Fault:
        err = errno.ENOSYS
    except Exception as e:
        sys.stderr.write('Unexpected error: {0}\n'.format(e))
        sys.exit(1)
    sys.stderr.write(os.strerror(err) + os.linesep)
    sys.exit(err)


if __name__ == '__main__':
    main()
