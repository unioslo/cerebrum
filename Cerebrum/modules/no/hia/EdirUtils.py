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
import time
import string

from mx import DateTime
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum.extlib import logging
from Cerebrum.modules.no.hia import EdirLDAP


class EdirUtils:
    
    def __init__(self, db, ldap_handle):
        self.__db = db
        self.__ldap_handle = ldap_handle
        self.logger = Factory.get_logger('cronjob')
        self.pq_attrlist = ['accountBalance', 'allowUnlimitedCredit']
        t = time.localtime()[0:3]
        self.date = '%s-%s-%s' % (t[0], t[1], t[2])
        self.c_person = 'objectClass=inetOrgPerson'
        self.c_group = 'objectClass=group'
        self.account_attrs = ['passwordAllowChange', 'givenName',
                              'sn', 'fullName', 'mail', 'passwordRequired',
                              'generationQualifier', 'uid', 'loginDisabled']

## CREATE OBJECT:
    def object_edir_create(self, dn, attrdict):
        """Create a user or group object in eDir."""
        self.__ldap_handle.ldap_add_object(dn, attrdict)

## GROUP:  add/remove group_member.
    def group_modify(self, mod_type, group_name, member_name, member_type):
        """Add an existing account object to a group in eDir."""
        attr_g = {}
        attr_m = {}
        ldap_group = self._find_object(group_name, self.c_group)
        if member_type == "account":
            ldap_member = self._find_object(member_name, self.c_person)
        elif member_type == "group":
            ldap_member = self._find_object(member_name, self.c_group)
        if ldap_group:
            (ldap_group_dn, group_attr) = ldap_group[0]
            if ldap_member:
                (ldap_member_dn, ldap_attr) = ldap_member[0]
                attr_g['member'] = [ldap_member_dn]
                if mod_type == 'add':
                    self.__ldap_handle.ldap_modify_object(ldap_group_dn, 'add', attr_g)
                elif mod_type == 'delete':
                    self.__ldap_handle.ldap_modify_object(ldap_group_dn, 'delete', attr_g)
                attr_m['groupMembership'] = [ldap_group_dn]
                if member_type == 'account':
                    attr_m['securityEquals'] = [ldap_group_dn]
                if mod_type == 'add':
                    self.__ldap_handle.ldap_modify_object(ldap_group_dn, 'add', attr_m)
                elif mod_type == 'delete':
                    self.__ldap_handle.ldap_modify_object(ldap_group_dn, 'delete', attr_g)
            else:
                self.logger.error("No such account |%s|" % member_name)
        else:
            self.logger.error("No such group, |%s|." % group_name)
            
## QUARANTINE: set/remove quarantine
    def account_set_quarantine(self, account_name):
        """Set loginDisabled attribute to True. Used when a
           change_log event 'quarantine_add' is found in
           change_log.""" 
        attr = {}
        l_disabled = 'loginDisabled'
        attr[l_disabled] = ['True']
        ldap_object = self._find_object(account_name,self.c_person)

        if ldap_object:
            print "OK %s" % account_name
            (ldap_object_dn, ldap_attr) = ldap_object[0]
            if l_disabled in ldap_attr.keys():
                self.__ldap_handle.ldap_modify_object(ldap_object_dn, 'replace', attr)
            else:
                self.__ldap_handle.ldap_modify_object(ldap_object_dn, 'add', attr)
            desc = 'Cerebrum: set quarantine %s' % (self.date)
            self.object_set_description(account_name, self.c_person, desc)
                
    def account_remove_quarantine(self, account_name):
        """Set loginDisabled attribute to False. Used when a
           change_log event 'quarantine_remove' or 'quarantine_mod'
           is found in change_log."""
        attr = {}
        l_disabled = 'loginDisabled'
        ldap_object = self._find_object(account_name,self.c_person)

        if ldap_object:
            (ldap_object_dn, ldap_attr) = ldap_object[0]
            attr[l_disabled] = ['False']
            if l_disabled in ldap_attr.keys():
                self.__ldap_handle.ldap_modify_object(ldap_object_dn, 'replace', attr)
                desc = 'Cerebrum: rem quarantine %s' % self.date 
                self.object_set_description(account_name, self.c_person, desc)

## PRINTER QUOTA: get quota info, set accountBalance, get all available quota info
    def get_pq_balance(self, account_name):
        """Get current value of attribute 'accountBalance' for
           account_name. If account has unlimited quota priviledges
           False is returned (no need to update attr)."""
        ldap_object = self._find_object(account_name, 
                                        self.c_person,
                                        self.pq_attrlist)
        if ldap_object:
            (ldap_object_dn, ldap_attr) = ldap_object[0]
            for k in ldap_attr.keys():
                if k == 'allowUnlimitedCredit':
                    if ldap_attr['allowUnlimitedCredit'] == True:
                        return False
                elif k == 'accountBalance':
                    return ldap_attr['accountBalance']
                else:
                    self.logger.warn('No printer quota info for %s.' % account_name)

    def set_pq_balance(self, account_name, pquota=cereconf.NW_FREEQUOTA):
        """Set value of attribute 'accountBalance' for account_name.
           Also set attr 'allowUnlimitedCredit' to False. This method
           is used only when the account has been found to be a student
           account and update is needed (term fee is paid).
           Change_log - lars vil ha updates inn der."""
        tmp = 0
        attrs = {}
        ldap_object = self._find_object(account_name,
                                        self.c_person,
                                        self.pq_attrlist)
        if ldap_object:
            (ldap_object_dn, ldap_attr) = ldap_object[0]
            if 'accountBalance' in ldap_attr.keys():
                tmp = int(ldap_attr['accountBalance'][0])
                pquota = tmp + pquota
                attrs['accountBalance'] = [str(pquota)]
                attrs['allowUnlimitedCredit'] = ['False']
                self.__ldap_handle.ldap_modify_object(ldap_object_dn, 'replace', attrs)
            else:
                self.__ldap_handle.ldap_modify_object(ldap_object_dn, 'add', attrs)
            self.logger.info("Updated quota for %s, new quota is %s" % (account_name,
                                                                   pquota))
            desc = "Cerebrum: update_quota (%s), old=%s, new=%s" % (self.date,
                                                                    tmp,
                                                                    pquota)
                                                                    
            self.object_set_description(account_name, self.c_person, desc)

    def get_all_pq_info(self):
        """Return available quota info on all user objects in eDir."""
        pq_info = []
        search_str = self.c_person
        ldap_objects = self.__ldap_handle.ldap_get_objects(cereconf.NW_LDAP_ROOT,
                                                           search_str, self.pq_attrlist)
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

## NAME MODIFICATIONS:
    def person_set_name(self, object_name, name_first, name_last, name_full):
        """Used if change_log events 'person_name_add' or 'person_name_mod'
           occur. Should a name be deleted and no other names are available
           the method returns and logs an error."""
        if name_first == "" or name_last == "" or name_full== "":
            self.logger.error("Cannot update name to None for %s" % object_name)
            return
        attrs = {}
        ldap_object = self._find_object(object_name,
                                        self.c_person)
        attrs['givenName']=[name_first]
        attrs['sn']=[name_last]
        attrs['fullName']=[name_full]
        if ldap_object:
            (ldap_object_dn, ldap_attrs) = ldap_object[0]            
            self.__ldap_handle.ldap_modify_object(ldap_object_dn, 'replace', attrs)
            self.logger.info("Modified name for %s, new name is %s" % (object_name,
                                                                       attrs['fullName']))
            desc = "Cerebrum: new name (%s)" % self.date
            self.object_set_description(object_name, self.c_person, desc)
                
        else:
            self.logger.info("No such object %s, can't update name!" %s % object_name)

## HELPER:            
    def _find_object(self, object_name, object_class, attrlist=None):
        """Find and return ref. to an ldap_object."""
        if object_class in [self.c_person, self.c_group]:
            search_str = "(&(cn=%s)(%s))" % (object_name, object_class)
        else:
            self.logger.error("No such object class %s" % object_class)
            return None

        ldap_object = self.__ldap_handle.ldap_get_objects(cereconf.NW_LDAP_ROOT,
                                                          search_str, attrlist)
        return ldap_object

## DESCRIPTION: update description
    def object_set_description(self, object_name, object_class, description):
        """Update or set 'description' attr for an object in eDir. This
           method is used every time a relevant change occurs in Cerebrum.
           Relevant changes are listed in edirsync.py.

           TODO: Det er ønskelig å endre den første kommentaren på
           alle brukere som er blitt opprettet i Cerebrum til
           Cerebrum: created yyyy-mm-dd (stud_nr hvis finnes)
           TODO: \n does not seem to work, changing back to ';'
           until a proper solution is found"""
        desc = []
        attrs = {}
        ldap_attrs = {}
        ldap_object_dn = None
        ldap_object = self._find_object(object_name,
                                        object_class,
                                        ['description'])
        if ldap_object:
            (ldap_object_dn, ldap_attrs) = ldap_object[0]            

        if ldap_attrs:
            temp = ldap_attrs['description']
            desc = string.split(temp[0], '\n')
            
        if len(desc) <= 4:
            desc.append(description)
        else:
            desc.pop(1)
            desc.append(description)

        attrs['description'] = string.join(desc,';')
        if not ldap_object_dn == None:
            self.__ldap_handle.ldap_modify_object(ldap_object_dn, 'replace', attrs)


## PASSWD: set account password
    def account_set_password(self, account_name, passwd):
        attr = {'userPassword': passwd}
        ldap_object = self._find_object(account_name, self.c_person)
        if ldap_object:
            (ldap_object_dn, ldap_attr) = ldap_object[0]
            self.__ldap_handle.ldap_modify_object(ldap_object_dn, 'replace', attr)
            if 'password' in ldap_attr.keys():
                logger.info("Updated password for %s", account_name)
            desc = "Cerebrum: password %s" % self.date
            self.object_set_description(account_name, self.c_person, desc)

            
## HOME: set home directory
## ikke i bruk
    def account_set_home(self, account_name, path):
        """Set attr nsdHomeDirectory for a user if change_log
           event e_account_move occurs. Home directory changes
           are actually handled through group membership so this
           method affects the attr only."""
        attr = {}
        home = 'ndsHomeDirectory'
        attr[home] = path
        ldap_object = self._find_object(account_name,self.c_person)
        if ldap_object:
            (ldap_object_dn, ldap_attr) = ldap_object[0]
            self.__ldap_handle.ldap_modify_object(ldap_object_dn, 'replace', attr)
            if home in ldap_attr.keys():
                if path <> ldap_attr[home]:
                    desc = "Cerebrum: user moved %s" % self.date
                    self.object_set_description(account_name, self.c_person, desc)
                    logger.info("Account ndsHomeDirectory changed for %s" % account_name)

# arch-tag: 5e6865d4-5cb2-11da-97b8-ad2f2be70968

