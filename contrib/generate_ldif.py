#!/usr/bin/env python2.2

# Copyright 2002, 2003 University of Oslo, Norway
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

import time

import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
posix_user = PosixUser.PosixUser(Cerebrum)
posix_group = PosixGroup.PosixGroup(Cerebrum)

entity2uname = {}

def generate_users():
    for row in posix_user.get_all_posix_users():
        id = Cerebrum.pythonify_data(row['account_id'])
        posix_user.clear()
        posix_user.find(id)
        # TODO: The value_domain should be fetched from somewhere
        # The array indexes should be replaced with hash-keys
        uname = posix_user.get_name(co.account_namespace)['entity_name']
        if entity2uname.has_key(id):
            raise ValueError, "Entity %d has multiple unames: (%s, %s)" % (
                entity2uname[id], uname)
        else:
            entity2uname[id] = uname
        # TODO: Something should set which auth_type to use for this map
        try:
            passwd = posix_user.get_account_authentication(co.auth_type_md5)
        except Errors.NotFoundError:
            passwd = '*'

        try:
            posix_group.clear()
            posix_group.find(posix_user.gid)
        except Errors.NotFoundError:
            continue

        # TODO: PosixUser.get_gecos() should default to .gecos.
        gecos = posix_user.gecos
        if gecos is None:
            gecos = posix_user.get_gecos()

        # TODO: Using .description to get the shell's path is ugly.
        shell = PosixUser._PosixShellCode(int(posix_user.shell))
        shell = shell.description

        print join(("dn: uid=%s,ou=users,dc=uio,dc=no" % uname,
                   "objectClass: top",
                   "objectClass: account",
                   "objectClass: posixAccount",
                   "cn: %s" % gecos,
                   "uid: %s" % uname,
                   "uidNumber: %s" % str(posix_user.posix_uid),
                   "gidNumber: %s" % str(posix_group.posix_gid),
                   "homeDirectory: %s" % posix_user.home,
                   "userPassword: {crypt}%s" % passwd,
                   "loginShell: %s" % shell,
                   "gecos: %s" % gecos))
        print "\n"


def join(fields, sep='\n'):
    for f in fields:
        if not isinstance(f, str):
            raise ValueError, "Type of '%r' is not str." % f
        if f.find(sep) <> -1:
            raise ValueError, \
                  "Separator '%s' present in string '%s'" % (sep, f)
    return sep.join(fields)


def main():
    generate_users()
    print "!!!"

if __name__ == '__main__':
    main()
