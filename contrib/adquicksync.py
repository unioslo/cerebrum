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
import re
import pickle

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import OU
from Cerebrum import Entity
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum.modules import CLHandler
import adutils

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
clco = Factory.get('CLConstants')(db)
entity = Entity.Entity(db)
entityname = Entity.EntityName(db)
ou = OU.OU(db)
group = Group.Group(db)
account = Account.Account(db)
cl = CLHandler.CLHandler(db)

delete_users = 0
delete_groups = 0
debug = False


def quick_user_sync():

#TBD: Will fail if remove spread is run on an entity that also is
#     removed from Cerebrum database.

    answer=cl.get_events('ad',(clco.group_add,clco.group_rem,clco.account_password,clco.spread_add,clco.spread_del,clco.quarantine_add,clco.quarantine_del,clco.quarantine_mod))

    for ans in answer:
        chg_type = ans['change_type_id']
        if debug:
            print "change_id:",ans['change_id']
        cl.confirm_event(ans)
        if chg_type == clco.account_password:
            change_params = pickle.loads(ans['change_params'])
            if change_pw(ans['subject_entity'],change_params):
		cl.confirm_event(ans)            
	    else:	            
		print 'WARNING: failed changing password for ',ans['subject_entity']
        elif chg_type == clco.group_add or chg_type == clco.group_rem:
            entity.clear()
            entity.find(ans['subject_entity'])
            #TBD:A group added to a group should be expanded and its members added. 
            if entity.has_spread(int(co.spread_uio_ad_account)):
                group.clear()
                g_obj = group.find(ans['dest_entity'])
                if group.has_spread(int(co.spread_uio_ad_group)):
                    account_name = id_to_name(ans['subject_entity'],'user')
                    group_name = id_to_name(ans['dest_entity'],'group')
                    if debug:
                        print ("account:%s,group_name:%s") % (account_name,group_name)
                    if chg_type == clco.group_add:
                        if group_add(account_name,group_name):
			    cl.confirm_event(ans)
			else:
		            print 'WARNING: failed adding',account_name,' to group ',group_name
                    else:    
			if group_rem(account_name,group_name):
			    cl.confirm_event(ans)
			else:
			    print 'WARNING: failed removing',account_name,' from group ',group_name            
		else:
                    if debug:
                        print ans['dest_entity'], 'add/rem group: missing spread_uio_ad_group'
            else:
                if debug:
                    print ans['subject_entity'],' add/rem group: missing spread_uio_ad_account'

        elif chg_type == clco.spread_add:
            change_params = pickle.loads(ans['change_params'])
            if add_spread(ans['subject_entity'],change_params['spread']):
		cl.confirm_event(ans)
        elif chg_type == clco.spread_del:
            change_params = pickle.loads(ans['change_params'])
            if del_spread(ans['subject_entity'],change_params['spread']):
		cl.confirm_event(ans)
	elif chg_type == clco.quarantine_add or chg_type == clco.quarantine_del or chg_type == clco.quarantine_mod:
	
	    change_quarantine(ans['subject_entity']) 
    cl.commit_confirmations()    


def change_quarantine(entity_id):
    account.clear()
    account.find(entity_id)
    if account.has_spread(int(co.spread_uio_ad_account)):	
    	if adutils.chk_quarantine(entity_id):
	    del_spread(entity_id,co.spread_uio_ad_account,0)
    	else:
	    add_spread(entity_id,co.spread_uio_ad_account)


def add_spread(entity_id,spread):
    if spread == co.spread_uio_ad_account:
        #TBD: Account must be added to relevant groups.
        account_name =id_to_name(entity_id,'user')	
	ou.clear()
    	ou.find(cereconf.AD_CERE_ROOT_OU_ID)
    	ourootname='OU=%s' % ou.acronym        
        
        if cereconf.AD_DEFAULT_OU=='0':
            ad_ou='CN=Users,%s' % (cereconf.AD_LDAP)
        else:
            pri_ou = adutils.get_primary_ou( entity_id, co.account_namespace)
            if not pri_ou:
                print "WARNING: No account_type information for object ", id
                ad_ou='CN=Users,%s' % (cereconf.AD_LDAP)
            else:
                ad_ou = adutils.id_to_ou_path( pri_ou, ourootname)


        sock.send('TRANS&%s/%s\n' % (cereconf.AD_DOMAIN, account_name))
        ou_in_ad = sock.read()[0]
        if ou_in_ad[0:3] == '210':
            #Account already in AD, we move to correct OU.
            sock.send('MOVEOBJ&%s&LDAP://%s\n' % ( ou_in_ad[4:],ad_ou )) 
        else:
            sock.send('NEWUSR&LDAP://%s&%s&%s\n' % ( ad_ou, account_name, account_name))
            #Set a random password on user, bacause NEWUSR creates an
            #account with blank password.
            if sock.read() == ['210 OK']:
                pw = account.make_passwd(account_name)
                pw=pw.replace('%','%25')
                pw=pw.replace('&','%26')
                sock.send('ALTRUSR&%s/%s&pass&%s\n' % (cereconf.AD_DOMAIN,account_name,pw))
            else:
                'WARNING: Failed creating new user ', account_name

        if sock.read() == ['210 OK']:            
            (full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE, login_script) = adutils.get_user_info(entity_id,account_name)
            sock.send('ALTRUSR&%s/%s&fn&%s&dis&%s&hdir&%s&hdr&%s&ls&%s&pexp&%s&ccp&%s\n' % ( cereconf.AD_DOMAIN, account_name, full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE, login_script, cereconf.AD_PASSWORD_EXPIRE, cereconf.AD_CANT_CHANGE_PW ))  
            #TBD:Even a new user that received AD_spread can have a quarantine setting.
            if sock.read() == ['210 OK']:
                #Make sure that the user is in the groups he should be.
                for row in group.list_groups_with_entity(account.entity_id):
                    group.clear()
                    group.find(row['group_id'])
                    if group.has_spread(int(co.spread_uio_ad_group)):
                        grp_name = '%s-gruppe' % (group.group_name)
                        if not group_add(account_name,grp_name):
                            print 'WARNING: add user %s to group %s failed' % (account_name,grp_name)                    
        else:    
            #TBD: This is serious and should write to std.err.
            print 'CRITICAL: ', account_name ,', failed replacing blank password.' 
            return False	            

    elif spread == co.spread_uio_ad_group:
        grp=id_to_name(entity_id,'group')
           
        if cereconf.AD_DEFAULT_OU=='0':
            ad_ou='CN=Users,%s' % (cereconf.AD_LDAP)
        else:
            ou.clear()
            ou.find(cereconf.AD_CERE_ROOT_OU_ID)
            ourootname='OU=%s' % ou.acronym
            ad_ou = id_to_ou_path(cereconf.AD_DEFAULT_OU,ourootname)

	sock.send('TRANS&%s/%s\n' % (cereconf.AD_DOMAIN, grp))
        ou_in_ad = sock.read()[0]
        if ou_in_ad[0:3] == '210':
            #Account already in AD, we move to correct OU.
            sock.send('MOVEOBJ&%s&LDAP://%s\n' % ( ou_in_ad[4:],ad_ou )) 
	else:
            sock.send('NEWGR&LDAP://%s&%s&%s\n' % ( ad_ou, grp, grp))        
        if sock.read() == ['210 OK']:
            group.clear()
            group.find(entity_id)
            for grpmemb in group.get_members():
                account.clear()
                account.find(grpmemb)
                if account.has_spread(co.spread_uio_ad_account):
                    name = account.get_name(int(co.account_namespace))
                    print 'INFO:Add', name, 'to', grp                
                    sock.send('ADDUSRGR&%s/%s&%s/%s\n' % (cereconf.AD_DOMAIN, name, cereconf.AD_DOMAIN, grp))
                    if sock.read() != ['210 OK']:		
                        print 'WARNING: Failed add', name, 'to', grp
	    return True
        print 'WARNING: create group failed ', grp,'in Users'
    else:
        if debug:
            print 'Add spread:', spread , ' not an ad_spread'
        return True    


def del_spread(entity_id,spread,delete=delete_users):

    if spread == co.spread_uio_ad_account:
        user=id_to_name(entity_id,'user')
        if delete:
            sock.send('DELUSR&%s/%s\n' % (cereconf.AD_DOMAIN, user))
            if sock.read() != ['210 OK']:
                print 'WARNING: Error deleting, ', user
        else:
            sock.send('ALTRUSR&%s/%s&dis&1\n' % ( cereconf.AD_DOMAIN, user))
            if sock.read() != ['210 OK']:
                print 'WARNING: Error disabling account', user
             
            sock.send('TRANS&%s/%s\n' % ( cereconf.AD_DOMAIN, user))
            ldap = sock.read()[0]
            if ldap[0:3] != "210":
                print 'WARNING: Error getting WinNT from LDAP path for', user
            else:
                if cereconf.AD_LOST_AND_FOUND not in adutils.get_ad_ou(ldap[4:]):
                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (
                        ldap[4:], cereconf.AD_LOST_AND_FOUND, cereconf.AD_LDAP))
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Error moving:', ldap[4:], 'to',cereconf.AD_LOST_AND_FOUND
                
    elif spread == co.spread_uio_ad_group:
        group_n=id_to_name(entity_id,'group')         
        if delete_groups:
            sock.send('DELGR&%s/%s\n' % (cereconf.AD_DOMAIN, group_n))
            if sock.read() != ['210 OK']:
                print 'WARNING: Error deleting ',group_n
        else:             
            sock.send('TRANS&%s/%s\n' % ( cereconf.AD_DOMAIN, group_n))
            ldap = sock.read()
            if ldap[0][0:3] != "210":
                print 'WARNING: Error Transforming WinNT to LDAP for', group_n
            else:
                if cereconf.AD_LOST_AND_FOUND not in adutils.get_ad_ou(ldap[0]):
                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (
                        ldap[0], cereconf.AD_LOST_AND_FOUND, cereconf.AD_LDAP))
                    if sock.read() == ['210 OK']:
                        sock.send('LGROUP&%s/%s\n' % (cereconf.AD_DOMAIN, group_n))
                        result = sock.readgrp()
                        for line in result.splitlines:
                            if line != '210 OK':
                                mem = l.split('&')
                                sock.send('DELUSRGR&%s/%s&%s/%s\n' % (cereconf.AD_DOMAIN, mem[1], cereconf.AD_DOMAIN, group_n))
                                if sock.read() != ['210 OK']:
                                    print 'WARNING: Failed delete', member, 'from', group_n    
                    else:
                        print 'WARNING: Error moving:', ldap[0], 'to',cereconf.AD_LOST_AND_FOUND            
                    
    else:
        if debug:            
            print 'Delete spread: ',spread,' not an AD spread.'
        return True     


def group_add(account_name,group_name):
    sock.send('ADDUSRGR&%s/%s&%s/%s\n' % ( cereconf.AD_DOMAIN,account_name, cereconf.AD_DOMAIN,group_name ))
    if sock.read() == ['210 OK']:
	return True
    return False		


def group_rem(account_name,group_name):
    sock.send('DELUSRGR&%s/%s&%s/%s\n' % ( cereconf.AD_DOMAIN,account_name, cereconf.AD_DOMAIN,group_name ))
    if sock.read() == ['210 OK']:
	return True
    return False


def change_pw(account_id,pw_params):
    account.clear()
    account.find(account_id)
    if account.has_spread(int(co.spread_uio_ad_account)):
        pw=pw_params['password']
        #These numbers represent the location in the ASCII table.
        pw=pw.replace('%','%25')
        pw=pw.replace('&','%26')
        user = id_to_name(account_id,'user')
        sock.send('ALTRUSR&%s/%s&pass&%s\n' % (cereconf.AD_DOMAIN,user,pw))
        if sock.read() == ['210 OK']:
	    return True
    else:
        if debug:
            print "Change password: Account %s, missing ad_spread" % (account_id)
        return True
    return False

            
def id_to_name(id,entity_type):
    grp_postfix = ''
    if entity_type == 'user':
        e_type = int(co.entity_account)
        namespace = int(co.account_namespace)
    elif entity_type == 'group':
        e_type = int(co.entity_group)
        namespace = int(co.group_namespace)
        grp_postfix = cereconf.AD_GROUP_POSTFIX
    entityname.clear()
    entityname.find(id)
    name = entityname.get_name(namespace)
    obj_name = "%s%s" % (name,grp_postfix)
    return obj_name
    
        
def get_args():
    global delete_users
    global delete_groups
    for arrrgh in sys.argv:
        if arrrgh == '--delete_users':
            delete_users = 1
        elif arrrgh == '--delete_groups':
            delete_groups = 1


if __name__ == '__main__':
    sock = adutils.SocketCom()  
    arg = get_args()    
    quick_user_sync()
    sock.close()

