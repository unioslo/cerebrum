#!/usr/bin/env python2.2

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
from Cerebrum.modules import ADAccount


Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
ad_object = ADObject.ADObject(Cerebrum)
ad_account = ADAccount.ADAccount(Cerebrum)
ou = OU.OU(Cerebrum)
person = Person.Person(Cerebrum)
account = Account.Account(Cerebrum)


#Tilsvarer hente navn fra FS, burde finne på mer fleksibel løsning her.

delete_users = 0
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
    adusers = get_ad_users()
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
            print account_disable,fields[17]
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

    #Sjekk også disable mot karantene.
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
    groups = get_ad_groups()
    sock.send('LGROUPS&' + AD_DOMAIN + '&1\n')
    receive = sock.read()		
    print receive
    for line in receive[1:-1]:
        fields = line.split('&')
        if fields[3] in groups:
            print 'updating group:',fields[3]
            #TODO:Syncing group members.
            del groups[fields[3]]
        elif fields[3] in AD_DONT_TOUCH:
            pass
        else:
            parts = fields[3].split('-')
            if parts[1] != 'gruppe':
                #UiO spesifik, all groups in NT is
                #prefixed with -gruppe
                pass
            else:
                print 'remove group:',fields[3]
                
            for grp in groups:
		#The remaining is new groups and should be created.
		print 'creating group:', grp
		
def get_args():
    global doit
    global delete_users
    val = 'none'
    for arrrgh in sys.argv:
        print arrrgh
        if arrrgh == '--quick':
            val = 'quick'
        elif arrrgh == '--full':
            val = 'full'
        elif arrrgh == '--doit':
            doit = 1
        elif arrrgh == '--delete_users':
            delete_users = 1
    return val

def now():
    return time.ctime(time.time())

def get_ad_users():
    ulist = {}
    count = 0
    for row in ad_object.get_all_ad_users():
        count = count+1
        if count > 100: break
        id = row['entity_id']
        ou_id = row['ou_id']
        id_and_ou = id,ou_id
        ad_object.find(id)
        uname = ad_object.get_name(22)
        ulist[uname['entity_name']]=id_and_ou
        ad_object.clear()

    print 'count:',count
    return ulist


def get_ad_groups():
    groups = []
    count = 0
    """
    for row in posix_group.list_all():
        print count
        count = count+1
        if count > 100: break
        posix_group.clear()
        posix_group.find(row.group_id)
        gname = posix_group.group_name
        groups.append(gname)
    return groups	
    """
	
def full_ou_sync():
	print 'Starting full_ou_sync at',now()
	print 'Expecting that all necessary OUs is already created, will fail\n if an OU specified in Cerebrum is missing in AD, The correspondence of OU structure in AD and at UIO limit the OU tree in AD to one level from the root, until an OU module to AD is made.'
	

def main():
	arg = get_args()
	if arg == 'quick':
		quick_sync()
	elif arg == 'full':
		full_ou_sync()
		full_user_sync()
	#	full_group_sync()
	else:
		print 'Wrong argumenets supplied'
	sock.close()	
        
		

if __name__ == '__main__':
	sock = SocketCom()
	main()
