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
Module with functions for Cerebrum export to Active Directory at HiH.

TODO:

* Distibution groups. What to do with them? They are just groups with
  different spreads that have some attributes that exchange like to
  know about.

  TBD: make subclass of CerebrumGroup and ADGroupSync to deal with this?

* Does it make any sense to export security groups to Exhange?

* La all tekst være unicode før sammenligning. Fetch_ad_data og
  fetch_cerebrum_data må fikse dette.

* fetch_email_info må skrives ferdig. homeMDB

* Group-sync...

* maillist-sync...

"""


import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hih.ADUtils import ADUserUtils, ADGroupUtils
from Cerebrum import Errors


class CerebrumEntity(object):
    """
    Represent a Cerebrum entity which may be exported to AD. This is a
    base class with common methods and attributes for users and
    groups.
    """
    @classmethod
    def initialize(cls, ou, domain):
        """
        OU and domain are the same for all instances. Thus set as
        class variables.

        @param ou: LDAP path to base ou for the entity type
        @type ou: str
        @param domain: AD domain
        @type domain: str    
        """
        cls.default_ou = ou
        cls.domain = domain


    def __init__(self):
        # Default state
        self.quarantined = False      # quarantined in Cerebrum?
        self.in_ad = False            # entity exists in AD?
        # TBD: Move these two to CerebrumAccount?
        self.to_exchange = False      # entity has exchange spread?
        self.update_recipient = False # run update_Recipients?
        # ad_attrs contains values calculated from cerebrum data
        self.ad_attrs = dict()
        # changes contains attributes that should be updated in AD
        self.changes = dict()


class CerebrumAccount(CerebrumEntity):
    """
    Represent a Cerebrum Account which may be exported to AD,
    depending wether the account info in AD differs.

    An instance contains information from Cerebrum and methods for
    comparing this information with the data from AD.
    """

    def __init__(self, account_id, owner_id, uname):
        """
        CerebrumAccount constructor
        
        @param account_id: Cerebrum id
        @type account_id: int
        @param owner_id: Cerebrum owner id
        @type owner_id: int
        @param uname: Cerebrum account name
        @type uname: str
        """
        CerebrumEntity.__init__(self)
        self.account_id = account_id
        self.owner_id = owner_id
        self.uname = uname
        # default values
        self.email = list()
        self.name_last = ""
        self.name_first = ""
        self.title = ""
        self.contact_phone = ""

    def __str__(self):
        return "%s (%s)" % (self.uname, self.account_id)


    def __repr__(self):
        return "Account: %s (%s, %s)" % (self.uname, self.account_id,
                                         self.owner_id)


    def calc_ad_attrs(self, config_attrs):
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
        # Update with with the given attrs from config_attrs
        ad_attrs.update(config_attrs)
        
        # Do the hardcoding for this sync.
        # Name and case of should be how they appear in AD
        ad_attrs["sAMAccountName"] = self.uname
        ad_attrs["sn"] = self.name_last
        ad_attrs["givenName"] = self.name_first
        # Cn is a RDN attribute and must be changed similar like OU
        ad_attrs["Cn"] = self.name_first
        ad_attrs["displayName"] = "%s %s" % (self.name_first, self.name_last)
        ad_attrs["distinguishedName"] = "CN=%s,%s" % (self.uname, self.default_ou)
        ad_attrs["ou"] = self.default_ou
        ad_attrs["ACCOUNTDISABLE"] = self.quarantined
        ad_attrs["homeDirectory"] %= self.uname 
        ad_attrs["Profile path"] %= self.uname 
        ad_attrs["userPrincipalName"] = "%s@%s" % (self.uname, self.domain) 
        ad_attrs["title"] = self.title
        ad_attrs["telephoneNumber"] = self.contact_phone
        ad_attrs["mail"] = ""
        if self.email:
            ad_attrs["mail"] = self.email[0]

        # Convert str to unicode before comparing with AD
        for attr_type, attr_val in ad_attrs.iteritems():
            if type(attr_val) is str:
                ad_attrs[attr_type] = unicode(attr_val, cereconf.ENCODING)

        self.ad_attrs.update(ad_attrs)


    def calc_exchange_attrs(self):
        """
        Calculate AD Exchange attrs from Cerebrum data.
        
        How to calculate Exchange attributes from Cerebrum data and
        policy must be hardcoded somewhere. Do this here and try to
        leave the rest of the code general.
        """        
        # Set exchange flag
        self.to_exchange = True
        # Set defaults
        for k in cereconf.AD_EX_ATTRIBUTES:
            self.ad_attrs[k] = None
        self.ad_attrs.update(cereconf.AD_EX_DEFAULTS)

        # Do the hardcoding for this sync. 
        self.ad_attrs["mailNickname"] = self.uname
        # set proxyAddresses attr
        if self.email:
            tmp = ["SMTP:" + self.email[0]]
            for alias_addr in self.email[1:]:
                if alias_addr != self.ad_attrs["mail"]:
                    tmp.append(("smtp:" + alias_addr))
            self.ad_attrs["proxyAddresses"] = tmp
    
    
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
        if not self.update_recipient and attr_type in cereconf.AD_EX_ATTRIBUTES:
            self.update_recipient = True


class CerebrumGroup(CerebrumEntity):
    """
    Represent a Cerebrum group which may be exported to AD, depending
    wether the account info in AD differs.

    An instance contains information from Cerebrum and methods for
    comparing this information with the data from AD.
    """

    def __init__(self, name, group_id, description):
        """
        CerebrumGroup constructor
        
        @param name: Cerebrum group name
        @type name: str
        @param group_id: Cerebrum id
        @type group_id: int
        @param description: Group description
        @type description: str
        """
        CerebrumEntity.__init__(self)
        self.name = name
        self.group_id = group_id
        self.description = description


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
        ad_attrs["displayName"] = self.name
        ad_attrs["displayNamePrintable"] = self.name
        ad_attrs["group_id"] = self.group_id
        ad_attrs["name"] = cereconf.AD_GROUP_PREFIX + self.name
        ad_attrs["distinguishedName"] = "CN=%s,%s" % (ad_attrs["name"],
                                                      self.default_ou)
        ad_attrs["description"] = self.description or "Not available"
        ad_attrs["OU"] = self.default_ou

        # Exchange
        # if self.to_exchange:
        #     ad_attrs["proxyAddresses"] = ["SMTP:" + self.name + "@" +
        #                                   self.domain]
        #     ad_attrs["mailNickname"] = self.name
        #     ad_attrs["mail"] = self.name + "@" + self.domain

        # Convert str to unicode before comparing with AD
        for attr_type, attr_val in ad_attrs.iteritems():
            if type(attr_val) is str:
                ad_attrs[attr_type] = unicode(attr_val, cereconf.ENCODING)
        
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


class ADUserSync(ADUserUtils):
    def __init__(self, db, logger, host, port, ad_domain_admin):
        """
        Connect to AD agent on host:port and initialize user sync.

        @param db: Connection to Cerebrum database
        @type db: Cerebrum.CLDatabase.CLDatabase
        @param logger: Cerebrum logger
        @type logger: Cerebrum.modules.cerelog.CerebrumLogger
        @param host: Server where AD agent runs
        @type host: str
        @param port: port number
        @type port: int
        @param ad_domain_admin: The user we connect to the AD agent as
        @type ad_domain_admin: str
        """

        ADUserUtils.__init__(self, logger, host, port, ad_domain_admin)
        self.db = db
        self.co = Factory.get("Constants")(self.db)
        self.ac = Factory.get("Account")(self.db)
        self.pe = Factory.get("Person")(self.db)
        self.accounts = dict()
        self.id2uname = dict()


    def configure(self, config_args):
        """
        Read configuration options from args and cereconf to decide
        which data to sync.

        @param config_args: Configuration data from cereconf and/or
                            command line options.
        @type config_args: dict
        """
        self.logger.info("Starting user-sync")
        # Sync settings for this module
        for k in ("user_spread", "user_exchange_spread",
                  "exchange_sync", "delete_users", "dryrun",
                  "ad_ldap", "store_sid"):
            if k in config_args:
                setattr(self, k, config_args.pop(k))
        
        # Set which attrs that are to be compared with AD
        self.sync_attrs = cereconf.AD_ATTRIBUTES
        if self.exchange_sync:
            self.sync_attrs += cereconf.AD_EX_ATTRIBUTES

        # The rest of the config args goes to the CerebrumAccount
        # class and instances
        CerebrumAccount.initialize(self.get_default_ou(),
                                   config_args.pop("ad_domain"))
        self.config_args = config_args
        self.logger.info("Configuration done. Will compare attributes: %s" %
                         ", ".join(self.sync_attrs))
        

    def fullsync(self):
        """
        This method defines what will be done in the sync.
        """
        # Fetch AD-data for users.     
        self.logger.debug("Fetching AD user data...")
        addump = self.fetch_ad_data(self.ad_ldap)
        self.logger.info("Fetched %i AD users" % len(addump))

        # Fetch cerebrum data. store in self.accounts
        self.logger.debug("Fetching cerebrum user data...")
        self.fetch_cerebrum_data()

        # Compare AD data with Cerebrum data
        for uname, ad_user in addump.iteritems():
            if uname in self.accounts:
                self.accounts[uname].in_ad = True
                self.compare(ad_user, self.accounts[uname])
            else:
                dn = ad_user["distinguishedName"]
                self.logger.debug("User %s in AD, but not in Cerebrum" % dn)
                # User in AD, but not in Cerebrum:
                # If user is in Cerebrum OU then deactivate
                if dn.upper().endswith(self.ad_ldap.upper()):
                    self.deactivate_user(ad_user)

        # Users exist in Cerebrum and has ad spread, but not in AD.
        # Create user if it's not quarantined
        for acc in self.accounts.itervalues():
            if acc.in_ad is False and acc.quarantined is False:
                self.create_ad_account(acc.ad_attrs, self.get_default_ou())

        #updating Exchange
        if self.exchange_sync:
            #self.logger.debug("Sleeping for 5 seconds to give ad-ldap time to update") 
            #time.sleep(5)
            for acc in self.accounts.itervalues():
                if acc.update_recipient:
                    self.update_Exchange(acc.uname)
        
        self.logger.info("User-sync finished")


    def fetch_cerebrum_data(self):
        """
        Fetch users, name and email information for all users with the
        given spread. Create CerebrumAccount instances and store in
        self.accounts.
        """
        # Find all users with relevant spread
        for row in self.ac.search(spread=self.user_spread):
            uname = row["name"].strip()
            self.accounts[uname] = CerebrumAccount(int(row["account_id"]),
                                                   int(row["owner_id"]),
                                                   uname)
            # We need to map account_id -> CerebrumAccount as well 
            self.id2uname[int(row["account_id"])] = uname
        self.logger.info("Fetched %i cerebrum users with spread %s" % (
            len(self.accounts), self.user_spread))

        # Remove/mark quarantined users
        self.filter_quarantines()
        self.logger.info("Found %i quarantined users" % len(
            [1 for v in self.accounts.itervalues() if v.quarantined]))

        # fetch names
        self.logger.debug("..fetch name information..")
        self.fetch_names()
        
        # fetch contact info: phonenumber and title
        self.logger.debug("..fetch contact info..")
        self.fetch_contact_info()

        # fetch email info
        self.logger.debug("..fetch email info..")
        self.fetch_email_info()
        
        # Finally, calculate attribute values based on Cerebrum data
        # for comparison with AD
        for acc in self.accounts.itervalues():
            acc.calc_ad_attrs(self.config_args)

        # Fetch exchange data and calculate attributes
        if self.exchange_sync:
            for row in self.ac.search(spread=self.user_exchange_spread):
                uname = self.id2uname.get(int(row["account_id"]))
                if uname:
                    self.accounts[uname].calc_exchange_attrs()
            self.logger.info("Fetched %i cerebrum users with spreads %s and %s" % (
                len([1 for acc in self.accounts.itervalues() if acc.to_exchange]),
                self.user_spread, self.user_exchange_spread))
    

    def filter_quarantines(self):
        """
        Mark quarantined accounts for disabling/deletion.
        """
        quarantined_accounts = [int(row["entity_id"]) for row in
                                self.ac.list_entity_quarantines(only_active=True)]
        # Set quarantine flag
        for a_id in set(self.id2uname) & set(quarantined_accounts):
            self.logger.debug("Quarantine flag is set for %s" %
                              self.accounts[self.id2uname[a_id]])
            self.accounts[self.id2uname[a_id]].quarantined = True


    def fetch_names(self):
        """
        Fetch names for all persons
        """
        pid2names = {}
        # getdict_persons_names might be faster
        for row in self.pe.list_persons_name(
            source_system = self.co.system_cached,
            name_type     = [self.co.name_first,
                             self.co.name_last]):
            pid2names.setdefault(int(row["person_id"]), {})[
                int(row["name_variant"])] = row["name"]
        # Set names
        for acc in self.accounts.itervalues():
            names = pid2names.get(acc.owner_id)
            if names:
                acc.name_first = names.get(int(self.co.name_first), "")
                acc.name_last = names.get(int(self.co.name_last), "")
            else:
                self.logger.warn("No name information for user " + acc.uname)
        

    def fetch_contact_info(self):
        """
        Get contact info: phonenumber and title. Personal title takes precedence.
        """
        pid2data = {}
        # Get phone number
        for row in self.pe.list_contact_info(source_system=self.co.system_sap,
                                             entity_type=self.co.entity_person,
                                             contact_type=self.co.contact_phone):
            pid2data.setdefault(int(row["entity_id"]), {})[
                int(row["contact_type"])] = row["contact_value"]
        # Get title
        for row in self.pe.list_persons_name(
            source_system = self.co.system_sap,
            name_type     = [self.co.name_personal_title,
                             self.co.name_work_title]):
            pid2data.setdefault(int(row["person_id"]), {})[
                int(row["name_variant"])] = row["name"]
        # set data
        for acc in self.accounts.itervalues():
            data = pid2data.get(acc.owner_id)
            if data:
                acc.contact_phone = data.get(int(self.co.contact_phone), "")
                acc.title = (data.get(int(self.co.name_personal_title), "") or
                             data.get(int(self.co.name_work_title), ""))
                

    def fetch_email_info(self):
        """
        Get primary email addresses from Cerebrum. If syncing to
        Exchange also get additional email info.
        """
        # Find primary addresses
        for uname, prim_mail in self.ac.getdict_uname2mailaddr(
            filter_expired=True, primary_only=True).iteritems():
            acc = self.accounts.get(uname, None)
            if acc:
                acc.primary_mail = prim_mail

        # Only get more email info if exchange sync is on
        if not self.exchange_sync:
            return

        #Find all valid addresses
        for uname, all_mail in self.ac.getdict_uname2mailaddr(
            filter_expired=True, primary_only=False).iteritems():
            acc = self.accounts.get(uname)
            if acc:
                acc.mail_addresses = all_mail

        # TODO: homeMDB, mangler spesifikasjon

        # Get quota info
        # TBD: Should we check if quota attrs are in
        # cereconf.AD_EX_ATTRIBUTES before doing this?
        from Cerebrum.modules.Email import EmailQuota
        equota = EmailQuota(self.db)

        # TBD: Can vi avvoid the equota.clear() ... equota.find() loop?
        for acc in self.accounts.itervalues():
            if not acc.to_exchange:
                continue
            # set quota attrs
            equota.clear()
            try:
                equota.find_by_target_entity(acc.account_id)
                acc.quota_soft = equota.get_quota_soft()
                acc.quota_hard = equota.get_quota_hard()
            except Errors.NotFoundError:
                self.logger.warning("Error finding EmailQuota for "
                                    "account %s. Setting default." % acc.uname)


    def fetch_ad_data(self, search_ou):
        """
        Returns full LDAP path to AD objects of type 'user' in search_ou and 
        child ous of this ou.
        
        @param search_ou: LDAP path to base ou for search
        @type search_ou: str
        """
        # Setting the user attributes to be fetched.
        self.server.setUserAttributes(self.sync_attrs,
                                      cereconf.AD_ACCOUNT_CONTROL)
        return self.server.listObjects("user", True, search_ou)


    def compare(self, ad_user, cb_user):
        """
        Compare Cerebrum user with the AD attributes listed in
        self.sync_attrs and decide if AD should be updated or not.

        @param ad_user: attributes for a user fetched from AD
        @type ad_user: dict 
        @param cb_user: CerebrumAccount instance
        @type cb_user: CerebrumAccount
        """
        cb_attrs = cb_user.ad_attrs
        # First check if user is quarantined. If so, disable
        if cb_attrs["ACCOUNTDISABLE"] and not ad_user["ACCOUNTDISABLE"]:
            self.disable_user(ad_user["distinguishedName"])
        
        # Check if user has correct OU. If not, move user
        if ad_user["distinguishedName"] != cb_attrs["distinguishedName"]:
            self.move_user(ad_user["distinguishedName"], cb_attrs["ou"])
            
        # Sync attributes
        for attr in self.sync_attrs:
            # Now, compare values from AD and Cerebrum
            cb_attr = cb_attrs.get(attr)
            ad_attr   = ad_user.get(attr)
            if cb_attr and ad_attr:
                # value both in ad and cerebrum => compare
                result = self.attr_cmp(cb_attr, ad_attr)
                if result: 
                    self.logger.debug("Changing attr %s from %s to %s",
                                      attr, ad_attr, cb_attr)
                    cb_user.add_change(attr, result)
            elif cb_attr:
                # attribute is not in AD and cerebrum value is set => update AD
                cb_user.add_change(attr, cb_attr)
            elif ad_attr:
                # value only in ad => delete value in ad
                cb_user.add_change(attr,"")

        # Special AD control attributes
        for attr, value in cereconf.AD_ACCOUNT_CONTROL.iteritems():
            if attr not in ad_user or ad_user[attr] != value:
                cb_user.add_change(attr, value)
                
        # Commit changes
        if cb_user.changes:
            self.commit_changes(ad_user["distinguishedName"], **cb_user.changes)


    def get_default_ou(self):
        "Return default user ou"
        return "%s,%s" % (cereconf.AD_USER_OU, self.ad_ldap)
    


class ADGroupSync(ADGroupUtils):
    def __init__(self, db, logger, host, port, ad_domain_admin):
        """
        Connect to AD agent on host:port and initialize group sync.

        @param db: Connection to Cerebrum database
        @type db: Cerebrum.CLDatabase.CLDatabase
        @param logger: Cerebrum logger
        @type logger: Cerebrum.modules.cerelog.CerebrumLogger
        @param host: Server where AD agent runs
        @type host: str
        @param port: port number
        @type port: int
        @param ad_domain_admin: The user we connect to the AD agent as
        @type ad_domain_admin: str
        """
        ADGroupUtils.__init__(self, logger, host, port, ad_domain_admin)
        self.db = db
        self.co = Factory.get("Constants")(self.db)
        self.group = Factory.get("Group")(self.db)
        self.groups = dict()
        

    def configure(self, config_args):
        """
        Read configuration options from args and cereconf to decide
        which data to sync.

        @param config_args: Configuration data from cereconf and/or
                            command line options.
        @type config_args: dict
        """
        # Settings for this module
        for k in ("group_spread", "group_exchange_spread", "user_spread"):
            # Group.search() must have spread constant or int to work,
            # unlike Account.search()
            if k in config_args:
                setattr(self, k, self.co.Spread(config_args[k]))
        for k in ("exchange_sync", "delete_groups", "dryrun", "store_sid",
                  "ad_ldap"):
            setattr(self, k, config_args[k])

        # Set which attrs that are to be compared with AD
        self.sync_attrs = cereconf.AD_GRP_ATTRIBUTES

        CerebrumGroup.initialize(self.get_default_ou(),
                                 config_args.get("ad_domain"))
        self.logger.info("Configuration done. Will compare attributes: %s" %
                         str(self.sync_attrs))


    def fullsync(self):
        """
        This method defines what will be done in the sync.
        """
        self.logger.info("Starting group-sync")
        # Fetch AD-data 
        self.logger.debug("Fetching AD group data...")
        addump = self.fetch_ad_data()
        self.logger.info("Fetched %i AD groups" % len(addump))

        #Fetch cerebrum data.
        self.logger.debug("Fetching cerebrum data...")
        self.fetch_cerebrum_data()

        # Compare AD data with Cerebrum data (not members)
        for gname, ad_group in addump.iteritems():
            if not gname.startswith(cereconf.AD_GROUP_PREFIX):
                self.logger.debug("Group %s doesn't start with correct prefix" %
                                  (gname))
                continue
            gname = gname[len(cereconf.AD_GROUP_PREFIX):]
            if gname in self.groups:
                self.groups[gname].in_ad = True
                self.compare(ad_group, self.groups[gname])
            else:
                self.logger.debug("Group %s in AD, but not in Cerebrum" % gname)
                # Group in AD, but not in Cerebrum:
                # Delete group if it's in Cerebrum OU and delete flag is True
                if (self.delete_groups and
                    ad_group["distinguishedName"].upper().endswith(self.ad_ldap.upper())):
                    self.delete_group(ad_group["distinguishedName"])

        # Create group if it exists in Cerebrum but is not in AD
        for grp in self.groups.itervalues():
            if grp.in_ad is False and grp.quarantined is False:
                self.create_ad_group(grp.ad_attrs, self.get_default_ou())
            
        #Syncing group members
        self.logger.info("Starting sync of group members")
        self.sync_group_members()
        
        #updating Exchange
        #if self.exchange_sync:
        #    self.update_Exchange([g.name for g in self.groups.itervalues()
        #                          if g.update_recipient])
        
        #Commiting changes to DB (SID external ID) or not.
        if self.store_sid:
            if self.dryrun:
                self.db.rollback()
            else:
                self.db.commit()
            
        self.logger.info("Finished group-sync")


    def fetch_ad_data(self):
        """Get list of groups with  attributes from AD 
        
        @return: group name -> group info mapping
        @rtype: dict
        """
        self.server.setGroupAttributes(self.sync_attrs)
        return self.server.listObjects('group', True, self.get_default_ou())


    def fetch_cerebrum_data(self):
        """
        Fetch relevant cerebrum data for groups with the given spread.
        Create CerebrumGroup instances and store in self.groups.
        """
        # Fetch name, id and description
        for row in self.group.search(spread=self.group_spread):
            # TBD: Skal gruppenavn kunne være utenfor latin-1?
            gname = unicode(row["name"], cereconf.ENCODING)
            self.groups[gname] = CerebrumGroup(gname, row["group_id"],
                                               row["description"])
        self.logger.info("Fetched %i groups with spread %s",
                         len(self.groups), self.group_spread)
        # Fetch groups with exchange spread
        for row in self.group.search(spread=self.group_exchange_spread):
            g = self.groups.get(row["name"])
            if g:
                g.to_exchange = True
        self.logger.info("Fetched %i groups with both spread %s and %s" % 
                         (len([1 for g in self.groups.itervalues() if g.to_exchange]),
                          self.group_spread, self.group_exchange_spread))
        # Set attr values for comparison with AD
        for g in self.groups.itervalues():
            g.calc_ad_attrs()


    def compare(self, ad_group, cb_group):
        """
        Compare Cerebrum group with the AD attributes listed in
        self.sync_attrs and decide if AD should be updated or not.

        @param ad_group: attributes for a group fetched from AD
        @type ad_group: dict 
        @param cb_group: CerebrumGroup instance
        @type cb_group: CerebrumGroup
        """
        cb_attrs = cb_group.ad_attrs
        for attr in self.sync_attrs:            
            cb_attr = cb_attrs.get(attr)
            ad_attr   = ad_group.get(attr)
            #self.logger.debug("attr: %s, c: %s, %s, a: %s, %s" % (
            #    attr, type(cb_attr), cb_attr, type(ad_attr), ad_attr))
            if cb_attr and ad_attr:
                # value both in ad and cerebrum => compare
                result = self.attr_cmp(cb_attr, ad_attr)
                if result: 
                    self.logger.debug("Changing attr %s from %s to %s",
                                      attr, ad_attr, cb_attr)
                    cb_group.add_change(attr, result)
            elif cb_attr:
                # attribute is not in AD and cerebrum value is set => update AD
                cb_group.add_change(attr, cb_attr)
            elif ad_attr:
                # value only in ad => delete value in ad
                cb_group.add_change(attr,"")
                
        # Commit changes
        if cb_group.changes:
            self.commit_changes(ad_group["distinguishedName"], **cb_group.changes)


    def get_default_ou(self):
        """
        Return default OU for groups.
        """
        return "%s,%s" % (cereconf.AD_GROUP_OU, self.ad_ldap)


    def sync_group_members(self):
        """
        Update group memberships in AD.
        """
        # TBD: Should we compare before sending members or just send them all?
        # Check all cerebrum groups with given spread
        for grp in self.groups.itervalues():
            # Find account members
            members = list()
            for usr in self.group.search_members(group_id=grp.group_id,
                                                 member_spread=self.user_spread,
                                                 include_member_entity_name=True):
                uname = usr['member_name']
                if uname:
                    members.append(uname)
            
            # Find group members
            for memgrp in self.group.search_members(group_id=grp.group_id,
                                                    member_spread=self.group_spread):
                gname = memgrp.get('member_name')
                if gname:
                    members.append('%s%s' % (cereconf.AD_GROUP_PREFIX, gname))
            
            # Sync members
            self.sync_members(grp.ad_attrs.get("distinguishedName"), members)

