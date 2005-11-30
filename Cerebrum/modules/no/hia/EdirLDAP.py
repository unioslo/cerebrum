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

import cerebrum_path
import cereconf

import ldap
import ldap.modlist

from Cerebrum.Utils import Factory

class LDAPConnection:

    def __init__(self, db, host=None, port=None,
                 binddn=None, password=None,
                 scope='SUB'):

	self.__db = db
        self.__host = host or cereconf.NW_LDAPHOST
        self.__port = port or cereconf.NW_LDAPPORT
        self.__binddn = binddn or cereconf.NW_ADMINUSER
        self.__logger = Factory.get_logger("cronjob")

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
        handle = False
        try:
            ldap.set_option(ldap.OPT_PROTOCOL_VERSION, ldap.VERSION3)
        except ldap.LDAPError:
            self.__logger.error("Protocol version LDAPv3 not supported, aborting connect")
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
                self.__logger.error("Could not find appropriate certificate, can't start encrypted connection!")
                return False
        try:
            handle = ldap.open(host)
        except ldap.LDAPError, e:
            self.__logger.error("Could not create ldap handler (ldap.open) for %s" % (host, str(e)))
            return False
        if crypted:
            try:
                handle.start_tls_s()
                self.__logger.info("TLS connection established to %s" % host)
            except ldap.LDAPError, e:
                self.__logger.error("Could not open TLS-connection to %s (%s)" % (host, str(e)))
                return False
        else:
            self.__logger.info("Trying to establish unencrypted connection to %s" % host)
        try:
            handle.simple_bind_s(binddn,password)
            self.__logger.debug("Successfully binded %s to %s" % (binddn, host))
        except ldap.LDAPError:
            self.__logger.error("Could not bind %s to %s." % (binddn, host))
            return False
        return handle

    def __unbind(self):
        """Close connection to a host"""
	self.__ldap_connection_handle.unbind()
	self.__ldap_connection_handle = None

    def __search(self, basedn, filter, scope=ldap.SCOPE_SUBTREE, attrs=None):
        return self.__ldap_connection_handle.search_s(basedn, scope, filter, attrlist=attrs)

    def __create(self, dn, attrs):
        return self.__ldap_connection_handle.add_s(dn, attrs)

    def __delete(self, dn):
        return self.__ldap_connection_handle.delete_s(dn)

    def __modify(self, dn, attrs):
        return self.__ldap_connection_handle.modify_s(dn, attrs)

    def _make_modlist(self, modtype, attrdict):
        attrlist = []
        if modtype == 'add':
            ldap_mod = ldap.MOD_ADD
        elif modtype == 'replace':
            ldap_mod = ldap.MOD_REPLACE
        elif modtype == 'delete':
            ldap_mod = ldap.MOD_DELETE
        else:
            self.__logger.warn("No such modify type (%s)!" % modtype)
            return None
        for kind, value in attrdict.iteritems():
            attrlist.append((ldap_mod, kind, value))
        return attrlist

    def close_connection(self):
        if self.__ldap_connection_handle:
            self.__unbind()
            self.__logger.info("Closed connection to %s" % self.__host)

    def ldap_get_objects(self, basedn, filter, attrlist=None):
        try:
            ldap_object = self.__search(basedn, filter, self.__scope, attrlist)
            return ldap_object
        except ldap.LDAPError, e:
            self.__logger.warn("Could not find object %s (%s)" % (filter, str(e)))
            return False

    def ldap_add_object(self, dn, attrdict):
        attrs = ldap.modlist.addModlist(attrdict)
        try:
            self.__create(dn, attrs)
            self.__logger.debug("Added new object %s." % dn)
        except ldap.LDAPError, e:
            self.__logger.warn("Could not add object %s (%s)." % (dn, str(e)))

    def ldap_delete_object(self, dn):
        try:
            self.__delete(dn)
            self.__logger.debug("Deleted object %s." % dn)
        except ldap.LDAPError, e:
            self.__logger.warn("Could not delete object %s (%s)." % (dn,
                                                                     str(e)))

    def ldap_modify_object(self, dn, modtype, attrdict):
        attrs = self._make_modlist(modtype, attrdict)
        try:
            self.__modify(dn, attrs)
            self.__logger.warn("Successfully modified object %s (%s)." % (dn,
                                                                          attrs))
        except ldap.LDAPError, e:
            self.__logger.warn("Could not modify object %s (%s)." % (dn,
                                                                     str(e)))


    # This method is currently not in use, but it might be usefull at some
    # point
    def ldap_rename_object(self, olddn, newdn, del_olddn=True):
        if del_olddn:
            try:
                self.__rename(olddn, newdn)
            except ldap.LDAPError, e:
                self.__logger.warn("Could not rename object %s (%s)." % (dn,
                                                                         str(e)))
        else:
            try:
                self.__rename(olddn, newdn, 0)
            except ldap.LDAPError, e:
                self.__logger.warn("Could not rename object %s (%s)." % (dn,
                                                                          str(e)))

# arch-tag: 5da697b0-5cb2-11da-8d27-542eaf022ad8
