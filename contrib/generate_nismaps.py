#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

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

import getopt
import sys
import os
import cerebrum_path
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum import Group
from Cerebrum import Disk
from Cerebrum.Entity import EntityName
from Cerebrum import QuarantineHandler
from Cerebrum.Constants import _SpreadCode

Factory = Utils.Factory
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
posix_user = PosixUser.PosixUser(db)
posix_group = PosixGroup.PosixGroup(db)
MAX_LINE_LENGTH = 1023
_SpreadCode.sql = db

entity2uname = {}
debug = 0
e_o_f = False

def generate_passwd(filename, spread=None):
    if spread is None:
        raise ValueError, "Must set user_spread"
    shells = {}
    for s in posix_user.list_shells():
        shells[int(s['code'])] = s['shell']
    f = Utils.SimilarSizeWriter(filename, "w")
    f.set_size_change_limit(5)
    n = 0
    diskid2path = {}
    disk = Disk.Disk(db)
    static_posix_user = PosixUser.PosixUser(db)
    for d in disk.list():
        diskid2path[int(d['disk_id'])] = d['path']
    for row in posix_user.list_extended_posix_users(auth_method=co.auth_type_crypt3_des,
                                                    spread=spread, include_quarantines=1):
        uname = row['entity_name']
        passwd = row['auth_data']
        if passwd is None:
            passwd = '*'
        posix_group.posix_gid = row['posix_gid']
        gecos = row['gecos']
        if gecos is None:
            gecos = row['name']
        if gecos is None:
            gecos = "GECOS NOT SET"
        gecos = Utils.latin1_to_iso646_60(gecos)
        home = row['home'] 
        shell = shells[int(row['shell'])]
        if row['quarantine_type'] is not None:
            qh = QuarantineHandler.QuarantineHandler(db, [row['quarantine_type']])
            if qh.should_skip():
                continue
            if qh.is_locked():
                passwd = '*locked'
            qshell = qh.get_shell()
            if qshell is not None:
                shell = qshell

        if home is None:
            if row['disk_id'] is None:
                print "Bad disk for %s" % uname
                continue
            home = diskid2path[int(row['disk_id'])] + "/" + uname
            
        line = join((uname, passwd, str(row['posix_uid']),
                    str(posix_group.posix_gid), gecos,
                    str(home), shell))
        if debug:
            print line
        f.write(line+"\n")
        # convert to 7-bit
        n += 1
        #if n > 100:
        #    break
    if e_o_f:
	f.write('E_O_F\n')
    f.close()

def generate_netgroup(filename, group_spread, user_spread):
    # TODO: It may be desireable to merge this method with
    # generate_group, currently separate as a number of things differ
    # and limited available time.
    group = Group.Group(db)
    gid2gname = {}
    en = EntityName(db)
    for row in en.list_names(int(co.account_namespace)):
        entity2uname[int(row['entity_id'])] = row['entity_name']
    entity2gname = {}
    for row in en.list_names(int(co.group_namespace)):
        entity2gname[int(row['entity_id'])] = row['entity_name']
    f = Utils.SimilarSizeWriter(filename, "w")
    f.set_size_change_limit(5)
    num = 0
    for row in group.list_all(spread=group_spread):
        group.clear()
        group.find(row.group_id)
        gid2gname[int(row.group_id)] = group.group_name
        group_members = []
        account_members = []
        for spread in (group_spread, user_spread):
            u, i, d = group.list_members(spread=spread)
            for row2 in u:
                if int(row2[0]) == co.entity_account:
                    account_members.append("(,%s,)" % entity2uname[int(row2[1])])
                elif int(row2[0]) == co.entity_group:
                    group_members.append(entity2gname[int(row2[1])])
        # TODO: Also process intersection and difference members.
        line = " ".join((join(group_members, ' '), join(account_members, ' ')))
        maxlen = MAX_LINE_LENGTH - (len(group.group_name) + 1)
        while len(line) > maxlen:
            pos = line.index(" ", len(line) - maxlen)
            tmp_gname = "x%02x" % num
            f.write("%s %s\n" % (tmp_gname, line[pos+1:]))
            line = "%s %s" % (tmp_gname, line[:pos])
            num += 1
        f.write("%s %s\n" % (group.group_name, line))
    if e_o_f:
	f.write('E_O_F\n')
    f.close()

def generate_group(filename, group_spread, user_spread):
    if group_spread is None or user_spread is None:
        raise ValueError, "Must set user_spread and group_spread"
    groups = {}
    f = Utils.SimilarSizeWriter(filename, "w")
    f.set_size_change_limit(5)
    en = EntityName(db)
    for row in en.list_names(int(co.account_namespace)):
        entity2uname[int(row['entity_id'])] = row['entity_name']
    account2def_group = {}
    for row in posix_user.list_extended_posix_users():
	account2def_group[int(row['account_id'])] = int(row['posix_gid'])
    for row in posix_group.list_all(spread=group_spread):
        posix_group.clear()
        posix_group.find(row.group_id)
        # Group.get_members will flatten the member set, but returns
        # only a list of entity ids; we remove all ids with no
        # corresponding PosixUser, and resolve the remaining ones to
        # their PosixUser usernames.
        gname = posix_group.group_name
        gid = str(posix_group.posix_gid)

        members = []
        for id in posix_group.get_members(spread=user_spread):
            id = db.pythonify_data(id)
            if entity2uname.has_key(id):
                if not account2def_group.get(id, None) == posix_group.posix_gid:
               	    members.append(entity2uname[id])
            else:
                raise ValueError, "Found no id: %s for group: %s" % (
                    id, gname)

        gline = join((gname, '*', gid, join(members, ',')))
        if len(gline) <= MAX_LINE_LENGTH:
            f.write(gline+"\n")
            groups[gname] = None
        else:
            groups[gname] = (gid, members)

    def make_name(base):
        name = base
        harder = False
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
    for g in groups.keys():
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
            f.write(join((gname, '*', gid, memb_str))+"\n")
            groups.setdefault(gname, None)
            gname = make_name(g)
        groups[g] = None
    if e_o_f:
	f.write('E_O_F\n')
    f.close()

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

def map_spread(id):
    try:
        return int(_SpreadCode(id))
    except Errors.NotFoundError:
        print "Error mapping %s" % id
        raise

def main():
    global debug
    global e_o_f
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dg:p:n:',
                                   ['debug', 'help', 'eof', 'group=',
                                    'passwd=', 'group_spread=',
                                    'user_spread=', 'netgroup='])
    except getopt.GetoptError:
        usage(1)

    user_spread = group_spread = None
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-d', '--debug'):
            debug += 1
        elif opt in ('--eof',):
            e_o_f = True
        elif opt in ('-g', '--group'):
            generate_group(val, group_spread, user_spread)
        elif opt in ('-p', '--passwd'):
            generate_passwd(val, user_spread)
        elif opt in ('-n', '--netgroup'):
            generate_netgroup(val, group_spread, user_spread)
        elif opt in ('--group_spread',):
            group_spread = map_spread(val)
        elif opt in ('--user_spread',):
            user_spread = map_spread(val)
        else:
            usage()
    if len(opts) == 0:
        usage(1)

def usage(exitcode=0):
    print """Usage: [options]
    -d | --debug
      Enable deubgging
    --group_spread value
      Filter by group_spread
    --user_spread value
      Filter by user_spread
    --eof
      End dump file with E_O_F to mark successful completion
    -p | --passwd outfile
      Write password map to outfile
    -g | --group outfile
      Write posix group map to outfile
    -n | --netgroup outfile
      Write netgroup map to outfile

    Generates a NIS map of the requested type for the requested spreads."""
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
