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
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
posix_user = PosixUser.PosixUser(Cerebrum)
posix_group = PosixGroup.PosixGroup(Cerebrum)

entity2uname = {}

def generate_passwd():
    count = 0
    for row in posix_user.get_all_posix_users():
        id = row['account_id']
        posix_user.find(id)
        # account.find(id)

        # TODO: The value_domain should be fetched from somewhere
        # The array indexes should be replaced with hash-keys
        uname = posix_user.get_name(co.account_namespace)[0][2]
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
            default_group = posix_group.find(posix_user.gid)
        except Errors.NotFoundError:
            continue

        # TODO: PosixUser.get_gecos() should default to .gecos.
        gecos = posix_user.gecos
        if gecos is None:
            gecos = posix_user.get_gecos()

        # TODO: Using .description to get the shell's path is ugly.
        shell = Constants._PosixShellCode(int(posix_user.shell)).description
        print join((uname, passwd, str(posix_user.posix_uid),
                    str(default_group.posix_gid), gecos,
                    posix_user.home, shell))
        # convert to 7-bit

def generate_group():
    groups = {}
    for row in posix_group.list_all():
        posix_group.find(row.group_id)
        # Group.get_members will flatten the member set, but returns
        # only a list of entity ids; we remove all ids with no
        # corresponding PosixUser, and resolve the remaining ones to
        # their PosixUser usernames.
        gname = posix_group.group_name
        gid = str(posix_group.posix_gid)
        members = [entity2uname[id] for id in posix_group.get_members()
                   if entity2uname.has_key(id)]
        gline = join((gname, '*', gid, join(members, ',')))
        if len(gline) <= MAX_LINE_LENGTH:
            print gline
            groups[gname] = None
        else:
            groups[gname] = (gid, members)

    def make_name(base):
        name = base
        harder = True
        while len(name) > 0:
            i = 0
            if harder:
                name = name[:-1]
            format = "%s%x"
            if len(name) < 7:
                format = "%s%02x"
            while True:
                tname = format % (name, i)
                if len(tname) > 8:
                    break
                if not groups.has_key(tname):
                    return tname
                i += 1
            harder = True

    # Groups with too many members to fit on one line.  Use multiple
    # lines with different (although similar) group names, but the
    # same numeric GID.
    for g in groups:
        if groups[g] is None:
            # Already printed out
            continue
        gname = g
        gid, members = groups[g]
        while members:
            # gname:*:gid:
            memb_str, members = maxjoin(members, MAX_LINE_LENGTH -
                                        (len(gname) + len(gid) + 4))
            if memb_str is None:
                break
            print join((gname, '*', gid, memb_str))
            groups.setdefault(gname, None)
            gname = make_name(g)
        groups[g] = None

def join(fields, sep=':'):
    for f in fields:
        if not isinstance(f, str):
            raise ValueError, "Type of '%r' is not str." % f
        if f.find(sep) <> -1:
            raise ValueError, \
                  "Separator '%s' present in string '%s'" % (sep, f)
    return sep.join(fields)

def maxjoin(elems, maxlen, sep=','):
    if not elems:
        return (None, elems)
    s = None
    for i in range(len(elems)):
        e = elems[i]
        if not s:
            s = e
        elif len(s) + len(sep) + len(e) >= maxlen:
            return (s, elems[i:])
        else:
            s += sep + e
    return (s, ())

def main():
    generate_passwd()
    generate_group()

if __name__ == '__main__':
    main()
