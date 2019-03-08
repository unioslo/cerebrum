#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2003-2007 University of Oslo, Norway
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

import getopt
import sys

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.Constants import _SpreadCode, _AuthenticationCode
from Cerebrum.modules.NISUtils import Passwd, FileGroup, UserNetGroup, MachineNetGroup
from Cerebrum.modules.NISUtils import HackUserNetGroupUIO

Factory = Utils.Factory
logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
co = Factory.get('Constants')(db)

# The "official" NIS max line length (consisting of key + NUL + value
# + NUL) is 1024; however, some implementations appear to have lower
# limits.
#
# Specifically, on Solaris 9 makedbm(1M) chokes on lines longer than
# 1018 characters.  Other systems might be even more limited.

_SpreadCode.sql = db

def map_spread(id):
    try:
        return int(_SpreadCode(id))
    except Errors.NotFoundError:
        print "Error mapping spread %s" % id  # no need to use logger here
        raise


def map_auth_method(id):
    if id == 'NOCRYPT':
        return 'NOCRYPT'
    try:
        return int(_AuthenticationCode(id))
    except Errors.NotFoundError:
        print "Error mapping auth_method %s" % id  # no need to use logger here
        raise


def main():
    global max_group_memberships
    global e_o_f
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'g:p:n:s:m:Z:a:',
                                   ['help', 'eof', 'group=',
                                    'passwd=', 'group_spread=',
                                    'user_spread=', 'netgroup=', 'auth_method=',
                                    'max_memberships=', 'shadow=',
                                    'mnetgroup=', 'zone=', 'this-is-an-ugly-hack='])
    except getopt.GetoptError, msg:
        usage(1)

    e_o_f = False
    user_spread = group_spread = None
    max_group_memberships = 16
    auth_method = co.auth_type_md5_crypt
    shadow_file = None
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--eof',):
            e_o_f = True
        elif opt in ('-a', '--auth_method'):
            auth_method = map_auth_method(val)
        elif opt in ('-g', '--group'):
            if not (user_spread and group_spread):
                sys.stderr.write("Must set user and group spread!\n")
                sys.exit(1)    
            fg = FileGroup(group_spread, user_spread)
            fg.write_filegroup(val, e_o_f)
        elif opt in ('-p', '--passwd'):
            if not user_spread:
                sys.stderr.write("Must set user spread!\n")
                sys.exit(1)
            p = Passwd(auth_method, user_spread)
            p.write_passwd(val, shadow_file, e_o_f)
            shadow_file = None
        elif opt in ('-n', '--netgroup'):
            if not (user_spread and group_spread):
                sys.stderr.write("Must set user and group spread!\n")
                sys.exit(1)
            ung = UserNetGroup(group_spread, user_spread)
            ung.write_netgroup(val, e_o_f)
        elif opt in ('--this-is-an-ugly-hack',):
            if not (user_spread and group_spread):
                sys.stderr.write("Must set user and group spread!\n")
                sys.exit(1)
            ung = HackUserNetGroupUIO(group_spread, user_spread)
            ung.write_netgroup(val, e_o_f)
        elif opt in ('-m', '--mnetgroup'):
            ngu = MachineNetGroup(group_spread, None, zone)
            ngu.write_netgroup(val, e_o_f)
        elif opt in ('--group_spread',):
            if val.find(',') == -1:
                group_spread = map_spread(val)
            else:
                group_spread = [map_spread(v) for v in val.split(',')]
        elif opt in ('-Z', '--zone',):
            zone = co.DnsZone(val)
        elif opt in ('--max_memberships',):
            max_group_memberships = val
        elif opt in ('--user_spread',):
            user_spread = map_spread(val)
        elif opt in ('-s', '--shadow'):
            shadow_file = val
        else:
            usage()
    if len(opts) == 0:
        usage(1)

def usage(exitcode=0):
    print """Usage: [options]
  
   [--user_spread spread [--shadow outfile]* [--passwd outfile]* \
    [--group_spread spread [--group outfile]* [--netgroup outfile]*]*]+

   Any of the two types may be repeated as many times as needed, and will
   result in generate_nismaps making several maps based on spread. If eg.
   user_spread is set, generate_nismaps will use this if a new one is not
   set before later passwd files. This is not the case for shadow.

   group_spread could be comma separated to support more than one spread.

   Misc options:
    -d | --debug
      Enable deubgging
    --eof
      End dump file with E_O_F to mark successful completion

   Group options:
    --group_spread value
      Filter by group_spread
    -g | --group outfile
      Write posix group map to outfile
    -n | --netgroup outfile
      Write netgroup map to outfile
    -m | --mnetgroup outfile
      Write netgroup.host map to outfile
    -Z | --zone dns zone postfix (example: .uio.no.)

   User options:
    --user_spread value
      Filter by user_spread
    -s | --shadow outfile
      Write shadow file. Password hashes in passwd will then be '!!' or '*'.
    -p | --passwd outfile
      Write password map to outfile

    Generates a NIS map of the requested type for the requested spreads."""
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
