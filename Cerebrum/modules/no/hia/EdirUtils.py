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

from mx import DateTime
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum import QuarantineHandler
from Cerebrum.extlib import logging
from Cerebrum.modules.no.hia import NWLdap


class EDirUtils:

    def __init__(self, db):
        self.db = db
        self.constants = Factory.get('Constants')(self.db)
        self.ldap_handle = NWLdap.LDAPConnection(self.db)
        self.logger = Factory.get_logger('cronjob')(self.db)

    def add_ldap_object(object_dn, attrlist):
        for kind, value in attrs:
	    if kind == 'userPassword':
		attrlist[kind] = 'xxxxxxxx'
        try:
            self.ldap_handle.create_object(object_dn, attrlist)
        except ldap.LDAPError:
            logger.warn("Could not add object %s." % object_dn)

    def delete_ldap_object(object_dn):
        try:
            self.ldap_handle.delete_object(object_dn)
        except ldap.LDAPError:
            logger.warn("Could not delete %s." % object_dn)

    def attr_add_ldap_object(object_dn, attrlist):
        attr_str = string.join(attrlist.values(),', ')
        try:
            self.ldap_handle.add_attributes(object_dn, attrlist)
        except ldap.LDAPError:
            logger.warn("Could not add attr %s for %s." % (object_dn,
                                                           attr_str))
            
    def attr_del_ldap_object(object_dn, attrlist):
        attr_str = string.join(attrlist.values(),', ')
        try:
            self.ldap_handle.delete_attributes(object_dn, attrlist)
        except ldap.LDAPError:
            logger.warn("Could not delete attr %s for %s." % (attr_str, object_dn))

    def attr_mod_ldap_object(object_dn, attrlist):
        for kind, value in attrlist:
            if kind == 'userPassword':
                attrlist[kind] = 'xxxxxxxx'
        attr_str = string.join(attrlist.values(),', ')
        try:
            self.ldap_handle.modify_attributes(object_dn, attrlist)
        except ldap.LDAPError:
            logger.warn("Could not modify object %s with %s." % (object_dn,
                                                                 attr_str))

    def person_set_name(account_name, name_first, name_last, name_full):

        ldap_object = self._find_object(account_name,
                                        object_class='person')

        attrs = {'givenName':name_first,
                 'sn':name_last,
                 'fullName':name_full}

        if ldap_object:
            (ldap_user, ldap_attrs) = ldap_object[0]
            for k, v in attrs.iteritems():
                ldap_update = [((k, [v]))]
                if a in ldap_attrs.keys():
                    self.attr_mod_ldap_object(ldap_user, ldap_update)
                else:
                    self.attr_add_ldap_object(ldap_user, ldap_update)
        else:
            return

    def _find_object(object_name, object_class=None, attrlist=None):
        tmp_str = ""
        if object_class == 'person':
            tmp_str = "(objectClass=inetOrgPerson)"
        elif object_class == 'group':
            tmp_str = "(objectclass=group)"
        else:
            self.logger.error("No such object class %s" % object_class)
            return None
        search_str = "(&(cn=%s)%s)" % (object_name, tmp_str)
        ldap_object = self.ldap_handle.get_objects(cereconf.NW_LDAP_ROOT,
                                                   search_str, attrlist)
        return ldap_object
    
    def get_pq_balance(account_name):
        ldap_object = self._find_object(account_name,
                                        object_class='person',
                                        attrlist = ['accountBalance',
                                                    'allowUnlimitedCredit'])
        if ldap_object:
            (ldap_user, ldap_attr) = ldap_object[0]
            if ldap_attr['allowUnlimitedCredit'] == True:
                return False
            else:
                return ldap_attr['accountBalance'][0]
        
    def set_pq_info(account_name, pquota=cereconf.NW_PR_QUOTA):
        ldap_object = self._find_object(account_name,
                                        object_class='person')
        if ldap_object:
            (ldap_object_dn, ldap_attr) = ldap_object[0]
            if 'accountBalance' in ldap_attr.keys():
                tot = int(ldap_attr['accountBalance'][0]) + pquota
                self.attr_mod_ldap_object(ldap_object_dn, [('accountBalance',
                                                            tot)])
            else:
                self.attr_mod_ldap_object(ldap_object_dn, [('accountBalance',
                                                            pquota)])
                
    def set_description(object_name, object_class='person', description):
        desc = []
        ldap_object = self._find_object(object_name,
                                        object_class)

        if ldap_object:
            desc = self.get_description(object_name, object_class)

        if len(desc) <= 4:
            desc.append(description)
        else:
            temp = desc[0]
            desc = desc[1:]
            desc.insert(temp, 0)
            desc.append(description)

        (ldap_object_dn, attrs) = ldap_object[0]
        self.attr_mod_ldap_object(ldap_object_dn, [('description',
                                                    desc)])
        
    def get_description(object_name, object_class='person'):
        desc = []
        
        if object_class == 'person':
            ldap_object = self._find_object(object_name,
                                            object_class='person',
                                            attrlist=['decription',])
        elif object_class == 'group':
            ldap_object = self._find_object(object_name,
                                            object_class='group',
                                            attrlist=['decription',])

        if ldap_object:
            (foo, ldap_attr) = ldap_object[0]
            desc = ldap_attr['description']
        return desc

# arch-tag: 5e6865d4-5cb2-11da-97b8-ad2f2be70968
