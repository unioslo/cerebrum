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


class HIHCerebrumUser(CerebrumUser):
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
        
        # Do the hardcoding for this sync.
        # Name and case of attributes should be as they are in AD
        ad_attrs["sAMAccountName"] = self.uname
        ad_attrs["cn"] = self.uname
        ad_attrs["sn"] = self.name_last
        ad_attrs["givenName"] = self.name_first
        ad_attrs["displayName"] = "%s %s" % (self.name_first, self.name_last)
        ad_attrs["distinguishedName"] = "CN=%s %s,%s" % (self.name_first,
                                                         self.name_last,
                                                         self.ou)
        ad_attrs["ACCOUNTDISABLE"] = self.quarantined
        ad_attrs["userPrincipalName"] = "%s@%s" % (self.uname, self.domain) 
        ad_attrs["title"] = self.title
        # TODO: finn en bedre måte å gjøre dette på
        ad_attrs["homeDirectory"] = cereconf.AD_HOME_DIR_ANSATT % self.uname
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
            #ad_attrs["homeMDB"] = self.exchange_homemdb
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



class HIHUserSync(UserSync):
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
    pass


class HIHDistGroupSync(DistGroupSync):
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

        # createObject succeded, return sid
        return sid



