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


TODO:

* homedir mapping:

Hjemmeområder:

Administrativt ansatte ( AFD,EA, Informasjonsavdelingen,STA, PØ, Rektoratet)
\\nihsrvv10-6\ADM_ans
<file:///\\nihsrvv10-6\ADM_ans>
( J:\Brukere\ADM_ansatte)

\\nihsrvv20-6\FAG_ans ( Fagligt ansatte- untatt SIM og FI dvs. SCP, SFP, SKP, SKS))
<file:///\\nihsrvv20-6\FAG_ans>
G:\brukere\ansatt

SIM-selsjonen:
\\nihsrvv20-6\SIM-ans
<file:///\\nihsrvv20-6\SIM-ans>
E:\brukere\ansatt

Forsvarets institutt ( FI)
\\nihsrvv20-6\FI-brukere
<file:///\\nihsrvv20-6\FI-brukere>
J:\FI\FI_brukere


"""


import cerebrum_path
import cereconf

from Cerebrum.modules.ad.CerebrumData import CerebrumUser
from Cerebrum.modules.ad.ADSync import ADUserSync, ADGroupSync

class CerebrumUser(CerebrumUser):
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
        ad_attrs["sn"] = self.name_last
        ad_attrs["givenName"] = self.name_first
        ad_attrs["displayName"] = "%s %s" % (self.name_first, self.name_last)
        ad_attrs["distinguishedName"] = "CN=%s,%s" % (self.uname,
                                                      self.ou)
        ad_attrs["ou"] = self.ou
        ad_attrs["ACCOUNTDISABLE"] = self.quarantined
        ad_attrs["userPrincipalName"] = "%s@%s" % (self.uname, self.domain) 
        ad_attrs["title"] = self.title

        # Need to calculate homedir from affiliation 
        ad_attrs["homeDirectory"] = self.calc_homedir()
        ad_attrs["homeDrive"] = self.calc_homedrive()

        #ad_attrs["mail"] = ""
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
            
            # Do the hardcoding for this sync. 
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
    

    def calc_homedir(self):
        """Calculate homedir based on account type (affiliation)"""

        sko = "001122"  # TODO: get sko
        return "%s\%s" % (sko, self.uname)
        
    def calc_homedrive(self):
        return "J:"


class ADUserSync(ADUserSync):
    def cb_account(self, account_id, owner_id, uname):
        "wrapper func for easier subclassing"
        return CerebrumUser(account_id, owner_id, uname, self.ad_domain,
                            self.get_default_ou())


    def fetch_cerebrum_data(self):
        # Run superclass' fetch_cerebrum_data
        super(ADUserSync, self).fetch_cerebrum_data()
        # In addition, fetch account types
        aid2aff = {} # account_id -> priority to aff mapping
        for row in self.ac.list_accounts_by_type(
            account_spread=self.co.Spread(self.user_spread),
            affiliation=self.co.affiliation_ansatt):
            aid2aff.setdefault(int(row['person_id']), {})[
                int(row['priority'])] = row['affiliation']


    def fetch_ad_data_contacts(self):
        """
        Returns full LDAP path to AD objects of type 'contact' and prefix
        indicating it is used for forwarding.

        @rtype: dict
        @return: a dict of dict wich maps contact obects name to
                 objects properties (dict)
        """
        self.server.setContactAttributes(cereconf.AD_CONTACT_FORWARD_ATTRIBUTES)
        search_ou = self.ad_ldap
        ad_contacts = self.server.listObjects('contact', True, search_ou)
        if not ad_contacts:
            return {}
        # Only deal with forwarding contact objects. 
        for object_name, value in ad_contacts.items():
            if not object_name.startswith("contact_for_"):
                del ad_contacts[object_name]
        return ad_contacts


class ADGroupSync(ADGroupSync):
    pass

