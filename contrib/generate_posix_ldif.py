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

import time, re, string, sys, getopt, base64, os

import cerebrum_path
import cereconf  
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.extlib import logging
from Cerebrum.Utils import Factory, latin1_to_iso646_60, SimilarSizeWriter
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum import QuarantineHandler
from Cerebrum.Constants import _SpreadCode

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)

logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
logger = logging.getLogger("cronjob")

entity2uname = {}
global dn_dict
dn_dict = {}
disablesync_cn = 'disablesync'

normalize_trans = string.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ\t\n\r\f\v",
    "abcdefghijklmnopqrstuvwxyz     ")



def init_ldap_dump(filename=None):
    if filename:
	f = file(filename, 'w')
    else:
	f = glob_fd
    init_str = "dn: %s\n" % (cereconf.LDAP_BASE)    
    init_str += "objectClass: top\n"
    for oc in cereconf.LDAP_BASE_OBJECTCLASS:
	init_str += "objectClass: %s\n" % oc
    init_str += "l: %s\n" % cereconf.LDAP_BASE_CITY
    for alt in cereconf.LDAP_BASE_ALTERNATIVE_NAME:
	init_str += "o: %s\n" % alt
    for des in cereconf.LDAP_BASE_DESCRIPTION:
	init_str += "description: %s\n" % des
    f.write(init_str)
    f.write("\n")
    for org in cereconf.LDAP_ORG_GROUPS:
	org = org.upper()
	org_name = str(getattr(cereconf, 'LDAP_' + org + '_DN'))
	init_str = "dn: %s=%s,%s\n" % (cereconf.LDAP_ORG_ATTR,org_name,cereconf.LDAP_BASE)
	init_str += "objectClass: top\n"
	for obj in cereconf.LDAP_ORG_OBJECTCLASS:
	    init_str += "objectClass: %s\n" % obj
	for ous in getattr(cereconf, 'LDAP_' + org + '_ALTERNATIVE_NAME'):
	    init_str += "%s: %s\n" % (cereconf.LDAP_ORG_ATTR,ous)
	init_str += "description: %s\n" % \
                    some2utf(getattr(cereconf, 'LDAP_' + org + '_DESCRIPTION'))
        try:
            for attrs in getattr(cereconf, 'LDAP_' + org + '_ADD_ATTR'):
                init_str += attrs + '\n'
        except AttributeError:
            pass
	init_str += '\n'
	f.write(init_str)
    if cereconf.LDAP_MAN_LDIF_ADD_FILE:
        try:
	    lfile = file(cereconf.LDAP_DUMP_DIR + '/' +
                         cereconf.LDAP_MAN_LDIF_ADD_FILE, 'r')
        except:
            pass
        else:
	    f.write(lfile.read().strip()) 
	    f.write('\n')
	    lfile.close()
    if filename:
	f.close()

def generate_users(spread=None,filename=None):
    posix_user = PosixUser.PosixUser(Cerebrum)
    disk = Factory.get('Disk')(Cerebrum)
    if spread: spreads = eval_spread_codes(spread)
    else: spreads = eval_spread_codes(cereconf.LDAP_USER_SPREAD)
    shells = {}
    for sh in posix_user.list_shells():
	shells[int(sh['code'])] = sh['shell']
    disks = {}
    for hd in disk.list(spread=spreads[0]):
	disks[int(hd['disk_id'])] = hd['path']  
    posix_dn = ",%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,
					cereconf.LDAP_USER_DN,
					cereconf.LDAP_BASE)
    posix_dn_string = "%s=" % cereconf.LDAP_USER_ATTR
    obj_string = "objectClass: top\n"
    for obj in cereconf.LDAP_USER_OBJECTCLASS:
	obj_string += "objectClass: %s\n" % obj
    if filename:
	f = file(filename,'w')
    else:
	f = glob_fd
    #done_users = {}
    # Change to uname2id
    # When all authentication-needing accounts possess an 'md5_crypt'
    # password hash, the below code can be fixed to call
    # list_extended_posix_users() only once.  Until then, we fall back
    # to using 'crypt3_des' hashes.
    #
    # We already favour the stronger 'md5_crypt' hash over any
    # 'crypt3_des', though.
    for auth_method in (co.auth_type_md5_crypt, co.auth_type_crypt3_des):
        prev_userid = 0
        for row in posix_user.list_extended_posix_users(auth_method, spreads, 
						include_quarantines = True):
            (acc_id, shell, gecos, uname) = (
                row['account_id'], row['shell'], row['gecos'],
                row['entity_name'])
            acc_id = int(acc_id)
            if entity2uname.has_key(acc_id):
                continue
            if row['auth_data'] is None:
                if auth_method == co.auth_type_crypt3_des:
                    # Neither md5_crypt nor crypt3_des hash found.
                    passwd = '{crypt}*Invalid'
                else:
                    continue
            else:
                passwd = "{crypt}%s" % row['auth_data']
            shell = shells[int(shell)]
            if row['quarantine_type'] is not None:
                qh = QuarantineHandler.QuarantineHandler(
                    Cerebrum, [row['quarantine_type']])
                if qh.should_skip():
                    continue
                if qh.is_locked():
                    passwd = '{crypt}*Locked'
                qshell = qh.get_shell()
                if qshell is not None:
                    shell = qshell
            if row['name']:
                cn = some2utf(row['name'])
            elif gecos:
                cn = some2utf(gecos)
            else:
                cn = uname
            if gecos:
                gecos = latin1_to_iso646_60(some2iso(gecos))
            else:
                gecos = latin1_to_iso646_60(some2iso(cn))
            if row['disk_id']:
                home = "%s/%s" % (disks[int(row['disk_id'])],uname)
            elif row['home']:
                home = row['home']
	    else:
                continue
            if acc_id <> prev_userid:
                f.write('dn: %s%s%s\n' % (posix_dn_string, uname, posix_dn))
                f.write('%scn: %s\n' % (obj_string, gecos))
                f.write('uid: %s\n' % uname)
                f.write('uidNumber: %s\n' % str(row['posix_uid']))
                f.write('gidNumber: %s\n' % str(row['posix_gid']))
                f.write('homeDirectory: %s\n' % home)
                f.write('userPassword: %s\n' % passwd)
                f.write('loginShell: %s\n' % shell)
                f.write('gecos: %s\n' % gecos)
                f.write('\n')
		entity2uname[acc_id] = uname
                prev_userid = acc_id
    f.write("\n")
    if filename:
	f.close()


def generate_posixgroup(spread=None,u_spread=None,filename=None):
    posix_group = PosixGroup.PosixGroup(Cerebrum)
    group = Factory.get('Group')(Cerebrum)
    if spread: spreads = eval_spread_codes(spread)
    else: spreads = eval_spread_codes(cereconf.LDAP_GROUP_SPREAD)
    if u_spread: u_spreads = eval_spread_codes(u_spread)
    else: u_spreads = eval_spread_codes(cereconf.LDAP_USER_SPREAD)
    if filename:
	f = file(filename, 'w')
    else:
	f = glob_fd
    groups = {}
    dn_str = "%s=%s,%s" % (cereconf.LDAP_ORG_ATTR, cereconf.LDAP_GROUP_DN,
                           cereconf.LDAP_BASE)
    obj_str = "objectClass: top\n"
    for obj in cereconf.LDAP_GROUP_OBJECTCLASS:
	obj_str += "objectClass: %s\n" % obj
    for row in posix_group.list_all_grp(spreads):
	posix_group.clear()
        posix_group.find(row.group_id)
        gname = posix_group.group_name
        pos_grp = "dn: %s=%s,%s\n" % (cereconf.LDAP_GROUP_ATTR, gname, dn_str)
        pos_grp += "%s" % obj_str
        pos_grp += "cn: %s\n" % gname
        pos_grp += "gidNumber: %s\n" % posix_group.posix_gid
        if posix_group.description:
            # latin1_to_iso646_60 later
            pos_grp += "description: %s\n" % some2utf(posix_group.description)
	group.clear()
        group.find(row.group_id)
        # Since get_members only support single user spread, spread is
        # set to [0]
        for id in group.get_members(spread=u_spreads[0], get_entity_name=True):
            uname_id = int(id[0])
            if not entity2uname.has_key(uname_id):
                entity2uname[uname_id] = id[1]
            pos_grp += "memberUid: %s\n" % entity2uname[uname_id]
	f.write("\n")
        f.write(pos_grp)
    f.write("\n")
    if filename:
	f.close()

def generate_netgroup(spread=None,u_spread=None,filename=None):
    global grp_memb
    pos_netgrp = Factory.get('Group')(Cerebrum)
    if filename:
        f = file(filename, 'w')
    else:
	f = glob_fd
    if spread: spreads = eval_spread_codes(spread)
    else: spreads = eval_spread_codes(cereconf.LDAP_NETGROUP_SPREAD)
    if u_spread: u_spreads = eval_spread_codes(u_spread)
    else: u_spreads = eval_spread_codes(cereconf.LDAP_USER_SPREAD)
    f.write("\n")
    dn_str = "%s=%s,%s" % (cereconf.LDAP_ORG_ATTR,
                           cereconf.LDAP_NETGROUP_DN,
                           cereconf.LDAP_BASE)
    obj_str = "objectClass: top\n"
    for obj in cereconf.LDAP_NETGROUP_OBJECTCLASS:
        obj_str += "objectClass: %s\n" % obj
    for row in pos_netgrp.list_all_grp(spreads):
	grp_memb = {}
        pos_netgrp.clear()
        pos_netgrp.find(row.group_id)
        netgrp_name = pos_netgrp.group_name
        netgrp_str = "dn: %s=%s,%s\n" % (cereconf.LDAP_NETGROUP_ATTR,
                                         netgrp_name, dn_str)
        netgrp_str += "%s" % obj_str
        netgrp_str += "cn: %s\n" % netgrp_name
        if not entity2uname.has_key(int(row.group_id)):
            entity2uname[int(row.group_id)] = netgrp_name
        if pos_netgrp.description:
            netgrp_str += "description: %s\n" % \
                          latin1_to_iso646_60(pos_netgrp.description)
        f.write(netgrp_str)
        get_netgrp(int(row.group_id), spreads, u_spreads, f)
        f.write("\n")
    if filename:
	f.close()

def get_netgrp(netgrp_id, spreads, u_spreads, f):
    pos_netgrp = Factory.get('Group')(Cerebrum)
    pos_netgrp.clear()
    pos_netgrp.entity_id = int(netgrp_id)
    for id in pos_netgrp.list_members(u_spreads[0], int(co.entity_account),\
						get_entity_name= True)[0]:
        uname_id,uname = int(id[1]),id[2]
        if ('_' not in uname) and not grp_memb.has_key(uname_id):
            f.write("nisNetgroupTriple: (,%s,)\n" % uname)
            grp_memb[uname_id] = True
    for group in pos_netgrp.list_members(None, int(co.entity_group),
						get_entity_name=True)[0]:
        pos_netgrp.clear()
        pos_netgrp.entity_id = int(group[1])
	if True in ([pos_netgrp.has_spread(x) for x in spreads]):
            f.write("memberNisNetgroup: %s\n" % group[2])
        else:
            get_netgrp(int(group[1]), spreads, u_spreads, f)


def eval_spread_codes(spread):
    spreads = []
    if isinstance(spread,(str,int)):
        if (spread_code(spread)):
            spreads.append(spread_code(spread))
    elif isinstance(spread,(list,tuple)):
        for entry in spread:
            if (spread_code(entry)):
                spreads.append(spread_code(entry))
    else:
        spreads = None
    return(spreads)


def spread_code(spr_str):
    spread=""
    #if isinstance(spr_str, _SpreadCode):
    #    return int(_SpreadCode(spr_str))
    try: spread = int(spr_str)
    except:
	try: spread = int(getattr(co, spr_str))
        except: 
	    try: spread = int(_SpreadCode(spr_str)) 
	    except:
		print "Not valid Spread-Code"
		spread = None
    return(spread)

#    return iso_str

# match an 8-bit string which is not an utf-8 string
iso_re = re.compile("[\300-\377](?![\200-\277])|(?<![\200-\377])[\200-\277]")

# match an 8-bit string
eightbit_re = re.compile('[\200-\377]')

# match multiple spaces
multi_space_re = re.compile('[%s]{2,}' % string.whitespace)

def some2utf(str):
    """Convert either iso8859-1 or utf-8 to utf-8"""
    if iso_re.search(str):
        str = unicode(str, 'iso8859-1').encode('utf-8')
    return str

def some2iso(str):
    """Convert either iso8859-1 or utf-8 to iso8859-1"""
    if eightbit_re.search(str) and not iso_re.search(str):
        str = unicode(str, 'utf-8').encode('iso8859-1')
    return str

    return ou_rdn_re.sub(' ', ou).strip()


def verify_printableString(str):
    """Not in use for the moment, remove this line if used """
    """Return true if STR is valid for the LDAP syntax printableString"""
    return printablestring_re.match(str)



def disable_ldapsync_mode():
    try:
	ldap_servers = cereconf.LDAP_SERVER
	from Cerebrum.modules import LdapCall
    except AttributeError:
	logger.info('No active LDAP-sync severs configured')
    except ImportError: 
	logger.info('LDAP modules missing. Probably python-LDAP')
    else:
	s_list = LdapCall.ldap_connect()
	LdapCall.add_disable_sync(s_list,disablesync_cn)
	LdapCall.end_session(s_list)
	logg_dir = cereconf.LDAP_DUMP_DIR + '/log'
	if os.path.isdir(logg_dir):  
	    rotate_file = '/'.join((logg_dir,'rotate_ldif.tmp'))
	    if not os.path.isfile(rotate_file):
		f = file(rotate_file,'w')
		f.write(time.strftime("%d %b %Y %H:%M:%S", time.localtime())) 
		f.close()

def main():
    global glob_fd
    glob_fd = SimilarSizeWriter(cereconf.LDAP_DUMP_DIR + "/" +  \
					cereconf.LDAP_POSIX_FILE)
    glob_fd.set_size_change_limit(10)
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'u:g:n:U:G:N:po',
					['help', 'group=','user=',
					'netgroup_spread=', 'group_spread=',
					'user_spread=', 'netgroup=','posix'])
    except getopt.GetoptError:
        usage(1)
    user_spread = group_spread = None
    p = {}
    for opt, val in opts:
	m_val = []
        if opt in ('--help',):
            usage()
	elif opt in ('-u', '--user'):
            p['u_file'] = val
	elif opt in ('-g', '--group'):
            p['g_file'] = val
	elif opt in ('-n', '--netgroup'):
            p['n_file'] = val
	elif opt in ('-U','--user_spread'):
	    [m_val.append(str(x)) for x in val.split(',')]
	    p['u_spr'] = eval_spread_codes(m_val)
	elif opt in ('-G','--group_spread',):
	    [m_val.append(str(x)) for x in val.split(',')]
	    p['g_spr'] = eval_spread_codes(m_val)
        elif opt in ('-N','--netgroup_spread',):
	    [m_val.append(str(x)) for x in val.split(',')]
            p['n_spr'] = eval_spread_codes(m_val)
	elif opt in ('--posix',):
	    disable_ldapsync_mode()
	    init_ldap_dump()
            generate_users()
            generate_posixgroup()
            generate_netgroup()
        else:
            usage()
    if len(opts) == 0:
        config()
    if p.has_key('n_file'):
        generate_netgroup(p.get('n_spr'), p.get('u_spr'), p.get('n_file'))
    if p.has_key('g_file'):
        generate_posixgroup(p.get('g_spr'), p.get('u_spr'), p.get('g_file'))
    if p.has_key('u_file'):
        generate_users(p.get('u_spr'), p.get('u_file'))
    glob_fd.close()

def usage(exitcode=0):
    print """Usage: [options]

 No option will generate a full dump with default values from cereconf.

  --user=<outfile>| -u <outfile> --user_spread=<value>|-U <value>
      Write users to a LDIF-file

  --group=<outfile>| -g <outfile>  --group_spread=<value>|-G <value> -U <value>
      Write posix groups to a LDIF-file

  --netgroup=<outfile>| -n <outfile> --netgroup_spread=<value>|-N <val> -U <val>
      Write netgroup map to a LDIF-file

  --posix
      write all posix-user,-group and -netgroup
      from default cereconf parameters

  Both --user_spread, --netgroup_spread  and --group_spread can handle
  multiple spread-values (<value> | <value1>,<value2>,,,)"""
    sys.exit(exitcode)

def config():
	disable_ldapsync_mode()
	init_ldap_dump()
	if (cereconf.LDAP_USER == 'Enable'):
	    generate_users()
	if (cereconf.LDAP_GROUP == 'Enable'):
	    generate_posixgroup()
	if (cereconf.LDAP_NETGROUP == 'Enable'):
	    generate_netgroup()
	else:
	    pass
	
if __name__ == '__main__':
    	main()
