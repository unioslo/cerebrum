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
    for row in posix_user.list_posix_users():

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
            passwd = posix_user.get_account_authentication(
                co.auth_type_md5_crypt)
        except Errors.NotFoundError:
            passwd = '*'

        try:
            posix_group.clear()
            posix_group.find(posix_user.gid)
        except Errors.NotFoundError:
            continue

        # TODO: PosixUser.get_gecos() should default to .gecos.
        gecos = posix_user.get_gecos()

        # TODO: Using .description to get the shell's path is ugly.
        shell = PosixUser._PosixShellCode(int(posix_user.shell))
        shell = shell.description

        print "dn: uid=%s,ou=users,dc=uio,dc=no" % uname
        print "objectClass: top"
        print "objectClass: account"
        print "objectClass: posixAccount"
        print "cn: %s" % gecos
        print "uid: %s" % uname
        print "uidNumber: %s" % str(posix_user.posix_uid)
        print "gidNumber: %s" % str(posix_group.posix_gid)
        print "homeDirectory: %s" % str(posix_user.get_home())
        print "userPassword: {crypt}%s" % passwd
        print "loginShell: %s" % shell
        print "gecos: %s" % gecos
        print "\n"


def generate_group():
    groups = {}
    for row in posix_group.list_all():
        posix_group.clear()
        posix_group.find(row.group_id)
        # Group.get_members will flatten the member set, but returns
        # only a list of entity ids; we remove all ids with no
        # corresponding PosixUser, and resolve the remaining ones to
        # their PosixUser usernames.
        gname = posix_group.group_name
        gid = str(posix_group.posix_gid)

        members = []
        for id in posix_group.get_members():
            id = Cerebrum.pythonify_data(id)
            if entity2uname.has_key(id):
                members.append(entity2uname[id])
            else:
                raise ValueError, "Found no id: %s for group: %s" % (
                    id, gname)

        print "dn: cn=%s,ou=filegroups,dc=uio,dc=no" % gname
        print "objectClass: top"
        print "objectClass: posixGroup"
        print "cn: %s" % gname
        print "gidNumber: %s" % gid
        if posix_group.description:
            print "description: %s" % posix_group.description
        for m in members:
            print "memberUid: %s" % m
        print "\n"


def main():
    generate_users()
    generate_group()

if __name__ == '__main__':
    main()
