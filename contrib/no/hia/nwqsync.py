#!/usr/bin/env python2.2
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


global ldap_handle, cl_mask, group_done, logger
group_done = {}
db = Factory.get('Database')()
const = Factory.get('CLConstants')(db)
co = Factory.get('Constants')(db)
logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
logger = logging.getLogger("console")
cl_events = (
		const.account_mod, \
		const.account_password, \
		const.group_add, \
		const.group_rem, \
		const.group_mod, \
		const.spread_add, \
		const.spread_del, \
		const.quarantine_add, \
		const.quarantine_mod, \
		const.quarantine_del
		)

dbg_level = -1
NONE = 0
ERROR = 1
WARN = 2
INFO = 3
DEBUG = 4


cltype = {}
cl_entry = {'group_mod' : 'pass', 	
	#'group_add' : 'group_mod(cll.change_type_id,cll.subject_entity,\
	#				cll.dest_entity,cll.change_id)',
	#'group_rem' : 'group_mod(cll.change_type_id,cll.subject_entity,\
	#				cll.dest_entity,cll.change_id)',
	#'account_mod' : 'mod_account(cll.subject_entity,i)',
	'spread_add' : 'change_spread(cll.subject_entity,cll.change_type_id,\
							cll.change_params)',
	'spread_del' : 'change_spread(cll.subject_entity,cll.change_type_id,\
							cll.change_params)',
	#'quarantine_add' : 'change_quarantine(cll.subject_entity,\
	#						cll.change_type_id)',
	#'quarantine_mod' : 'change_quarantine(cll.subject_entity,\
	#						cll.change_type_id)',
	#'quarantine_del' : 'change_quarantine(cll.subject_entity,\
	#						cll.change_type_id)'
	'account_password' : 'change_passwd(cll.subject_entity, cll.change_params)'
	}
									


def nwqsync(spreads):
    i = 0
    global spread_ids
    spread_ids = []
    clh = CLHandler.CLHandler(db)
    ch_log_list = clh.get_events('nwqsync',cl_events)
    for spread in spreads.split(','):
      spread_ids.append(int(getattr(co, spread)))
    for cll in ch_log_list:
        try:
            func = cltype[int(cll.change_type_id)]
        except KeyError:
	    pass
            #int_log.write("#event_type %d not handled\n" % cll.change_type_id)
        else:
            exec cltype[int(cll.change_type_id)]
            clh.confirm_event(cll)
        i += 1
        clh.confirm_event(cll)
    clh.commit_confirmations()

def ldap_connect(serv_l=None):
    global con
    con = None
    if not serv_l:
	serv_l = []
	serv_l.append('%s:%s' % (cereconf.NW_LDAPHOST,
					cereconf.NW_ADMINUSER))
    for server in serv_l:
	try:
	    serv,user = [str(y) for y in server.split(':')]
	    con = ldap.open(serv)
	    con.protocol_version = ldap.VERSION3
	except ldap.LDAPError, e:
	    logger.warn(e)
	    con = None

def get_ldap_value(search_id,dn,retrieveAttributes=None):
    searchScope = ldap.SCOPE_SUBTREE
    result_set = []
    try:
	ldap_result_id = con.search(search_id,searchScope,dn,retrieveAttributes)
	while 1:
	    result_type, result_data = con.result(ldap_result_id, 0)
	    if (result_data == []):
		break
	    else:
		if result_type == ldap.RES_SEARCH_ENTRY:
		    result_set.append(result_data)
		else:
		    pass
    except ldap.LDAPError, e:
	logger.warn(e)
	return(None)
    return(result_set)


#def dbg_print(lvl, str):
#    if dbg_level >= lvl:
#        print str
    


def delete_ldap(obj_dn):
    try:
        ldap_handle.DeleteObject(obj_dn)
	log_str = '\n' + ldif.CreateLDIF(obj_dn,{'changetype': \
                                                        ('delete',)})
	int_log.write(log_str)
    except ldap.LDAPError, e:
        logger.info("delete_ldap() ERROR: ", e)
    
    
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
        logger.info("add_ldap() ERROR: ", e, obj_dn, attrs)
        
    
    
def attr_add_ldap(obj_dn, attrs):
    try:
        ldap_handle.AddAttributes(obj_dn, attrs)
	for obj,value in attrs:
            attr = [(ldap.MOD_ADD,obj,value)]
	log_str = '\n' + ldif.CreateLDIF(obj_dn,attr)
        int_log.write(log_str)
    except ldap.LDAPError, e:
        logger.info("attr_add_ldap() ERROR: ", e, obj_dn, attrs)
    
    
def attr_del_ldap(obj_dn, attrs):
    try:
        ldap_handle.DeleteAttributes(obj_dn, attrs)
	attr = []
	for obj,value in attrs:
	    attr.append( (ldap.MOD_DELETE,obj,value))
	log_str = '\n' + ldif.CreateLDIF(obj_dn,attr)
        int_log.write(log_str)
    except ldap.LDAPError, e:
        logger.info("attr_del_ldap() ERROR: ", e, obj_dn, attrs)
    
    
def attr_mod_ldap(obj_dn, attrs):
    try:
        ldap_handle.ModifyAttributes(obj_dn, attrs)
	attr = []
	for obj,value in attrs:
	    if obj == 'userPassword':
		value = 'xxxxxxx'
	    attr.append((ldap.MOD_REPLACE,obj,value))	
	log_str = '\n' + ldif.CreateLDIF(obj_dn,attr)
	int_log.write(log_str)
    except ldap.LDAPError, e:
        logger.info("attr_mod_ldap() ERROR: ", e, obj_dn, attrs)
    
    
    
def user_add_del_grp(ch_type,dn_user,dn_dest):
    return
    group = Group.Group(db)
    group.clear()
    account = Account.Account(db)
    group.entity_id = int(dn_dest)
    group_name = cereconf.NW_GROUP_PREFIX + group.get_name(co.group_namespace) + cereconf.NW_GROUP_POSTFIX
    search_str = "cn=%s" % group_name
    search_dn = "%s" % cereconf.NW_LDAP_ROOT
    #ldap_obj = ldap_handle.GetObjects(search_dn,search_str)
    ldap_obj = get_ldap_value(search_dn,search_str)[0]
    if ldap_obj == []:
       # Group not in LDAP (yet)
       logger.warn("WARNING: Group %s not found in LDAP" % search_str)
       pass
    else:
        (ldap_group, ldap_attrs) = ldap_obj [0]
        if not nwutils.touchable(ldap_attrs):
            logger.info("ERROR: LDAP object %s not managed by Cerebrum." % ldap_group)
            return
        account.clear()
        account.find(dn_user)
        search_str = "(&(cn=%s)(objectClass=inetOrgPerson))" % account.account_name
        search_dn = "%s" % cereconf.NW_LDAP_ROOT
        #ldap_obj = ldap_handle.GetObjects(search_dn,search_str)
	ldap_obj = get_ldap_value(search_dn,search_str)
        if ldap_obj == []:
            return
        (ldap_user, ldap_uattrs) = ldap_obj [0][0]
        if not nwutils.touchable(ldap_uattrs):
            logger.warn("ERROR: LDAP object %s not managed by Cerebrum." % ldap_user)
            return
        attrs = []
        attrs.append( ("securityEquals", ldap_group) )
        attrs.append( ("groupMembership", ldap_group) )
        if ch_type == const.group_add:
            if ldap_attrs.has_key('member'):
                if ldap_user in ldap_attrs['member']:
                    logger.warn("WARNING: User %s already member in group %s" % (ldap_user, ldap_group))
                    return
            attr_add_ldap(ldap_user, attrs)
            attrs = []
            attrs.append( ("member", ldap_user) )
            attr_add_ldap(ldap_group, attrs)
        elif ldap_user in ldap_attrs['member']:
            attr_del_ldap(ldap_user, attrs)
            attrs = []
            attrs.append( ("member", ldap_user) )
            attr_del_ldap(ldap_group, attrs)
        else:
            logger.info("WARNING: unhandled group logic")


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
    if ldap_disk == []:
      del attrs[idx]
    else:
      disk_str = "%s#0#%s" % (ldap_disk[0][0], path)
      attrs[idx] = ('ndsHomeDirectory', disk_str)
    return disk_str


def change_user_spread(dn_id,ch_type,ch_params):
    account = Account.Account(db)
    group = Group.Group(db)
    param_list = []
    param_list = string.split(ch_params,'\n')
    cl_spread = int(re.sub('\D','',param_list[3]))
    if cl_spread in spread_ids:
        account.find(dn_id)
        search_str = "(&(cn=%s)(objectClass=inetOrgPerson))" % account.account_name
        search_dn = "%s" % cereconf.NW_LDAP_ROOT
        #ldap_obj = ldap_handle.GetObjects(search_dn,search_str)
	ldap_obj = get_ldap_value(search_dn,search_str)
        if (ch_type == int(const.spread_del)):
	    if ldap_obj <> []:
		(ldap_user, ldap_attrs) = ldap_obj[0][0]
                if not nwutils.touchable(ldap_attrs):
                    return
                delete_ldap(ldap_user)
        elif (ch_type == int(const.spread_add)):
            if (ldap_obj == []):
                (ldap_user, ldap_attrs) = nwutils.get_account_info(dn_id, cl_spread, None)
                path2edir(ldap_attrs)
                #ldap_user = ldap_user.replace('ou=HIST', 'o=HiST')
		#if input.lower() == 'y':
		#print ldap_user,ldap_attrs
		add_ldap(ldap_user,ldap_attrs)
            else:
                (ldap_user, ldap_attrs) = ldap_obj [0][0]
                logger.info("WARNING: User %s already exist as %s" % (account.account_name, ldap_user))
            for grp in group.list_groups_with_entity(dn_id):
                user_add_del_grp(const.group_add, dn_id, grp['group_id'])



def change_group_spread(dn_id,ch_type,ch_params):    
    group = Group.Group(db)
    param_list = []
    param_list = string.split(ch_params,'\n')
    cl_spread = int(re.sub('\D','',param_list[3]))
    if cl_spread not in spread_ids:
        return
    if group_done.has_key(dn_id) and group_done[dn_id] is ch_type:
        return
    group.clear()
    group.entity_id = int(dn_id)
    group_name = cereconf.NW_GROUP_PREFIX + group.get_name(co.group_namespace) + cereconf.NW_GROUP_POSTFIX
    utf8_ou = nwutils.get_ldap_group_ou(group_name)
    utf8_dn = unicode('cn=%s,' % group_name, 'iso-8859-1').encode('utf-8') + utf8_ou
    search_dn = "%s" % cereconf.NW_LDAP_ROOT
    ldap_obj = get_ldap_value(search_dn, utf8_dn)
    if ldap_obj <> []:
        (ldap_group, ldap_attrs) = ldap_obj [0][0]
        if not nwutils.touchable(ldap_attrs):
            logger.info("ERROR: LDAP object %s not managed by Cerebrum." % ldap_group)
            return
    if True in [group.has_spread(x) for x in spread_ids]:
        attrs = []
        attrs.append( ("ObjectClass", "group") )
        attrs.append( ("description", "Cerebrum;%d;%s" % (dn_id,nwutils.now()) ) )
        add_ldap(utf8_dn, attrs)
        for mem in group.get_members():
            user_add_del_grp(const.group_add,mem,dn_id)
        group_done[dn_id] = ch_type
    else:
        delete_ldap(utf8_dn)


def change_spread(dn_id,ch_type,ch_params):
    entity = Entity.Entity(db)
    try:
	entity.find(int(dn_id))
    except Errors.NotFoundError:
	logger.info("Entity_id %d do not exist" % dn_id)
	return
    #What to do with ch_param
    if entity.entity_type == int(co.entity_account):
	print "in user spread"
        change_user_spread(dn_id,ch_type,ch_params)
    elif entity.entity_type == int(co.entity_group):
        change_group_spread(dn_id,ch_type,ch_params)
    else:
        logger.info("# Change_spread did not resolve request (%s,%s)" 
					% (dn_id,ch_type)) 


def mod_account(dn_id,i):
    account = Account.Account(db)
    account.clear()
    account.find(dn_id)
    has_spread = 0
    if True in [account.has_spread(x) for x in spread_ids]:
        search_str = "(&(cn=%s)(objectClass=inetOrgPerson))" % account.account_name
        search_dn = "%s" % cereconf.NW_LDAP_ROOT
        ldap_entry = get_ldap_value(search_dn,search_str)
        (cerebrm_dn, base_entry) = nwutils.get_account_dict(dn_id, spread_ids[0], None)
        if ldap_entry != []:
            (dn_str,ldap_attr) = ldap_entry[0][0]
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
    if True in [account.has_spread(x) for x in spread_ids]:
	search_str = "(&(cn=%s)(objectClass=inetOrgPerson))" % account.account_name
	search_dn = "%s" % cereconf.NW_LDAP_ROOT
	ldap_obj = get_ldap_value(search_dn,search_str,retrieveAttributes=['dn',])
    	if ldap_obj == []:
	    logger.info("User could not be found on server: %s\n " % search_str)
            return
    	try:
	    ldap_entry = ldap_obj[0]
	    # Because of some strange attributes on some users in eDir, 
	    # we have to change passwordAllowChange to True -> change passwd -> False
	    attrs = []
	    attrs.append(('passwordAllowChange',['TRUE']))
	    attr_mod_ldap(ldap_entry[0][0],attrs)
	    attrs = []
            pwd = pickle.loads(ch_params)['password']
            attrs.append( ("userPassword", [unicode(pwd, 'iso-8859-1').encode('utf-8')]) )
	    attrs.append(('passwordAllowChange',['FALSE']))
	    for attr in attrs:
		attr_l = [attr ,]
		attr_mod_ldap(ldap_entry[0][0],attr_l)
	except:
            logger.warn('Could not update password on user:%s\n' % account.account_name)  
    



def group_mod(ch_type,dn_id,dn_dest,log_id):
    # We remember groups we're done with because we don't want to
    # re-read LDAP for every group_mod event.
    group = Group.Group(db)
    group.clear()
    group.entity_id = int(dn_dest)
    group_name = cereconf.NW_GROUP_PREFIX + group.get_name(co.group_namespace) + cereconf.NW_GROUP_POSTFIX
    search_str = "cn=%s" % group_name	# Find a proper objectclass to avoid name-space collition
    search_dn = "%s" % cereconf.NW_LDAP_ROOT
    if group_done.has_key(dn_dest):
        return
    ldap_obj = get_ldap_value(search_dn,search_str)
    if ldap_obj <> []:
        (ldap_group, ldap_attrs) = ldap_obj [0][0]
        for mem in group.get_members(spread=spread_ids[0]):
            user_add_del_grp(ch_type,mem,dn_dest)
        group_done[dn_dest] = "Synced"
    else:
       # Group not in LDAP (yet)
       logger.info("WARNING: Group %s not found in LDAP" % search_str)
       group_done[dn_dest] = "not found"
    
    

def load_cltype_table(cltype):
    for clt,proc in cl_entry.items():
	# make if-entry to list in cereconf to remove dynamic service
	cltype[int(getattr(co,clt))] = proc	


def usage(exitcode=0):
    print """Usage: nwqsync.py [ -S server ] [ -p port ] -s spread """
    sys.exit(exitcode)


def main():
    global ldap_handle, dbg_level, int_log
    port = host = spread = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'S:s:p:d:', ['help'])
    except getopt.GetoptError:
        usage(1)

    if args:
        usage(1)
    for opt, val in opts:
        if opt == '--help':
            usage()
        elif opt == '-S':
            server = val
        elif opt == '-s':
            spread = val
        elif opt == '-p':
            port = int(val)
        elif opt == '-d':
            dbg_level = int(val)
    if spread is not None:
        if host is None:
            host = cereconf.NW_LDAPHOST
        if port is None:
            port = cereconf.NW_LDAPPORT
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
	ldap_connect()
	if con:
	    load_cltype_table(cltype)
	    nwqsync(spread)
	    int_log.write("\n# End at  %s \n" % time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.localtime()))
	else:
	    int_log.write("\n # Could not connect to server!")
	int_log.close()
    else:
        usage(1);        
    
    
        
        
if __name__ == '__main__':
    main()

# arch-tag: a32a53e6-7025-443e-917a-cb78b5175435
