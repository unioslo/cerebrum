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
import time
import re
import socket 

import cereconf
import adutils
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import OU
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum.Utils import Factory
from Cerebrum.modules import ADAccount
from Cerebrum.modules import ADObject

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ad_object = ADObject.ADObject(db)
ad_account = ADAccount.ADAccount(db)
ou = OU.OU(db)
group = Group.Group(db)
account = Account.Account(db)

delete_users = 0
delete_groups = 0
max_nmbr_users = 50
domainusers = []


def full_user_sync():
    """Checking each user in AD, and compare with cerebrum information."""
    # TODO: mangler setting av passord ved oppretting av nye brukere.
    # Mangler en mer stabil sjekk på hvilken OU brukeren hører hjemme
    # utfra cerebrum
        
    global domainusers
    print 'INFO: Starting full_user_sync at', adutils.now()
    adusers = {}
    adusers = get_ad_objects('user')
    sock.send('LUSERS&LDAP://%s&1\n' % (cereconf.AD_LDAP))
    receive = sock.read()

    
    for line in receive[1:-1]:
        fields = line.split('&')
        domainusers.append(fields[3])
        if fields[3] in adusers:
            user_id = adusers[fields[3]]
##          OU sjekk er ikke et krav til UiO Cerebrum. 
##          ou_seq = adutils.get_cere_ou(user_id[1])
##          if ou_seq not in adutils.get_ad_ou(fields[1]):
##              sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (
##                    fields[1], ou_seq, cereconf.AD_LDAP))
##                if sock.read() != ['210 OK']:
##                    print "WARNING: move user failed, ", fields[3], 'to', ou_seq
            (full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE,
             login_script) = adutils.get_user_info(user_id[0])            
            # TODO: cereconf.AD_CANT_CHANGE_PW is set as initial value for
            # a new user, the value is not changeable afterwards. Issue should b            # e worked out in the adsiservice 
            try:
                if ((full_name, account_disable, cereconf.AD_HOME_DRIVE, home_dir,login_script) != (fields[9],fields[17],fields[15], fields[7], fields[13])):
                    sock.send('ALTRUSR&%s/%s&fn&%s&dis&%s&hdir&%s&hdr&%s&ls&%s&pexp&%s&ccp&%s\n' % ( cereconf.AD_DOMAIN, fields[3], full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE, login_script, cereconf.AD_PASSWORD_EXPIRE, cereconf.AD_CANT_CHANGE_PW))
                    
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Error updating fields for', fields[3]
                else:
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
##      OUer ikke et krav i UiO Cerebrum...enda  
##        ou_struct = adutils.get_cere_ou(user_id[1])
        sock.send('NEWUSR&LDAP://CN=Users,%s&%s&%s\n' % (cereconf.AD_LDAP,user, user))
        if sock.read() == ['210 OK']:
            print 'INFO: created user, ', user, 'in Users'
            passw = adutils.get_password(user_id[0])
            (full_name,account_disable,home_dir,cereconf.AD_HOME_DRIVE,login_script)\
                    = adutils.get_user_info(user_id[0])
            sock.send('ALTRUSR&%s/%s&pass&%s&fn&%s&dis&%s&hdir&%s&hdr&%s&ls&%s&pexp&%s&ccp&%s\n' % (cereconf.AD_DOMAIN,user,passw,full_name,\
                    account_disable,home_dir,cereconf.AD_HOME_DRIVE,login_script,cereconf.AD_PASSWORD_EXPIRE,cereconf.AD_CANT_CHANGE_PW))            
            sock.read()
        else:
            print 'WARNING: create user failed, ', user, 'in Users'




def full_group_sync():
    """Checking each group in AD, and compare with cerebrum"""
    print 'INFO: Starting full_group_sync at', adutils.now()
    global domainusers
    adgroups = {}
    adgroups = get_ad_objects(int(co.entity_group))
    sock.send('LGROUPS&LDAP://%s\n' % (cereconf.AD_LDAP))
    receive = sock.read()
    for line in receive[1:-1]:
        fields = line.split('&')
        if fields[3] in adgroups:
            print 'INFO: updating group:', fields[3]
            sock.send('LGROUP&%s/%s\n' % (cereconf.AD_DOMAIN, fields[3]))
            res = sock.read()
            # AD service only list user members not group members of
            # groups, therefore Cerebrum groups are expanded to a list
            # of users.
            group.clear()
            group.find(adgroups[fields[3]][0])
            memblist = []
            for grpmemb in group.get_members():
                ad_object.clear()
                try:
                    ad_object.find(grpmemb)
                except Errors.NotFoundError:
                    print "WARNING: Could not find groupmemb,", grpmemb
                    pass
                name = ad_object.get_name(int(co.account_namespace))
                memblist.append(name)
            for l in res:
                if l=='210 OK': break
                p = re.compile(cereconf.AD_DOMAIN+'/(.+)')
                m = p.search(l)
                member = m.group(1)
                if member not in memblist:
                    sock.send('DELUSRGR&%s/%s&%s/%s\n' % (cereconf.AD_DOMAIN, m.group(1), cereconf.AD_DOMAIN, fields[3]))
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Failed delete', member, 'from', fields[1]
                else:
                    memblist.remove(member)                    
            for memb in memblist:
                if memb in domainusers:
                    sock.send('ADDUSRGR&%s/%s&%s/%s\n' % (cereconf.AD_DOMAIN, memb,
                                                      cereconf.AD_DOMAIN, fields[3]))
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

##      Ikke OU støtte i UIO versjonen.
##        grp_ou = adgroups[grp]
##        ou_struct = adutils.get_cere_ou(grp_ou[1])
        sock.send('NEWGR&LDAP://CN=Users,%s&%s&%s\n' % ( cereconf.AD_LDAP, grp, grp))
        if sock.read() == ['210 OK']:
            group.clear()
            group.find(adgroups[grp][0])
            for grpmemb in group.get_members():
                try:
                    ad_object.clear()
                    ad_object.find(grpmemb)
                    name = ad_object.get_name(int(co.account_namespace))
                    print 'INFO:Add', name, 'to', grp
                    if name in domainusers:
                        sock.send('ADDUSRGR&%s/%s&%s/%s\n' % (cereconf.AD_DOMAIN, name, cereconf.AD_DOMAIN, grp))
                        if sock.read() != ['210 OK']:
                            print 'WARNING: Failed add', name, 'to', grp
                except Errors.NotFoundError:
                    print "WARNING: Could not find group member ",grpmemb," in db"
        else:
            print 'WARNING: create group failed ', grp,'in Users'


def get_args():
    global delete_users
    global delete_groups
    for arrrgh in sys.argv:
        if arrrgh == '--delete_users':
            delete_users = 1
        elif arrrgh == '--delete_groups':
            delete_groups = 1


def get_ad_objects(entity_type):
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
    for row in ad_object.list_ad_objects(e_type):
        if count > max_nmbr_users: break
        id = row['entity_id']
        ad_object.find(id)
        #test:
        #if not ad_object.got_spread(spread):
        #    ad_object.add_spread(spread)
        #    ad_object.commit()
        if ad_object.got_spread(spread):
            count = count+1                   
            ou_id = row['ou_id']
            id_and_ou = id, ou_id
            name = ad_object.get_name(namespace)
            obj_name = '%s%s' % (name,grp_postfix)
            ulist[obj_name]=id_and_ou
        ad_object.clear()
    print "INFO: Found %s nmbr of objects" % (count)    
    return ulist


if __name__ == '__main__':
    sock = adutils.SocketCom()    
    arg = get_args()
    full_user_sync()
    full_group_sync()
    sock.close()

