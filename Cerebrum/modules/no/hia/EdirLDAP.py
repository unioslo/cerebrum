# -*- coding: iso-8859-1 -*-
#
# Copyright 2003, 2004, 2005 University of Oslo, Norway
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

import ldap

class LDAPConnection:

    def __init__(self, host=None, port=389,
                 binddn=None, password=None,
                 scope= 'SUB', db):

	self.db = db
        self.__host = host or cereconf.NW_LDAPHOST
        self.__port = port or cereconf.NW_LDAPPORT
        self.__binddn = binddn or cereconf.NW_ADMINUSER
        
	if not password:
	    user = cereconf.NW_ADMINUSER.split(',')[:1][0]
	    self.__password = self.db._read_password(cereconf.NW_LDAPHOST,
                                                     user)
	else:
	    self.__password = password
            
        if scope.upper() == 'SUB':
            self.__scope = ldap.SCOPE_SUBTREE
        elif scope.upper() == 'ONE':
            self.__scope = ldap.SCOPE_ONE
        else:
            self.__scope = ldap.SCOPE_BASE

        self.__ldap_connection_handle = None
    
    def __connect( self, host, binddn, password, port, crypted=True):
        """Try to establish a (per default encrypted) connection
           to a given host."""

        ldap.set_option(ldap.OPT_PROTOCOL_VERSION, ldap.VERSION3)

        if crypted:  
            try:
                if cereconf.TLS_CACERT_FILE is not None:
                    ldap.set_option(ldap.OPT_X_TLS_CACERTFILE,
                                    cereconf.TLS_CACERT_FILE)
                else:
                    if cereconf.TLS_CACERT_DIR is not None:
                        ldap.set_option(ldap.OPT_X_TLS_CACERTDIR,
                                        cereconf.TLS_CACERT_DIR)
            except ldap.LDAPError:
                logger.error("Could not find appropriate certificate, can't start encrypted connection!")
                return False
             try:
                 handle = ldap.open(host)
            except ldap.LDAPError:
                logger.error( "Could not do ldap.open to %s" % host)
                return False
            try:
                handle.start_tls_s()
                logger.info("TLS connection established to %s" % host)
            except ldap.LDAPError:
                logger.error("Could not open TLS-connection to %s" % host)
                return False
            try:
                handle.simple_bind_s(binddn,password)
                logger.debug("Successfully binded '%s' to '%s'" % (binddn, host))
            except ldap.LDAPError:
                logger.info( "Could not bind '%s' to '%s'." % (binddn, host))
                return False
            return handle
        else:
            try:
                handle.simple_bind_s(binddn, password)
                logger.info("Opened unencrypted connection to %s" % host)
            except:
                logger.info("Could not open unencrypted connection to %s" % host)
                return False
            return handle
    
    def __unbind(self):
        """Close connection to a host"
	self.__ldap_connection_handle.unbind()
	self.__ldap_connection_handle = None

    def __search(self, handle, basedn, filter,
                 scope=ldap.SCOPE_SUBTREE, attrs=None):
        if not handle:
            return False
        return handle.search_s(basedn, scope, filter, attrlist=attrs)
    
    def __create(self, handle, dn, attrs):
        if not handle:
            return False
        handle.add_s(dn, attrs)
        
    def __delete(self, handle, dn):
        if not handle:
            return False
        handle.delete_s(dn)
    
    def __rename(self, handle, olddn, newdn, delete_olddn=1):
        if not handle:
            return False
        handle.modrdn_s(olddn, newdn, delete_olddn)
        
    def __modify(self, handle, dn, attrs):
        if not handle:
            return False
        handle.modify_s(dn, attrs)

    def get_objects(self, basedn, filter, attrlist=None):
        if not self.__ldap_connection_handle:
            return None
        res = self.__search(self.__ldap_connection_handle, basedn, filter, self.__scope, attrlist)
        return res
    
    def create_object(self, dn, attrlist):
        ok = True
        if not self.__ldap_connection_handle:
            ok = False
        else:
            self.__create(self.__ldap_connection_handle, dn, attrs)
        return ok
    
    def delete_object(self, dn):
        ok = True
        if not self.__ldap_connection_handle:
            ok = False
        else:
            self.__delete( self.__ldap_connection_handle, dn )
        return ok

    def rename_object(self, olddn, newdn, del_olddn=True ):
        if not self.__ldap_connection_handle:
            return False
        if del_olddn:
            self.__rename(self.__ldap_connection_handle, olddn, newdn)
        else:
            self.__rename(self.__ldap_connection_handle, olddn, newdn, 0)
        return ok
            
    def add_attributes(self, dn, newattrs):
        ok = True
        if not self.__ldap_connection_handle:
            ok = False
        else:
            attrs = []
            for type, value in newattrs:
                attrs.append((ldap.MOD_ADD, type, value))
                self.__modify(self.__ldap_connection_handle, dn, attrs)
        return ok
        
    def modify_attributes(self, dn, changedattrs):
        ok = True
        if not self.__ldap_connection_handle:
            ok = False
        else:
            attrs = []
            for type, value in changedattrs:
                attrs.append((ldap.MOD_REPLACE, type, value))
                self.__modify(self.__ldap_connection_handle, dn, attrs)
        return ok

    def raw_modify_attributes(self, dn, changedattrs):
        ok = True
        if not self.__ldap_connection_handle:
            ok = False
        else:
            self.__modify(self.__ldap_connection_handle, dn, changedattrs)
        return ok

        
    def delete_attributes(self, dn, delattrs):
        ok = True
        if not self.__ldap_connection_handle:
            ok = False
        else:
            attrs = []
            for type,value in delattrs:
                attrs.append((ldap.MOD_DELETE, type, value))
                self.__modify(self.__ldap_connection_handle, dn, attrs)
        return ok
        
    def modify_object(self, dn, attrs):
        ok = True
        if not self.__ldap_connection_handle:
            ok = False
        else:
            self.__modify(self.__ldap_connection_handle, dn, attrs)
        return ok

# arch-tag: 5da697b0-5cb2-11da-8d27-542eaf022ad8
