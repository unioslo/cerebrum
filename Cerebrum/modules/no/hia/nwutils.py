#!/usr/bin/env python2.2
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

import cerebrum_path
import os 
import sys
import time
import ldap
import pickle
import re
import cereconf
 
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum import QuarantineHandler
from Cerebrum.extlib import logging
from ldap import modlist
 
# Set up the basics.
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
db.cl_init(change_program='add_disk')
logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
logger = logging.getLogger("cronjob")


account = Factory.get('Account')(db)
person = Factory.get('Person')(db)
disk = Factory.get('Disk')(db)
host = Factory.get('Host')(db)
quarantine = Entity.EntityQuarantine(db)
ou = Factory.get('OU')(db)
ent_name = Entity.EntityName(db)

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
    
    
    def __connect( self, host, binddn, password, port=389, crypted=True):
        handle = ldap.open( host )
        handle.protocol_version = ldap.VERSION3
        if handle:
	    if crypted:  
		try:
		    if cereconf.TLS_CACERT_FILE is not None:
                        handle.OPT_X_TLS_CACERTFILE = cereconf.TLS_CACERT_FILE
                except:  pass
                try:
                    if cereconf.TLS_CACERT_DIR is not None:
                        handle.OPT_X_TLS_CACERTDIR = cereconf.TLS_CACERT_DIR
                except:  pass
            if crypted:
                try:
                    handle.start_tls_s()
                    handle.simple_bind_s(binddn,password)
                    logger.debug("TLS connection established to %s" % host)
                except:
                    logger.info( "Could not open TLS-connection to %s" % host)
		    return False
            else:
                try:
                    handle.simple_bind_s( binddn, password )
                    logger.info("Unencrypted connection to %s" % host)
                except:
                    logger.info("Could not open unencrypted connection to %s" % host)
       		    return False
            return handle
        return False
    
    def __unbind(self):
	self.__ldap_connection_handle.unbind()
	self.__ldap_connection_handle = None

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
	#self.__unbind()


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



def get_primary_affiliation(account_id, namespace):
    account.clear()
    account.find(account_id)
    name = account.get_name(namespace)
    try:
        acc_types = account.get_account_types()
    except Errors.NotFoundError:
        return(None)
    c = 0
    current = 0
    pri = 9999
    for acc in acc_types:
        if acc['priority'] < pri:
            current = c
            pri = acc['priority']
            c = c+1
    if acc_types:
        return acc_types[current]['affiliation']
    else:
        return None



# Creates the array we can feed directly to ldap"
def get_account_info(account_id, spread, site_callback):
    usr_attr = {}
    ent_name.clear()
    ent_name.find(account_id)
    #pq = PrinterQuotas.PrinterQuotas(db);
    name = ent_name.get_name(co.account_namespace)
    (first_n,last_n,account_disable,home_dir,affiliation,ext_id,email,pers) = get_user_info(account_id, spread)
    passwords = db.get_log_events(types=(int(co.account_password),), subject_entity=account_id)

    pwd_rows = [row for row in passwords]
    try:
        pwd = pickle.loads(pwd_rows[-1].change_params)['password']
    except:
        type, value, tb = sys.exc_info()
        logger.warn("Aiee! %s %s" % (str(type), str(value)))
        pwd = ''
    if pers:
	try:
	    pri_ou = get_primary_ou(account_id, co.account_namespace)
	except Errors.NotFoundError:
	    logger.info("Unexpected error me thinks")
	if not pri_ou:
	    logger.warn("WARNING: no primary OU found for",name,"in namespace", 
							co.account_namespace)
	    pri_ou = cereconf.NW_DEFAULT_OU_ID
	crbrm_ou = id_to_ou_path(pri_ou , cereconf.NW_LDAP_ROOT)
	ldap_ou = get_ldap_usr_ou(crbrm_ou, affiliation)
	ldap_dn = unicode('cn=%s,' % name, 'iso-8859-1').encode('utf-8') + ldap_ou
    else:
	ldap_ou = "%s,%s" % (unicode(cereconf.NW_LDAP_STUDOU, 'iso-8859-1').encode('utf-8'),
                        unicode(cereconf.NW_LDAP_ROOT, 'iso-8859-1').encode('utf-8'))
	ldap_dn = unicode('cn=%s,' % name, 'iso-8859-1').encode('utf-8') + ldap_ou
    try:
	if cereconf.NW_PRINTER_QUOTAS.lower() == 'enable': 
	    from Cerebrum.modules.no import PrinterQuotas 
	    pq = PrinterQuotas.PrinterQuotas(db)
            pq.clear();
    	    pq.find(account_id)
	    print_quota = pq.printer_quota
    except Errors.NotFoundError:
        print_quota = None  # User has no quota
    except:
        if affiliation == co.affiliation_student:
            print_quota = '11000'
        else:
            print_quota = None
    time_now = time.strftime("%H:%M:%S %d/%m/%Y",time.localtime()) 
    attrs = []
    attrs.append( ("ObjectClass", "user" ) )
    attrs.append( ("givenName", unicode(first_n, 'iso-8859-1').encode('utf-8') ) )
    attrs.append( ("sn", unicode(last_n, 'iso-8859-1').encode('utf-8') ) )
    fullName = unicode(first_n, 'iso-8859-1').encode('utf-8') +" "+ unicode(last_n, 'iso-8859-1').encode('utf-8')
    attrs.append( ("fullName",  fullName) )
    if home_dir is not None:
        utf8_home = unicode(home_dir, 'iso-8859-1').encode('utf-8')
        attrs.append( ("ndsHomeDirectory",  utf8_home) )
    attrs.append( ("description","Cerebrum;%d" % ext_id ) )
    attrs.append( ("generationQualifier","%d ,%s" % (ext_id,time_now) ))
    attrs.append( ("passwordAllowChange", cereconf.NW_CAN_CHANGE_PW) )
    attrs.append( ("loginDisabled", account_disable) )
    if print_quota is not None:
    	attrs.append( ("accountBalance", print_quota) )
	attrs.append( ("allowUnlimitedCredit", "FALSE"))
    if email:
	attrs.append( ("mail", email))
    passwd = unicode(pwd, 'iso-8859-1').encode('utf-8')
    attrs.append( ("userPassword", passwd) )
    attrs.append( ("uid", name) )
    if site_callback is not None:
      attrs += site_callback(account_id, spread, ext_id)
    return (ldap_dn,attrs)



def get_account_dict(dn_id, spread, site_callback):
    return_dict = {}
    (ldap_dn, entry) = get_account_info(dn_id, spread, site_callback)
    for attr in entry:
        return_dict[attr[0]] = attr[1]
    return (ldap_dn, return_dict)



def get_user_info(account_id, spread):
    affiliation = None
    account.clear()
    account.find(account_id)
    ent_name.clear()
    ext_id = 0
    ent_name.find(account.owner_id)
    home_dir = find_home_dir(account_id, account.account_name, spread)
    names = {'name_last':None,'name_first':None,'name_full':None}
    if ent_name.entity_type == int(co.entity_person):
	pers = True
    else:
	pers = False
    if pers:
	try:
	    person_id = account.owner_id
	    person.clear()
	    person.find(person_id)
	    for name_var in names:
		try:
		    names[name_var] = person.get_name(int(co.system_cached), int(getattr(co,name_var)))
		except Errors.NotFoundError:
		    name[name_var] = None
	    if not names['name_last'] or not names['name_first']:
		if names['name_full']:
		    name_l = names['name_full'].split(' ')
		    if len(name_l) > 1:
			names['name_last'] = name_l[len(name_l)-1]
			names['name_first'] = ' '.join(name_l[:len(name_l)-1])
		    else: 
			names['name_last'] = names['name_full']
			names['name_first'] = names['name_full']
		else:
		    for name_var in names:
			names[name_var] = account.account_name	
    	except Errors.NotFoundError:
	    logger.debug("find on person or account failed, user_id:", account_id)
	    for name_var in names:
		names[name_var] = account.account_name
	try:
	    affiliation = get_primary_affiliation(account_id, co.account_namespace)
	    if affiliation == co.affiliation_student:
		ext_id = int(person.get_external_id(co.system_fs, co.externalid_studentnr)[0]['external_id'])
	    else: 
		ext_id = int(person.get_external_id(source_system=None,id_type=co.externalid_sap_ansattnr)[0]['external_id'])
	except:
	    pass
	try:
	    email = account.get_primary_mailaddress()
	except:
	    email = None
    else:
    	email = None
	affiliation = None
	names = {'name_last':account.account_name, 
		'name_first':account.account_name}
    account_disable = 'FALSE'
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
                account_disable = 'TRUE'
        except KeyError:        
            logger.info("WARNING: missing QUARANTINE_RULE")    
    if (account.is_expired()):
        account_disable = 'TRUE'
    return (names['name_first'], names['name_last'], account_disable, 
		home_dir, affiliation, ext_id, email, pers)


def get_primary_ou(account_id,namespace):
    account.clear()
    account.find(account_id)
    name = account.get_name(namespace)
    try:
        acc_types = account.get_account_types()
    except Errors.NotFoundError:
        return None
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



def get_ldap_group_ou(grp_name):
    # Default
    utf8_ou = unicode("ou=%s,%s" % (cereconf.NW_LOST_AND_FOUND, cereconf.NW_LDAP_ROOT), 'iso-8859-1').encode('utf-8')
    if grp_name.find('stud') != -1:
        if cereconf.NW_LDAP_STUDGRPOU != None:
            utf8_ou = "%s,%s" % (unicode(cereconf.NW_LDAP_STUDGRPOU, 'iso-8859-1').encode('utf-8'),
			unicode(cereconf.NW_LDAP_ROOT, 'iso-8859-1').encode('utf-8'))
    elif grp_name.find('ans') != -1:
        if cereconf.NW_LDAP_ANSGRPOU != None:
	    utf8_ou = "%s,%s" % (unicode(cereconf.NW_LDAP_ANSGRPOU, 'iso-8859-1').encode('utf-8'),
			unicode(cereconf.NW_LDAP_ROOT, 'iso-8859-1').encode('utf-8'))
    return utf8_ou


def get_ldap_usr_ou(crbm_ou, aff):

    if cereconf.NW_LDAP_STUDOU != None and (aff == co.affiliation_student or \
				ent_name.has_spread(co.spread_hia_novell_labuser)):
	utf8_ou = "%s,%s" % (unicode(cereconf.NW_LDAP_STUDOU, 'iso-8859-1').encode('utf-8'),
			unicode(cereconf.NW_LDAP_ROOT, 'iso-8859-1').encode('utf-8'))
    elif cereconf.NW_LDAP_ANSOU != None and aff == co.affiliation_ansatt:
	utf8_ou = "%s,%s" % (unicode(cereconf.NW_LDAP_ANSOU, 'iso-8859-1').encode('utf-8'),
		unicode(cereconf.NW_LDAP_ROOT, 'iso-8859-1').encode('utf-8'))
    elif crbm_ou != None:
        utf8_ou = unicode(crbm_ou, 'iso-8859-1').encode('utf-8')
    else:
        utf8_ou = unicode("ou=%s,%s" % (cereconf.NW_LDAP_STUDOU, cereconf.NW_LDAP_ROOT), 'iso-8859-1').encode('utf-8')
    return utf8_ou



def get_crbrm_ou(ou_id):
    if ou_id != None:
        try:        
            ou.clear()
            ou.find(ou_id)
            path = ou.structure_path(co.perspective_fs)
            #TBD: Utvide med spread sjekk, OUer uten acronym, problem?
            return 'ou=%s' % path.replace('/',',ou=')
        except Errors.NotFoundError:
            logger.info("WARNING: Could not find OU with id",ou_id)
    else:
        return('student')

def id_to_ou_path(ou_id,ourootname):
    crbrm_ou = get_crbrm_ou(ou_id)
    if crbrm_ou == ourootname:
        if cereconf.NW_DEFAULT_OU == '0':
            crbrm_ou = 'cn=Users,%s' % ourootname
        else:
            crbrm_ou = get_crbrm_ou(cereconf.NW_DEFAULT_OU_ID)
    if (cereconf.NW_LDAP_ROOT != ""):
    	crbrm_ou = crbrm_ou.replace(ourootname,cereconf.NW_LDAP_ROOT)
    return crbrm_ou






def find_home_dir(account_id, account_name, spread):
    try:
        account.clear()
        account.find(account_id)
        tmp = account.get_home(spread=spread)
        if tmp['home'] is not None:
            return tmp['home']
        disk.clear()
        disk.find(tmp['disk_id'])
    except Errors.NotFoundError:
        return None
    return "%s/%s" % (disk.path, account_name)



def find_login_script(account):
    #This value is a specific UIO standard.
    return "users\%s.bat" % (account)


def touchable(attrs):
    """Given attributes and their values we determine if we are allowed to
       modify this object"""
    if attrs.has_key('description'):
        if attrs['description'][0][0:8] == 'Cerebrum':
           return True
    return False



if __name__ == '__main__':
    pass

# arch-tag: 01ab4c39-ae52-4e60-80fe-ce71bd5087ce
