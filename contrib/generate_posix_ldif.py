#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2002, 2003, 2004 University of Oslo, Norway
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

"""Usage: generate_posix_ldif.py [options]

Write user and group information to an LDIF file (if enabled in
cereconf), which can then be loaded into LDAP.

  --user=<outfile>      | -u <outfile>  Write users to a LDIF-file
  --filegroup=<outfile> | -f <outfile>  Write posix filegroups to a LDIF-file
  --netgroup=<outfile>  | -n <outfile>  Write netgroup map to a LDIF-file
  --posix  Write all of the above, plus optional top object and extra file,
           to a file given in cereconf (unless the above options override).
           Also disable ldapsync first.

With none of the above options, do the same as --posix.

  --user_spread=<value>      | -U <value>  (used by all components)
  --filegroup_spread=<value> | -F <value>  (used by --filegroup component)
  --netgroup_spread=<value>  | -N <value>  (used by --netgroup component)

The spread options accept multiple spread-values (<value1>,<value2>,...)."""

import time
import sys
import getopt
import os.path

import cerebrum_path
import cereconf  
from Cerebrum.Utils import Factory, latin1_to_iso646_60
from Cerebrum.modules import PosixUser, PosixGroup
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.modules.LDIFutils import *

db = Factory.get('Database')()
co = Factory.get('Constants')(db)

logger = Factory.get_logger("cronjob")

entity2name = {}
disablesync_cn = 'disablesync'


def init_ldap_dump():
    if cereconf.LDAP_POSIX.get('dn'):
        glob_fd.write(container_entry_string('POSIX'))


def generate_users(spread=None,filename=None):
    posix_user = PosixUser.PosixUser(db)
    account = Factory.get('Account')(db)
    disk = Factory.get('Disk')(db)
    spread = map_spreads(spread or cereconf.LDAP_USER['spread'], int)
    shells = {}
    for sh in posix_user.list_shells():
	shells[int(sh['code'])] = sh['shell']
    disks = {}
    for hd in disk.list(spread=spread):
	disks[int(hd['disk_id'])] = hd['path']  
    quarantines = {}
    now = db.DateFromTicks(time.time())
    for row in account.list_entity_quarantines(
            entity_types = co.entity_account):
        if (row['start_date'] <= now
            and (row['end_date'] is None or row['end_date'] >= now)
            and (row['disable_until'] is None or row['disable_until'] < now)):
            # The quarantine in this row is currently active.
            quarantines.setdefault(int(row['entity_id']), []).append(
                int(row['quarantine_type']))
    posix_dn = "," + ldapconf('USER', 'dn')
    f = ldif_outfile('USER', filename, glob_fd)
    f.write(container_entry_string('USER'))

    # When all authentication-needing accounts possess an 'md5_crypt'
    # password hash, the below code can be fixed to call
    # list_extended_posix_users() only once.  Until then, we fall back
    # to using 'crypt3_des' hashes.
    #
    # We already favour the stronger 'md5_crypt' hash over any
    # 'crypt3_des', though.
    for auth_method in (co.auth_type_md5_crypt, co.auth_type_crypt3_des):
        for row in posix_user.list_extended_posix_users(auth_method, spread, 
						include_quarantines = False):
            (acc_id, shell, gecos, uname) = (
                row['account_id'], row['shell'], row['gecos'],
                row['entity_name'])
            acc_id = int(acc_id)
            if entity2name.has_key(acc_id):
                continue
            if row['auth_data']:
                passwd = "{crypt}" + row['auth_data']
            elif auth_method != co.auth_type_crypt3_des:
                # Get the password in the next pass.
                continue
            else:
                # Final pass - neither md5_crypt nor crypt3_des hash found.
                passwd = "{crypt}*Invalid"
            shell = shells[int(shell)]
            if acc_id in quarantines:
                qh = QuarantineHandler(db, quarantines[acc_id])
                if qh.should_skip():
                    continue
                if qh.is_locked():
                    passwd = "{crypt}*Locked"
                qshell = qh.get_shell()
                if qshell is not None:
                    shell = qshell
            if row['disk_id']:
                home = "%s/%s" % (disks[int(row['disk_id'])],uname)
            elif row['home']:
                home = row['home']
	    else:
                continue
            cn = row['name'] or gecos or uname
            gecos = latin1_to_iso646_60(gecos or cn)
            f.write("".join((
                "dn: "              "uid=", uname, posix_dn, "\n"
                "objectClass: "     "top"           "\n"
                "objectClass: "     "account"       "\n"
                "objectClass: "     "posixAccount"  "\n"
                "cn: ",             iso2utf(cn),    "\n"
                "uid: ",            uname,          "\n"
                "uidNumber: ",      str(int(row['posix_uid'])), "\n"
                "gidNumber: ",      str(int(row['posix_gid'])), "\n"
                "homeDirectory: ",  home,           "\n"
                "userPassword: ",   passwd,         "\n"
                "loginShell: ",     shell,          "\n"
                "gecos: ",          gecos,          "\n"
                "\n")))
            entity2name[acc_id] = uname
    end_ldif_outfile('USER', f, glob_fd)


def generate_posixgroup(spread=None, u_spread=None, filename=None):
    posix_group = PosixGroup.PosixGroup(db)
    group = Factory.get('Group')(db)
    spreads = map_spreads(spread or cereconf.LDAP_FILEGROUP['spread'])
    u_spread = map_spreads(u_spread or cereconf.LDAP_USER['spread'], int)
    f = ldif_outfile('FILEGROUP', filename, glob_fd)
    f.write(container_entry_string('FILEGROUP'))

    groups = {}
    dn_str = ldapconf('FILEGROUP', 'dn')
    for row in posix_group.list_all_grp(spreads):
	posix_group.clear()
        posix_group.find(row.group_id)
        gname = iso2utf(posix_group.group_name)
        members = []
        entry = {'objectClass': ('top', 'posixGroup'),
                 'cn':          (gname,),
                 'gidNumber':   (str(int(posix_group.posix_gid)),),
                 'memberUid':   members}
        if posix_group.description:
            # latin1_to_iso646_60 later
            entry['description'] = (iso2utf(posix_group.description),)
	group.clear()
        group.find(row.group_id)
        # Since get_members only support single user spread, spread is
        # set to [0]
        for id in group.get_members(spread=u_spread, get_entity_name=True):
            uname_id = int(id[0])
            if not entity2name.has_key(uname_id):
                entity2name[uname_id] = id[1]
            members.append(entity2name[uname_id])
        f.write(entry_string("cn=%s,%s" % (gname, dn_str), entry, False))
    end_ldif_outfile('FILEGROUP', f, glob_fd)


def generate_netgroup(spread=None, u_spread=None, filename=None):
    global grp_memb
    pos_netgrp = Factory.get('Group')(db)
    f = ldif_outfile('NETGROUP', filename, glob_fd)
    f.write(container_entry_string('NETGROUP'))

    spreads = map_spreads(spread or cereconf.LDAP_NETGROUP['spread'])
    u_spread = map_spreads(u_spread or cereconf.LDAP_USER['spread'], int)
    dn_str = ldapconf('NETGROUP', 'dn')
    for row in pos_netgrp.list_all_grp(spreads):
	grp_memb = {}
        pos_netgrp.clear()
        pos_netgrp.find(row.group_id)
        netgrp_name = iso2utf(pos_netgrp.group_name)
        entry = {'objectClass':       ('top', 'nisNetGroup'),
                 'cn':                (netgrp_name,),
                 'nisNetgroupTriple': [],
                 'memberNisNetgroup': []}
        if not entity2name.has_key(int(row.group_id)):
            entity2name[int(row.group_id)] = netgrp_name
        if pos_netgrp.description:
            entry['description'] = (
                latin1_to_iso646_60(pos_netgrp.description),)
        get_netgrp(pos_netgrp, spreads, u_spread,
                   entry['nisNetgroupTriple'], entry['memberNisNetgroup'])
        f.write(entry_string("cn=%s,%s" % (netgrp_name, dn_str), entry, False))
    end_ldif_outfile('NETGROUP', f, glob_fd)


def get_netgrp(pos_netgrp, spreads, u_spread, triples, members):
    for id in pos_netgrp.list_members(u_spread, int(co.entity_account),\
						get_entity_name= True)[0]:
        uname_id,uname = int(id[1]),id[2]
        if ("_" not in uname) and not grp_memb.has_key(uname_id):
            triples.append("(,%s,)" % uname)
            grp_memb[uname_id] = True
    for group in pos_netgrp.list_members(None, int(co.entity_group),
						get_entity_name=True)[0]:
        pos_netgrp.clear()
        pos_netgrp.entity_id = int(group[1])
	if filter(pos_netgrp.has_spread, spreads):
            members.append(iso2utf(group[2]))
        else:
            get_netgrp(pos_netgrp, spreads, u_spread, triples, members)


def disable_ldapsync_mode():
    ldap_servers = cereconf.LDAP.get('server')
    if ldap_servers is None:
	logger.info("No active LDAP-sync servers configured")
        return
    try:
	from Cerebrum.modules import LdapCall
    except ImportError: 
	logger.info("LDAP modules missing. Probably python-LDAP")
    else:
	s_list = LdapCall.ldap_connect()
	LdapCall.add_disable_sync(s_list,disablesync_cn)
	LdapCall.end_session(s_list)
	log_dir = os.path.join(cereconf.LDAP['dump_dir'], "log")
	if os.path.isdir(log_dir):  
	    rotate_file = os.path.join(log_dir, "rotate_ldif.tmp")
	    if not os.path.isfile(rotate_file):
		f = file(rotate_file,'w')
		f.write(time.strftime("%d %b %Y %H:%M:%S", time.localtime())) 
		f.close()


def main():
    short2long_opts = (("u:", "U:", "f:", "F:", "n:", "N:"),
                       ("user=",      "user_spread=",
                        "filegroup=", "filegroup_spread=",
                        "netgroup=",  "netgroup_spread="))
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "".join(short2long_opts[0]),
                                   ("help", "posix") + short2long_opts[1])
        opts = dict(opts)
    except getopt.GetoptError, e:
        usage(str(e))
    if args:
        usage("Invalid arguments: " + " ".join(args))
    if "--help" in opts:
        usage()
    # Copy long options into short options
    for short, long in zip(*short2long_opts):
        val = opts.get("--" + long.replace("=", ""))
        if val is not None:
            opts["-" + short.replace(":", "")] = val

    got_file = filter(opts.has_key, ("-u", "-f", "-n"))
    for opt in filter(opts.has_key, ("-U", "-F", "-N")):
        opts[opt] = map_spreads(opts[opt].split(","))
    do_all = "--posix" in opts or not got_file

    global glob_fd
    glob_fd = None
    if do_all:
        glob_fd = ldif_outfile('POSIX')
        disable_ldapsync_mode()
        init_ldap_dump()
    for var, func, args in \
            (('LDAP_USER',      generate_users,            ("-U", "-u")),
             ('LDAP_FILEGROUP', generate_posixgroup, ("-F", "-U", "-f")),
             ('LDAP_NETGROUP',  generate_netgroup,   ("-N", "-U", "-n"))):
        if (do_all or args[-1] in opts) and getattr(cereconf, var).get('dn'):
            func(*map(opts.get, args))
        elif args[-1] in opts:
            sys.exit("Option %s requires cereconf.%s['dn']." % (args[-1], var))
    if glob_fd:
        end_ldif_outfile('POSIX', glob_fd)


def usage(err=0):
    if err:
        print >>sys.stderr, err
    print >>sys.stderr, __doc__
    sys.exit(bool(err))


if __name__ == '__main__':
    	main()

# arch-tag: a8422a23-97b1-4ac9-a1f1-023ff76a4935
