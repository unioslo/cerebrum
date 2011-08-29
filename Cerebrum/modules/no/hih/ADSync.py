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
        ad_attrs["telephoneNumber"] = self.contact_mobile_phone
        
        if self.is_student():
            ad_attrs["cn"] = self.uname
            ad_attrs["distinguishedName"] = "CN=%s,%s" % (self.uname,
                                                          self.ou)
            ad_attrs["homeDirectory"] = cereconf.AD_HOME_DIR_STUDENT % self.uname
            ad_attrs["profilePath"] = cereconf.AD_PROFILE_PATH_STUDENT % self.uname
        else:
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

<<<<<<< .working
    # HIH wants to export mobile phones bothe for students and employees
=======

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
                  "ad_ldap", "store_sid", "ad_subset", "cb_subset"):
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
            # For testing or special cases where we only want to sync
            # a subset
            if self.cb_subset and uname not in self.cb_subset:
                continue
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
        for row in self.pe.search_person_names(
            source_system = self.co.system_cached,
            name_variant  = [self.co.name_first,
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
        

>>>>>>> .merge-right.r14198
    def fetch_contact_info(self):
        """
        Get contact info: phonenumber and title. Personal title takes precedence.
        """
        self.logger.debug("..fetch hih contact info..")
        pid2data = {}
        # Get phone number
        for row in self.pe.list_contact_info(source_system=(self.co.system_sap,
                                                            self.co.system_fs),
                                             entity_type=self.co.entity_person,
                                             contact_type=self.co.contact_mobile_phone):
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

