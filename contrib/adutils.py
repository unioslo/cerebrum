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
from Cerebrum import Disk
from Cerebrum import OU
from Cerebrum import Entity
from Cerebrum.modules import ADAccount
from Cerebrum import QuarantineHandler

import cereconf

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
account = Account.Account(db)
person = Person.Person(db)
ad_account = ADAccount.ADAccount(db)
disk = Disk.Disk(db)
host = Disk.Host(db)
quarantine = Entity.EntityQuarantine(db)
ou = OU.OU(db)

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
        self.sockobj.send("QUIT\n")
        self.sockobj.close()

def now():
    return time.ctime(time.time())


#Shared procedures for adsync and adquicksync.

def get_user_info(account_id, account_name):

    try:
        ad_account.clear()
        ad_account.find(account_id)
        home_dir = ad_account.home_dir
        login_script = ad_account.login_script
    except Errors.NotFoundError:    
        home_dir = find_home_dir(account_id, account_name)
        login_script = find_login_script(account_name)
        
        
    try:
        account.clear()
        account.find(account_id)
        person_id = account.owner_id
        person.clear()
        person.find(person_id)
        for ss in cereconf.AD_SOURCE_SEARCH_ORDER:
            try:
                first_n = person.get_name(int(getattr(co, ss)), int(co.name_first))
                last_n = person.get_name(int(getattr(co, ss)), int(co.name_last))
                full_name = first_n +' '+ last_n
            except Errors.NotFoundError:
                pass
        if full_name == '':
            print "WARNING: getting persons name failed, account.owner_id:",person_id
    except Errors.NotFoundError:
        print "WARNING: find on person or account failed, aduser_id:", account_id        
    

    account_disable = '0'
    # Check against quarantine.
    quarantine.clear()
    quarantine.find(account_id)
    quarantines = quarantine.get_entity_quarantine()
    qua = []
    for row in quarantines:
        qua.append(row['quarantine_type']) 
    qh = QuarantineHandler.QuarantineHandler(db, qua)
    try:
        if qh.is_locked():           
            account_disable = '1'
    except KeyError:        
        print "WARNING: missing QUARANTINE_RULE"    

    return (full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE, login_script)

def get_primary_ou(account_id,namespace):
    account.clear()
    account.find(account_id)
    name = account.get_name(namespace)
    acc_types = account.get_account_types()
    c = 0
    current = 0
    pri = 9999
    for acc in acc_types:
        if acc['priority'] < pri:
            current = c
            pri = acc['priority']
            c = c+1
    if acc_types:
        return acc_types[current]['ou_id']
    else:
        return None
        
def get_ad_ou(ldap_path):
    ou_list = []
    p = re.compile(r'OU=(.+)')
    ldap_list = ldap_path.split(',')
    for elem in ldap_list:
        ret = p.search(elem)
        if ret:
            ou_list.append(ret.group(1))
    return ou_list


def get_crbrm_ou(ou_id):

    try:        
        ou.clear()
        ou.find(ou_id)
        path = ou.structure_path(co.perspective_lt)
        #TBD: Utvide med spread sjekk, OUer uten acronym, problem?
        return 'OU=%s' % path.replace('/',',OU=')
    except Errors.NotFoundError:
        print "WARNING: Could not find OU with id",ou_id


def id_to_ou_path(ou_id,ourootname):
    crbrm_ou = get_crbrm_ou(ou_id)
    if crbrm_ou == ourootname:
        if cereconf.AD_DEFAULT_OU == '0':
            crbrm_ou = 'CN=Users,%s' % ourootname
        else:
            crbrm_ou = get_crbrm_ou(cereconf.AD_DEFAULT_OU)

    crbrm_ou = crbrm_ou.replace(ourootname,cereconf.AD_LDAP)
    return crbrm_ou

def find_home_dir(account_id, account_name):
    try:
        account.clear()
        account.find(account_id)
        disk.clear()
        disk.find(account.disk_id)
        host.clear()
        host.find(disk.host_id)
        home_srv = host.name
        #TBD:In the UiO version we need to make a translate from host to
        #samba server   
        return "\\\\%s\\%s" % (home_srv,account_name)
    except Errors.NotFoundError:
        print "WARNING: Failure finding the disk of account ",account_id
        

def find_login_script(account):
    #This value is a specific UIO standard.
    return "users\%s.bat" % (account)


if __name__ == '__main__':
    pass

