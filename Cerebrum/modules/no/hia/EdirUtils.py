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
from Cerebrum.modules.no.hia import EdirLDAP


class EdirUtils:
    
    def __init__(self, db, ldap_handle):
        self.__db = db
        self.__ldap_handle = ldap_handle #EdirLDAP.LDAPConnection(self.__db)
        self.__logger = Factory.get_logger('cronjob')
        self.__pq_attrlist = ['accountBalance', 'allowUnlimitedCredit']

    def get_pq_balance(self, account_name):
        ldap_object = self._find_object(account_name, 
                                        self.__pq_attrlist,
                                        'objectClass=inetOrgPerson')
        if ldap_object:
            (ldap_object_dn, ldap_attr) = ldap_object[0]
            for k in ldap_attr.keys():
                if k == 'allowUnlimitedCredit':
                    if ldap_attr['allowUnlimitedCredit'] == True:
                        return False
                elif k == 'accountBalance':
                    return ldap_attr['accountBalance']
                else:
                    logger.warn('No printer quota info for %s.' % account_name)
        
    def set_pq_balance(self, account_name, pquota=cereconf.NW_PR_QUOTA):
        attrs = {}
        ldap_object = self._find_object(account_name,
                                        object_class='objectClass=inetOrgPerson')
        if ldap_object:
            (ldap_object_dn, ldap_attr) = ldap_object[0]
            if 'accountBalance' in ldap_attr.keys():
                pquota = int(ldap_attr['accountBalance'][0]) + pquota
                attrs['accountBalance'] = [pquota]
                attrs['allowUnlimitedCredit'] = ['False']
                self.__ldap_handle.ldap_modify_object(ldap_object_dn, 'replace', attrs)
            else:
                self.__ldap_handle.ldap_modify_object(ldap_object_dn, 'add', attrs)
            logger.info("Updated quota for %s, new quota is %s" % (account_name,
                                                                   pquota))

    def get_all_pq_info(self):
        pq_info = []
        search_str = 'objectClass=inetOrgPerson'
        ldap_objects = self.__ldap_handle.ldap_get_objects(cereconf.NW_LDAP_ROOT,
                                                           search_str, self.__pq_attrlist)
        i = 0
        while i < len(ldap_objects):
            (ldap_object_dn, ldap_attrs) = ldap_objects[i]
            i = i + 1
            if not ldap_attrs:
                pq_info.append('No quota information for %s!' % ldap_object_dn)
                continue
            for k in ldap_attrs.keys():
                if k == 'allowUnlimitedCredit':
                    if ldap_attrs[k] == True:
                        pq_info.append('Unlimited printer quota for %s' % ldap_object_dn)
                if k == 'accountBalance':
                    pq_info.append('Limited quota for %s, current balance %s'% (ldap_object_dn,
                                                                                ldap_attrs[k]))
        return pq_info
            

    def _find_object(self, object_name, attrlist, object_class):
        if object_class in ['objectClass=inetOrgPerson', 'objectclass=group']:
            search_str = "(&(cn=%s)(%s))" % (object_name, object_class)
        else:
            self.__logger.error("No such object class %s" % object_class)
            return None

        ldap_object = self.__ldap_handle.ldap_get_objects(cereconf.NW_LDAP_ROOT,
                                                          search_str, attrlist)
        return ldap_object

    def person_set_name(object_name, object_class='objectClass=inetOrgPerson',
                        attrs={'givenName':name_first,
                               'sn':name_last,
                               'fullName':name_full}):
        
        ldap_object = self._find_object(account_name,
                                        object_class)
        if ldap_object:
            (ldap_user, ldap_attrs) = ldap_object[0]
            for k, v in attrs.iteritems():
                ldap_update = [((k, [v]))]
                if k in ldap_attrs.keys():
                    self.__ldap_handle.ldap_object_mod_attr(ldap_user, ldap_update)
                else:
                    self.__ldap_handle.ldap_object_add_attr(ldap_user, ldap_update)
            logger.info("Modified name for %s, new name is %s" % (object_name,
                                                                  attrs['fullName'])
        else:
            logger.info("No such object %s, can't update name!" %s % object_name)


    ## FIXME: These method will not work right now as I made som changes
    ##        to ldap_object-methods. 
    def set_description(self, object_name, object_class='objectClass=inetOrgPerson', description):
        desc = []
        attrs = {}
        ldap_object = self._find_object(object_name,
                                        ['description']
                                        object_class)

        (ldap_object_dn, ldap_attrs) = ldap_object[0]

        desc = ldap_attrs
        
        if len(desc) <= 4:
            desc.append(description)
        else:
            temp = desc[0]
            desc = desc[1:]
            desc.insert(temp, 0)
            desc.append(description)

        attrs['description'] = string.join(desc,';')
        self.__ldap_handle.ldap_modify_object(ldap_object_dn, attrs)

# arch-tag: 5e6865d4-5cb2-11da-97b8-ad2f2be70968