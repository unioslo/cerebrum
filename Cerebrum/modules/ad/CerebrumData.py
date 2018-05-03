#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2011-2018 University of Oslo, Norway
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
This module contains classes that represent Cerebrum data for easier
comparison with AD data.

The object types in AD which we alter in the synchronisation are user,
contact, security group, and distribution group. Data in Cerebrum are
organized in a different manner. Thus we have defined classes, which
represent Cerebrum data in a more AD friendly manner. Each class has a
calc_ad_attrs method that defines the attributes which are to be
compared with attributes from data objects from AD.

"""

import cereconf


class CerebrumEntity(object):
    """
    Represent a Cerebrum entity which may be exported to AD. This is a
    base class with common methods and attributes for users and
    groups.
    """
    def __init__(self, domain, ou):
        self.domain = domain
        self.ou = ou
        # Default state
        self.quarantined = False       # quarantined in Cerebrum?
        self.in_ad = False             # entity exists in AD?
        # TBD: Move these two to CerebrumUser?
        self.to_exchange = False       # entity has exchange spread?
        self.update_recipient = False  # run update_Recipients?
        # ad_attrs contains values calculated from cerebrum data
        self.ad_attrs = dict()
        # changes contains attributes that should be updated in AD
        self.changes = dict()


class CerebrumUser(CerebrumEntity):
    """
    Represent a Cerebrum Account which may be exported to AD,
    depending wether the account info in AD differs.

    An instance contains information from Cerebrum and methods for
    comparing this information with the data from AD.
    """

    def __init__(self, account_id, owner_id, uname, domain, ou):
        """
        CerebrumUser constructor

        @param account_id: Cerebrum id
        @type account_id: int
        @param owner_id: Cerebrum owner id
        @type owner_id: int
        @param uname: Cerebrum account name
        @type uname: str
        """
        super(CerebrumUser, self).__init__(domain, ou)
        self.account_id = account_id
        self.owner_id = owner_id
        self.uname = uname
        # default values
        self.email_addrs = list()
        self.contact_objects = list()
        self.name_last = ""
        self.name_first = ""
        self.title = ""
        self.contact_phone = ""

    def __str__(self):
        return "%s (%s)" % (self.uname, self.account_id)

    def __repr__(self):
        return "Account: %s (%s, %s)" % (self.uname, self.account_id,
                                         self.owner_id)

    def calc_ad_attrs(self, exchange=False):
        """
        Calculate AD attrs from Cerebrum data.

        How to calculate AD attr values from Cerebrum data and policy
        must be hardcoded somewhere. Do this here and try to leave the
        rest of the code general.

        @param config_attrs: attributes that are given from cereconf
                             or command line arguments.
        @type config_attrs: dict
        """
        # Read which attrs to calculate from cereconf
        ad_attrs = dict().fromkeys(cereconf.AD_ATTRIBUTES, None)
        # Set predefined default values
        ad_attrs.update(cereconf.AD_ACCOUNT_CONTROL)
        ad_attrs.update(cereconf.AD_DEFAULTS)

        # Do the hardcoding for this sync.
        # Name and case of attributes should be as they are in AD

        ad_attrs.update({
            "sAMAccountName": self.uname,
            "sn": self.name_last,
            "givenName": self.name_first,
            "displayName": "%s %s" % (self.name_first, self.name_last),
            "distinguishedName": "CN=%s,%s" % (self.uname, self.ou),
            "ACCOUNTDISABLE": self.quarantined,
            "userPrincipalName": "%s@%s" % (self.uname, self.domain),
            "title": self.title,
            "telephoneNumber": self.contact_phone,
        })

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

        self.ad_attrs.update(ad_attrs)

    def add_forward(self, forward_addr):
        contact = CerebrumContact(self.ad_attrs["displayName"], forward_addr,
                                  self.domain, )
        self.contact_objects.append(contact)

    def create_dist_group(self):
        name = getattr(cereconf, "AD_FORWARD_GROUP_PREFIX", "") + self.uname
        # TBD: cereconf?
        description = "Forward group for " + self.uname
        dg = CerebrumDistGroup(name, description)
        dg.calc_ad_attrs()

    def add_change(self, attr_type, value):
        """
        Add attribute type and value that is to be synced to AD. Some
        attributes changes must be sent to Exchange also. If that is
        the case set update_recipient to True

        @param attr_type: AD attribute type
        @type attr_type: str
        @param value: AD attribute value
        @type value: varies
        """
        self.changes[attr_type] = value
        # Should update_Recipients be run for this account?
        if (not self.update_recipient and
                attr_type in cereconf.AD_EXCHANGE_ATTRIBUTES):
            self.update_recipient = True


class CerebrumContact(CerebrumEntity):
    """
    This class contains forward info for a Cerebrum account.

    """

    def __init__(self, name, forward_addr, domain, ou):
        """
        CerebrumContact constructor

        @param name: Owners name
        @type name: str
        @param forward_addr: forward address
        @type forward_addr: str
        """
        super(CerebrumContact, self).__init__(domain, ou)
        # forward_attrs contains values calculated from cerebrum data
        self.forward_attrs = dict()
        self.name = name
        self.forward_addr = forward_addr

    def __str__(self):
        return self.name

    def calc_forward_attrs(self):
        """
        Calculate forward attributes for the accounts with forward
        email addresses.
        """
        self.forward_attrs.update({
            "name": "Contact for " + self.name,
            "displayName": "Contact for " + self.name,
            "mail": self.forward_addr,
            "mailNickname": self.forward_addr,
            "sAMAccountName": "contact_for_" + self.forward_addr,
            "proxyAddresses": self.forward_addr,
            "msExchPoliciesExcluded": True,
            "msExchHideFromAddressLists": True,
            "targetAddress": self.forward_addr,
        })

    def add_change(self, attr_type, value):
        """
        Add attribute type and value that is to be synced to AD. Some
        attributes changes must be sent to Exchange also. If that is
        the case set update_recipient to True

        @param attr_type: AD attribute type
        @type attr_type: str
        @param value: AD attribute value
        @type value: varies
        """
        self.changes[attr_type] = value


class CerebrumGroup(CerebrumEntity):
    """
    Represent a Cerebrum group which may be exported to AD, depending
    wether the account info in AD differs.

    An instance contains information from Cerebrum and methods for
    comparing this information with the data from AD.
    """

    def __init__(self, gname, group_id, description, domain, ou):
        """
        CerebrumGroup constructor

        @param name: Cerebrum group name
        @type name: str
        @param group_id: Cerebrum id
        @type group_id: int
        @param description: Group description
        @type description: str
        """
        super(CerebrumGroup, self).__init__(domain, ou)
        self.gname = gname
        self.description = description
        self.group_id = group_id
        # CN part of distinguishedName and sAMAccountName might
        # differ. We need to know both
        self.ad_dn = None

    def calc_ad_attrs(self):
        """
        Calculate AD attrs from Cerebrum data.

        How to calculate AD attr values from Cerebrum data and policy
        must be hardcoded somewhere. Do this here and try to leave the
        rest of the code general.
        """
        # Read which attrs to calculate from cereconf
        ad_attrs = dict().fromkeys(cereconf.AD_GRP_ATTRIBUTES, None)
        ad_attrs.update(cereconf.AD_GRP_DEFAULTS)

        # Do the hardcoding for this sync.
        ad_attrs.update({
            "displayName": self.gname,
            "displayNamePrintable": self.gname,
            "name": cereconf.AD_GROUP_PREFIX + self.gname,
            "distinguishedName": "CN=%s,%s" % (ad_attrs["name"], self.ou),
            "description": self.description or "N/A",
        })

        self.ad_attrs.update(ad_attrs)

    def add_change(self, attr_type, value):
        """
        The attributes stored in self.changes will be synced to AD.

        @param attr_type: AD attribute type
        @type attr_type: str
        @param value: AD attribute value
        @type value: varies
        """
        self.changes[attr_type] = value


class CerebrumDistGroup(CerebrumGroup):
    """
    This class represent a virtual Cerebrum distribution group that
    contain contact objects.
    """

    def __init__(self, gname, group_id, description, domain, ou):
        """
        CerebrumDistGroup constructor

        @param name: Cerebrum group name
        @type name: str
        @param group_id: Cerebrum id
        @type group_id: int
        @param description: Group description
        @type description: str
        """
        super(CerebrumDistGroup, self).__init__(gname, group_id, description,
                                                domain, ou)
        # Dist groups should be exposed to Exchange
        self.to_exchange = True

    def add_change(self, attr_type, value):
        """
        Add attribute type and value that is to be synced to AD. Some
        attributes changes must be sent to Exchange also. If that is
        the case set update_recipient to True

        @param attr_type: AD attribute type
        @type attr_type: str
        @param value: AD attribute value
        @type value: varies
        """
        self.changes[attr_type] = value
        # Should update_Recipients be run for this dist group?
        if (not self.update_recipient and
                attr_type in cereconf.AD_DIST_GRP_UPDATE_EX):
            self.update_recipient = True

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
        ad_attrs.update({
            "name": self.gname,
            "displayName": cereconf.AD_DIST_GROUP_PREFIX + self.gname,
            "description": self.description or "N/A",
            "displayNamePrintable": ad_attrs["displayName"],
            "distinguishedName": "CN=%s,%s" % (self.gname, self.ou),
        })
        # TODO: add mail and proxyAddresses, etc

        self.ad_attrs.update(ad_attrs)
