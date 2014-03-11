#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2011 University of Oslo, Norway
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

"""
Module with functions for Cerebrum export to Active Directory at NIH.

"""


import cerebrum_path
import cereconf

from Cerebrum.modules.ad.CerebrumData import CerebrumUser
from Cerebrum.modules.ad.CerebrumData import CerebrumDistGroup
from Cerebrum.modules.ad.ADSync import UserSync
from Cerebrum.modules.ad.ADSync import GroupSync
from Cerebrum.modules.ad.ADSync import DistGroupSync


class HIHCerebrumUser(CerebrumUser):
    def __init__(self, account_id, owner_id, uname, domain, ou):
        """
        HIHCerebrumUser constructor
        
        @param account_id: Cerebrum id
        @type account_id: int
        @param owner_id: Cerebrum owner id
        @type owner_id: int
        @param uname: Cerebrum account name
        @type uname: str
        """
        CerebrumUser.__init__(self, account_id, owner_id, uname, domain, ou)
        self.contact_mobile_phone = ""
        self.contact_phone = ""


    def is_student(self):
        # It seems smarter to compare domain, but on the testserver
        # employees and students are in the same domain...
        #if self.domain == AD_DOMAIN_STUDENT:
        if cereconf.AD_LDAP_STUDENT in self.ou:
            return True
        return False

    
    def calc_ad_attrs(self, exchange=False):
        """
        Calculate AD attrs from Cerebrum data.
        
        How to calculate AD attr values from Cerebrum data and policy
        must be hardcoded somewhere. Do this here and try to leave the
        rest of the code general.

        """
        # Read which attrs to calculate from cereconf
        ad_attrs = dict().fromkeys(cereconf.AD_ATTRIBUTES, None)
        # Set predefined default values
        ad_attrs.update(cereconf.AD_ACCOUNT_CONTROL)
        ad_attrs.update(cereconf.AD_DEFAULTS)
        if self.is_student():
            ad_attrs.update(cereconf.AD_DEFAULTS_STUDENT)
        else:
            ad_attrs.update(cereconf.AD_DEFAULTS_ANSATT)
        
        # Do the hardcoding for this sync.
        # Name and case of attributes should be as they are in AD
        ad_attrs["sAMAccountName"] = self.uname
        ad_attrs["sn"] = self.name_last
        ad_attrs["givenName"] = self.name_first
        ad_attrs["displayName"] = "%s %s" % (self.name_first, self.name_last)
        ad_attrs["ACCOUNTDISABLE"] = self.quarantined
        ad_attrs["userPrincipalName"] = "%s@%s" % (self.uname, self.domain) 
        ad_attrs["title"] = self.title
        
        if self.is_student():
            ad_attrs["cn"] = self.uname
            ad_attrs["distinguishedName"] = "CN=%s,%s" % (self.uname,
                                                          self.ou)
            ad_attrs["homeDirectory"] = cereconf.AD_HOME_DIR_STUDENT % self.uname
            ad_attrs["profilePath"] = cereconf.AD_PROFILE_PATH_STUDENT % self.uname
            ad_attrs["telephoneNumber"] = self.contact_mobile_phone
        else:
            ad_attrs["mobile"] = self.contact_mobile_phone
            ad_attrs["description"] = self.title
            ad_attrs["telephoneNumber"] = self.contact_phone
            ad_attrs["cn"] = "%s %s" % (self.name_first, self.name_last)
            ad_attrs["distinguishedName"] = "CN=%s %s,%s" % (self.name_first,
                                                             self.name_last,
                                                             self.ou)
            ad_attrs["homeDirectory"] = cereconf.AD_HOME_DIR_ANSATT % self.uname
            ad_attrs["profilePath"] = cereconf.AD_PROFILE_PATH_ANSATT % self.uname

        if self.email_addrs:
            ad_attrs["mail"] = self.email_addrs[0]

        # Calculate Exchange attributes?
        if exchange:
            # Set exchange flag
            self.to_exchange = True
            # Set defaults
            for k in cereconf.AD_EXCHANGE_ATTRIBUTES:
                ad_attrs[k] = None
            ad_attrs.update(cereconf.AD_EXCHANGE_DEFAULTS)
            if self.is_student():
                ad_attrs.update(cereconf.AD_EXCHANGE_DEFAULTS_STUDENT)
            else:
                ad_attrs.update(cereconf.AD_EXCHANGE_DEFAULTS_ANSATT)                

            # Exchange attributes hardcoding
            ad_attrs["mailNickname"] = self.uname
            if self.is_student():                
                ad_attrs["homeMDB"] = cereconf.AD_HOMEMDB_STUDENT
            else:
                ad_attrs["homeMDB"] = cereconf.AD_HOMEMDB_ANSATT
                
            # set proxyAddresses attr
            if self.email_addrs:
                tmp = ["SMTP:" + self.email_addrs[0]]
                for alias_addr in self.email_addrs[1:]:
                    if alias_addr != ad_attrs["mail"]:
                        tmp.append(("smtp:" + alias_addr))
                ad_attrs["proxyAddresses"] = tmp

        # Convert str to unicode before comparing with AD
        for attr_type, attr_val in ad_attrs.iteritems():
            if type(attr_val) is str:
                ad_attrs[attr_type] = unicode(attr_val, cereconf.ENCODING)

        self.ad_attrs.update(ad_attrs)



class HIHUserSync(UserSync):

    # HIH wants to export mobile phones bothe for students and employees
    def fetch_contact_info(self):
        """
        Get contact info: phonenumber and title. Personal title takes precedence.
        """
        self.logger.debug("..fetch hih contact info..")
        pid2data = {}
        # Get phone number
        for row in self.pe.list_contact_info(source_system=(self.co.system_sap,
                                                            self.co.system_fs,
                                                            self.co.system_manual),
                                             entity_type=self.co.entity_person,
                                             contact_type=(self.co.contact_mobile_phone,
                                                           self.co.contact_phone)):
            # Omit phone numbers unless they were registered manually
            if (row["contact_type"] == self.co.contact_phone) and \
               (row["source_system"] != self.co.system_manual):
                continue
            # Omit mobile phone numbers unless they were registered manually or 
            # came from student information database
            if (row["contact_type"] == self.co.contact_mobile_phone) and \
               (row["source_system"] != self.co.system_manual) and \
               (row["source_system"] != self.co.system_fs):
                continue
            pid2data.setdefault(int(row["entity_id"]), {})[
                int(row["contact_type"])] = row["contact_value"]
        # Get title
        for row in self.pe.search_name_with_language(
                               entity_type=self.co.entity_person,
                               name_variant=(self.co.personal_title,
                                             self.co.work_title),
                               name_language=self.co.language_nb):
            pid2data.setdefault(int(row["entity_id"]), {})[
                int(row["name_variant"])] = row["name"]
        # set data
        for acc in self.accounts.itervalues():
            data = pid2data.get(acc.owner_id)
            if data:
                acc.contact_mobile_phone = data.get(int(self.co.contact_mobile_phone), "")
                acc.contact_phone = data.get(int(self.co.contact_phone), "")
                acc.title = (data.get(int(self.co.personal_title), "") or
                             data.get(int(self.co.work_title), ""))


    def fetch_ad_data(self):
        """
        Fetch all or a subset of users in search_ou from AD.
        
        @return: AD attributes and values for AD objects of type
                 'user' in search_ou and child ous of this ou.
        @rtype: dict (uname -> {attr type: value} mapping)
        """
        # Setting the user attributes to be fetched.
        self.server.setUserAttributes(self.sync_attrs,
                                      cereconf.AD_ACCOUNT_CONTROL)
        ret = self.server.listObjects("user", True, self.ad_ldap)
        if not ret:
            return
        # lowercase all keys
        retdict = dict()
        for k,v in ret.iteritems():
            retdict[k.lower()] = v
            
        if self.subset:
            tmp = dict()
            for u in self.subset:
                if u in retdict:
                    tmp[u] = retdict.get(u)
            retdict = tmp
        return retdict


    def cb_account(self, account_id, owner_id, uname):
        "wrapper func for easier subclassing"
        return HIHCerebrumUser(account_id, owner_id, uname, self.ad_domain,
                               self.get_default_ou())


    def get_default_ou(self):
        "Return default user ou"
        return "%s,%s" % (cereconf.AD_USER_OU, self.ad_ldap)

    def get_deleted_ou(self):
        "Return deleted ou"
        return "%s,%s" % (cereconf.AD_LOST_AND_FOUND, self.ad_ldap)
    


class HIHGroupSync(GroupSync):
    def get_default_ou(self):
        """
        Return default OU for groups.
        """
        return "%s,%s" % (cereconf.AD_GROUP_OU, self.ad_ldap)


class HIHCerebrumDistGroup(CerebrumDistGroup):
    """
    This class represent a virtual Cerebrum distribution group that
    contain contact objects.
    """
    def calc_ad_attrs(self):
        """
        Calculate AD attrs from Cerebrum data.
        
        How to calculate AD attr values from Cerebrum data and policy
        must be hardcoded somewhere. Do this here and try to leave the
        rest of the code general.
        """
        # Read which attrs to calculate from cereconf
        ad_attrs = dict().fromkeys(cereconf.AD_DIST_GRP_ATTRIBUTES, None)
        ad_attrs.update(cereconf.AD_DIST_GRP_DEFAULTS)
        
        # Do the hardcoding for this sync.
        ad_attrs["name"] = self.gname
        ad_attrs["displayName"] = cereconf.AD_DIST_GROUP_PREFIX + self.gname
        ad_attrs["description"] = self.description or "N/A"
        ad_attrs["displayNamePrintable"] = self.gname
        ad_attrs["distinguishedName"] = "CN=%s,%s" % (self.gname, self.ou)
        # TODO: spesifiser disse. Likt for stud og ans?
        #ad_attrs["mail"] = ""
        #ad_attrs["mailNickName"] = ""
        #ad_attrs["proxyAddresses"] = ""

        # Convert str to unicode before comparing with AD
        for attr_type, attr_val in ad_attrs.iteritems():
            if type(attr_val) is str:
                ad_attrs[attr_type] = unicode(attr_val, cereconf.ENCODING)
        
        self.ad_attrs.update(ad_attrs)


class HIHDistGroupSync(DistGroupSync):
    def cb_group(self, gname, group_id, description):
        "wrapper func for easier subclassing"
        return HIHCerebrumDistGroup(gname, group_id, description,
                                    self.ad_domain, self.get_default_ou())


    def get_default_ou(self):
        """
        Return default OU for groups.
        """
        return "%s,%s" % (cereconf.AD_GROUP_OU, self.ad_ldap)

