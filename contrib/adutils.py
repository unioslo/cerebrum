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

import socket
import re
import time

from Cerebrum.Utils import Factory
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.modules import ADAccount

import cereconf

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
account = Account.Account(db)
person = Person.Person(db)
ad_account = ADAccount.ADAccount(db)

class SocketCom(object):
    """Class for Basic socket communication to connect to the ADserver"""

    p = re.compile('210 OK')
    
    def __init__(self):
        self.connect()

        
    def connect(self):    
        try:
	    self.sockobj = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	    self.sockobj.connect((cereconf.AD_SERVER_HOST, cereconf.AD_SERVER_PORT))
            print 'INFO: Connecting, starting session', now()
            print ">>", self.sockobj.recv(8192),
	    print "<< Authenticating"
	    self.sockobj.send(cereconf.AD_PASSWORD)
	    self.read()
        except:
	    print 'CRITICAL: failed connecting to:', cereconf.AD_SERVER_HOST, cereconf.AD_SERVER_PORT
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


    def close(self):
        print 'INFO: Finished, ending session', now()
        self.sockobj.send("QUIT")
        self.sockobj.close()

def now():
    return time.ctime(time.time())

#Shared procedures for adsync and adquicksync.

def get_password(user_id):
    # TODO: get correct plaintext password.
    # This is the same as in adsync.
    "Return the uncrypted password from cerebrum."
    passw = 'B4r3Tu11'
    return passw

def get_user_info(user_id):
    #This is the same as in adsync.   
    account.clear()
    try:
        account.find(user_id)
        person_id = account.owner_id
        person.clear()
        person.find(person_id)
    except Errors.NotFoundError:
        print "WARNING: find on person or account failed, aduser_id:", user_id
        pass
    
    for ss in cereconf.AD_SOURCE_SEARCH_ORDER:
        try:
            first_n = person.get_name(int(getattr(co, ss)), int(co.name_first))
            last_n = person.get_name(int(getattr(co, ss)), int(co.name_last))
            full_name = first_n +' '+ last_n
            break
        except Errors.NotFoundError:
            print "WARNING: getting persons name failed, account.owner_id:",person_id
            pass
    # TODO:check against quarantine.
    if account.get_account_expired():
        account_disable = '1'
    else:
        account_disable = '0'
    ad_account.clear()
    ad_account.find(user_id)
    home_dir = ad_account.home_dir
    login_script = ad_account.login_script
    return (full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE, login_script)

def get_ad_ou(ldap_path):
    ou_list = []
    p = re.compile(r'OU=(.+)')
    ldap_list = ldap_path.split(',')
    for elem in ldap_list:
        ret = p.search(elem)
        if ret:
            ou_list.append(ret.group(1))
    return ou_list

def get_cere_ou(ou_id):
    ou.clear()
    ou.find(ou_id)
    return ou.acronym


if __name__ == '__main__':
    pass

