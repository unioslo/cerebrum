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
from Cerebrum import Errors
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
# OK:account added spread ad, but missing adding user to relevant groups.
# OK:account delete spread ad, ad takes care of removing user from groups.
# OK:account changed password
# NOT NEEDED IN V.1.0: account changed value in ad tables
# account_mod
# CAN WAIT FOR HIST:account_move
# NOT NEEDED IN V.1.0: ou set parent
# OK:group added spread ad
# OK:group deleted spread ad
# OK:account added to group with spread ad
# OK:account deleted from group with spread ad
# quarantine_add for account.
# quarantine_del for account.


    answer=cl.get_events('ad',(clco.group_add,clco.group_rem,clco.account_password,clco.spread_add,clco.spread_del))

    for ans in answer:
        chg_type = ans['change_type_id']
        
        if chg_type == clco.account_password:
            change_params = pickle.loads(ans['change_params'])
            change_pw(ans['subject_entity'],change_params)            

        elif chg_type == clco.group_add or chg_type == clco.group_rem:
            account.clear()
            a_obj = account.find(ans['subject_entity'])
            #test: account.add_spread(int(co.spread_uio_ad_account))
            if account.has_spread(int(co.spread_uio_ad_account)):
                group.clear()
                g_obj = group.find(ans['dest_entity'])

                if group.has_spread(int(co.spread_uio_ad_group)):
                    print ans['dest_entity'], "missing spread_uio_ad_group"

                else:
                    account_id = id_to_name(ans['subject_entity'],'user')
                    group_id = id_to_name(ans['dest_entity'],'group')

                    if chg_type == clco.group_add:
                        group_add(account_id,group_id)
                    else:
                        group_rem(account_id,group_id)
            else:
                print ans['subject_entity'], "missing spread_uio_ad_account"

        elif chg_type == clco.spread_add:
            change_params = pickle.loads(ans['change_params'])
            add_spread(ans['subject_entity'],change_params)
        elif chg_type == clco.spread_del:
            change_params = pickle.loads(ans['change_params'])
            del_spread(ans['subject_entity'],change_params)
        cl.commit()    



def add_spread(entity_id,param):
    spread=param['spread']

    if spread == co.spread_uio_ad_account:
        #TBD: Account must be added to relevant groups.
        account_name =id_to_name(entity_id,'user')
                
        try:
            ad_object.clear()
            ad_object.find(entity_id)
            ad_ou = adutils.id_to_ou_path(ad_object.ou_id,ourootname)                
        except Errors.NotFoundError:
            pri_ou = adutils.get_primary_ou( entity_id, co.account_namespace)
            if not pri_ou:
                print "WARNING: No account_type information for object ", id
            else:
                ad_ou = adutils.id_to_ou_path( pri_ou, ourootname)

        sock.send('TRANS&%s/%s\n' % (cereconf.AD_DOMAIN, account_name))
        ou_in_ad = sock.read()[0]
        if ou_in_ad[0:3] == '210':
            #Account already in AD, we move to correct OU.
            sock.send('MOVEOBJ&%s&LDAP://%s\n' % ( ou_in_ad[4:],ad_ou )) 
        else:
            sock.send('NEWUSR&LDAP://%s&%s&%s\n' % ( ad_ou, account_name, account_name))
            
        if sock.read() == ['210 OK']:
            #Should users already in AD keep their old password??
            pw = account.make_passwd(account_name)
            pw=pw.replace('%','%25')
            pw=pw.replace('&','%26')
            
            (full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE, login_script) = adutils.get_user_info(entity_id,account_name)
            
            sock.send('ALTRUSR&%s/%s&pass&%s&fn&%s&dis&%s&hdir&%s&hdr&%s&ls&%s&pexp&%s&ccp&%s\n' % ( cereconf.AD_DOMAIN, account_name, pw, full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE, login_script, cereconf.AD_PASSWORD_EXPIRE, cereconf.AD_CANT_CHANGE_PW ))  

            if sock.read() != ['210 OK']:
                print 'WARNING: alter user failed for ', account_name
        else:
            print 'WARNING:create/move of account ',account_name,' in/to ',ad_ou,' failed'
            
    elif spread == co.spread_uio_ad_group:
        grp=id_to_name(entity_id,'group')
           
        try:
            ad_object.clear()
            ad_object.find(entity_id)
            ad_ou = ad_object.ou_id
        except:
            if cereconf.AD_DEFAULT_OU=='0':
                ad_ou='CN=Users,%s' % (cereconf.AD_LDAP)
            else:
                ou.clear()
                ou.find(cereconf.AD_CERE_ROOT_OU_ID)
                ourootname='OU=%s' % ou.acronym
                ad_ou = id_to_ou_path(cereconf.AD_DEFAULT_OU,ourootname)

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
                        TBD: Should remove all users from the group.
                        pass                    
                    else:
                        print 'WARNING: Error moving:', ldap[0], 'to',cereconf.AD_LOST_AND_FOUND            
                    
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
    account.find(ans['subject_entity'])
    if account.has_spread(int(co.spread_uio_ad_account)):
        pw=pw_params['password']
        #These numbers represent the location in the ASCII table.
        pw=pw.replace('%','%25')
        pw=pw.replace('&','%26')
        user = id_to_name(account_id,'user')
        sock.send('ALTRUSR&%s/%s&pass&%s\n' % (cereconf.AD_DOMAIN,user,pw))
        if sock.read() != ['210 OK']:
            print 'WARNING: failed changing password for ',user

            


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

