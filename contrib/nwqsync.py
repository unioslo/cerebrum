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


import sys
import getopt
import time
import string
import pickle
import re
import ldap

import cerebrum_path
import cereconf
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import OU
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler
import nwutils


global spread_id, ldap_handle, cl_mask, group_done
group_done = {}
db = Factory.get('Database')()
const = Factory.get('CLConstants')(db)
co = Factory.get('Constants')(db)
cl_events = (const.account_mod, \
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
	'group_add' : 'group_mod(cll.change_type_id,cll.subject_entity,\
					cll.dest_entity,cll.change_id)',
	'group_rem' : 'group_mod(cll.change_type_id,cll.subject_entity,\
					cll.dest_entity,cll.change_id)',
	'account_mod' : 'mod_account(cll.subject_entity,i)',
	'account_password' : 'change_passwd(cll.subject_entity, cll.change_params)',
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


def nwqsync(spread):
    global spread_id
    i = 0
    clh = CLHandler.CLHandler(db)
    ch_log_list = clh.get_events('ldap',cl_events)
    spread_id = int(getattr(co, spread))
    for cll in ch_log_list:
        try:
            func = cltype[int(cll.change_type_id)]
        except KeyError:
            print "event_type %d not handled" % cll.change_type_id
        else:
            exec cltype[int(cll.change_type_id)]
 #           clh.confirm_event(cll)
        i += 1
 #       clh.confirm_event(cll)
 #   clh.commit_confirmations()


def dbg_print(lvl, str):
    if dbg_level >= lvl:
        print str
    


def delete_ldap(obj_dn):
    dbg_print(DEBUG, "delete_ldap()%s", obj_dn)
    try:
        ldap_handle.DeleteObject(obj_dn)
    except ldap.LDAPError, e:
        print "delete_ldap() ERROR: ", e
    
    
def add_ldap(obj_dn, attrs):
    dbg_print(DEBUG, ("add_ldap():", obj_dn, attrs))
    try:
        ldap_handle.CreateObject(obj_dn, attrs)
    except ldap.LDAPError, e:
        print "add_ldap() ERROR: ", e, obj_dn, attrs
        
    
    
def attr_add_ldap(obj_dn, attrs):
    dbg_print(DEBUG, ("attr_add_ldap():", obj_dn, attrs))
    try:
        ldap_handle.AddAttributes(obj_dn, attrs)
    except ldap.LDAPError, e:
        print "attr_add_ldap() ERROR: ", e, obj_dn, attrs
    
    
def attr_del_ldap(obj_dn, attrs):
    dbg_print(DEBUG, ("attr_del_ldap():", obj_dn, attrs))
    try:
        ldap_handle.DeleteAttributes(obj_dn, attrs)
    except ldap.LDAPError, e:
        print "attr_del_ldap() ERROR: ", e, obj_dn, attrs
    
    
def attr_mod_ldap(obj_dn, attrs):
    dbg_print(DEBUG, ("attr_mod_ldap():", obj_dn, attrs))
    try:
        ldap_handle.ModifyAttributes(obj_dn, attrs)
    except ldap.LDAPError, e:
        print "attr_mod_ldap() ERROR: ", e, obj_dn, attrs
    
    
    
def user_add_del_grp(ch_type,dn_user,dn_dest):
    group = Group.Group(db)
    group.clear()
    account = Account.Account(db)
    group.entity_id = int(dn_dest)
    group_name = cereconf.NW_GROUP_PREFIX + group.get_name(co.group_namespace) + cereconf.NW_GROUP_POSTFIX
    search_str = "cn=%s" % group_name
    search_dn = "%s" % cereconf.NW_LDAP_ROOT
    ldap_obj = ldap_handle.GetObjects(search_dn,search_str)
    if ldap_obj == []:
       # Group not in LDAP (yet)
       dbg_print(WARN, "WARNING: Group %s not found in LDAP" % search_str)
       pass
    else:
        (ldap_group, ldap_attrs) = ldap_obj [0]
        if not nwutils.touchable(ldap_attrs):
            dbg_print((ERROR, "ERROR: LDAP object %s not managed by Cerebrum." % ldap_group))
            return
        account.clear()
        account.find(dn_user)
        search_str = "cn=%s" % account.account_name
        search_dn = "%s" % cereconf.NW_LDAP_ROOT
        ldap_obj = ldap_handle.GetObjects(search_dn,search_str)
        if ldap_obj == []:
            return
        (ldap_user, ldap_uattrs) = ldap_obj [0]
        if not nwutils.touchable(ldap_uattrs):
            dbg_print((ERROR, "ERROR: LDAP object %s not managed by Cerebrum." % ldap_user))
            return
        attrs = []
        attrs.append( ("securityEquals", ldap_group) )
        attrs.append( ("groupMembership", ldap_group) )
        if ch_type == const.group_add:
            if ldap_attrs.has_key('member'):
                if ldap_user in ldap_attrs['member']:
                    dbg_print(WARN, "WARNING: User %s already member in group %s" % (ldap_user, ldap_group))
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
            print dbg_print(WARN, "WARNING: unhandled group logic")


    

def change_user_spread(dn_id,ch_type,ch_params):
    account = Account.Account(db)
    group = Group.Group(db)
    param_list = []
    param_list = string.split(ch_params,'\n')
    cl_spread = int(re.sub('\D','',param_list[3]))
    if cl_spread == spread_id:
        account.find(dn_id)
        search_str = "cn=%s" % account.account_name
        search_dn = "%s" % cereconf.NW_LDAP_ROOT
        ldap_obj = ldap_handle.GetObjects(search_dn,search_str)
        if (ch_type == int(const.spread_del)):
            for (ldap_user, ldap_attrs) in ldap_obj:
                if not nwutils.touchable(ldap_attrs):
                    return
                delete_ldap(ldap_user)
        elif (ch_type == int(const.spread_add)):
            if (ldap_obj == []):
                (ldap_user, ldap_attrs) = nwutils.get_account_info(dn_id, spread_id)
                add_ldap(ldap_user,ldap_attrs)
            else:
                (ldap_user, ldap_attrs) = ldap_obj [0]
                dbg_print(WARN, "WARNING: User %s already exist as %s" % (account.account_name, ldap_user))
            for grp in group.list_groups_with_entity(dn_id):
                user_add_del_grp(const.group_add, dn_id, grp['group_id'])



def change_group_spread(dn_id,ch_type,ch_params):    
    group = Group.Group(db)
    param_list = []
    param_list = string.split(ch_params,'\n')
    cl_spread = int(re.sub('\D','',param_list[3]))
    if cl_spread != spread_id:
        return
    if group_done.has_key(dn_id) and group_done[dn_id] is ch_type:
        return
    group.clear()
    group.entity_id = int(dn_id)
    group_name = cereconf.NW_GROUP_PREFIX + group.get_name(co.group_namespace) + cereconf.NW_GROUP_POSTFIX
    utf8_ou = nwutils.get_ldap_group_ou(group_name)
    utf8_dn = unicode('cn=%s,' % group_name, 'iso-8859-1').encode('utf-8') + utf8_ou
    search_dn = "%s" % cereconf.NW_LDAP_ROOT
    ldap_obj = ldap_handle.GetObjects(search_dn, utf8_dn)
    if ldap_obj <> []:
        (ldap_group, ldap_attrs) = ldap_obj [0]
        if not nwutils.touchable(ldap_attrs):
            dbg_print((ERROR, "ERROR: LDAP object %s not managed by Cerebrum." % ldap_group))
            return
    if group.has_spread(spread_id):
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
    entity.find(int(dn_id))
    """What to do with ch_param"""
    if entity.entity_type == int(co.entity_account):
        change_user_spread(dn_id,ch_type,ch_params)
    elif entity.entity_type == int(co.entity_group):
        change_group_spread(dn_id,ch_type,ch_params)
    else:
        print("\n# Change_spread did not resolve request (%s,%s)" 
					% (dn_id,ch_type)) 


def mod_account(dn_id,i):
    account = Account.Account(db)
    account.clear()
    account.find(dn_id)
    if account.has_spread(spread_id):
        search_str = "cn=%s" % account.account_name
        search_dn = "%s" % cereconf.NW_LDAP_ROOT
        ldap_entry = ldap_handle.GetObjects(search_dn,search_str)
        base_entry = nwutils.get_account_dict(dn_id, spread_id)
        if ldap_entry != []:
            print ldap_entry
            (dn_str,ldap_attr) = ldap_entry[0]
        else:
            dbg_print(WARN, "WARNING: CL Modify on object not in LDAP")
            return
        for entry in base_entry.keys():
            try:
                if (ldap_attr[entry] <> base_entry[entry]):
                    if entry in ('userPassword',):
                        pass
                    else:
                        print "Diff:", ldap_attr[entry], base_entry[entry]
                        value = (entry, base_entry[entry]),
                        attr_mod_ldap(dn_str, value)
            except KeyError:
                pass



def change_passwd(dn_id, ch_params):
    account = Account.Account(db)
    account.clear()
    account.find(dn_id)
    ldap_entry = []
    if account.has_spread(spread_id):
        search_str = "cn=%s" % account.account_name
        search_dn = "%s" % cereconf.NW_LDAP_ROOT
        ldap_entry = ldap_handle.GetObjects(search_dn,search_str)
    if ldap_entry == []:
        return
    try:
        attrs = []
        pwd = pickle.loads(ch_params)['password']
        attrs.append( ("userPassword", unicode(pwd, 'iso-8859-1').encode('utf-8')) )
        attr_mod_ldap(ldap_entry[0][0], attrs)
    except:
        pass
    



def group_mod(ch_type,dn_id,dn_dest,log_id):
    # We remember groups we're done with because we don't want to
    # re-read LDAP for every group_mod event.
    group = Group.Group(db)
    group.clear()
    group.entity_id = int(dn_dest)
    group_name = cereconf.NW_GROUP_PREFIX + group.get_name(co.group_namespace) + cereconf.NW_GROUP_POSTFIX
    search_str = "cn=%s" % group_name
    search_dn = "%s" % cereconf.NW_LDAP_ROOT
    if group_done.has_key(dn_dest):
        return
    else:
        print "Group mod on id", dn_dest
    ldap_obj = ldap_handle.GetObjects(search_dn,search_str)
    if ldap_obj <> []:
        (ldap_group, ldap_attrs) = ldap_obj [0]
        for mem in group.get_members(spread=spread_id):
            user_add_del_grp(ch_type,mem,dn_dest)
        group_done[dn_dest] = "Synced"
    else:
       # Group not in LDAP (yet)
       dbg_print(WARN, "WARNING: Group %s not found in LDAP" % search_str)
       group_done[dn_dest] = "not found"
    
    

def load_cltype_table(cltype):
    for clt,proc in cl_entry.items():
	# make if-entry to list in cereconf to remove dynamic service
	cltype[int(getattr(co,clt))] = proc	


def usage(exitcode=0):
    print """Usage: nwqsync.py [ -S server ] [ -p port ] -s spread """
    sys.exit(exitcode)


def main():
    global ldap_handle, dbg_level
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
        dbg_print(INFO, 'INFO: Novell eDirectory quicksync starting at %s' % nwutils.now())
        ldap_handle = nwutils.LDAPConnection(host, port,
                                    binddn=cereconf.NW_ADMINUSER, password=cereconf.NW_PASSWORD, scope='sub')
        load_cltype_table(cltype)                            
        nwqsync(spread)
        dbg_print(INFO, 'INFO: Novell eDirectory quicksync done at %s' % nwutils.now())
    else:
        usage(1);        
    
    
        
        
if __name__ == '__main__':
    main()
