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
import time
import re

import cerebrum_path
import cereconf
import adutils
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.modules import ADAccount
from Cerebrum.modules import ADObject


db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ad_object = ADObject.ADObject(db)
ad_account = ADAccount.ADAccount(db)
ou = Factory.get('OU')(db)
ent_name = Entity.EntityName(db)
group = Factory.get('Group')(db)
account = Factory.get('Account')(db)

delete_users = 0
delete_groups = 0
domainusers = []
#For test,
max_nmbr_users = 60000

def full_ou_sync():

    #Will not delete OUs only create new ones.
    print 'INFO: Starting full_ou_sync at', adutils.now()
    OUs = []
    root = cereconf.AD_CERE_ROOT_OU_ID   
    sock.send('LORGS&LDAP://%s\n' % (cereconf.AD_LDAP))
    receive = []
    #TODO: some problem arise if out=0
    receive = sock.read(out=1)
    res=[]
    for line in receive:
        for l in line.splitlines():
            res.append(l[16:])
    OUs = res[1:-1]
    if not 'OU=%s,%s' % (cereconf.AD_LOST_AND_FOUND,cereconf.AD_LDAP) in OUs:
        sock.send('NEWORG&LDAP://%s&%s&%s\n' % ( cereconf.AD_LDAP, cereconf.AD_LOST_AND_FOUND, cereconf.AD_LOST_AND_FOUND))
        if sock.read() != ['210 OK']:
            print "WARNING: create OU AD_LOST_AND_FOUND failed"

    def find_children(parent_id,parent_acro):

        ou.clear()
        ou.find(parent_id)
        chldrn = ou.list_children(co.perspective_lt)

        for child in chldrn:
            name=parent_acro
            ou.clear()
            ou.find(child['ou_id'])
            if ou.acronym:
                name = 'OU=%s,%s' % (ou.acronym,name)
                if not name.replace('/','\/') in OUs:
                    
                    print "INFO:creating ",ou.acronym," in ",parent_acro
                    sock.send('NEWORG&LDAP://%s&%s&%s\n' % ( parent_acro, ou.acronym, ou.acronym ))
                    if sock.read() != ['210 OK']:
                        print "WARNING:failed creating ",ou.acronym," in ",parent_acro
                        
            chldrn = ou.list_children(co.perspective_lt)
            find_children(child['ou_id'], name)

    children = find_children(root,cereconf.AD_LDAP)



def full_user_sync():
    """Checking each user in AD, and compare with cerebrum information."""
    # TODO:Mangler en mer stabil sjekk på hvilken OU brukeren hører hjemme
    # utfra cerebrum
        
    global domainusers
    print 'INFO: Starting full_user_sync at', adutils.now()
    adusers = {}
    adusers = get_ad_objects('user')
    # Initialize socket at this point, because socket timeout. 	
    sock = adutils.SocketCom()    	
    sock.send('LUSERS&LDAP://%s&1\n' % (cereconf.AD_LDAP))
    receive = sock.read(out=0)
    
    for line in receive[1:-1]:
        fields = line.split('&')
        domainusers.append(fields[3])
        if fields[3] in adusers:
            user_id = adusers[fields[3]]
            
            if 'CN=%s,%s' % (fields[3],user_id[1]) != fields[1][7:]:
                sock.send('MOVEOBJ&%s&LDAP://%s\n' % (fields[1], user_id[1]))
                if sock.read() != ['210 OK']:
                    print "WARNING: move user failed, ", fields[1], 'to', user_id[1]

            (full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE,
             login_script) = adutils.get_user_info(user_id[0],fields[3])            
            # TODO: cereconf.AD_CANT_CHANGE_PW is set as initial value for
            # a new user, the value is not changeable afterwards. Issue should be
            # worked out in the adsiservice 
            try:
#                print "cere:",full_name, account_disable, cereconf.AD_HOME_DRIVE, home_dir,login_script
#                print "ad  :",fields[9],fields[17],fields[15], fields[7], fields[13]
                if ((full_name, account_disable, cereconf.AD_HOME_DRIVE, str(home_dir),str(login_script)) != (fields[9],fields[17],fields[15], fields[7], fields[13])):
                    
                    sock.send('ALTRUSR&%s/%s&fn&%s&dis&%s&hdir&%s&hdr&%s&ls&%s&pexp&%s&ccp&%s\n' % ( cereconf.AD_DOMAIN, fields[3], full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE, login_script, cereconf.AD_PASSWORD_EXPIRE, cereconf.AD_CANT_CHANGE_PW))
                    
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Error updating fields for', fields[3]
                #else:
                    print "INFO:Bruker ",fields[3]," OK"
            except IndexError:
                print "WARNING: list index out of range, fields:", full_name, account_disable, cereconf.AD_HOME_DRIVE, home_dir, login_script, cereconf.AD_PASSWORD_EXPIRE 
            del adusers[fields[3]]
        elif fields[3] in cereconf.AD_DONT_TOUCH:
            pass
        else:
            if delete_users:
                sock.send('DELUSR&%s/%s\n' % (cereconf.AD_DOMAIN, fields[3]))
                if sock.read() != ['210 OK']:
                    print 'WARNING: Error deleting, ', fields[3]
            else:
                if cereconf.AD_LOST_AND_FOUND not in adutils.get_ad_ou(fields[1]):
                    sock.send('ALTRUSR&%s/%s&dis&1\n' % ( cereconf.AD_DOMAIN, fields[3]))
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Error disabling account', fields[3]
                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (fields[1], cereconf.AD_LOST_AND_FOUND, cereconf.AD_LDAP))
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Error moving, ', fields[3], 'to', cereconf.AD_LOST_AND_FOUND
                    

    for user in adusers:
        # The remaining accounts in the list should be created.
        user_id = adusers[user]
        sock.send('NEWUSR&LDAP://%s&%s&%s\n' % (user_id[1] ,user, user))
        if sock.read() == ['210 OK']:
            print 'INFO: created user, ', user, 'in Users'
            #Set a random password on the created user, and remove & characters.
            passw = account.make_passwd(user)
            passw=passw.replace('%','%25')
            passw=passw.replace('&','%26')
            (full_name,account_disable,home_dir,cereconf.AD_HOME_DRIVE,login_script)\
                    = adutils.get_user_info(user_id[0],user)
            sock.send('ALTRUSR&%s/%s&pass&%s&fn&%s&dis&%s&hdir&%s&hdr&%s&ls&%s&pexp&%s&ccp&%s\n' % (cereconf.AD_DOMAIN,user,passw,full_name,\
                    account_disable,home_dir,cereconf.AD_HOME_DRIVE,login_script,cereconf.AD_PASSWORD_EXPIRE,cereconf.AD_CANT_CHANGE_PW))            
            if sock.read() != ['210 OK']:
                sock.send('DELUSR&%s/%s\n' % (cereconf.AD_DOMAIN, user))
                if sock.read() != ['210 OK']:
                    print 'FATAL: Error deleting account after failed alteration of new user:', user, ', probably unsecure password.'                    
        else:
            print 'WARNING: create user failed, ', user, ' in ',user_id[1]
    sock.close()

#For testing of Group sync..
def gen_domain_users():

    global domainusers
    print 'INFO: Starting gen_domain_users at', adutils.now()
    sock.send('LUSERS&LDAP://%s&1\n' % (cereconf.AD_LDAP))
    receive = sock.read(out=1)    
    for line in receive[1:-1]:
        fields = line.split('&')
        domainusers.append(fields[3])



def full_group_sync():
    """Checking each group in AD, and compare with cerebrum"""
    print 'INFO: Starting full_group_sync at', adutils.now()
    global domainusers
    adgroups = {}
    adgroups = get_ad_objects(int(co.entity_group))
    # Initialize socket at this point, because socket timeout. 	
    sock = adutils.SocketCom()    	
    sock.send('LGROUPS&LDAP://%s\n' % (cereconf.AD_LDAP))
    receive = sock.read(out=0)
    for line in receive[1:-1]:
        fields = line.split('&')
        if fields[3] in adgroups:
            grp_id = adgroups[fields[3]]
            print 'INFO: updating group:', fields[3]
            
            if 'CN=%s,%s' % (fields[3],grp_id[1]) != fields[1][7:]:
                sock.send('MOVEOBJ&%s&LDAP://%s\n' % (fields[1], grp_id[1]))
                if sock.read() != ['210 OK']:
                    print "WARNING: move user failed, ", fields[1], 'to', grp_id[1]

            # AD service only list user members not group members of
            # groups, therefore Cerebrum groups are expanded to a list
            # of users.
            group.clear()
            group.find(grp_id[0])
            memblist = []
            for grpmemb in group.get_members():
                try:
                    ent_name.clear()
                    ent_name.find(grpmemb)                   
                    if ent_name.has_spread(co.spread_uio_ad_account):
                        name = ent_name.get_name(int(co.account_namespace))
                        if not name in memblist:
                            memblist.append(name)
                except Errors.NotFoundError:
                    print "WARNING: Could not find groupmemb,", grpmemb

            sock.send('LGROUP&%s/%s\n' % (cereconf.AD_DOMAIN, fields[3]))
            result = sock.readgrp()
            for line in result.splitlines():
                if line != '210 OK':
                    mem = line.split('&')
                    if mem[1] in memblist:
                        memblist.remove(mem[1])
                    else:
                        sock.send('DELUSRGR&%s/%s&%s/%s\n' % (cereconf.AD_DOMAIN, mem[1], cereconf.AD_DOMAIN, fields[3]))
                        if sock.read() != ['210 OK']:
                            print 'WARNING: Failed delete', mem[1] , 'from', fields[1]
                                  
            for memb in memblist:
                if memb in domainusers:
                    sock.send('ADDUSRGR&%s/%s&%s/%s\n' % (cereconf.AD_DOMAIN, memb, cereconf.AD_DOMAIN, fields[3]))
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Failed add', memb, 'to', fields[3] 
                else:
                    print "WARNING:groupmember",memb,"in group",fields[3],"not in AD"
            del adgroups[fields[3]]

        elif fields[3] in cereconf.AD_DONT_TOUCH:
            pass
        else:
            if delete_groups:
                sock.send('DELGR&%s/%s\n' % (cereconf.AD_DOMAIN, fields[3]))
                if sock.read() != ['210 OK']:
                    print 'WARNING: Error deleting ', fields[3]
            else:
                if cereconf.AD_LOST_AND_FOUND not in adutils.get_ad_ou(fields[1]):
                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (
                        fields[1], cereconf.AD_LOST_AND_FOUND, cereconf.AD_LDAP))
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Error moving:', fields[3], 'to', \
                              cereconf.AD_LOST_AND_FOUND


    for grp in adgroups:
        # The remaining is new groups and should be created.

        sock.send('NEWGR&LDAP://%s&%s&%s\n' % ( adgroups[grp][1], grp, grp))
        if sock.read() == ['210 OK']:
            group.clear()
            group.find(adgroups[grp][0])
            for grpmemb in group.get_members():
                try:
                    ent_name.clear()
                    ent_name.find(grpmemb)
                    name = ent_name.get_name(int(co.account_namespace))
                    if name in domainusers:
                        print 'INFO:Add', name, 'to', grp
                        sock.send('ADDUSRGR&%s/%s&%s/%s\n' % (cereconf.AD_DOMAIN, name, cereconf.AD_DOMAIN, grp))
                        if sock.read() != ['210 OK']:
                            print 'WARNING: Failed add', name, 'to', grp
                    else:
                        print "WARNING: groupmember",name,"in group",grp,"not in AD"
                except Errors.NotFoundError:
                    print "WARNING: Could not find group member ",grpmemb," in db"
        else:
            print 'WARNING: create group failed ', grp,'in Users'
    
    sock.close()

def get_args():
    global delete_users
    global delete_groups
    for arrrgh in sys.argv:
        if arrrgh == '--delete_users':
            delete_users = 1
        elif arrrgh == '--delete_groups':
            delete_groups = 1


def get_ad_objects(entity_type):
    #get all objects with spread ad, in a hash identified by name with id and ou.
    global max_nmbr_users
    grp_postfix = ''
    if entity_type == 'user':
        e_type = int(co.entity_account)
        namespace = int(co.account_namespace)
        spread = int(co.spread_uio_ad_account)
    else:
        e_type = int(co.entity_group)
        namespace = int(co.group_namespace)
        grp_postfix = cereconf.AD_GROUP_POSTFIX
        spread = int(co.spread_uio_ad_group)
    ulist = {}
    count = 0    
    ou.clear()
    ou.find(cereconf.AD_CERE_ROOT_OU_ID)
    ourootname='OU=%s' % ou.acronym
    
    for row in ent_name.list_all_with_spread(spread):
        count = count+1
        if count > max_nmbr_users: break
        id = row['entity_id']
# removed because it's obsolite.
#        try:
#            ad_object.clear()
#            ad_object.find(id)
#            ou_path = adutils.id_to_ou_path(ad_object.ou_id,ourootname)
#            id_and_ou = id, ou_path 
#            name = ad_object.get_name(namespace)            
#            obj_name = '%s%s' % (name,grp_postfix)
#            ulist[obj_name]=id_and_ou
#        except Errors.NotFoundError:
	ent_name.clear()
        ent_name.find(id)
        name = ent_name.get_name(namespace)
        if entity_type == 'user':
	    if cereconf.AD_DEFAULT_OU == '0':
      		crbrm_ou = 'CN=Users,%s' % cereconf.AD_LDAP
	    else:
	        pri_ou = adutils.get_primary_ou(id,namespace)              
		if not pri_ou:
		    count = count - 1
		    print "WARNING: No account_type information for object ", id
            	else:    
                    crbrm_ou = adutils.id_to_ou_path( pri_ou ,ourootname)
 
            id_and_ou = id, crbrm_ou
            obj_name = '%s' % (name)
            ulist[obj_name]=id_and_ou    

        else:
            if cereconf.AD_DEFAULT_OU == '0':
      		crbrm_ou = 'CN=Users,%s' % cereconf.AD_LDAP
            else:
                crbrm_ou = adutils.get_crbrm_ou(adutils.AD_DEFAULT_OU)
            
	    id_and_ou = id, crbrm_ou
            obj_name = '%s%s' % (name,grp_postfix)
            ulist[obj_name]=id_and_ou
                
    print "INFO: Found %s nmbr of objects" % (count)
    return ulist

                    
if __name__ == '__main__':

#    sock = adutils.SocketCom()    
    arg = get_args()
#    full_ou_sync()
    full_user_sync()
#    gen_domain_users()
    full_group_sync()


# arch-tag: 3fe00456-c60e-45a0-b034-f682f07b6362
