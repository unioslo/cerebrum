#!/usr/bin/env python2.2
# Copyright 2002 University of Oslo, Norway
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

import sys, time, re
from socket import *

#kanskje ikke helt bra?
from cereconf import *
#import cerebrum_path

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
doit = 0

class SocketCom:
    """Class for Basic socket communication"""
    def __init__(self):
        try:
	    self.sockobj = socket(AF_INET, SOCK_STREAM)
	    self.sockobj.connect((AD_SERVER_HOST,AD_SERVER_PORT))
	    print ">>",self.sockobj.recv(1024),
	    print "<< Authenticating"
	    self.sockobj.send(AD_PASSWORD)
	    self.read()
        except:
	    print 'Error connecting to:',AD_SERVER_HOST,AD_SERVER_PORT	    

    def send(self,message):
        self.sockobj.send(message)
        print "<<",message,
			
    def read(self):
        received = []
	data = self.sockobj.recv(1024)
	received.extend(data.split('\n'))
	received.remove('')
	while received[-1][3] == '-':
	    data = self.sockobj.recv(1024)
	    received.extend(data.split('\n'))
	    received.remove('')
	for elem in received:
	    print '>>',elem
	return received

    def close(self):
        self.sockobj.close()


def full_user_sync():
    "Checking each user in AD, and compare with cerebrum information."

    #TODO: mangler setting av passord ved oppretting av nye brukere.
    #Mangler en mer stabil sjekk på hvilken OU brukeren hører hjemme
    #utfra cerebrum
    
    print 'Starting full_user_sync at',now(),' doit=',doit
    adusers = {}
    adusers = get_ad_objects('user')
    sock.send('LUSERS&LDAP://%s&1\n' % (AD_LDAP))
    receive = sock.read()

    for line in receive[1:-1]:
        fields = line.split('&')

        if fields[3] in adusers:
            user_id = adusers[fields[3]]
            ou_seq = get_cere_ou(user_id[1])

            #Checking if user is in correct OU.
            #TBD In this case two OUs should not have the same name, better method would be to compare two lists.
            if ou_seq not in get_ad_ou(fields[1]):
                sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % \
                          (fields[1],ou_seq,AD_LDAP))
                if sock.read() != ['210 OK']:
                    print "move user failed:",fields[3],'to',ou_seq

            (full_name,account_disable,home_dir,AD_HOME_DRIVE,login_script)\
                    = get_user_info(user_id[0])

            #TODO:AD_CANT_CHANGE_PW gir feil output på query, skyldes antageligvis problemer med AD service. Mulige problemer med password expire flag.
            if (full_name,account_disable,AD_HOME_DRIVE,home_dir, \
                login_script,AD_PASSWORD_EXPIRE)!=(fields[9],fields[17], \
                        fields[15],fields[7],fields[13],fields[21]):
                sock.send('ALTRUSR&%s/%s&fn&%s&dis&%s&hdir&%s&hdr&%s&ls&%s&pexp&%s&ccp&%s\n' % (AD_DOMAIN,fields[3],full_name,\
                        account_disable,home_dir,AD_HOME_DRIVE,login_script,\
                        AD_PASSWORD_EXPIRE,AD_CANT_CHANGE_PW))
                if sock.read() != ['210 OK']:
                    print 'Error updating fields for',fields[3]
            del adusers[fields[3]]
        elif fields[3] in AD_DONT_TOUCH:
            pass
        else:
            if delete_users:
                sock.send('DELUSR&%s/%s\n' % (AD_DOMAIN,fields[3]))
                if sock.read() != ['210 OK']:
                    print 'Error deleting:',fields[3]
            else:
                if AD_LOST_AND_FOUND not in get_ad_ou(fields[1]):
                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' %\
                              (fields[1],AD_LOST_AND_FOUND,AD_LDAP))
                    if sock.read() != ['210 OK']:
                        print 'Error moving:',fields[3],'to',AD_LOST_AND_FOUND 

    for user in adusers:
        #The remaining accounts in the list should be created.
        user_id = adusers[user]
        ou_struct = get_cere_ou(user_id[1])

        sock.send('NEWUSR&LDAP://OU=%s,%s&%s&%s\n' % (ou_struct,AD_LDAP,user,user))
        if sock.read() == ['210 OK']:
            print 'created user:',user,'in',ou_struct
            passw = get_password(user_id[0])
            (full_name,account_disable,home_dir,AD_HOME_DRIVE,login_script)\
                    = get_user_info(user_id[0])
            sock.send('ALTRUSR&%s/%s&pass&%s&fn&%s&dis&%s&hdir&%s&hdr&%s&\
                    ls&%s&pexp&%s&ccp&%s\n' % (AD_DOMAIN,user,passw,full_name,\
                    account_disable,home_dir,AD_HOME_DRIVE,login_script,\
                    AD_PASSWORD_EXPIRE,AD_CANT_CHANGE_PW))
            sock.read()
        else:
            print 'create user failed:',user,'in',ou_struct
			
def get_password(user_id):
    #TODO: get correct plaintext password.
    "Return the uncrypted password from cerebrum."
    passw = 'B4r3Tu11'
    return passw
    
def get_user_info(user_id):
    
    account.clear()
    account.find(user_id)
    person_id = account.owner_id
    person.clear()
    person.find(person_id)

    for ss in AD_SOURCE_SEARCH_ORDER:
        try:
            first_n = person.get_name(int(getattr(co, ss)),int(co.name_first))
            last_n = person.get_name(int(getattr(co, ss)),int(co.name_last))
            full_name = first_n +' '+ last_n
            break
        except Errors.NotFoundError:
            pass

    #TODO:sjekk også disable mot karantene.
    if account.get_account_expired():
        account_disable = '1'
    else:
        account_disable = '0'
        
    ad_account.clear()
    ad_account.find(user_id)
    home_dir = ad_account.home_dir
    login_script = ad_account.login_script
    return (full_name,account_disable,home_dir,AD_HOME_DRIVE,login_script)
		
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
    "Checking each group in AD, and compare with cerebrum"
    
    print 'Starting full_group_sync at',now(),' doit=',doit
    adgroups = {}
    adgroups = get_ad_objects(int(co.entity_group))
    sock.send('LGROUPS&LDAP://%s\n' % (AD_LDAP))
    receive = sock.read()		
    
    for line in receive[1:-1]:
        fields = line.split('&')
        if fields[3] in adgroups:
            print 'updating group:',fields[3]
            sock.send('LGROUP&%s/%s\n' % (AD_DOMAIN,fields[3]))
            res = sock.read()
        #AD service only list user members not group members of groups,
        #therefore Cerebrum groups are expanded to a list of users. 

            group.clear()
            group.find(adgroups[fields[3]][0])
            memblist = []
            for grpmemb in group.get_members():
                ad_object.clear()
                ad_object.find(grpmemb)
                name = ad_object.get_name(int(co.account_namespace))
                memblist.append(name.entity_name)

            for l in res[:-1]:
                print l
                p = re.compile(AD_DOMAIN+'/(.+)')
                m = p.search(l)
                member = m.group(1)
                if member not in memblist:
                    sock.send('DELUSRGR&%s/%s&%s/%s\n' % (AD_DOMAIN,m.group(1),AD_DOMAIN,fields[3]))
                    if sock.read() != ['210 OK']:
                        print 'Failed delete',member,'from',fields[1]
                else:
                    memblist.remove(member)

            for memb in memblist:
                sock.send('ADDUSRGR&%s/%s&%s/%s\n' % (AD_DOMAIN,memb,AD_DOMAIN,fields[3]))
                if sock.read() != ['210 OK']:
                    print 'Failed add',memb,'to',fields[3]
                  
                
            del adgroups[fields[3]]
            
        elif fields[3] in AD_DONT_TOUCH:
            pass
        else:
            if delete_groups:
                sock.send('DELGR&%s/%s\n' % (AD_DOMAIN,fields[3]))
                if sock.read() != ['210 OK']:
                    print 'Error deleting:',fields[3]
            else:
                if AD_LOST_AND_FOUND not in get_ad_ou(fields[1]):
                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' %\
                              (fields[1],AD_LOST_AND_FOUND,AD_LDAP))
                    if sock.read() != ['210 OK']:
                        print 'Error moving:',fields[3],'to',AD_LOST_AND_FOUND 
                        
                
    for grp in adgroups:
        #The remaining is new groups and should be created.
        grp_ou = adgroups[grp]
        ou_struct = get_cere_ou(grp_ou[1])
        sock.send('NEWGR&LDAP://OU=%s,%s&%s&%s\n' % (ou_struct,AD_LDAP,grp,grp))
        if sock.read() == ['210 OK']:
            group.clear()
            group.find(adgroups[grp][0])
            for grpmemb in group.get_members():
                ad_object.clear()
                ad_object.find(grpmemb)
                name = ad_object.get_name(int(co.account_namespace))
                name.entity_name
                sock.send('ADDUSRGR&%s/%s&%s/%s\n' % (AD_DOMAIN,name.entity_name,AD_DOMAIN,grp))
                if sock.read() != ['210 OK']:
                    print 'Failed add',memb,'to',grp            
        else:
            print 'create group failed:',grp,'in',ou_struct


def get_args():
    global doit
    global delete_users
    global delete_groups
    val = 'none'
    for arrrgh in sys.argv:
        if arrrgh == '--quick':
            val = 'quick'
        elif arrrgh == '--full':
            val = 'full'
        elif arrrgh == '--doit':
            doit = 1
        elif arrrgh == '--delete_users':
            delete_users = 1
        elif arrrgh == '--delete_groups':
            delete_groups = 1
            
    return val

def now():
    return time.ctime(time.time())

def get_ad_objects(entity_type):

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
        if count > 100: break
        id = row['entity_id']
        ou_id = row['ou_id']
        id_and_ou = id,ou_id
        ad_object.find(id)
        name = ad_object.get_name(namespace)
        obj_name = name['entity_name'] + grp_postfix
        ulist[obj_name]=id_and_ou
        ad_object.clear()
    return ulist

	
def full_ou_sync():
	print 'Starting full_ou_sync at',now()
#	print 'Expecting that all necessary OUs is already created, will fail\n if an OU specified in Cerebrum is missing in AD, The correspondence of OU structure in AD and at UIO limit the OU tree in AD to one level from the root, until an OU module to AD is made.'
	

def main():
	arg = get_args()
	if arg == 'quick':
		quick_sync()
	elif arg == 'full':
		full_ou_sync()
		full_user_sync()
		full_group_sync()
	else:
		print 'Wrong argumenets supplied'
	sock.close()	
        
		

if __name__ == '__main__':
	sock = SocketCom()
	main()
