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
from Cerebrum.modules.ad.ADSync import UserSync
from Cerebrum.modules.ad.ADSync import GroupSync
from Cerebrum.modules.ad.ADSync import DistGroupSync


class NIHCerebrumUser(CerebrumUser):
    def __init__(self, account_id, owner_id, uname, domain, ou):
        """NIHCerebrumUser constructor"""
        CerebrumUser.__init__(self, account_id, owner_id, uname, domain, ou)
        self.aff_status = None
        self.exchange_homemdb = None
        

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
        
        # Do the hardcoding for this sync.
        # Name and case of attributes should be as they are in AD
        ad_attrs["sAMAccountName"] = self.uname
        ad_attrs["cn"] = self.uname
        ad_attrs["sn"] = self.name_last
        ad_attrs["givenName"] = self.name_first
        ad_attrs["displayName"] = "%s %s" % (self.name_first, self.name_last)
        ad_attrs["distinguishedName"] = "CN=%s,%s" % (self.uname, self.ou)
        ad_attrs["ACCOUNTDISABLE"] = self.quarantined
        ad_attrs["userPrincipalName"] = "%s@%s" % (self.uname, self.domain) 
        ad_attrs["title"] = self.title
        # Need to calculate homedir and homedrive affiliation
        homedir = self.calc_homedir()
        if homedir:
            ad_attrs["homeDirectory"] = homedir
        homedrive = self.calc_homedrive()
        if homedrive:
            ad_attrs["homeDrive"] = homedrive
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

            # Exchange attributes hardcoding
            ad_attrs['msExchHomeServerName'] = cereconf.AD_EX_HOME_SERVER
            ad_attrs["homeMDB"] = self.exchange_homemdb
            ad_attrs["mailNickname"] = self.uname
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

    
    def set_aff_status(self, aff_status):
        self.aff_status = aff_status
        

    def calc_homedir(self):
        """Calculate homedir based on affiliation status"""
        if not self.aff_status:
            return None
        if self.aff_status.startswith("STUDENT"):
            ret = cereconf.AFF_STATUS2AD_HOMEDIR.get("STUDENT")
            return ret % self.uname
        else:
            return cereconf.AFF_STATUS2AD_HOMEDIR.get(self.aff_status, "")

        
    def calc_homedrive(self):
        """Calculate homedrive based on affiliation status"""
        if not self.aff_status:
            return None
        if self.aff_status.startswith("STUDENT"):
            return cereconf.AFF_STATUS2AD_HOMEDRIVE.get("STUDENT")
        else:
            return cereconf.AFF_STATUS2AD_HOMEDRIVE.get(self.aff_status, "")


class NIHUserSync(UserSync):
    def cb_account(self, account_id, owner_id, uname):
        "wrapper func for easier subclassing"
        return NIHCerebrumUser(account_id, owner_id, uname, self.ad_domain,
                               self.get_default_ou())


    def fetch_cerebrum_data(self):
        # Run superclass' fetch_cerebrum_data
        super(NIHUserSync, self).fetch_cerebrum_data()

        # In addition, fetch account types and person affiliation
        # status. Used to define homedir and homedrive 
        self.logger.debug("..fetch affiliation status..")
        aid2aff = {} # account_id -> priority to aff mapping
        for row in self.ac.list_accounts_by_type(
            account_spread=self.co.Spread(self.user_spread)):
            aid2aff.setdefault(int(row['account_id']), {})[
                int(row['priority'])] = int(row['affiliation'])

        pid2affstatus = {}
        for row in self.pe.list_affiliations():
            pid2affstatus.setdefault(int(row['person_id']), {})[
                int(row['affiliation'])] = str(row['status'])
            
        # Set the highest prioritized affiliation status for each
        # CerebrumUser
        for a in self.accounts.itervalues():
            priority2aff = aid2aff.get(a.account_id)
            if not priority2aff:
                continue
            # Get aff with highest priority (lowest priority value)
            aff = priority2aff.get(min(priority2aff.keys()))
            aff2status = pid2affstatus.get(a.owner_id)
            if not aff2status:
                continue
            try:
                a.set_aff_status(str(self.co.PersonAffStatus(
                    aff2status.get(aff))))
            except TypeError:
                self.logger.warning("Couldn't set aff status for %s" % a.uname)

        # Find homeMDB stored as traits
        if self.exchange_sync:
            self.logger.debug("..fetch homemdb traits..")
            for row in self.ac.list_traits(code=self.co.trait_exchange_mdb):
                uname = self.id2uname.get(int(row["entity_id"]))
                if not uname:
                    continue
                self.accounts[uname].exchange_homemdb = "CN=%s,%s" % (
                    row["strval"], cereconf.AD_EX_HOME_MDB)
        

    def fetch_ad_data_contacts(self):
        """
        Returns full LDAP path to AD objects of type 'contact' and prefix
        indicating it is used for forwarding.

        @rtype: dict
        @return: a dict of dict wich maps contact obects name to
                 objects properties (dict)
        """
        self.server.setContactAttributes(cereconf.AD_CONTACT_FORWARD_ATTRIBUTES)
        ad_contacts = self.server.listObjects('contact', True, cereconf.AD_LDAP)
        if not ad_contacts:
            return {}
        # Only deal with forwarding contact objects. 
        for object_name, value in ad_contacts.items():
            if not object_name.startswith("contact_for_"):
                del ad_contacts[object_name]
        return ad_contacts


class NIHGroupSync(GroupSync):
    pass


class NIHDistGroupSync(DistGroupSync):
    # Override ADUtils.ADGroupUtils.create_ad_group
    def create_ad_group(self, attrs, ou):
        """
        Create AD group.

        @param attrs: AD attrs to be set for the account
        @type attrs: dict        
        @param ou: LDAP path to base ou for the entity type
        @type ou: str        
        """
        gname = attrs.pop("name")
        if self.dryrun:
            self.logger.debug("DRYRUN: Not creating group %s" % gname)
            return

        # Create group object
        sid = self.run_cmd("createObject", "Group", ou, gname)
        if not sid:
            # Don't continue if createObject fails
            return
        self.logger.info("created group %s with sid %s", gname, sid)
        # # Set other properties
        dn = attrs.pop("distinguishedName")
        self.run_cmd("putGroupProperties", attrs)
        self.run_cmd("setObject")
        # Since NIH uses '+' as perfix for dist groups we need to do a
        # more complicated create group method. We can't send a name
        # with + directly. Instead we create the group, and then
        # rename it
        self.rename_object(dn, ou, "CN=\+%s" % gname)

        # createObject succeded, return sid
        return sid



