#!/usr/bin/env python2.2
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

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules import ADObject
from Cerebrum import OU
from Cerebrum import Entity
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum.modules import ADAccount
from Cerebrum.modules import CLHandler
import adutils

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
clco = Factory.get('CLConstants')(db)
ad_object = ADObject.ADObject(db)
ad_account = ADAccount.ADAccount(db)
entity = Entity.Entity(db)
entityname = Entity.EntityName(db)
ou = OU.OU(db)
group = Group.Group(db)
account = Account.Account(db)
cl = CLHandler.CLHandler(db)

delete_users = 0
delete_groups = 0


def quick_user_sync():

#
# Cases when updates is done in ad-domain. 
#
# OK:account added spread ad
# OK:account delete spread ad
# account quarantined
# OK:account changed password
# NOT NEEDED IN V.1.0: account changed value in ad tables
# CAN WAIT FOR HIST: user moved disk

# OK:group added spread ad
# OK:group deleted spread ad
# group quarantined
# OK:account added to group with spread ad
# OK:account deleted from group with spread ad
#

    answer=cl.get_events('ad',(clco.g_add,clco.g_rem,clco.a_password,clco.s_add,clco.s_del))

    for ans in answer:
        chg_type = ans['change_type_id']
        
        if chg_type == clco.a_password:
            change_params = pickle.loads(ans['change_params'])
            change_pw(ans['subject_entity'],change_params)            

        elif chg_type == clco.g_add or chg_type == clco.g_rem:
            account.clear()
            a_obj = account.find(ans['subject_entity'])
            #test: account.add_spread(int(co.spread_uio_ad_account))
            if account.got_spread(int(co.spread_uio_ad_account)):
                group.clear()
                g_obj = group.find(ans['dest_entity'])

                if group.got_spread(int(co.spread_uio_ad_group)):
                    print ans['dest_entity'], "missing spread_uio_ad_group"

                else:
                    account_id = id_to_name(ans['subject_entity'],'user')
                    group_id = id_to_name(ans['dest_entity'],'group')

                    if chg_type == clco.g_add:
                        group_add(account_id,group_id)
                    else:
                        group_rem(account_id,group_id)
            else:
                print ans['subject_entity'], "missing spread_uio_ad_account"

        elif chg_type == clco.s_add:
            change_params = pickle.loads(ans['change_params'])
            add_spread(ans['subject_entity'],change_params)
        elif chg_type == clco.s_del:
            change_params = pickle.loads(ans['change_params'])
            del_spread(ans['subject_entity'],change_params)
#        cl.commit()    



def add_spread(entity_id,param):
    spread=param['spread']
    
    if spread == co.spread_uio_ad_account:
        account=id_to_name(entity_id,'user')
        print 'adding new user ',account
        entity.clear()
        entity.find(entity_id)
        
        try:
            ad_object.clear()
            ad_object.find(entity_id)
        except:
            print "populating ad_object"
            ad_object.clear()
            ad_object.populate(int(cereconf.AD_DEFAULT_OU), None, entity )
            ad_object.write_db()
            ad_object.commit()
        #find users homedir.
        homedir = find_home_dir(account)
        loginscript = find_login_script(account)
        #Adding user to ad table.
        try:
            ad_account.clear()
            ad_account.find(entity_id)
            
        except:
            print "populating ad_account"
            ad_account.clear()
            ad_account.populate(loginscript, homedir, None, None, ad_object)
            ad_account.write_db()
            ad_account.commit()

        if cereconf.AD_DEFAULT_OU == '0':
            ad_ou = 'CN=Users'
        else:
            ou.clear()
            ou.find(int(cereconf.AD_DEFAULT_OU))
            ad_ou = 'OU=',ou.acronym
        sock.send('NEWUSR&LDAP://%s,%s&%s&%s\n' % ( ad_ou, cereconf.AD_LDAP, account, account))
        if sock.read() == ['210 OK']:
            passw = adutils.get_password(entity_id)
            (full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE, login_script) = adutils.get_user_info(entity_id)

            sock.send('ALTRUSR&%s/%s&pass&%s&fn&%s&dis&%s&hdir&%s&hdr&%s&ls&%s&pexp&%s&ccp&%s\n' % ( cereconf.AD_DOMAIN, account, passw, full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE, login_script, cereconf.AD_PASSWORD_EXPIRE, cereconf.AD_CANT_CHANGE_PW ))  

            if sock.read() != ['210 OK']:
                print 'WARNING: alter user failed for ', user
        else:
            print 'WARNING:creating account ',account,' in ',ad_ou,' failed'
            
    elif spread == co.spread_uio_ad_group:
        grp=id_to_name(entity_id,'group')
        #Add group to ad_entity table.
        entity.clear()
        entity.find(entity_id)

        try:
            ad_object.clear()
            ad_object.find(entity_id)
        except:
            print  "populating ad_object"
            ad_object.clear()
            ad_object.populate(int(cereconf.AD_DEFAULT_OU), None, entity )
            ad_object.write_db()
            ad_object.commit()

        if cereconf.AD_DEFAULT_OU == '0':
            ad_ou = 'CN=Users'
        else:
            ou.clear()
            ou.find(int(cereconf.AD_DEFAULT_OU))
            ad_ou = 'OU=',ou.acronym
        sock.send('NEWGR&LDAP://%s,%s&%s&%s\n' % ( ad_ou, cereconf.AD_LDAP, grp, grp))        

        if sock.read() == ['210 OK']:
            group.clear()
            group.find(entity_id)
            for grpmemb in group.get_members():
                ad_object.clear()
                try:
                    ad_object.find(grpmemb)
                except Errors.NotFoundError:
                    print 'WARNING:account ',grpmemb,' not found in ad_tables'  
                name = ad_object.get_name(int(co.account_namespace))
                if ad_object.got_spread(int(co.spread_uio_ad_account)):
                    print 'INFO:Add', name, 'to', grp                
                    sock.send('ADDUSRGR&%s/%s&%s/%s\n' % (cereconf.AD_DOMAIN, name, cereconf.AD_DOMAIN, grp))
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Failed add', name, 'to', grp
        else:
            print 'WARNING: create group failed ', grp,'in Users'
    else:
        print 'WARNING: unknown spread ',spread,' to add'



def del_spread(entity_id,param):
    spread=param['spread']    
    if spread == co.spread_uio_ad_account:
        user=id_to_name(entity_id,'user')
        if delete_users:
            sock.send('DELUSR&%s/%s\n' % (cereconf.AD_DOMAIN, user))
            if sock.read() != ['210 OK']:
                print 'WARNING: Error deleting, ', user
        else:
            sock.send('ALTRUSR&%s/%s&dis&1\n' % ( cereconf.AD_DOMAIN, user))
            if sock.read() != ['210 OK']:
                print 'WARNING: Error disabling account', user
             
            sock.send('TRANS&%s/%s\n' % ( cereconf.AD_DOMAIN, user))
            ldap = sock.read()
            if ldap[0][0:3] != "210":
                print 'WARNING: Error Transforming WinNT to LDAP for', user
            else:
                if cereconf.AD_LOST_AND_FOUND not in adutils.get_ad_ou(ldap[0][4:]):
                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (
                        ldap[0], cereconf.AD_LOST_AND_FOUND, cereconf.AD_LDAP))
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Error moving:', ldap[0], 'to', \
                              cereconf.AD_LOST_AND_FOUND
                
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
                if AD_LOST_AND_FOUND not in adutils.get_ad_ou(ldap[0]):
                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (
                        ldap[0], cereconf.AD_LOST_AND_FOUND, cereconf.AD_LDAP))
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Error moving:', ldap[0], 'to', \
                              cereconf.AD_LOST_AND_FOUND            
    else:
        print 'WARNING:unknown spread ',spread,' to delete'




def group_add(account_id,group_id):
    print 'Try adding ',account_id,' to group ',group_id
    sock.send('ADDUSRGR&%s/%s&%s/%s\n' % ( cereconf.AD_DOMAIN,account_id, cereconf.AD_DOMAIN,group_id ))
    if sock.read() != ['210 OK']:
        print 'WARNING: failed adding',account_id,' to group ',group_id



def group_rem(account_id,group_id):
    print 'Try removing ',account_id,' to group ',group_id
    sock.send('DELUSRGR&%s/%s&%s/%s\n' % ( cereconf.AD_DOMAIN,account_id, cereconf.AD_DOMAIN,group_id ))
    if sock.read() != ['210 OK']:
        print 'WARNING: failed removing',account_id,' from group ',group_id

        
    
def change_pw(account_id,pw_params):
    account.clear()
    a_obj = account.find(ans['subject_entity'])
    if account.got_spread(int(co.spread_uio_ad_account)):
        pw=pw_params['password']
        user = id_to_name(account_id,'user')
        sock.send('ALTRUSR&%s/%s&pass&%s\n' % (cereconf.AD_DOMAIN,user,pw))
        if sock.read() != ['210 OK']:
            print 'WARNING: failed changing password for ',user

            
def find_home_dir(account):
    #Here some work must be done to map samba servers to user.
    #The disk class do not have this value.  
    return "\\\\ulrik\\%s" % (account)

def find_login_script(account):
    #This value is a specific UIO standard.
    return "users\%s.bat" % (account)


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

