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

""" 	The ldapqsync module is a module that use pythonldap-module to 
	dynamic update the LDAP-servers by using the change_log and
	fetch information from the database. It will update the LDAP-servers
	with LDAP/SSL and log it in LDIF-format."""

#import ldap, ldapurl, locale, getopt, base64
import ldif, sys, os, re, time, string 
import cerebrum_path
import cereconf
from ldap import modlist
from Cerebrum import Errors
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum import Disk
from Cerebrum import Entity
from Cerebrum import QuarantineHandler 
from Cerebrum.Utils import Factory,latin1_to_iso646_60
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum.modules import Ldap
from Cerebrum.Constants import _SpreadCode
from Cerebrum.extlib import logging
from Cerebrum.modules import CLHandler
from Cerebrum.modules import ChangeLog
from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import get_tree_dn

db = Factory.get('Database')()
const = Factory.get('CLConstants')(db)
co = Factory.get('Constants')(db)
dis_sync_cn = 'disablesync'
cltype = {}
cl_entry = {'group_mod' : 'pass', 				
	'group_add' : 'group_mod(cll.change_type_id,cll.subject_entity,\
					cll.dest_entity,cll.change_id)',
	'group_rem' : 'group_mod(cll.change_type_id,cll.subject_entity,\
					cll.dest_entity,cll.change_id)',
	'account_mod' : 'mod_account(cll.subject_entity,i)',
	'spread_add' : 'change_spread(cll.subject_entity,cll.change_type_id,\
							cll.change_params)',
	'spread_del' : 'change_spread(cll.subject_entity,cll.change_type_id,\
							cll.change_params)',
	'quarantine_add' : 'change_quarantine(cll.subject_entity,\
							cll.change_type_id)',
	'quarantine_mod' : 'change_quarantine(cll.subject_entity,\
							cll.change_type_id)',
	'quarantine_del' : 'change_quarantine(cll.subject_entity,\
							cll.change_type_id)'}

global user_dn, person_dn, group_dn, ngroup_dn
user_dn   = get_tree_dn('USER')
person_dn = get_tree_dn('PERSON')
group_dn  = get_tree_dn('GROUP')
ngroup_dn = get_tree_dn('NETGROUP')



def mod_account(dn_id,i):
    j = i + 1
    account = Account.Account(db)
    account.clear()
    account.find(dn_id)
    if (j < len(ch_log_list)):
	try:
	    if ((ch_log_list[j]['change_type_id']) == \
			int(const.account_password)):
		change_passwd(dn_id)
	except: pass 
    else:
	if True in [account.has_spread(x) for x in u_spreads]:
	    search_str = "uid=%s" % account.account_name
	    ldap_entry = lc.get_ldap_value(user_dn,search_str,None)
	    dn_str,ldap_entry_u = ldap_entry[0][0]
	    base_entry = get_user_info_dict(dn_id)
	    for entry in base_entry.keys():
		if (ldap_entry_u[entry] <> base_entry[entry]):
		    value =  (str(base_entry[entry]))[2:-2]
		    lc.mod_ldap(ldap.MOD_REPLACE,entry,value,dn_str)

def get_user_info_dict(dn_id):
    return_dict = {}
    for entry in get_user_info(dn_id):
	return_dict[entry[0]] = entry[1]
    return(return_dict)


def change_passwd(dn_id):
    acc = Account.Account(db)
    acc.find(int(dn_id))
    search_str = "uid=%s" % acc.account_name
    search_dn = "%s,%s" % (search_str,user_dn)
    passwd_attr = 'userPassword'
    attr_list = []
    try:
    	new_passwd = "{crypt}%s" % \
		acc.get_account_authentication(co.auth_type_md5_crypt)
    except Errors.NotFoundError: 
	try:
	    new_passwd = "{crypt}%s" % \
		acc.get_account_authentication(co.auth_type_crypt3_des)
	except Errors.NotFoundError: new_passwd = '*Invalid'
    if (acc.get_entity_quarantine() <> []): new_passwd = '*Invalid'
    attr_list.append(passwd_attr)
    if True in ([acc.has_spread(x) for x in u_spreads]):
	ldap_res = lc.get_ldap_value(user_dn,search_str,attr_list)
	if ldap_res <> []:
	    lc.mod_ldap(ldap.MOD_REPLACE,passwd_attr,new_passwd,search_dn)
    if (lc.get_ldap_value(person_dn,search_str,None) <> []):
	lc.mod_ldap(ldap.MOD_REPLACE,passwd_attr,new_passwd,pers_dn)	

def change_quarantine(dn_id,ch_type):
    posusr = PosixUser.PosixUser(db)
    try:
	posusr.find(dn_id)
    except Errors.NotFoundError: 
	logger.info("ID:%s was no account!" % dn_id)
    if True in [posusr.has_spread(x) for x in u_spreads]:
	spread_u = True
    else: spread_u = False
    search_str = "uid=%s" % posusr.account_name
    search_dn = "%s,%s" % (search_str,user_dn)
    user = {}
    passwd = 'userPassword'
    shells = 'loginShell'
    try:
	user[passwd] = "{crypt}%s" % \
		posusr.get_account_authentication(co.auth_type_md5_crypt)
    except Errors.NotFoundError:
        try:
	    user[passwd] = "{crypt}%s" % \
		posusr.get_account_authentication(co.auth_type_crypt3_des)
	except Errors.NotFoundError: 
		user[passwd] = '*Invalid'
    ldap_people_res = lc.get_ldap_value(person_dn,search_str,None)
    pers_string = '%s,%s' % (search_str,person_dn)
    quaran = eval_quarantine(dn_id)
    if (int(ch_type) == int(co.quarantine_del)) and not quaran and spread_u:
	lc.mod_ldap(ldap.MOD_REPLACE,shells,
			posixuser.shell,search_dn)
	lc.mod_ldap(ldap.MOD_REPLACE,passwd,
			user[passwd],search_dn)
	if ldap_people_res:
	    lc.mod_ldap(ldap.MOD_REPLACE,passwd,user[passwd],pers_string)
    elif quaran and spread_u:
	for attr,value in quaran.items():
	    lc.mod_ldap(ldap.MOD_REPLACE,attr,value,search_dn)
        if ldap_people_res:
            lc.mod_ldap(ldap.MOD_REPLACE,passwd,quaran[passwd],pers_string)
    elif ldap_people_res and not spread_u:
	if (int(ch_type) == int(co.quarantine_del)) and quaran:
	    lc.mod_ldap(ldap.MOD_REPLACE,passwd,new_passwd,pers_string)
	elif quaran:
	    new_passwd = '*Locked'
	    lc.mod_ldap(ldap.MOD_REPLACE,passwd,quaran[passwd],pers_string)
    else: pass

def eval_quarantine(dn_id):
    account = Account.Account(db)
    account.find(dn_id)
    now = db.DateFromTicks(time.time())
    quarantines = []
    for row in account.get_entity_quarantine():
	if (row['start_date'] <= now
                    and (row['end_date'] is None or row['end_date'] >= now)
                    and (row['disable_until'] is None
                         or row['disable_until'] < now)):
	    quarantines.append(row['quarantine_type'])
    if quarantines == []:
	return(None)
    else:
	params = {}
	qh = QuarantineHandler.QuarantineHandler(db, quarantines)
	if qh.should_skip():
	    pass #raise UserSkipQuarantine
	if qh.is_locked():
	    params['userPassword'] = '[crypt]*locked'
	qshell = qh.get_shell()
	if qshell is not None:
	   params['loginShell'] = qshell
	return(params)


def change_spread(dn_id,ch_type,ch_params):
    """Spread can be users, filegroup or netgroup. Since e_account.create 
    not necesary include spread to posix, creation of user-,filegroup- and
    netgroup-record will be based on add/mod/del spread"""
    entity = Entity.Entity(db)
    try:
	entity.find(int(dn_id))
    except Errors.NotFoundError:
	return
    if entity.entity_type == int(co.entity_account):
	change_user_spread(dn_id,ch_type,ch_params)
    elif entity.entity_type == int(co.entity_group):
	 change_group_spread(dn_id,ch_type,ch_params)
    else:
	logger.info("Change_spread did not resolve request (%s,%s)" 
					% (dn_id,ch_type)) 

def change_group_spread(dn_id,ch_type,ch_params):
    group = Group.Group(db)
    #posgrp = PosixGroup.PosixGroup(db)
    try:
	group.find(int(dn_id))
    except Errors.NotfoundError:
	# Not sure whats happening if group is deleted
	# maybe it should search as entity and not group
	logger.info("Fault could not find group: %d " % dn_id)
	return
    search_dn = "cn=%s" % group.group_name
    param_list = string.split(ch_params,'\n')
    cl_spread = int(re.sub('\D','',param_list[3]))
    if cl_spread in g_spreads:
	search_dn = "%s,%s" % (search_str,group_dn)
	if True in [group.has_spread(x) for x in g_spreads]:
	    spread_stat = True
	else:
	    spread_stat = False
	ldap_res = lc.get_ldap_value(group_dn,search_str,None)
	if (ch_type == int(const.spread_del)) and not spread_stat and ldap_res <> []:
	    lc.delete_ldap(search_dn)
	elif (ch_type == int(const.spread_add)) and spread_stat and ldap_res == []:
	    grp_list = get_group_info(dn_id)
	    lc.add_ldap(search_dn,grp_list)
	else:
	    logger.info("Could not resolve changelog request on group: %s" % \
							group.group_name) 
    elif cl_spread in n_spreads:
	search_dn = "%s,%s" % (search_str,ngroup_dn)
        if True in [group.has_spread(x) for x in n_spreads]:
            spread_stat = True
        else:
            spread_stat = False
        ldap_res = lc.get_ldap_value(group_dn,search_str,None)
        if (int(ch_type) == int(const.spread_del)) and not spread_stat and \
							ldap_res <> []:
            lc.delete_ldap(search_dn)
        elif (int(ch_type) == int(const.spread_add)) and spread_stat and \
							ldap_res == []:
            grp_list = get_netgroup_info(dn_id)
            lc.add_ldap(search_dn,grp_list)
        else:
            logger.info("Could not resolve changelog request on group: %s" % \
                                                        group.group_name)
    else:
	pass



def change_user_spread(dn_id, ch_type, ch_params):
    account = Account.Account(db)
    group = Group.Group(db)
    param_list = []
    param_list = string.split(ch_params,'\n')
    cl_spread = int(re.sub('\D','',param_list[3]))
    if cl_spread in u_spreads:
	account.find(dn_id)
	search_str = "uid=%s" % account.account_name
	search_dn = "%s,%s" % (search_str,user_dn)
	if (ch_type == int(const.spread_del)):
	    for entry in lc.get_ldap_value(user_dn,search_str,None):
		lc.delete_ldap_serv(search_dn,entry[1])
	    for grp in group.list_groups_with_entity(dn_id):
		user_add_del_grp(const.group_rem,dn_id,grp['group_id'])
	elif (ch_type == int(const.spread_add)):
	    usr_list = get_user_info(dn_id)
	    ldap_res = lc.get_ldap_value(user_dn,search_str,None)
	    if (ldap_res == []):
		lc.add_ldap(search_dn,usr_list)
	    else:
		for serv in s_list.keys():
		    if serv in [x[1] for x in ldap_res]:
			logger.info("\n# User: %s exist in server: %s" % \
						(account.account_name,serv))
		    else: lc.add_ldap_serv(search_dn,usr_list,serv)
	    for grp in group.list_groups_with_entity(dn_id):
		 user_add_del_grp(const.group_add,dn_id,grp['group_id'])
	
	
def get_user_info(dn_id):
    pos = PosixUser.PosixUser(db)
    shells = {}
    for sh in pos.list_shells():
	shells[int(sh['code'])] = sh['shell']
    objcl_list = ['top', 'account', 'posixAccount']
    try:
	pos.clear()
	pos.find(dn_id)
	r_name = pos.get_gecos()
	cn_name = some2utf(r_name)
	if not pos.gecos:
	    gecos = latin1_to_iso646_60(some2iso(r_name))
	else:
	    gecos = latin1_to_iso646_60(some2iso(pos.gecos))
	user_home = pos.get_posix_home(u_spreads[0])
	user_shell = shells[int(pos.shell)]
	if not cn_name:
	    cn_name = pos.get_gecos()
	try:
	    passwd = "{crypt}%s" % \
		pos.get_account_authentication(co.auth_type_md5_crypt)
	except Errors.NotFoundError:
	    try:
		passwd = "{crypt}%s" % \
			pos.get_account_authentication(co.auth_type_crypt3_des)
	    except Errors.NotFoundError: passwd = '{crypt}*Invalid'
	quaran = eval_quarantine(dn_id)
	if quaran is not None:
	    try:
	    	passwd = quaran['userPassword']
	    	user_shell = quaran['loginShell']
	    except: pass
	ldif_list = modlist.addModlist({'objectClass': objcl_list,
					'cn': [cn_name],
					'uid': [pos.account_name],
					'uidNumber': [str(pos.posix_uid)],
					'gidNumber': [str(pos.gid_id)],
					'homeDirectory': [user_home],
					'userPassword': [passwd],
					'loginShell': [user_shell],
					'gecos': [gecos]})
	return(ldif_list)
    except: 
	logger.info("Not valid user-info of user: %s" % dn_id) 
	return(None)

iso_re = re.compile("[\300-\377](?![\200-\277])|(?<![\200-\377])[\200-\277]")

eightbit_re = re.compile('[\200-\377]')

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

def get_group_info(dn_id):
    posixgroup = PosixGroup.PosixGroup(db)
    try:
	posixgroup.find(dn_id)
	objcl_list = ['top', 'posixGroup']
	ldif_list = modlist.addModlist({'objectClass': objcl_list})
	ldif_list.append(('cn',[posixgroup.group_name]))
	ldif_list.append(('gidNumber',[str(posixgroup.posix_gid)]))
	if posixgroup.description:
	    ldif_list.append(('description', 
		[latin1_to_iso646_60(some2iso(posixgroup.description))]))
	member = []
	for memb in posixgroup.get_members(spread=u_spreads[0],\
					get_entity_name=True):
	    member.append(memb[1])
	ldif_list.append(('memberUid',member))
    	return(ldif_list)
    except Errors.NotFoundError: return(None)

def get_netgroup_info(dn_id):
    group = Group.Group(db)
    try:
        group.find(dn_id)
        objcl_list = ['top', 'nisNetGroup']
        ldif_list = modlist.addModlist({'objectClass': objcl_list})
        ldif_list.append(('cn',[group.group_name]))
        if group.description:
            ldif_list.append(('description', 
			[latin1_to_iso646_60(some2iso(group.description))]))
        members = []
	groups = []
	get_netgroup_mem(dn_id,members,groups)
        ldif_list.append(('nisNetgroupTriple',members))
	ldif_list.append(('membernisNetgroup',groups))
        return(ldif_list)
    except Errors.NotFoundError: return(None)

def get_netgroup_mem(netgrp_id,members,groups):
    pos_netgrp = Factory.get('Group')(db)
    pos_netgrp.clear()
    pos_netgrp.entity_id = int(netgrp_id)
    for uname in [id[2] for id in pos_netgrp.list_members(u_spreads[0],\
			int(co.entity_account),get_entity_name= True)[0]]:    
        if ('_' not in uname) and uname not in members: members.append(uname)
    for group in pos_netgrp.list_members(None, int(co.entity_group)\
					,get_entity_name=True)[0]:
        pos_netgrp.clear()
        pos_netgrp.entity_id = int(group[1])
        if True in ([pos_netgrp.has_spread(x) for x in n_spreads]):
	    groups.append(group[2])
        else:
            get_netgrp(int(group[1]),members,groups)
 
 

def group_mod(ch_type,dn_id,dn_dest,log_id):
    entity = Entity.Entity(db)
    entity.clear()
    entity.find(dn_id)
    if True in ([entity.has_spread(x) for x in u_spreads]):
	user_add_del_grp(ch_type,dn_id,dn_dest)
    elif (int(entity.entity_type) == int(co.entity_group)): 
	if True in [entity.has_spread(x) for x in n_spreads]:
	    add_netg2netg(ch_type,dn_id,dn_dest)
	if True in [entity.has_spread(x) for x in g_spreads]:
	    group = Group.Group(db)
	    group.entity_id = int(dn_id)
	    for mem in group.get_members(spread=u_spreads[0]):
		user_add_del_grp(ch_type,mem,dn_dest)
    	if not True in [entity.has_spread(x) for x in (n_spreads + g_spreads)]:
	    for mem in group.get_members(get_members(spread=u_spreads[0])):
                user_add_del_grp(ch_type,mem,dn_dest)
     

def add_netg2netg(ch_type,dn_id,dn_dest):
    posgrp = PosixGroup.PosixGroup(db)
    posgrp.clear()
    posgrp.find(int(dn_dest))
    if True in [posgrp.has_spread(x) for x in n_spreads]:
	cn = "cn=%s" % posgrp.group_name
	dn = cn + ',' + ngroup_dn
	ng__attr = 'memberNisNetgroup'
	posgrp.clear()
	posgrp.find(int(dn_id))
        search_dn = "(&(%s)(%s=%s))" % (cn,ng_attr,posgrp.group_name)
        ldap_value = lc.get_ldap_value(ngroup_dn,search_dn,[ng_attr,])
	if (int(ch_type) == int(const.group_add)):
	    if (ldap_value == []):
		lc.mod_ldap(ldap.MOD_ADD,ng_attr,posgrp.group_name,dn)
	    else:
		for serv in s_list.keys():
		    if serv in [x[1] for x in ldap_value]:
			logger.info('\n# %s: Group:%s already in group:%s'\
						% (serv,posgrp.group_name,cn))
		    else:
			lc.mod_ldap_serv(ldap.MOD_ADD,ng_attr,posgrp.group_name,\
									dn,serv)
	elif (int(ch_type) == int(const.group_rem)):
    	    if (ldap_value == []):
		logger.info('Group:%s doesent exist in group:%s' \
						% (posgrp.group_name,cn))
	    else:
		for serv in s_list.keys():
                    if serv in [x[1] for x in ldap_value]:
                        lc.mod_ldap_serv(ldap.MOD_DELETE,ng_attr,\
						posgrp.group_name,dn,serv)
		    else:
			 logger.info('%s: Group:%s already in group:%s'\
                                                % (serv,posgrp.group_name,cn))



def user_add_del_grp(ch_type,user_id,dn_dest):
    group = Group.Group(db)
    account = Account.Account(db)
    account.entity_id = int(user_id)
    group.clear()
    group.entity_id = int(dn_dest)
    if True in ([group.has_spread(x) for x in g_spreads]):
	grp_list = [int(dn_dest),]
    else: grp_list = []
    for grp in get_groups(group.entity_id,g_spreads,grp_list,fg=True):
	group.clear()
	group.entity_id = int(grp)
	dn = "cn=%s,%s" % (group.get_name(co.group_namespace),group_dn)
	memb_attr = 'memberUid'
	user = account.get_name(co.account_namespace)
	memb_id = '%s=%s' % (memb_attr,user)
	ldap_value = lc.get_ldap_value(dn,memb_id)
	if (ch_type == const.group_add):
	    if (ldap_value == []):
		lc.mod_ldap(ldap.MOD_ADD,memb_attr,user,dn)
	    else:
		mod_s = []
		for entry in ldap_value:
		    mod_s.append(entry[1])
		for serv,value in s_list.items():
		    if serv in mod_s:
			logger.info('%s: User:%s already in group:%s'\
								%(serv,user,dn))
		    else: 
			lc.mod_ldap_serv(ldap.MOD_ADD,memb_attr,user,\
									dn,serv)
	elif (ch_type == const.group_rem):
	    mem_list = [(mem[1]) for mem in group.get_members(spread=\
					u_spreads[0],get_entity_name=True)]
	    if user not in mem_list:
		for ldap_entry in ldap_value:
		    lc.mod_ldap_serv(ldap.MOD_DELETE,memb_attr,user,dn,\
							ldap_entry[1])  
	else: logger.info("Uknown command at log ")
    group.clear()
    group.entity_id = int(dn_dest)
    if True in ([group.has_spread(x) for x in n_spreads]):
        grp_list = [int(dn_dest),]
    else: 
	ng_list = []
	grp_list = get_groups(group.entity_id,n_spreads,ng_list,fg=False)
    for grp in grp_list:
	group.clear()
        group.entity_id = int(grp)
        cn = "cn=%s" % group.get_name(co.group_namespace)
	dn = "%s,%s" % (cn,ngroup_dn)
        mem_attr = 'nisNetgroupTriple'
	acc_name = account.get_name(co.account_namespace)
        user = '(,%s,)' % acc_name
        mem_id = '%s=%s' % (mem_attr,user)
        ldap_value = lc.get_ldap_value(ngroup_dn,cn)
	if (ch_type == const.group_add) and (ldap_value <> None) and \
							(ldap_value <> []):
	    for entry in ldap_value:
		if entry[0][1].has_key('nisNetgroupTriple'):
		    pres_value = entry[0][1]['nisNetgroupTriple']
		    if user not in pres_value:
			pres_value.append(user)
			lc.mod_ldap_serv(ldap.MOD_REPLACE,mem_attr,
					pres_value,dn,entry[1],list=True)
		else: 
		    lc.mod_ldap_serv(ldap.MOD_ADD,mem_attr,[user,],\
						dn,entry[1],list=True)
	if (ch_type == const.group_rem) and (ldap_value <> []) and \
						(ldap_value <> None):
	    cer_mem = [x[2] for x in group.list_members(spread=u_spreads[0],\
			member_type=co.entity_account,get_entity_name= True)[0]]
	    if acc_name not in cer_mem:
	    	for entry in ldap_value:
		    if entry[0][1].has_key('nisNetgroupTriple'):
			pres_value = entry[0][1]['nisNetgroupTriple']
			if user in pres_value:
			    pres_value.remove(user)
			    lc.mod_ldap_serv(ldap.MOD_REPLACE,mem_attr,\
					pres_value,dn,entry[1],list=True)

		    
	


def iso2utf(s):
    """Convert iso8859-1 to utf-8"""
    utf_str = unicode(s,'iso-8859-1').encode('utf-8')
    return utf_str


def get_groups(grp_id,spreads,grp_list,fg=False):
    # Pain: En såkalt "supergruppe" kan få nye medlemmer og da 
    # må disse nye medlemene  knyttes til § 
    # 
    group = Group.Group(db)
    for entry in group.list_groups_with_entity(grp_id):
	if (int(entry['member_type']) == int(co.entity_group)):
	    group.clear()
	    group.entity_id = int(entry['group_id'])
	    if (fg and True in [group.has_spread(x) for x in spreads]):
		grp_list.append(int(entry['group_id']))
	    	get_groups(group.entity_id,spreads,grp_list,fg)
	    elif (not fg and True in [group.has_spread(x) for x in spreads]):
		grp_list.append(int(entry['group_id']))
    return(grp_list)
    


def file_exist(filename):
    if os.path.isfile(filename):
	return(1)
    else: return(None)
    
def load_cltype_table(cltype):
    for clt,proc in cl_entry.items():
	# make if-entry to list in cereconf to remove dynamic service
	cltype[int(getattr(co,clt))] = proc	


def main():
    # Recieve info from CLhandler or started by job_runner
    # and fetch entry in a tupple. 5 type of changes:
    # add, delete and mod DN and add and delete attributes in DN
    # add and delete 
    clh = CLHandler.CLHandler(db)
    global logger,ch_log_list, u_spreads, g_spreads, n_spreads, lc
    u_spreads = [int(getattr(co,x)) for x in cereconf.LDAP_USER_SPREAD]
    g_spreads = [int(getattr(co,x)) for x in cereconf.LDAP_GROUP_SPREAD]
    n_spreads = [int(getattr(co,x)) for x in cereconf.LDAP_NETGROUP_SPREAD]
    load_cltype_table(cltype)
    logg_dir = cereconf.LDAP_DUMP_DIR + '/log'
    if not os.path.isdir(logg_dir):
	os.makedirs(logg_dir, mode = 0770)
    logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
    logger = logging.getLogger("console")
    if os.path.exists(logg_dir + '/' + 'rotate_ldif.tmp'):
	args = ['-f','-f','-s','',logg_dir +'/log.conf']
	os.spawnvp(os.P_WAIT,'/usr/sbin/logrotate',args)
	os.remove(logg_dir + '/' + 'rotate_ldif.tmp')
    lc = Ldap.LdapCall(db)
    lc.ldap_connect()
    valid_sync_mode = lc.check_sync_mode(dis_sync_cn)
    if valid_sync_mode:
	i = 0
	ch_log_list = clh.get_events('ldap',(const.account_mod,\
		const.account_password,const.group_add,const.group_rem,\
		const.group_mod,const.spread_add,const.spread_del,\
		const.quarantine_add,const.quarantine_mod,\
		const.quarantine_del))
	for cll in ch_log_list:
	    try:
		exec cltype[int(cll.change_type_id)]
		clh.confirm_event(cll)
	    except: pass 
	    i += 1
	    clh.confirm_event(cll)
	clh.commit_confirmations()
    lc.end_session()
    


if __name__ == '__main__':
        main()


# Get CLdata. Activate elseif on entry_type (modify-,delete- or add-user, same 
# for filegroups and netgroups
# user_modify: check datebase and ldap -> generate ldif, do ldap_mod (exception 
