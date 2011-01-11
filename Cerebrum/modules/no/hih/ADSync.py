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
Module with functions for cerebrum export to Active Directory at HiH.

TODO:

* Mer dok.

* La all tekst være unicode før sammenligning. Fetch_ad_data og
  fetch_cerebrum_data må fikse dette.

* fetch_email_info må skrives ferdig. homeMDB

* Group-sync...

* maillist-sync...

* Ta et valg når det gjelder kommando-API 


TBD:

* ad_ldap peker strengt tatt til Cerebrum-ou, f.eks
  OU=cerebrum,DC=hih,DC=no. Burde kanskje døpe om til cerebrum_ou?

"""


import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hih.ADUtils import ADUtils, ADGroupUtils
from Cerebrum import Errors


class CerebrumAccount(object):
    """
    Represent a Cerebrum Account which may be exported to AD,
    depending wether the account info in AD differs.

    An instance contains information from Cerebrum and methods for
    comparing this information with the data from AD.
    """
    @classmethod
    def initialize(cls, ou, domain):
        cls.default_ou = ou
        cls.domain = domain

    def __init__(self, account_id, owner_id, uname):
        self.account_id = account_id
        self.owner_id = owner_id
        self.uname = uname

        # default values
        self.quarantined = False
        self.in_ad = False 
        self.to_exchange = False
        self.primary_mail = ""
        self.name_last = ""
        self.name_first = ""
        

    def __str__(self):
        return "%s (%s)" % (self.uname, self.account_id)


    def __repr__(self):
        return "Account: %s (%s, %s)" % (self.uname, self.account_id, self.owner_id)


    def calc_ad_attrs(self, encoding="ISO-8859-1", **config_args):
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
        # Update with with the given attrs from config_args
        ad_attrs.update(config_args)
        
        # Do the hardcoding for this sync. 
        ad_attrs["sAMAccountName"] = self.uname
        ad_attrs["sn"] = self.name_last
        ad_attrs["givenName"] = self.name_first
        ad_attrs["displayName"] = "%s %s" % (self.name_first, self.name_last)
        ad_attrs["distinguishedName"] = "CN=%s,%s" % (self.uname, self.default_ou)
        ad_attrs["ou"] = self.default_ou
        ad_attrs["ACCOUNTDISABLE"] = self.quarantined
        ad_attrs["homeDirectory"] %= self.uname 
        ad_attrs["Profile path"] %= self.uname 
        ad_attrs["userPrincipalName"] = "%s@%s" % (self.uname, self.domain) 
        ad_attrs["title"] = self.title
        ad_attrs["telephoneNumber"] = self.contact_phone
        ad_attrs["mail"] = self.primary_mail

        # Convert str to unicode before comparing with AD
        for attr_type, attr_val in ad_attrs.iteritems():
            if type(attr_val) is str:
                ad_attrs[attr_type] = unicode(attr_val, encoding)

        self.ad_attrs = ad_attrs


    def calc_exchange_attrs(self):
        """
        Calculate AD Exchange attrs from Cerebrum data.
        
        How to calculate Exchange attr values from Cerebrum data and
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
        tmp = ["SMTP:" + self.ad_attrs["mail"]]
        for alias_addr in self.mail_addresses:
            if alias_addr != self.ad_attrs["mail"]:
                tmp.append(("smtp:" + alias_addr))
        self.ad_attrs["proxyAddresses"] = tmp


class CerebrumGroup(object):
    """
    Represent a Cerebrum group which may be exported to AD, depending
    wether the account info in AD differs.

    An instance contains information from Cerebrum and methods for
    comparing this information with the data from AD.
    """
    @classmethod
    def initialize(cls, ou, domain):
        cls.default_ou = ou
        cls.domain = domain

    def __init__(self, name, group_id, description):
        self.name = name
        self.group_id = group_id
        self.description = description
        # default values
        self.quarantined = False
        self.in_ad = False 
        self.to_exchange = False


    def calc_ad_attrs(self, encoding="ISO-8859-1", **config_args):
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
        ad_attrs["groupType"] = cereconf.AD_GROUP_TYPE
        ad_attrs["displayName"] = self.name
        ad_attrs["displayNamePrintable"] = self.name
        ad_attrs["group_id"] = self.group_id
        ad_attrs["name"] = cereconf.AD_GROUP_PREFIX + self.name
        ad_attrs["distinguishedName"] = "CN=%s,%s" % (ad_attrs["name"],
                                                      self.default_ou)
        ad_attrs["description"] = self.description or "Not available"
        ad_attrs["OU"] = self.default_ou

        # Exchange
        if self.to_exchange:
            ad_attrs["proxyAddresses"] = ["SMTP:" + self.name + "@" +
                                          self.domain]
            ad_attrs["mailNickname"] = self.name
            ad_attrs["mail"] = self.name + "@" + self.domain

        # Convert str to unicode before comparing with AD
        for attr_type, attr_val in ad_attrs.iteritems():
            if type(attr_val) is str:
                ad_attrs[attr_type] = unicode(attr_val, encoding)
        self.ad_attrs = ad_attrs


class ADUserSync(ADUtils):
    def __init__(self, db, logger, host, port, ad_domain_admin):
        ADUtils.__init__(self, logger, host, port, ad_domain_admin)
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
        """
        # Sync settings for this module
        for k in ("user_spread", "user_exchange_spread",
                  "exchange_sync", "delete_users", "dryrun",
                  "ad_ldap", "store_sid"):
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
                         str(cereconf.AD_ATTRIBUTES))
        

    def fullsync(self):
        """
        This method defines what will be done in the sync.
        """
        
        self.logger.info("Starting user-sync")
        # Fetch AD-data for users.     
        self.logger.debug("Fetching AD user data...")
        addump = self.fetch_ad_data(self.ad_ldap)
        self.logger.info("Fetched %i AD users" % len(addump))

        # Fetch cerebrum data. store in self.accounts
        self.logger.debug("Fetching cerebrum user data...")
        self.fetch_cerebrum_data()

        # Compare AD data with Cerebrum data
        for uname, ad_user in addump.items():
            if uname in self.accounts:
                self.accounts[uname].in_ad = True
                self.compare(ad_user, self.accounts[uname].ad_attrs)
            else:
                self.logger.debug("User %s (%s) in AD, but not in Cerebrum" %
                                  (uname, str(ad_user)))
                # User in AD, but not in Cerebrum:
                # If user is in Cerebrum OU then deactivate
                if ad_user["distinguishedName"].upper().endswith(
                    self.ad_ldap.upper()):
                    self.deactivate_user(ad_user)

        # Users exist in Cerebrum and has ad spread, but is not in AD.
        # Create user if it's not quarantined
        for cere_acc in [acc for acc in self.accounts.values() if
                         acc.in_ad is False and acc.quarantined is False]:
            self.create_ad_account(cere_acc.ad_attrs, self.get_default_ou())
            
        self.logger.info("User-sync finished")


    def fetch_cerebrum_data(self):
        """
        Fetch users, name and email information for all users with the
        given spread.
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
            [1 for v in self.accounts.itervalues() if v.quarantined is True]))

        # fetch names
        self.logger.debug("..fetch name information..")
        self.fetch_names()
        
        # fetch contact info: phonenumber and title
        self.logger.debug("..fetch contact info..")
        self.fetch_contact_info()

        # fetch email info
        self.logger.debug("..fetch email info..")
        self.fetch_email_info()
        
        # Fetch exchange data and calculate attributes
        if self.exchange_sync:
            for row in self.ac.search(spread=self.user_exchange_spread):
                uname = self.id2uname.get(int(row["account_id"]), None)
                if uname:
                    self.accounts[uname].calc_exchange_attrs()
            self.logger.info("Fetched %i cerebrum users with spreads %s and %s" % (
                len([1 for acc in self.accounts.itervalues() if acc.to_exchange]),
                self.user_spread, self.user_exchange_spread))

        # Finally, calculate attribute values based on Cerebrum data
        # for comparison with AD
        for acc in self.accounts.itervalues():
            acc.calc_ad_attrs(**self.config_args)

    

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
        # TBD: just fetch persons with a given spread might be faster? Or not?
        pid2names = {}
        for row in self.pe.list_persons_name(
            source_system = self.co.system_cached,
            name_type     = [self.co.name_first,
                             self.co.name_last]):
            pid2names.setdefault(int(row["person_id"]), {})[
                int(row["name_variant"])] = row["name"]
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
        for acc in self.accounts.itervalues(): 
            self.pe.clear()
            try:
                self.pe.find(acc.owner_id)
            except Errors.NotFoundError:
                self.logger.info("Getting contact info: Skipping user=%s,"
                                 "owner (id=%s) is not a person entity." 
                                 % (acc.uname, acc.owner_id))
                continue
            phones = self.pe.get_contact_info(type=self.co.contact_phone)
            acc.contact_phone = ""
            if phones:
                acc.contact_phone = phones[0]["contact_value"]

            acc.title = ""
            for title_type in (self.co.name_work_title, 
                               self.co.name_personal_title):
                try:
                    acc.title = self.pe.get_name(self.co.system_sap, title_type)
                except Errors.NotFoundError:
                    pass


    def fetch_email_info(self):
        """
        Get primary email addresses from Cerebrum. If syncing to
        Exchange also get additional email info.
        """
        # Find primary addresses and set mail attribute
        for uname, prim_mail in self.ac.getdict_uname2mailaddr(
            filter_expired=True, primary_only=True).iteritems():
            acc = self.accounts.get(uname, None)
            if acc:
                acc.primary_mail = prim_mail

        # Only get more email info if exchange sync is on
        if not self.exchange_sync:
            return

        #Find all valid addresses and set proxyaddresses attribute
        for uname, all_mail in self.ac.getdict_uname2mailaddr(
            filter_expired=True, primary_only=False).iteritems():
            acc = self.accounts.get(uname, None)
            if acc and acc.to_exchange:
                acc.mail_addresses = all_mail

        # TODO: homeMDB, mangler spesifikasjon

        # Get quota info
        # TBD: Should we check if quota attrs are in
        # cereconf.AD_EX_ATTRIBUTES before doing this?
        from Cerebrum.modules.Email import EmailQuota
        equota = EmailQuota(self.db)
        
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
        @type search_ou: String
        """
        # Setting the userattributes to be fetched.
        self.server.setUserAttributes(cereconf.AD_ATTRIBUTES,
                                      cereconf.AD_ACCOUNT_CONTROL)
        return self.server.listObjects("user", True, search_ou)


    def compare(self, ad_user, cere_user):
        """
        Compare Cerebrum user with the AD attributes listed in
        cereconf.AD_ATTRIBUTES and decide if AD must be updated or not.
        """
        # First check if user is quarantined. If so, disable
        if cere_user["ACCOUNTDISABLE"] and not ad_user["ACCOUNTDISABLE"]:
            self.disable_user(ad_user)
        
        # Check if user has correct OU. If not, move user
        if ad_user["distinguishedName"] != cere_user["distinguishedName"]:
            self.move_user(ad_user, ou=cere_user["ou"])
            
        # Sync attributes
        #for attr in cere_user:
        for attr in cereconf.AD_ATTRIBUTES:
            # Some attribuets need special attention
            if attr in ("altRecipient", "deliverAndRedirect"):
                # Ignore these attributes if not doing forward sync
                if not self.forward_sync:
                    continue
            # Now, compare values from AD and Cerebrum
            cere_attr = cere_user.get(attr, None)
            ad_attr   = ad_user.get(attr, None)
            if cere_attr and ad_attr:
                # value both in ad and cerebrum => compare
                result = self.attr_cmp(attr, cere_attr, ad_attr)
                if result: 
                    self.logger.debug("Changing attr %s from %s to %s",
                                      attr, ad_attr, cere_attr)
                    self.add_change(attr, result)
            elif cere_attr:
                # attribute is not in AD and cerebrum value is set => update AD
                self.add_change(attr, cere_attr)
            elif ad_attr:
                # value only in ad => delete value in ad
                self.add_change(attr,"")

        # TBD: Sett default versjon i cereconf og sammenligne i løkka over?
        for attr, value in cereconf.AD_ACCOUNT_CONTROL.items():
            if attr in cere_user:
                if attr not in ad_user or ad_user[attr] != cere_user[attr]:
                    self.add_change(attr, cere_user[attr])
            elif attr not in ad_user or ad_user[attr] != value:
                self.add_change(attr, value)
                
        # Commit changes
        if self.changes:
            self.commit_changes(ad_user["distinguishedName"])


    def attr_cmp(self, attr_type, cere_attr, ad_attr):
        """
        Compare new and old ad attributes. Most of the time it is a
        simple string comparison, but there are exceptions.
        """
        if attr_type == "msExchPoliciesExcluded":
            # xmlrpclib appends chars [' and '] to 
            # this attribute for some reason
            tmpstring = ad_attr.replace("['","")
            tmpstring = tmpstring.replace("']","")
            if tmpstring != cere_attr:
                return cere_attr
        else:
            if cere_attr != ad_attr:
                return cere_attr


    def get_default_ou(self):
        return "%s,%s" % (cereconf.AD_USER_OU, self.ad_ldap)
    


class ADGroupSync(ADGroupUtils):
    def __init__(self, db, logger, host, port, ad_domain_admin):
        ADGroupUtils.__init__(self, logger, host, port, ad_domain_admin)
        self.db = db
        self.co = Factory.get("Constants")(self.db)
        self.group = Factory.get("Group")(self.db)
        self.groups = dict()
        

    def configure(self, config_args):
        """
        Read configuration options from args and cereconf to decide
        which data to sync.
        """
        # Settings for this module
        for k in ("group_spread", "group_exchange_spread", "user_spread"):
            # Group.search() must have spread constant or int to work,
            # unlike Account.search()
            setattr(self, k, self.co.Spread(config_args.pop(k)))
        for k in ("exchange_sync", "delete_groups", "dryrun", "store_sid",
                  "ad_ldap"):
            setattr(self, k, config_args.pop(k))
        CerebrumGroup.initialize(self.get_default_ou(),
                                 config_args.pop("ad_domain"))
        self.config_args = config_args
        # The rest of the config args goes to the CerebrumGroup class
        # and instances
        self.ad_attributes = config_args
        self.logger.info("Configuration done. Will compare attributes: %s" %
                         str(cereconf.AD_ATTRIBUTES))


    def fullsync(self):
        self.logger.info("Starting group-sync(group_spread = %s, "
                         #"exchange_spread = %s, user_spread = %s, "
                         "delete = %s, dry_run = %s, store_sid = %s)" %
                         #(self.group_spread, self.exchange_spread, self.user_spread, self.delete,
                         (self.group_spread, self.delete_groups,
                          self.dryrun, self.store_sid))
        # Fetch AD-data 
        self.logger.debug("Fetching AD group data...")
        addump = self.fetch_ad_data()
        self.logger.info("Fetched %i AD groups" % len(addump))

        #Fetch cerebrum data.
        self.logger.debug("Fetching cerebrum data...")
        self.fetch_cerebrum_data()

        # Compare AD data with Cerebrum data (not members)
        for gname, ad_group in addump.items():
            if not gname.startswith(cereconf.AD_GROUP_PREFIX):
                self.logger.debug("Group %s doesn't start with correct prefix" %
                                  (gname))
                continue
            gname = gname[len(cereconf.AD_GROUP_PREFIX):]
            if gname in self.groups:
                self.groups[gname].in_ad = True
                self.compare(ad_group, self.groups[gname].ad_attrs)
            else:
                self.logger.debug("Group %s in AD, but not in Cerebrum" % gname)
                # Group in AD, but not in Cerebrum:
                # Delete group if it's in Cerebrum OU and delete flag is True
                if (self.delete_groups and
                    ad_group["distinguishedName"].upper().endswith(self.ad_ldap.upper())):
                    self.delete_group(ad_group)

        # Group exist in Cerebrum and has ad spread, but is not in AD. Create.
        for cb_group in [grp for grp in self.groups.itervalues() if
                         grp.in_ad is False and grp.quarantined is False]:
            self.create_ad_group(cb_group.ad_attrs, self.get_default_ou())
            
        #Syncing group members
        self.logger.info("Starting sync of group members")
        self.sync_group_members()
        
        #updating Exchange
        if self.exchange_sync:
            self.update_Exchange([g.name for g in self.groups.itervalues()
                                  if g.to_exchange])
        
        #Commiting changes to DB (SID external ID) or not.
        if self.store_sid:
            if self.dryrun:
                self.db.rollback()
            else:
                self.db.commit()
            
        self.logger.info("Finished group-sync")


    def fetch_ad_data(self, filter_forward_groups=True):
        """Get list of groups with  attributes from AD 
        
        @returm ad_dict : group name -> group info mapping
        @type ad_dict : dict
        """
        self.server.setGroupAttributes(cereconf.AD_GRP_ATTRIBUTES)
        ad_groups = self.server.listObjects('group', True, self.get_default_ou())
        if filter_forward_groups:
            for grp_name in ad_groups:
                if grp_name.startswith(cereconf.AD_FORWARD_GROUP_PREFIX):
                    del ad_groups[grp_name]
        return ad_groups


    def fetch_cerebrum_data(self):
        """
        Fetch relevant cerebrum data for groups with the given spread.
        One spread indicating export to AD, and one spread indicating
        that it should also be prepped and activated for Exchange 2007.

        @param spread: ad group spread for a domain
        @type spread: _SpreadCode
        @param exchange_spread: exchange group spread
        @type exchange_spread: _SpreadCode
        @rtype: dict
        @return: a dict {grpname: {'adAttrib': 'value'}} for all groups
        of relevant spread. Typical attributes::
        
        'displayName': String,          # gruppenavn
        'mail': String,                 # default e-post adresse
        'Exchange' : Bool,              # Flag - skal i Exchange eller ikke 
        'msExchPoliciesExcluded' : int, # Exchange verdi
        'msExchHideFromAddressLists' : Bool, # Exchange verdi
        'mailNickname' : String         # gruppenavn
        'proxyAddresses' : String       # default e-post adresse
        'displayNamePrintable' : String # gruppenavn
        'description' : String          # beskrivelse
        'groupType' : Int               # type gruppe
        """
        # Fetch name, id and description
        for row in self.group.search(spread=self.group_spread):
            # TBD: Skal gruppenavn kunne være utenfor latin-1?
            gname = unicode(row["name"], "iso-8859-1")
            self.groups[gname] = CerebrumGroup(gname, row["group_id"],
                                               row["description"])
        self.logger.info("Fetched %i groups with spread %s",
                         len(self.groups), self.group_spread)
        # Fetch groups with exchange spread
        for row in self.group.search(spread=self.group_exchange_spread):
            g = self.groups.get(row["name"], None)
            if g:
                g.to_exchange = True
        self.logger.info("Fetched %i groups with both spread %s and %s" % 
                         (len([1 for g in self.groups.itervalues() if g.to_exchange]),
                          self.group_spread, self.group_exchange_spread))
        # Set attr values for comparison with AD
        for g in self.groups.itervalues():
            g.calc_ad_attrs(**self.ad_attributes)


    def compare(self, ad_group, cere_group):
        """ Sync group info with AD

        Check if any values about groups other than group members
        should be updated in AD.
        """
        # Sjekke plassering? Vi henter jo data fra
        # OU=Groups,OU=Cerebrum,DC=... uansett. Da er det ingen andre
        # steder å flytte til. Hvis vi i stedet skal hente grupper fra
        # et videre OU, så er saken annerledes.
        for attr in cereconf.AD_GRP_ATTRIBUTES:            
            cere_attr = cere_group.get(attr, None)
            ad_attr   = ad_group.get(attr, None)
            #self.logger.debug("attr: %s, c: %s, %s, a: %s, %s" % (
            #    attr, type(cere_attr), cere_attr, type(ad_attr), ad_attr))
            if cere_attr and ad_attr:
                # value both in ad and cerebrum => compare
                result = self.attr_cmp(attr, cere_attr, ad_attr)
                if result: 
                    self.logger.debug("Changing attr %s from %s to %s",
                                      attr, ad_attr, cere_attr)
                    self.add_change(attr, result)
            elif cere_attr:
                # attribute is not in AD and cerebrum value is set => update AD
                self.add_change(attr, cere_attr)
            elif ad_attr:
                # value only in ad => delete value in ad
                self.add_change(attr,"")
                
        # Commit changes
        if self.changes:
            self.commit_changes(ad_group["distinguishedName"])


    def attr_cmp(self, attr_type, cere_attr, ad_attr):
        """
        Compare new and old ad attributes. Most of the time it is a
        simple string comparison, but there are exceptions.
        """
        #if attr_type in "msExchPoliciesExcluded":
        if isinstance(ad_attr, list):
            # self.logger.debug("attr %s is a list from AD %s" % (attr_type, ad_attr))
            ad_attr = ad_attr[0]
        if cere_attr != ad_attr:
            return cere_attr

        

    def get_default_ou(self):
        """
        Return default OU for groups. Burde vaere i cereconf?
        """
        return "%s,%s" % (cereconf.AD_GROUP_OU,self.ad_ldap)


    def sync_group_members(self):
        """
        Update group memberships in AD
        """

        #To reduce traffic, we send current list of groupmembers to AD, and the
        #server ensures that each group have correct members.   
        entity2name = dict([(x["entity_id"], x["entity_name"]) for x in 
                           self.group.list_names(self.co.account_namespace)])
        entity2name.update([(x["entity_id"], x["entity_name"]) for x in
                           self.group.list_names(self.co.group_namespace)])    

        # Check all cerebrum groups with given spread
        for grp in self.groups.itervalues():
            # Find account members
            members = list()
            for usr in self.group.search_members(group_id=grp.group_id,
                                                 member_spread=self.user_spread):
                user_id = usr["member_id"]
                if user_id not in entity2name:
                    self.logger.warning("Missing name for account id=%s", user_id)
                    continue
                members.append(entity2name[user_id])
                #self.logger.debug("Try to sync member account id=%s, name=%s",
                #                  user_id, entity2name[user_id])

            # Find group members
            for memgrp in self.group.search_members(group_id=grp.group_id,
                                                    member_spread=self.group_spread):
                memgrp_id = memgrp["member_id"]
                if memgrp_id not in entity2name:
                    self.logger.warning("Missing name for group id=%s", memgrp_id)
                    continue
                members.append('%s%s' % (cereconf.AD_GROUP_PREFIX,
                                         entity2name[memgrp_id]))            
                #self.logger.debug("Try to sync member group id=%s, name=%s",
                #                   memgrp_id, entity2name[memgrp_id])
            
            # Sync members
            self.sync_members(grp.ad_attrs.get("distinguishedName"), members)

