#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
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


import sys, os, getopt, time, string, pickle, re, ldap, ldif

import cerebrum_path
import cereconf
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import OU
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum import Entity
from Cerebrum.extlib import logging
from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler
from Cerebrum.modules.no.hia import nwutils

#class UserSkipQuarantine(Exception): pass

global group_done, logger
group_done = {}
int_log = None
db = Factory.get('Database')()
const = Factory.get('CLConstants')(db)
co = Factory.get('Constants')(db)
db.cl_init(change_program='nwqsync')
logger = Factory.get_logger("cronjob")
cl_events = (
		const.account_mod, \
		const.account_password, \
		const.group_add, \
		const.group_rem, \
		const.group_mod, \
		const.entity_name_del,
		const.spread_add, \
		const.spread_del, \
		const.quarantine_add, \
		const.quarantine_mod, \
		const.quarantine_del
		)

cl_entry = {'group_mod' : 'pass', 	
	'group_add' : 'group_mod(cll.change_type_id,cll.subject_entity,\
					cll.dest_entity,cll.change_id)',
	'group_rem' : 'group_mod(cll.change_type_id,cll.subject_entity,\
					cll.dest_entity,cll.change_id)',
	#'account_mod' : 'mod_account(cll.subject_entity,i)',
	'spread_add' : 'change_spread(cll.subject_entity,cll.change_type_id,\
						cll.change_params)',
	'spread_del' : 'change_spread(cll.subject_entity,cll.change_type_id,\
						cll.change_params)',
	'quarantine_add' : 'change_quarantine(cll.subject_entity)',
	'quarantine_mod' : 'change_quarantine(cll.subject_entity)',
	'quarantine_del' : 'change_quarantine(cll.subject_entity)',
	'account_password' : 'change_passwd(cll.subject_entity, cll.change_params)'
	}

# Replace constants-name with database contants integer 
for clt,proc in cl_entry.items():
    del cl_entry[clt]
    cl_entry[int(getattr(co,clt))] = proc


								
def main():
    global int_log, ldap_handle
    int_log = port = host = spread = g_spread = ldap_handle = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'S:s:p:g', ['help'])
    except getopt.GetoptError:
        usage(1)
                                                                                                                                               
    if args:
        usage(1)
    for opt, val in opts:
        if opt == '--help':
            usage()
        elif opt == '-S':
            host = val
        elif opt == '-s':
            spread = val
        elif opt == '-p':
            port = int(val)
        elif opt == '-g':
            g_spread = [x for x in val.split(',')]
    if spread is not None:
        host = host or cereconf.NW_LDAPHOST
        if not host:
            logger.error("No valid server in arg or config")
            sys.exit(0)
        port = port or cereconf.NW_LDAPPORT
        if not port:
            logger.info("No port in arg or config. Port set to default(389)!")
            port = 389
        # TODO fix with som default and cereconf values
        default_dir = '/cerebrum/dumps/eDir/'
        default_file = 'edir.ldif'
        if not os.path.isdir(default_dir):
            os.makedirs(default_dir, mode = 0770)
        if not os.path.exists(default_dir + default_file):
            int_log = file((default_dir + default_file),'w')
        else:
            int_log = file((default_dir + default_file),'a')
        int_log.write("\n# %s \n" % time.strftime("%a, %d %b %Y %H:%M:%S +0000",
                                                        time.localtime()))
        passwd = db._read_password(host,cereconf.NW_ADMINUSER.split(',')[:1][0])
        ldap_handle = nwutils.LDAPConnection(host, port,
                                        binddn=cereconf.NW_ADMINUSER,
                                        password=passwd, scope='sub')
        if ldap_handle:
            nwqsync(spread, g_spread)
        else:
            logger.error("Could not create TLS-channel to server %s." % host)
        int_log.write("\n# End at  %s \n" % time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.localtime()))
        #else:
        #    int_log.write("\n # Could not connect to server!")
        int_log.close()
    else:
        usage(1);


def nwqsync(spreads,g_spread):
    i = 0
    global spread_ids, spread_grp, ent_name_cache
    spread_ids = []
    # Since delete entity_name are done before delete of group and spread
    # we will cache all entity_id/entity_name
    ent_name_cache = {}
    spread_grp = None
    clh = CLHandler.CLHandler(db)
    ch_log_list = clh.get_events('nwqsync',cl_events)
    for spread in spreads.split(','):
	spread_ids.append(int(getattr(co, spread)))
    try:
	spread_grp = [int(getattr(co,x)) for x in (g_spread or \
					cereconf.NW_GROUP_SPREAD)]
    except:
	logger.warn('No group spread is found?')
	sys.exit(1)	    
    for cll in ch_log_list:
	if int(cll.change_type_id) in [const.entity_name_del,]:
	    param_list = string.split(cll.change_params,'\n')
	    domain = re.sub('\D','',param_list[3])
            ent_name = param_list[6].split('\'')[1]
	    ent_name_cache[cll.subject_entity] = {'name':ent_name,'value_domain':domain}
	    clh.confirm_event(cll)
	    continue
        try:
	    exec cl_entry[int(cll.change_type_id)]
            clh.confirm_event(cll)
        except KeyError:
	    pass
            #int_log.write("#event_type %d not handled\n" % cll.change_type_id)
	#else:
        #    exec cltype[int(cll.change_type_id)]
            #clh.confirm_event(cll)
        i += 1
        clh.confirm_event(cll)
    clh.commit_confirmations()

    


def delete_ldap(obj_dn):
    try:
        ldap_handle.DeleteObject(obj_dn)
	log_str = '\n' + ldif.CreateLDIF(obj_dn,{'changetype': \
                                                        ('delete',)})
	int_log.write(log_str)
    except ldap.LDAPError, e:
        logger.warn("delete_ldap() ERROR: ", e)
    
    
def add_ldap(obj_dn, attrs):
    try:
        ldap_handle.CreateObject(obj_dn, attrs)
	attr = []
	for obj,value in attrs:
	    if obj == 'userPassword':
		value = 'xxxxxx'
	    attr.append((obj,[value,]))
	log_str = '\n' + ldif.CreateLDIF(obj_dn,attr)
	int_log.write(log_str)
    except ldap.LDAPError, e:
        logger.warn("add_ldap() ERROR: ", e, obj_dn, attrs)
        
    
    
def attr_add_ldap(obj_dn, attrs):
    try:
        ldap_handle.AddAttributes(obj_dn, attrs)
	for obj,value in attrs:
            attr = [(ldap.MOD_ADD,obj,value)]
	log_str = '\n' + ldif.CreateLDIF(obj_dn,attr)
        int_log.write(log_str)
    except ldap.LDAPError, e:
        logger.warn("attr_add_ldap() ERROR: ", e, obj_dn, attrs)
    
    
def attr_del_ldap(obj_dn, attrs):
    try:
        ldap_handle.DeleteAttributes(obj_dn, attrs)
	attr = []
	for obj,value in attrs:
	    attr.append( (ldap.MOD_DELETE,obj,value))
	log_str = '\n' + ldif.CreateLDIF(obj_dn,attr)
        int_log.write(log_str)
    except ldap.LDAPError, e:
        logger.warn("attr_del_ldap() ERROR: ", e, obj_dn, attrs)
    
    
def attr_mod_ldap(obj_dn, attrs):
    try:
        ldap_handle.ModifyAttributes(obj_dn, attrs)
	attr = []
	for obj,value in attrs:
	    if obj == 'userPassword':
		value = ['xxxxxxx',]
	    attr.append((ldap.MOD_REPLACE,obj,value))	
	log_str = '\n' + ldif.CreateLDIF(obj_dn,attr)
	int_log.write(log_str)
    except ldap.LDAPError, e:
        logger.warn("attr_mod_ldap() ERROR: ", e, obj_dn, attrs)
    


def evaluate_grp_name(grp_name):
    try:
	if re.match('\w',cereconf.NW_GROUP_PREFIX):
	    grp_name  = '-'.join((cereconf.NW_GROUP_PREFIX, grp_name))
    except AttributeError:
	pass
    except TypeError:
	logger.warn('Cereconf variabel NW_GROUP_PREFIX is not a string')
    try:
	if re.match('\w',cereconf.NW_GROUP_POSTFIX):
	    grp_name  = '-'.join((grp_name,cereconf.NW_GROUP_POSTFIX))
    except AttributeError:
        pass
    except TypeError:
        logger.warn('Cereconf variabel NW_GROUP_POSTFIX is not a string')
    return(grp_name)

    
def user_add_del_grp(ch_type,dn_user,dn_dest):
    group = Group.Group(db)
    group.clear()
    account = Account.Account(db)
    group.entity_id = int(dn_dest)
    grp_list = [int(group.entity_id) for s in spread_grp if group.has_spread(s)]
    grp_list += group.list_member_groups(dn_dest, spread_grp)
    if not grp_list:
	return
    # Sjekk om gruppa har riktig spread eller om den er indirecte medlem
    # i andre grupper som har spread 
    for grp in grp_list:
	group.clear()
	group.find(grp)
	group_name = evaluate_grp_name(group.get_name(co.group_namespace))
	search_str = "(&(cn=%s)(objectclass=group))" % group_name
	search_dn = "%s" % cereconf.NW_LDAP_ROOT
	ldap_obj = ldap_handle.GetObjects(search_dn,search_str)
	if not isinstance(ldap_obj,list):
	    logger.warn("Lost TLS-connection to server.")
	    sys.exit(0)
	if ldap_obj == []:
	    # Group not in LDAP (yet)
	    logger.warn("WARNING: Group %s not found in LDAP" % search_str)
	    continue
	(ldap_group, ldap_attrs) = ldap_obj[0]
	if isinstance(dn_user,(str,int)):
	    dn_user = [int(dn_user),] 
	ldap_users = {}
	# Check if all user are registrated
	# This might be "over the egde" with verifying,
	# and maybe it should be removed because CPU and time
	for user in dn_user: 
            account.clear()
            account.find(int(user))
            search_str = "(&(cn=%s)(objectClass=inetOrgPerson))" % \
                         account.account_name
            search_dn = "%s" % cereconf.NW_LDAP_ROOT
            ldap_obj = ldap_handle.GetObjects(search_dn,search_str)
            if ldap_obj == []:
                logger.warn("#del/add member:%s to group %s, failed." & \
						(search_str,group_name))
                dn_user.remove(user)
            else:
                ldap_users[int(user)] = ldap_obj[0][0]
	if ch_type == const.group_add:
	    # Check if user already a member of the p
	    if ldap_attrs.has_key('member'):
		for user, cn_user in ldap_users.items(): 
		    if cn_user in ldap_attrs['member']:
			logger.info("User %s already member in group %s" % \
						(cn_user, ldap_group))
			del ldap_users[user]
	    if ldap_users:
		attr_add_ldap(ldap_group,[('member',ldap_users.values())])
		for users in ldap_users.values():
		    attr_add_ldap(users,[('groupMembership', [ldap_group,])])
		    attr_add_ldap(users,[('securityEquals', [ldap_group,])])
	elif ch_type == const.group_rem:
	    grp_mem = []
	    for spr in spread_ids:
	    # Support multiple spread. Fetch all unuque users.
	        grp_mem += [int(x) for x in group.get_members(spread=spr) \
				if int(x) not in grp_mem]
	    # Remove users that still are suppose to be in the group
	    # This users may be indirect members from internal groups
	    for del_user in [x for x in grp_mem if ldap_users.has_key(x)]:
		del ldap_users[del_user]
	    if ldap_users:
		attr_del_ldap(ldap_group, [('member',ldap_users.values())])
		for users in ldap_users.values():
		    attr_del_ldap(users, [('groupMembership', [ldap_group,])])
		    attr_del_ldap(users, [('securityEquals', [ldap_group,])])
	else:
	    logger.info("WARNING: unhandled group logic")


def change_quarantine(dn_id):
    account = Factory.get('Account')(db)
    try:
        account.find(dn_id)
    except Errors.NotFoundError:
        logger.info("Could not resolve id:%d ,quarantine not changed" % dn_id)
        return
    if not [spr for spr in spread_ids if account.has_spread(spr)]:
        return
    try:
        (ldap_user,ldap_attr) = ldap_handle.GetObjects(cereconf.NW_LDAP_ROOT,\
					"(&(cn=%s)(objectClass=inetOrgPerson))" \
					% account.account_name)[0]
    except ValueError:
        logger.warn("Could not find user:%s at server" % account.account_name)
        return
    nw_stat_login = 1
    new_login = 'FALSE'
    try:
        if ldap_obj[0][1]['loginDisabled'][0] != 'FALSE':
            nw_stat_login = 2
    except KeyError:
        nw_stat_login = False
    quarantines = account.get_entity_quarantine()
    if quarantines:
        from Cerebrum import QuarantineHandler
        now = db.DateFromTicks(time.time())
        quarant = []
        for qua in quarantines:
            if (qua['start_date'] <= now and (qua['end_date'] or \
				qua['end_date'] >= now) and \
				(qua['disable_until'] or \
				qua['disable_until'] < now)):
                quarant.append(qua['quarantine_type'])
            qh = QuarantineHandler.QuarantineHandler(db, quarant)
            #if qh.should_skip():
            #    raise UserSkipQuarantine
            if qh.is_locked():
                new_login = 'TRUE'
    if not nw_stat_login or (nw_stat_login == 1 and new_login == 'TRUE') or \
						(nw_stat_login == 2 and \
						new_login == 'FALSE'):
	attr_mod_ldap(ldap_user,[('loginDisabled',[new_login,])])
        


def path2edir(attrs):
    idx = 0
    disk_str = None
    for (attr, value) in attrs:
      if attr == 'ndsHomeDirectory':
        break
      idx=idx+1
    if attr != 'ndsHomeDirectory':
      return None
    try:
      (foo,srv,vol,path) = value.split("/", 3)
    except:
      del attrs[idx]
      return None
    search_str = "cn=%s_%s" % (srv,vol)
    search_dn = "%s" % cereconf.NW_LDAP_ROOT
    ldap_disk = ldap_handle.GetObjects(search_dn,search_str)
    if not isinstance(ldap_disk,list):
	logger.warn("Lost TLS-connection to server.")
	sys.exit(0)
    if ldap_disk == []:
      del attrs[idx]
    else:
      disk_str = "%s#0#%s" % (ldap_disk[0][0], path)
      attrs[idx] = ('ndsHomeDirectory', disk_str)
    return disk_str


def change_user_spread(dn_id,ch_type,spread,uname=None):
    account = Factory.get('Account')(db)
    group = Group.Group(db)
    if not uname:
	try:
	    account.find(dn_id)
	    acc_name = account.account_name
	except Errors.NotFoundError:
	    logger.error("Account could not be found: %s" % dn_id)
	    return
    else: acc_name = uname
    search_str = "(&(cn=%s)(objectClass=inetOrgPerson))" % acc_name
    search_dn = "%s" % cereconf.NW_LDAP_ROOT
    ldap_obj = ldap_handle.GetObjects(search_dn,search_str)
    if not isinstance(ldap_obj,list):
	logger.warn("Lost TLS-connection to server.")
	sys.exit(0)
    if (ch_type == int(const.spread_del)):
	# Set loginDisable and move user to a specific (rem-user
	# 
	if ldap_obj == []:
	    logger.info('Delete_user %s ,but doesnt exist on eDir-server' % \
								acc_name)
	else: 
	    (ldap_user, ldap_attrs) = ldap_obj[0]
	    for grp in group.list_groups_with_entity(dn_id):
                user_add_del_grp(const.group_rem, dn_id, grp['group_id'])
	    delete_ldap(ldap_user)
    elif (ch_type == int(const.spread_add)):
	if ldap_obj == [] and [x for x in spread_ids if account.has_spread(x)]:
	    (ldap_user, ldap_attrs) = nwutils.get_account_info(dn_id, \
							spread, None)
            path2edir(ldap_attrs)
	    add_ldap(ldap_user,ldap_attrs)
            # Check if 
            for delay in range(3,8):
                if ldap_handle.GetObjects(search_dn,search_str):
                    account.set_home(spread,status=co.home_status_on_disk)
                    break
                time.sleep(delay)
            else:
                logger.warn("Could not verify that user:%s was created on eDir-server"\
                            % ldap_user)
	    for grp in group.list_groups_with_entity(dn_id):
                user_add_del_grp(const.group_add, dn_id, grp['group_id'])
	elif ldap_obj <> []:
            (ldap_user, ldap_attrs) = ldap_obj[0]
            logger.warn("WARNING: add_user but user %s already exist as %s" % \
							(acc_name,ldap_user))
	else: 
	    logger.warn('User_add/del bu could not resolve!')
    else:
	logger.info('Something is really wrong (id:%s,ch-type:%s' % (dn_id,\
								ch_type))



def change_group_spread(dn_id,ch_type,gname=None):    
    group = Group.Group(db)
    #if group_done.has_key(dn_id) and group_done[dn_id] is ch_type:
    #    return
    group.clear()
    if not gname:
	try: 
	    group.find(dn_id)
	    grp_name = group.group_name 
        except:
	    logger.error('Group-entity can not be found: ch-id:%s subj-id:%s' % (ch_id,dn_id))
    else: grp_name = gname	
    group_name = evaluate_grp_name(grp_name)
    utf8_dn = unicode('cn=%s' % group_name, 'iso-8859-1').encode('utf-8')
    search_cn = "(&(%s)(objectclass=group))" % utf8_dn
    search_dn = "%s" % cereconf.NW_LDAP_ROOT
    ldap_obj = ldap_handle.GetObjects(search_dn, search_cn)
    if not isinstance(ldap_obj,list):
	logger.warn("Lost TLS-connection to server.")
	sys.exit(0)
    if ch_type==int(const.spread_del) and ldap_obj <> []:
	(ldap_group, ldap_attrs) = ldap_obj[0]
	#if not nwutils.touchable(ldap_attrs):
	#    logger.info("ERROR: LDAP object %s not managed by Cerebrum." % ldap_group)
	#    return
	#else:
	for mem in ldap_attrs['member']:
	    attr_del_ldap(mem, [('groupMembership', [ldap_group,])])
	    attr_del_ldap(mem, [('securityEquals', [ldap_group,])])
	delete_ldap(ldap_group)
    elif ch_type==int(co.spread_add) and ldap_obj == []:
	try:
	    attrs = []
	    attrs.append(("ObjectClass", "group"))
	    attrs.append(("description", "Cerebrum;%d;%s" % (dn_id,
							nwutils.now())))
	    student_grp = False
	    grp_mem = []
	    for mem in group.get_members(spread = spread_ids[0],get_entity_name=False):
		if  (co.affiliation_student == \
				nwutils.get_primary_affiliation(mem,co.account_namespace)):
		    student_grp = True
		grp_mem.append(int(mem))
		# If any of this members does not exist on eDirectory server,
		# it will only give you a LDAP-protocl message "NDS error".
		# While using  method user_add_del_group, it will do a LDAP-search
		# to verify that user exist on server.
		# Do: get_entity_name=True and mem -> mem[0]
	    if student_grp:
		grp_dn = utf8_dn + ',ou=grp,ou=stud,' + cereconf.NW_LDAP_ROOT
	    else:
		grp_dn = utf8_dn + ',ou=grp,ou=ans,' + cereconf.NW_LDAP_ROOT
	    add_ldap(grp_dn, attrs)
	    for delay in range(3,8):
		if ldap_handle.GetObjects(search_dn, search_cn):
		    user_add_del_grp(const.group_add, grp_mem, dn_id)
		    return
		time.sleep(delay)
	    logger.warn("Group not found on server: %s (%s)" %\
							(group_name,dn_id))
	except:
	    logger.error('Error occured while creating group %s' % dn_id)
    else:
	if ldap_obj <> []:
	    logger.debug('Group already exist: %s' % ldap_obj[0][0])
	else:
	    logger.warn('Group_add/del could not solve subject_id: %s' % dn_id)
	


def change_spread(dn_id,ch_type,ch_params):
    spread = int(re.sub('\D','',(string.split(ch_params,'\n')[3])))
    if spread not in (spread_ids + spread_grp): 
	return
    entity = Entity.Entity(db)
    try:
	entity.find(int(dn_id))
	if entity.entity_type == int(co.entity_account) and spread in spread_ids:
	    change_user_spread(dn_id,ch_type,spread)
	elif entity.entity_type == int(co.entity_group) and spread in spread_grp:
	    change_group_spread(dn_id,ch_type)
	else: pass 
	    # Maybe it should be a logger message
    except Errors.NotFoundError:
	if not (ch_type == const.spread_del):
	    log_txt = "Could not resolve account/group name for entity-id: "
            logger.error(log_txt + dn_id)
	    return
	if ent_name_cache.has_key(dn_id) or get_cl_event(dn_id):
	    if (ent_name_cache[dn_id]['domain'] == const.group_namespace) \
						and spread in spread_grp:
		change_group_spread(dn_id,ch_type,\
			gname=ent_name_cache[dn_id]['name'])
	    elif ent_name_cache[dn_id]['domain'] == const.account_namespace \
						and spread in spread_ids:
	    	change_user_spread(dn_id,ch_type, spread,\
                        uname=ent_name_cache[dn_id]['name'])
	    else: pass
	else:
	    log_txt = "Could not resolve account/group name for entity-id: "
	    logger.error(log_txt + dn_id)
	    # If entry not in cache, search changelog for event: subject_id=dn_id,
	    # change_type_id=const.entity_name_del, if none then  
	    # logger.error("Could not delete because could not resolve 
	    # group/account: %s name" % dn_id)


def mod_account(dn_id):
    account = Account.Account(db)
    account.clear()
    account.find(dn_id)
    #has_spread = 0
    if [x for x in spread_ids if account.has_spread(x)]: 
        search_str = "(&(cn=%s)(objectClass=inetOrgPerson))" % account.account_name
        search_dn = "%s" % cereconf.NW_LDAP_ROOT
	ldap_obj = ldap_handle.GetObjects(search_dn,search_str)
	if not isinstance(ldap_obj,list):
	    logger.warn("Lost TLS-connection to server.")
	    sys.exit(0)
        (cerebrm_dn, base_entry) = nwutils.get_account_dict(dn_id, spread_ids[0], None)
        if ldap_obj <> []:
            (dn_str,ldap_attr) = ldap_obj[0]
	else:
            logger.info("WARNING: CL Modify on object not in LDAP")
            return
        if base_entry.has_key('ndsHomeDirectory'):
            newpath = path2edir([('ndsHomeDirectory', base_entry['ndsHomeDirectory'])])
            if newpath != None:
            	base_entry['ndsHomeDirectory'] = newpath[1]
	    else:
		del base_entry['ndsHomeDirectory']
        for entry in base_entry.keys():
            try:
                if (ldap_attr[entry] <> base_entry[entry]):
                    if entry in ('userPassword',):
                        pass
		    else:
                        value = (entry, base_entry[entry]),
                        attr_mod_ldap(dn_str, value)
            except KeyError:
                pass



def change_passwd(dn_id, ch_params):
    account = Account.Account(db)
    account.clear()
    account.find(dn_id)
    if [x for x in spread_ids if account.has_spread(x)]:
	search_str = "(&(cn=%s)(objectClass=inetOrgPerson))" % account.account_name
	search_dn = "%s" % cereconf.NW_LDAP_ROOT
	ldap_obj = ldap_handle.GetObjects(search_dn,search_str)
	if not isinstance(ldap_obj,list):
	    logger.warn("Lost TLS-connection to server.")
	    sys.exit(0)
    	if ldap_obj == []:
	    logger.info("User could not be found on server: %s\n " % search_str)
            return
    	try:
	    (ldap_user,ldap_attr) = ldap_obj[0]
	    #attrs = []
	    #attrs.append(('passwordAllowChange',['TRUE']))
	    #attr_mod_ldap(ldap_user,attrs)
	    attrs = []
            pwd = pickle.loads(ch_params)['password']
            attrs.append( ("userPassword", [unicode(pwd, 'iso-8859-1').encode('utf-8')]) )
	    #attrs.append(('passwordAllowChange',['FALSE']))
	    for attr in attrs:
		attr_l = [attr ,]
		attr_mod_ldap(ldap_user,attr_l)
	except:
            logger.warn('Could not update password on user:%s\n' % account.account_name)  
    



def group_mod(ch_type,dn_id,dest_id,log_id):
    # We remember groups we're done with because we don't want to
    # re-read LDAP for every group_mod event.
    # We asume only support to one level groups and expand all
    # groups with members, even if cerebrum contains several levels
    # of internal- and external-groups.  
    entity = Entity.Entity(db)
    try:
    	entity.find(int(dn_id))
    except Errors.NotFoundError:
	logger.warn("Subject:%s could not be found. Changelog-id:%s" % \
                                                        (dn_id,log_id))
	return
    group = Factory.get('Group')(db)
    try:
	group.entity_id = int(dest_id)
    except Errors.NotFoundError:
	logger.warn("Group-id:%s could not be found. Changelog-id: %s" % \
                                                        (dest_id,log_id))
	return
    user_list = []
    if entity.entity_type == co.entity_group:
	group.clear()
	group.find(entity.entity_id)
	for spr in spread_ids:
	    user_list += [int(mem) for mem in group.get_members(spread=spr) \
				if int(mem) not in user_list]
    elif entity.entity_type == co.entity_account:
	if [ x for x in spread_ids if entity.has_spread(x)]:
	    user_list.append(entity.entity_id)
	else:
	    return
    else:
	logger.warn("Could not solve entity-id:%s. Changelog_id:%s" % \
							 (dn_id,log_id))
	return
    group.clear()
    group.entity_id = int(dest_id)	
    grp_list =  group.list_member_groups(dest_id,spread_grp)
    # If initial destination group has spread, add group to list.	
    grp_list += [group.entity_id for x in spread_grp if group.has_spread(x) \
					and group.entity_id not in grp_list]
    for grp in grp_list:
	user_add_del_grp(ch_type,user_list,grp)		


def get_cl_event(subject_id, change_type=[const.entity_name_del,],
					param=6, dest_id=None):
    """
    Used to fetch deleted entity-names if not prefected earlier
    in same session.
    """
    cl_val =  db.get_log_events(subject_entity=subject_id,
					types=change_type,
					dest_entity= dest_id)
    for row in cl_val:
	param_list = string.split(row['change_params'],'\n')
	domain = re.sub('\D','',param_list[3])
	ent_name = param_list[int(param)].split('\'')[1]
	ent_name_cache[subject_id] = {'name':ent_name,'value_domain':domain}
	return(True)
    else:
	return(False)


def usage(exitcode=0):
    print """Usage: nwqsync.py [ -S server ] [ -p port ] -s spread """
    sys.exit(exitcode)



if __name__ == '__main__':
    main()

# arch-tag: a32a53e6-7025-443e-917a-cb78b5175435
