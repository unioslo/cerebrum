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

#import cerebrum_path
# TODO: Should probably avoid "import *" here.
from cereconf import *

from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import ADObject
from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum.modules import ADAccount


Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
ad_object = ADObject.ADObject(Cerebrum)
ad_account = ADAccount.ADAccount(Cerebrum)
ou = OU.OU(Cerebrum)
person = Person.Person(Cerebrum)
group = Group.Group(Cerebrum)
account = Account.Account(Cerebrum)

delete_users = 0
delete_groups = 0
max_nmbr_users = 20
domainusers = []


class SocketCom(object):
    """Class for Basic socket communication"""

    p = re.compile('210 OK')
    
    def __init__(self):
        self.connect()

        
    def connect(self):    
        try:
	    self.sockobj = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	    self.sockobj.connect((AD_SERVER_HOST, AD_SERVER_PORT))
            print ">>", self.sockobj.recv(8192),
	    print "<< Authenticating"
	    self.sockobj.send(AD_PASSWORD)
	    self.read()
        except:
	    print 'FAILURE connecting to:', AD_SERVER_HOST, AD_SERVER_PORT
            raise 

    def send(self, message):
        print "<<", message,
        self.last_send=message
        self.sockobj.send(message)
        
    def read(self,out=1):
        received = []
        rec = []
        while 1:
            data = self.sockobj.recv(8192)
            if data[3] != '-': break
            m=self.p.search(data)
            if m: break
            received.append(data)            
        received.append(data)
        #process data
        for i in received:
            rec.append(i.strip())
        if out:     
            for elem in rec:
                 print '>>', elem
        return rec    

            
##    def read(self,out=1):
##        received = []
##	data = self.sockobj.recv(8192)                    
        #Betyr at oppkoblingen har timet ut, prøver igjen.    
##        if data == '':
##            self.connect()
##           print "WARNING: reconnect, last_send:",self.last_send
##            self.send(self.last_send)
##            data = self.sockobj.recv(8192)                    
##	received.extend(data.split('\n'))
##        if '' in received:
##            received.remove('')
##        while received[-1][3]== '-':
##        while data:
##            data = self.sockobj.recv(8192)   
##            received.extend(data.split('\n'))
##            if '' in received:
##                received.remove('')
##        if out:     
##            for elem in received:
##                print '>>', elem
##	return received

        

    
    def close(self):
        print 'INFO: Finished, ending session', now()
        self.sockobj.send("QUIT")
        self.sockobj.close()


def full_user_sync():
    """Checking each user in AD, and compare with cerebrum information."""
    # TODO: mangler setting av passord ved oppretting av nye brukere.
    # Mangler en mer stabil sjekk på hvilken OU brukeren hører hjemme
    # utfra cerebrum
    # Mangler spread.
    global domainusers
    print 'INFO: Starting full_user_sync at', now()
    adusers = {}
    adusers = get_ad_objects('user')
    sock.send('LUSERS&LDAP://%s&1\n' % (AD_LDAP))
    receive = sock.read()
    for line in receive[1:-1]:
        fields = line.split('&')
        domainusers.append(fields[3])
        if fields[3] in adusers:
            user_id = adusers[fields[3]]
##          OU sjekk er ikke et krav til UiO Cerebrum. 
##          ou_seq = get_cere_ou(user_id[1])
##          if ou_seq not in get_ad_ou(fields[1]):
##              sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (
##                    fields[1], ou_seq, AD_LDAP))
##                if sock.read() != ['210 OK']:
##                    print "WARNING: move user failed, ", fields[3], 'to', ou_seq
            (full_name, account_disable, home_dir, AD_HOME_DRIVE,
             login_script) = get_user_info(user_id[0])            
            # TODO: AD_CANT_CHANGE_PW gir feil output på query,
            # skyldes antageligvis problemer med AD service. Mulige
            # problemer med password expire flag.
            try:
                if ((full_name, account_disable, AD_HOME_DRIVE, home_dir,login_script, AD_PASSWORD_EXPIRE) != (fields[9],fields[17],fields[15], fields[7], fields[13], fields[21])):
                     sock.send('ALTRUSR&%s/%s&fn&%s&dis&%s&hdir&%s&hdr&%s&ls&%s&pexp&%s&ccp&%s\n' % ( AD_DOMAIN, fields[3], full_name, account_disable, home_dir, AD_HOME_DRIVE, login_script, AD_PASSWORD_EXPIRE, AD_CANT_CHANGE_PW))
                     
                     if sock.read() != ['210 OK']:
                         print 'WARNING: Error updating fields for', fields[3]
                else:
                    print "INFO:Bruker ",fields[3]," OK"
            except IndexError:
                print "WARNING: list index out of range, fields:", full_name, account_disable, AD_HOME_DRIVE, home_dir, login_script, AD_PASSWORD_EXPIRE 
            del adusers[fields[3]]
        elif fields[3] in AD_DONT_TOUCH:
            pass
        else:
            if delete_users:
                sock.send('DELUSR&%s/%s\n' % (AD_DOMAIN, fields[3]))
                if sock.read() != ['210 OK']:
                    print 'WARNING: Error deleting, ', fields[3]
            else:
                if AD_LOST_AND_FOUND not in get_ad_ou(fields[1]):
                    sock.send('ALTRUSR&%s/%s&dis&1\n' % ( AD_DOMAIN, fields[3]))
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Error disabling account', fields[3]
                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (fields[1], AD_LOST_AND_FOUND, AD_LDAP))
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Error moving, ', fields[3], 'to', AD_LOST_AND_FOUND
                    

    for user in adusers:
        # The remaining accounts in the list should be created.
        user_id = adusers[user]
##      OUer ikke et krav i UiO Cerebrum...enda  
##        ou_struct = get_cere_ou(user_id[1])
        sock.send('NEWUSR&LDAP://CN=Users,%s&%s&%s\n' % (AD_LDAP,user, user))
        if sock.read() == ['210 OK']:
            print 'INFO: created user, ', user, 'in Users'
            passw = get_password(user_id[0])
            (full_name,account_disable,home_dir,AD_HOME_DRIVE,login_script)\
                    = get_user_info(user_id[0])
            sock.send('ALTRUSR&%s/%s&pass&%s&fn&%s&dis&%s&hdir&%s&hdr&%s&ls&%s&pexp&%s&ccp&%s\n' % (AD_DOMAIN,user,passw,full_name,\
                    account_disable,home_dir,AD_HOME_DRIVE,login_script,\
                    AD_PASSWORD_EXPIRE,AD_CANT_CHANGE_PW))            
            sock.read()
        else:
            print 'WARNING: create user failed, ', user, 'in Users'

def get_password(user_id):
    # TODO: get correct plaintext password.
    "Return the uncrypted password from cerebrum."
    passw = 'B4r3Tu11'
    return passw

def get_user_info(user_id):
    account.clear()
    try:
        account.find(user_id)
        person_id = account.owner_id
        person.clear()
        person.find(person_id)
    except Errors.NotFoundError:
        print "WARNING: find on person or account failed, aduser_id:", user_id
        pass
    
    for ss in AD_SOURCE_SEARCH_ORDER:
        try:
            first_n = person.get_name(int(getattr(co, ss)), int(co.name_first))
            last_n = person.get_name(int(getattr(co, ss)), int(co.name_last))
            full_name = first_n +' '+ last_n
            break
        except Errors.NotFoundError:
            print "WARNING: getting persons name failed, account.owner_id:",person_id
            pass
    # TODO:sjekk også disable mot karantene.
    if account.get_account_expired():
        account_disable = '1'
    else:
        account_disable = '0'
    ad_account.clear()
    ad_account.find(user_id)
    home_dir = ad_account.home_dir
    login_script = ad_account.login_script
    return (full_name, account_disable, home_dir, AD_HOME_DRIVE, login_script)

def get_cere_ou(ou_id):
    ou.clear()
    ou.find(ou_id)
    return ou.acronym

def get_ad_ou(ldap_path):
    ou_list = []
    p = re.compile(r'OU=(.+)')
    ldap_list = ldap_path.split(',')
    for elem in ldap_list:
        ret = p.search(elem)
        if ret:
            ou_list.append(ret.group(1))
    return ou_list

def full_group_sync():
    """Checking each group in AD, and compare with cerebrum"""
    print 'INFO: Starting full_group_sync at', now()
    global domainusers
    adgroups = {}
    adgroups = get_ad_objects(int(co.entity_group))
    sock.send('LGROUPS&LDAP://%s\n' % (AD_LDAP))
    receive = sock.read()
    for line in receive[1:-1]:
        fields = line.split('&')
        if fields[3] in adgroups:
            print 'INFO: updating group:', fields[3]
            sock.send('LGROUP&%s/%s\n' % (AD_DOMAIN, fields[3]))
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
                p = re.compile(AD_DOMAIN+'/(.+)')
                m = p.search(l)
                member = m.group(1)
                if member not in memblist:
                    sock.send('DELUSRGR&%s/%s&%s/%s\n' % (AD_DOMAIN, m.group(1), AD_DOMAIN, fields[3]))
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Failed delete', member, 'from', fields[1]
                else:
                    memblist.remove(member)                    
            for memb in memblist:
                if memb in domainusers:
                    sock.send('ADDUSRGR&%s/%s&%s/%s\n' % (AD_DOMAIN, memb,
                                                      AD_DOMAIN, fields[3]))
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Failed add', memb, 'to', fields[3] 
                else:
                    print "WARNING:groupmember",memb,"in group",fields[3],"not in AD"
            del adgroups[fields[3]]
        elif fields[3] in AD_DONT_TOUCH:
            pass
        else:
            if delete_groups:
                sock.send('DELGR&%s/%s\n' % (AD_DOMAIN, fields[3]))
                if sock.read() != ['210 OK']:
                    print 'WARNING: Error deleting ', fields[3]
            else:
                if AD_LOST_AND_FOUND not in get_ad_ou(fields[1]):
                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (
                        fields[1], AD_LOST_AND_FOUND, AD_LDAP))
                    if sock.read() != ['210 OK']:
                        print 'WARNING: Error moving:', fields[3], 'to', \
                              AD_LOST_AND_FOUND
    for grp in adgroups:
        # The remaining is new groups and should be created.

##      Ikke OU støtte i UIO versjonen.
##        grp_ou = adgroups[grp]
##        ou_struct = get_cere_ou(grp_ou[1])
        sock.send('NEWGR&LDAP://CN=Users,%s&%s&%s\n' % ( AD_LDAP, grp, grp))
        if sock.read() == ['210 OK']:
            group.clear()
            group.find(adgroups[grp][0])
            for grpmemb in group.get_members():
                ad_object.clear()
                ad_object.find(grpmemb)
                name = ad_object.get_name(int(co.account_namespace))
                print 'INFO:Add', name, 'to', grp
                sock.send('ADDUSRGR&%s/%s&%s/%s\n' % (AD_DOMAIN, name, AD_DOMAIN, grp))
                if sock.read() != ['210 OK']:
                    print 'WARNING: Failed add', name, 'to', grp
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

def now():
    return time.ctime(time.time())

def get_ad_objects(entity_type):
    global max_nmbr_users
    grp_postfix = ''
    if entity_type == 'user':
        e_type = int(co.entity_account)
        namespace = int(co.account_namespace)
    else:
        e_type = int(co.entity_group)
        namespace = int(co.group_namespace)
        grp_postfix = AD_GROUP_POSTFIX
    ulist = {}
    count = 0
    for row in ad_object.list_ad_objects(e_type):
        count = count+1
        if count > max_nmbr_users: break
        id = row['entity_id']
        ou_id = row['ou_id']
        id_and_ou = id, ou_id
        ad_object.find(id)
        name = ad_object.get_name(namespace)
        obj_name = "%s%s" % (name,grp_postfix)
        ulist[obj_name]=id_and_ou
        ad_object.clear()
    print "INFO: Found %s nmbr of objects" % (count)    
    return ulist

if __name__ == '__main__':
    sock = SocketCom()    
    arg = get_args()
    full_user_sync()
    full_group_sync()
    sock.close()

