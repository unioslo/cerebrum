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

import cerebrum_path
import os 
import sys
import time
import ldap
import cereconf
 
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Disk
from Cerebrum import OU
from Cerebrum import Errors
from Cerebrum import QuarantineHandler
 
# Set up the basics.
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
db.cl_init(change_program='add_disk')

account = Account.Account(db)
person = Person.Person(db)
# ad_account = ADAccount.ADAccount(db)
disk = Disk.Disk(db)
host = Disk.Host(db)
quarantine = Entity.EntityQuarantine(db)
ou = OU.OU(db)

class LDAPConnection:
    __port = 0
    def __init__( self, host, port, binddn, password, scope ):
        self.__host = host
        self.__port = port
        self.__binddn = binddn
        self.__password = password
        if scope.upper() == "SUB":
            self.__scope = ldap.SCOPE_SUBTREE
        elif scope.upper() == "ONE":
            self.__scope = ldap.SCOPE_ONE
        else:
            self.__scope = ldap.SCOPE_BASE
        self.__ldap_connection_handle = 0
    
    def __connect( self, host, binddn, password, port=389 ):
        handle = ldap.open( host, port )
        if handle:
            handle.simple_bind_s( binddn, password )
            print "Connected ok\n"
            return handle
        return False
    
    def __search( self, handle, basedn, filter, scope=ldap.SCOPE_SUBTREE):
        if not handle:
            return False
        return handle.search_s( basedn, scope, filter )
    
    def __create( self, handle, dn, attrs ):
        if not handle:
            return False
        handle.add_s( dn, attrs )
        
    def __delete( self, handle, dn ):
        if not handle:
            return False
        handle.delete_s( dn )
    
    def __rename( self, handle, olddn, newdn, delete_olddn=1 ):
        if not handle:
            return False
        handle.modrdn_s( olddn, newdn, delete_olddn )
        
    def __modify( self, handle, dn, attrs ):
        if not handle:
            return False
        handle.modify_s( dn, attrs )
                
    def TestConnection( self, basedn, filter ):
        # Create a test connection.
        # This will try to connect and search based on the
        # input given to the class.  If the connection fails,
        # it will return False.  If the connection succeeds
        # but there is nothing in the tree at the search base,
        # it will return False; so it is important to provide
        # real search data.
        self.__ldap_connection_handle = self.__connect( self.__host, self.__binddn, self.__password, self.__port )
        if not self.__ldap_connection_handle:
            return False
        return len( self.__search( self.__ldap_connection_handle, basedn, filter, self.__scope ) ) != 0
    
    def GetObjects( self, basedn, filter ):
        if not self.__ldap_connection_handle:
            self.__ldap_connection_handle = self.__connect( self.__host, self.__binddn, self.__password, self.__port )
            if not self.__ldap_connection_handle:
                return False
        return self.__search( self.__ldap_connection_handle, basedn, filter, self.__scope )
    
    def CreateObject( self, dn, attrs ):
        if not self.__ldap_connection_handle:
            self.__ldap_connection_handle = self.__connect( self.__host, self.__binddn, self.__password, self.__port )
            if not self.__ldap_connection_handle:
                return False
        self.__create( self.__ldap_connection_handle, dn, attrs )
        return True
    
    def DeleteObject( self, dn ):
        if not self.__ldap_connection_handle:
            self.__ldap_connection_handle = self.__connect( self.__host, self.__binddn, self.__password, self.__port )
            if not self.__ldap_connection_handle:
                return False
        self.__delete( self.__ldap_connection_handle, dn )
        return True
    
    def RenameObject( self, olddn, newdn, del_olddn=True ):
        if not self.__ldap_connection_handle:
            self.__ldap_connection_handle = self.__connect( self.__host, self.__binddn, self.__password, self.__port )
            if not self.__ldap_connection_handle:
                return False
        if del_olddn:
            self.__rename( self.__ldap_connection_handle, olddn, newdn )
        else:
            self.__rename( self.__ldap_connection_handle, olddn, newdn, 0 )
            
    def AddAttributes( self, dn, newattrs ):
        if not self.__ldap_connection_handle:
            self.__ldap_connection_handle = self.__connect( self.__host, self.__binddn, self.__password, self.__port )
            if not self.__ldap_connection_handle:
                return False
        attrs = []
        for type, value in newattrs:
            attrs.append( (ldap.MOD_ADD,type,value) )
        self.__modify( self.__ldap_connection_handle, dn, attrs )
        
    def ModifyAttributes( self, dn, changedattrs ):
        if not self.__ldap_connection_handle:
            self.__ldap_connection_handle = self.__connect( self.__host, self.__binddn, self.__password, self.__port )
            if not self.__ldap_connection_handle:
                return False
        attrs = []
        for type, value in changedattrs:
            attrs.append( (ldap.MOD_REPLACE,type,value) )
        self.__modify( self.__ldap_connection_handle, dn, attrs )


    def RawModifyAttributes( self, dn, changedattrs ):
        if not self.__ldap_connection_handle:
            self.__ldap_connection_handle = self.__connect( self.__host, self.__binddn, self.__password, self.__port )
            if not self.__ldap_connection_handle:
                return False
        self.__modify( self.__ldap_connection_handle, dn, changedattrs )

        
    def DeleteAttributes( self, dn, delattrs ):
        if not self.__ldap_connection_handle:
            self.__ldap_connection_handle = self.__connect( self.__host, self.__binddn, self.__password, self.__port )
            if not self.__ldap_connection_handle:
                return False
        attrs = []
        for type,value in delattrs:
            attrs.append( (ldap.MOD_DELETE,type,value) )
        self.__modify( self.__ldap_connection_handle, dn, attrs )
        
    def ModifyObject( self, dn, attrs ):
        if not self.__ldap_connection_handle:
            self.__ldap_connection_handle = self.__connect( self.__host, self.__binddn, self.__password, self.__port )
            if not self.__ldap_connection_handle:
                return False
        self.__modify( self.__ldap_connection_handle, dn, attrs )        
            

def op_check(attrs, value_name, new_value):
    op = None
    if new_value:
        if not attrs.has_key(value_name): 
            op = ldap.MOD_ADD
        elif new_value != attrs[value_name][0]:
            op = ldap.MOD_REPLACE
    return op




def now():
    return time.ctime(time.time())


def get_user_info(account_id, account_name):

    account.clear()
    account.find(account_id)
    home_dir = find_home_dir(account_id, account_name)
        
    try:
        account.clear()
        account.find(account_id)
        person_id = account.owner_id
        person.clear()
        person.find(person_id)
        for ss in cereconf.NW_SOURCE_SEARCH_ORDER:
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
    if qua != []:    
        try:
            qh = QuarantineHandler.QuarantineHandler(db, qua)
            if qh.is_locked():           
                account_disable = '1'
        except KeyError:        
            print "WARNING: missing QUARANTINE_RULE"    

    return (first_n, last_n, account_disable, home_dir)


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
        
def get_nw_ou(ldap_path):
    ou_list = []
    p = re.compile(r'ou=(.+)')
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
        path = ou.structure_path(co.perspective_fs)
        #TBD: Utvide med spread sjekk, OUer uten acronym, problem?
        return 'ou=%s' % path.replace('/',',ou=')
    except Errors.NotFoundError:
        print "WARNING: Could not find OU with id",ou_id


def id_to_ou_path(ou_id,ourootname):
    crbrm_ou = get_crbrm_ou(ou_id)
    if crbrm_ou == ourootname:
        if cereconf.NW_DEFAULT_OU == '0':
            crbrm_ou = 'cn=Users,%s' % ourootname
        else:
            crbrm_ou = get_crbrm_ou(cereconf.NW_DEFAULT_OU_ID)
    crbrm_ou = crbrm_ou.replace(ourootname,cereconf.NW_LDAP_ROOT)
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
        return "%s" % disk.name
    except Errors.NotFoundError:
        print "WARNING: Failure finding the disk of account ",account_id
        

def find_login_script(account):
    #This value is a specific UIO standard.
    return "users\%s.bat" % (account)


if __name__ == '__main__':
    pass

