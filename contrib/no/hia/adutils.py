#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2003 University of Oslo, Norway
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

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum import QuarantineHandler
from Cerebrum.modules import MountHost

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
account = Factory.get('Account')(db)
person = Factory.get('Person')(db)
moho = MountHost.MountHost(db)
disk = Factory.get('Disk')(db)
host = Factory.get('Host')(db)
quarantine = Entity.EntityQuarantine(db)
ou = Factory.get('OU')(db)


class SocketCom(object):
    """Class for Basic socket communication to connect to the ADserver"""

    p = re.compile('210 OK')
    s = re.compile('(&pass&.+)&|(&pass&.+)\n')
    
    def __init__(self):
        self.connect()

        
    def connect(self):    
        try:
	    self.sockobj = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	    self.sockobj.connect((cereconf.AD_SERVER_HOST, cereconf.AD_SERVER_PORT))
            logger(">>%s" % self.sockobj.recv(8192))
	    logger("<<Authenticating")
	    self.sockobj.send(cereconf.AD_PASSWORD)
	    logger(">>%s" % self.read(out=0))
        except:
	    logger("failed connecting to %s:%s" % (cereconf.AD_SERVER_HOST, cereconf.AD_SERVER_PORT))
            raise 


    def send(self, message,out=0):
	self.sockobj.send(message)
	if out:
            m = self.s.search(message)
            if m:
            	if not m.group(2):
                    gr=1
            	else:
                    gr=2            
            	print '<< %s&pass&XXXXXXXX%s' % (message[0:m.start(gr)],message[m.end(gr):-1])
            else:
            	print '<<', message,
        
        

    def read(self,out=0):
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


    def readgrp(self,out=0):
        received = []
        rec = ''
        while 1:
            data = self.sockobj.recv(8192)
            m=self.p.search(data)
            if m: 
		break
	    else:
            	received.append(data)
        received.append(data)
        #process data
        for i in received:
	    i.strip()
	    rec = '%s%s' % (rec,i)		   	
        if out:     
            print '>>', rec
        return rec    


    def close(self):
        print 'INFO: Finished, ending session', now()
        self.sockobj.send("QUIT\n")
        self.sockobj.close()



def now():
    return time.ctime(time.time())

def logger(text):
    print text, "\n"

#Shared procedures for adsync and adquicksync.

def get_user_info(account_id, account_name):

#    home_dir = find_home_dir(account_id, account_name)
#    login_script = find_login_script(account_name)
        
    account.clear()
    account.find(account_id)
    try:
        person_id = account.owner_id
        person.clear()
        person.find(person_id)
        full_name = person.get_name(int(co.system_cached), int(co.name_full)) 
        if not full_name:
            print "WARNING: getting persons name failed, account.owner_id:",person_id
    except Errors.NotFoundError:        
        #This account is missing a person_id.
        full_name = account.account_name
        
    account_disable = '0'	
    if chk_quarantine(account_id):
        account_disable = '1'	

    return (full_name, account_disable)


def chk_quarantine(account_id):
    # Check against quarantine.
    quarantine.clear()
    quarantine.find(account_id)
    quarantines = quarantine.get_entity_quarantine()
    if not quarantines:
        return False
    qua = []
    for row in quarantines:
        qua.append(row['quarantine_type'])
    qh = QuarantineHandler.QuarantineHandler(db, qua)    
    try:        
        if qh.is_locked():           
	    return True
    except KeyError:        
	pass
#        logger.info("No QUARANTINE_RULE for id:%s" % account_id)    
    
    return False


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
     ou.clear()
     ou.find(cereconf.AD_CERE_ROOT_OU_ID)	
     return 'OU=%s' % ou.acronym
     	
#    Do not use OU placement at UiO.
#    try:      
#        ou.clear()
#        ou.find(ou_id)
#        path = ou.structure_path(co.perspective_lt)
#        #TBD: Utvide med spread sjekk, OUer uten acronym, problem?
#        return 'OU=%s' % path.replace('/',',OU=')
#    except Errors.NotFoundError:
#        print "WARNING: Could not find OU with id",ou_id


def id_to_ou_path(ou_id,ourootname):
    crbrm_ou = get_crbrm_ou(ou_id)
    if crbrm_ou == ourootname:
        if cereconf.AD_DEFAULT_OU == '0':
            crbrm_ou = 'CN=Users,%s' % ourootname
        elif cereconf.AD_DEFAULT_OU == '-1':
            crbrm_ou = ourootname
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
        try:
	    moho.clear()	
	    moho.find(disk.host_id)	
	    home_srv = moho.mount_name			
	except Errors.NotFoundError:
	    host.clear()
            host.find(disk.host_id)
            home_srv = host.name
	return "\\\\%s\\%s" % (home_srv,account_name)
    except Errors.NotFoundError:
        logger("Failure finding the disk of account %s" % account_id)
        

def find_login_script(account):
    #This value is a specific UIO standard.
    return "users\%s.bat" % (account)


if __name__ == '__main__':
    pass

# arch-tag: c22f185e-418a-4330-b526-aa0037d3048b
