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

    def __init__(self, host=None, port=None,
                 binddn=None, password=None,
                 scope= 'SUB', db):

	self.__db = db
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

        self.__ldap_connection_handle = self.__connect(self.__host,
                                                       self.__binddn,
                                                       self.__password,
                                                       self.__port)

    def __connect(self, host, binddn, password, port, crypted=True):
        """Try to establish a (per default encrypted) connection
           to a given host."""
        try:
            ldap.set_option(ldap.OPT_PROTOCOL_VERSION, ldap.VERSION3)
        except ldap.LDAPError:
            logger.error("Protocol version LDAPv3 not supported, aborting connect")
            return False

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
            logger.error( "Could not create ldap handler (ldap.open) for %s" % host)
            return False

        if crypted:
            try:
                handle.start_tls_s()
                logger.info("TLS connection established to %s" % host)
            except ldap.LDAPError:
                logger.error("Could not open TLS-connection to %s" % host)
                return False
        else:
            logger.info("Trying to establish unencrypted connection to %s" % host)
        try:
            handle.simple_bind_s(binddn,password)
            logger.debug("Successfully binded '%s' to '%s'" % (binddn, host))
        except ldap.LDAPError:
            logger.error("Could not bind '%s' to '%s'." % (binddn, host))
            return False
        return handle
        
    
    def __unbind(self):
        """Close connection to a host"
	self.__ldap_connection_handle.unbind()
	self.__ldap_connection_handle = None

    # TBD:
    #
    # skal vi gjøre forsøk på å utføre connect i disse metodene?
    # jeg liker ideen med å gjøre eksplisitt connect og unbind, men
    # det er ikke sikkert på at det er optimalt...
    
    def __search(self, basedn, filter, scope=ldap.SCOPE_SUBTREE, attrs=None):
        if not self.__ldap_connection_handle:
            self.__connect(self.__host, self.__binddn, self.__password, self.__port)
        return self.__ldap_connection_handle.search_s(basedn, scope, filter, attrlist=attrs)
    
    def __create(self, dn, attrs):
        if not self.__ldap_connection_handle:
            self.__connect(self.__host, self.__binddn, self.__password, self.__port)
        self.__ldap_connection_handle.add_s(dn, attrs)
        return True
        
    def __delete(self, dn):
        if not self.__ldap_connection_handle:
            self.__connect(self.__host, self.__binddn, self.__password, self.__port)
        self.__ldap_connection_handle.delete_s(dn)
        return True
    
    def __modify(self, dn, attrs):
        if not self.__ldap_connection_handle:
            self.__connect(self.__host, self.__binddn, self.__password, self.__port)
        self.__ldap_connection_handle.modify_s(dn, attrs)
        return True
    
        # Mange av metodene under bruker False og None om hverandre.
        # Folk koder ofte "if <kall inn i API>"og dette vil feile
        # hvis handle ikke er opprettet(litt rart kanskje?) og sikkert
        # hvis kallet i ldap returnerer None eller False.

    def close_connection(self):
        if self.__ldap_connection_handle:
            self.__unbind()
            logger.info("Closed connection to %s" % self.__host())

    def _make_filter(object_dn):
        return 
    # Object level
    
    def ldap_get_objects(self, basedn, filter, attrlist=None):
        ldap_object = None
        try:
            ldap_object = self.__search(basedn, filter, self.__scope, attrlist)
        except ldap.LDAPError, e:
            logger.warn("Could not find object %s (%s)" % (basedn, str(e))
        return ldap_object
            
    def ldap_add_object(object_dn, attrlist):
        for kind, value in attrs:
            if kind == 'userPassword':
                attrlist[kind] = 'xxxxxxxx'
        try:
            self.__create(self.__ldap_connection_handle, dn, attrs)
        except ldap.LDAPError, e:
            logger.warn("Could not add object %s (%s)." % (object_dn, str(e))
            
    def ldap_delete_object(self, dn):
        try:
            self.__delete(self.__ldap_connection_handle, dn)
        except ldap.LDAPError, e:
            logger.warn("Could not delete object %s (%s)." % (object_dn, str(e))

    def ldap_rename_object(self, olddn, newdn, del_olddn=True ):
        if del_olddn:
            try:
                self.__rename(self.__ldap_connection_handle, olddn, newdn)
            except ldap.LDAPError, e:
                logger.warn("Could not rename object %s (%s)." % (object_dn, str(e))
        else:
            try:
                self.__rename(self.__ldap_connection_handle, olddn, newdn, 0)
            except ldap.LDAPError, e:
                logger.warn("Could not rename object %s (%s)." % (object_dn, str(e))
                
    def ldap_modify_object(self, dn, attrs):
        try:
            self.__modify(self.__ldap_connection_handle, dn, attrs)
        except ldap.LDAPError, e:
            logger.warn("Could not modify object %s (%s)." % (object_dn, str(e))
            
    # Attribute level
    def ldap_add_attributes(self, object_dn, attrs):
        attrlist = []
        try:
            for kind, value in attrs:
                attrslist.append((ldap.MOD_ADD, type, value))
            self.__modify(self.__ldap_connection_handle, dn, attrlist)
        except ldap.LDAPError, e:
            logger.warn("Could not add attr %s for %s." % (object_dn,
                                                           attr_str,
                                                           str(e)))

    def ldap_modify_attributes(self, object_dn, attrs):
        attrlist = []
        for kind, value in attrs:
            if kind == 'userPassword':
                attrs[kind] = 'xxxxxxxx'           
            attrlist.append((ldap.MOD_REPLACE, kind, value))
        attr_str = string.join(attrlist.values(),', ')
        try:
            self.__modify(self.__ldap_connection_handle, object_dn, attrlist)
        except ldap.LDAPError, e:
            logger.warn("Could not modify object %s with %s (%s)." % (object_dn,
                                                                      attr_str,
                                                                      str(e)))
    
    def ldap_object_del_attributes(object_dn, attrs):
        attrlist = []
        for kind, value in attrs:
            attrlist.append((ldap.MOD_DELETE, kind, value))
        attr_str = string.join(attrlist.values(),', ')
        try:
            self.__modify(self.__ldap_connection_handle, object_dn, attrlist)
        except ldap.LDAPError, e:
            logger.warn("Could not delete attr %s for %s (%s)." % (attr_str,
                                                                   object_dn,
                                                                   str(e)))
# arch-tag: 5da697b0-5cb2-11da-8d27-542eaf022ad8
