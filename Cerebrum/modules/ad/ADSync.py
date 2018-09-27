# -*- coding: utf-8 -*-
#
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
Generic module for AD synchronisation

This module contains functionality for a generic AD synchronisation
script. A sync script must create a sync type instance, configure the
sync by sending a dict with configuration variables and run the
fullsync method. E.g.:

  sync = ADUserSync(db, logger, host, port, ad_domain_admin)
  sync.configure(config_args)
  sync.fullsync()

If the configuration mechanism doesn't offer enough flexibility just
write a subclass and overwrite the methods neccessary for a custom
sync.

"""
import itertools
import time

import cereconf

from Cerebrum.Errors import NotFoundError
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.Utils import Factory
from Cerebrum.modules.ad.ADUtils import ADUserUtils, ADGroupUtils
from Cerebrum.modules.ad.CerebrumData import CerebrumDistGroup
from Cerebrum.modules.ad.CerebrumData import CerebrumGroup
from Cerebrum.modules.ad.CerebrumData import CerebrumUser


class UserSync(ADUserUtils):

    def __init__(self, db, logger, host, port, ad_domain_admin):
        """
        Connect to AD agent on host:port and initialize user sync.

        :type db: Cerebrum.CLDatabase.CLDatabase
        :type logger: Cerebrum.logutils.loggers.CerebrumLogger
        :param str host: Server where xmlrpc AD agent runs
        :param int port: port number
        :param str ad_domain_admin: The user we connect to the AD agent as
        """

        ADUserUtils.__init__(self, db, logger, host, port, ad_domain_admin)
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
        # Sync settings for this module
        for k in ("user_spread", "user_exchange_spread", "forward_sync",
                  "exchange_sync", "delete_users", "dryrun", "ad_domain",
                  "ad_ldap", "ad_dc", "store_sid", "create_homedir", "subset",
                  "first_run"):
            if k in config_args:
                setattr(self, k, config_args.pop(k))

        msg = "Starting user-sync"
        if self.dryrun:
            msg += " in dryrun mode. No changes will be performed"
        self.logger.info(msg)
        # Set which attrs that are to be compared with AD
        self.sync_attrs = cereconf.AD_ATTRIBUTES
        if self.exchange_sync:
            self.sync_attrs += cereconf.AD_EXCHANGE_ATTRIBUTES
        self.logger.info("Configuration done. Will compare attributes: %s",
                         ", ".join(self.sync_attrs))
        if self.subset:
            self.logger.info("Sync will only be run for the subset %r",
                             self.subset)

    def fullsync(self):
        """
        This method defines what will be done in the sync.
        """
        # Fetch AD-data for users.
        self.logger.debug("Fetching AD user data...")
        addump = self.fetch_ad_data()
        # Check if we get any dat from AD.
        if addump is None or addump is False:
            self.logger.critical("No data from AD. Something's wrong!")
            return
        self.logger.info("Fetched %i AD users", len(addump))
        # Fetch cerebrum data. store in self.accounts
        self.logger.debug("Fetching cerebrum user data...")
        self.fetch_cerebrum_data()
        # Calculate attribute values based on Cerebrum data for
        # comparison with AD
        for acc in self.accounts.itervalues():
            acc.calc_ad_attrs(exchange=self.exchange_sync)

        # TBD: move these two for loops to compare method?
        # Compare AD data with Cerebrum data
        for uname, ad_user in addump.iteritems():
            if uname in self.accounts:
                self.accounts[uname].in_ad = True
                self.compare(ad_user, self.accounts[uname])
            else:
                self.logger.debug("User %r in AD, but not in Cerebrum", uname)
                self.deactivate_user(ad_user)

        # Users exist in Cerebrum and has ad spread, but not in AD.
        # Create user if it's not quarantined
        for acc in self.accounts.itervalues():
            if acc.in_ad is False and acc.quarantined is False:
                sid = self.create_ad_account(acc.ad_attrs,
                                             self.get_default_ou(),
                                             self.create_homedir)
                if sid and self.store_sid:
                    self.store_ext_sid(acc.account_id, sid)
                if sid and acc.to_exchange:
                    time.sleep(5)
                    self.update_Exchange(acc.uname)

        # Sync forward addresses and forward distribution groups if
        # forward sync option is true
        if self.forward_sync:
            self.fullsync_forward()

        # Update Exchange if exchange sync option is true
        if self.exchange_sync:
            self.logger.debug("Sleeping for 5 seconds to give ad-ldap time to"
                              " update")
            time.sleep(5)
            for acc in self.accounts.itervalues():
                if acc.update_recipient:
                    self.update_Exchange(acc.uname)

        if self.store_sid:
            if self.dryrun:
                self.logger.info("Rolling back sid changes")
                self.db.rollback()
            else:
                self.logger.info("Committing sid changes")
                self.db.commit()
        self.logger.info("User-sync finished")

    def fetch_cerebrum_data(self):
        """
        Fetch users, name and email information for all users with the
        given spread. Create CerebrumUser instances and store in
        self.accounts.
        """
        # Find all users with relevant spread
        for row in self.ac.search(spread=self.user_spread):
            uname = row["name"].strip()
            # For testing or special cases where we only want to sync
            # a subset
            if self.subset and uname not in self.subset:
                continue
            self.accounts[uname] = self.cb_account(int(row["account_id"]),
                                                   int(row["owner_id"]),
                                                   uname)
            # We need to map account_id -> CerebrumUser as well
            # TBD: join self.accounts and self.id2uname?
            self.id2uname[int(row["account_id"])] = uname
        self.logger.info("Fetched %i cerebrum users with spread %s",
                         len(self.accounts), self.user_spread)

        # If exchange sync, get all users with exchange spread
        if self.exchange_sync:
            for row in self.ac.search(spread=self.user_exchange_spread):
                uname = row["name"].strip()
                if self.subset and uname not in self.subset:
                    continue
                acc = self.accounts.get(uname)
                if acc:
                    acc.to_exchange = True
            self.logger.info("Fetched %i cerebrum users with both %s and %s"
                             " spreads",
                             len([1 for a in self.accounts.itervalues()
                                  if a.to_exchange is True]),
                             self.user_spread,
                             self.user_exchange_spread)

        # Remove/mark quarantined users
        self.filter_quarantines()
        self.logger.info("Found %i quarantined users",
                         len([1 for v in self.accounts.itervalues()
                              if v.quarantined]))

        # fetch names
        self.fetch_names()
        # fetch contact info: phonenumber and title
        self.fetch_contact_info()
        # fetch email info
        self.fetch_email_info()

    def cb_account(self, account_id, owner_id, uname):
        "wrapper func for easier subclassing"
        return CerebrumUser(account_id, owner_id, uname, self.ad_domain,
                            self.get_default_ou())

    def filter_quarantines(self):
        """
        Mark quarantined accounts for disabling/deletion.
        """
        quarantined_accounts = QuarantineHandler.get_locked_entities(
            self.db,
            entity_types=self.co.entity_account)

        # Set quarantine flag
        for a_id in set(self.id2uname) & set(quarantined_accounts):
            self.logger.debug("Quarantine flag is set for %s",
                              self.accounts[self.id2uname[a_id]])
            self.accounts[self.id2uname[a_id]].quarantined = True

    def fetch_names(self):
        """
        Fetch person names
        """
        # Fetch names from Cerebrum for all persons
        # TBD: getdict_persons_names might be faster
        self.logger.debug("..fetch name information..")
        pid2names = {}
        for row in self.pe.search_person_names(
                source_system=self.co.system_cached,
                name_variant=[self.co.name_first, self.co.name_last]):
            pid2names.setdefault(int(row["person_id"]), {})[
                int(row["name_variant"])] = row["name"]
        # And set names for those relevant
        for acc in self.accounts.itervalues():
            names = pid2names.get(acc.owner_id)
            if names:
                acc.name_first = names.get(int(self.co.name_first), "")
                acc.name_last = names.get(int(self.co.name_last), "")
            else:
                entity = Factory.get("Entity")(self.db)
                try:
                    entity.find(acc.owner_id)
                except NotFoundError:
                    self.logger.error("could not find owner-entity for account"
                                      " %r, this should never happen",
                                      acc.uname)
                    return
                if int(entity.entity_type) == self.co.entity_person:
                    self.logger.warn("No name information for user %r",
                                     acc.uname)
                else:
                    self.logger.debug("Non-personal account %r, don't need "
                                      "full name", acc.uname)

    def fetch_contact_info(self):
        """
        Get contact info: phonenumber and title. Personal title takes
        precedence.
        """
        self.logger.debug("..fetch contact info..")
        pid2data = {}
        # Get phone number
        for row in self.pe.list_contact_info(
                source_system=self.co.system_sap,
                entity_type=self.co.entity_person,
                contact_type=self.co.contact_phone):
            pid2data.setdefault(int(row["entity_id"]), {})[
                int(row["contact_type"])] = row["contact_value"]
        # Get title
        for row in self.pe.search_name_with_language(
                name_language=self.co.language_nb,
                name_variant=[self.co.personal_title, self.co.work_title]):
            pid2data.setdefault(int(row["entity_id"]), {})[
                int(row["name_variant"])] = row["name"]
        # set data
        for acc in self.accounts.itervalues():
            data = pid2data.get(acc.owner_id)
            if data:
                acc.contact_phone = data.get(int(self.co.contact_phone), "")
                acc.title = (data.get(int(self.co.personal_title), "") or
                             data.get(int(self.co.work_title), ""))

    def fetch_email_info(self):
        """Get email addresses from Cerebrum"""
        self.logger.debug("..fetch email info..")
        # Get primary email addr
        for uname, prim_mail in self.ac.getdict_uname2mailaddr(
                filter_expired=True,
                primary_only=True).iteritems():
            acc = self.accounts.get(uname, None)
            if acc:
                acc.email_addrs.append(prim_mail)

        if self.exchange_sync:
            # Get all email addrs
            for uname, all_mail in self.ac.getdict_uname2mailaddr(
                    filter_expired=True,
                    primary_only=False).iteritems():
                acc = self.accounts.get(uname)
                if acc:
                    acc.email_addrs.extend(all_mail)

    def fullsync_forward(self):
        # Fetch ad data
        self.logger.debug("Fetching ad data about contact objects...")
        ad_contacts = self.fetch_ad_data_contacts()
        self.logger.info("Fetched %i ad forwards", len(ad_contacts))

        # Fetch forward_info
        self.logger.debug("Fetching forwardinfo from cerebrum...")
        self.fetch_forward_info()
        for acc in self.accounts.itervalues():
            for fwd in acc.contact_objects:
                fwd.calc_forward_attrs()
        # Compare forward info
        self.compare_forwards(ad_contacts)

        # Fetch ad dist group data
        self.logger.debug("Fetching ad data about distrubution groups...")
        self.fetch_ad_data_distribution_groups()
        # create a distribution group for each cerebrum user with
        # forward addresses
        for acc in self.accounts.itervalues():
            if acc.contact_objects:
                acc.create_dist_group()
        # Compare dist group info
        # TBD: dist group sync should perhaps be a sub class of group
        # sync?
        # self.compare_dist_groups(ad_dist_groups)
        # self.sync_dist_group_members()

    def fetch_forward_info(self):
        """
        Fetch forward info for all users with both AD and exchange spread.
        """
        # from Cerebrum.modules.Email import EmailDomain
        from Cerebrum.modules.Email import EmailTarget
        from Cerebrum.modules.Email import EmailForward
        etarget = EmailTarget(self.db)
        # rewrite = EmailDomain(self.db).rewrite_special_domains
        eforward = EmailForward(self.db)

        # We need a email target -> entity_id mapping
        target_id2target_entity_id = {}
        for row in etarget.list_email_targets_ext():
            if row['target_entity_id']:
                te_id = int(row['target_entity_id'])
                target_id2target_entity_id[int(row['target_id'])] = te_id

        # Check all email forwards
        for row in eforward.list_email_forwards():
            te_id = target_id2target_entity_id.get(int(row['target_id']))
            acc = self.get_account(account_id=te_id)
            # We're only interested in those with AD and exchange spread
            if acc.to_exchange:
                acc.add_forward(row['forward_to'])

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
        # Check if we get any dat from AD. If no data the AD service
        # returns None. If we actually expect no data (the option
        # first_run is given), then we want an empty dict rather than
        # None
        if ret is None and self.first_run:
            ret = dict()

        if self.subset:
            tmp = dict()
            for u in self.subset:
                if u in ret:
                    tmp[u] = ret.get(u)
            ret = tmp
        return ret

    def fetch_ad_data_contacts(self):
        """
        Returns full LDAP path to AD objects of type 'contact' and prefix
        indicating it is used for forwarding.

        @return: a dict of dicts wich maps contact obects name to that
                 objects properties (dict)
        @rtype: dict
        """
        ret = dict()
        self.server.setContactAttributes(
            cereconf.AD_CONTACT_FORWARD_ATTRIBUTES)
        ad_contacts = self.server.listObjects('contact', True, self.ad_ldap)
        if ad_contacts:
            # Only deal with forwarding contact objects.
            for object_name, properties in ad_contacts.iteritems():
                # TBD: cereconf-var?
                if object_name.startswith("Forward_for_"):
                    ret[object_name] = properties
        return ret

    def fetch_ad_data_distribution_groups(self):
        """
        Returns full LDAP path to AD objects of type 'group' and prefix
        indicating it is to hold forward contact objects.

        @rtype: dict
        @return: a dict of dict wich maps distribution group names to
                 distribution groupproperties (dict)
        """
        ret = dict()
        self.server.setGroupAttributes(cereconf.AD_DIST_GRP_ATTRIBUTES)
        ad_dist_grps = self.server.listObjects('group', True, self.ad_ldap)
        if ad_dist_grps:
            # Only deal with forwarding groups. Groupsync deals with other
            # groups.
            for grp_name, properties in ad_dist_grps.iteritems():
                if grp_name.startswith(cereconf.AD_FORWARD_GROUP_PREFIX):
                    ret[grp_name] = properties
        return ret

    def compare(self, ad_user, cb_user):
        """
        Compare Cerebrum user with the AD attributes listed in
        self.sync_attrs and decide if AD should be updated or not.

        @param ad_user: attributes for a user fetched from AD
        @type ad_user: dict
        @param cb_user: CerebrumUser instance
        @type cb_user: CerebrumUser
        """
        cb_attrs = cb_user.ad_attrs
        dn = ad_user["distinguishedName"]

        # Check if user is quarantined. If so, disable
        if cb_attrs["ACCOUNTDISABLE"] and not ad_user["ACCOUNTDISABLE"]:
            self.disable_user(dn)

        # Check if user has correct OU. If not, move user.
        if self.get_ou(dn) != cb_user.ou:
            self.move_user(dn, cb_user.ou)
            # Object is moved, so dn must be corrected
            dn = dn.replace(self.get_ou(dn), cb_user.ou)

        # Sync attributes
        for attr in self.sync_attrs:
            # Now, compare values from AD and Cerebrum
            cb_attr = cb_attrs.get(attr)
            ad_attr = ad_user.get(attr)
            if cb_attr and ad_attr:
                # value both in ad and cerebrum => compare
                result = self.attr_cmp(cb_attr, ad_attr)
                # Special case: Change name of AD user object?
                if attr == "cn" and result:
                    cb_cn = "CN=" + cb_attrs["cn"]
                    self.rename_object(dn, self.get_ou(dn), cb_cn)
                    dn = "%s,%s" % (cb_cn, self.get_ou(dn))
                # Normal cases
                elif result:
                    self.logger.debug("Changing attr %s from %r to %r",
                                      attr, ad_attr, cb_attr)
                    cb_user.add_change(attr, result)
            elif cb_attr:
                # attribute is not in AD and cerebrum value is set => update AD
                cb_user.add_change(attr, cb_attr)
            elif ad_attr:
                # value only in ad => delete value in ad
                # TBD: is this correct behavior?
                cb_user.add_change(attr, "")

        # Special AD control attributes
        for attr, value in cereconf.AD_ACCOUNT_CONTROL.iteritems():
            if attr in cb_user.ad_attrs:
                value = cb_user.ad_attrs[attr]
            if attr not in ad_user or ad_user[attr] != value:
                cb_user.add_change(attr, value)

        # Commit changes
        if cb_user.changes:
            self.commit_changes(dn, **cb_user.changes)

    def compare_forwards(self, ad_contacts):
        """
        Compare forward objects from AD with forward info in Cerebrum.

        @param ad_contacts: a dict of dicts wich maps contact obects
                            name to that objects properties (dict)
        @type ad_contacts: dict
        """
        for acc in self.accounts.itervalues():
            for contact in acc.contact_objects:
                cb_fwd = contact.forward_attrs
                ad_fwd = ad_contacts.pop(cb_fwd['sAMAccountName'], None)
                if not ad_fwd:
                    # Create AD contact object
                    self.create_ad_contact(cb_fwd, self.default_ou)
                    continue
                # contact object is in AD and Cerebrum -> compare OU
                # TBD: should OU's be compared?
                ou = cereconf.AD_CONTACT_OU
                cb_dn = 'CN=%s,%s' % (cb_fwd['sAMAccountName'], ou)
                if ad_fwd['distinguishedName'] != cb_dn:
                    self.move_contact(cb_dn, ou)

                # Compare other attributes
                # TODO: This block of code is riddled with NameErrors...
                #       There's no way this ever worked
                raise NotImplementedError("If you reached this,"
                                          " you've encountered a bug!")
                #   for attr_type, cb_fwd_attr in fwd.iteritems():
                #       ad_fwd_attr = ad_fwd.get(attr_type)
                #       if cb_fwd_attr and ad_fwd_attr:
                #           # value both in ad and cerebrum => compare
                #           result = self.attr_cmp(cb_fwd_attr, ad_fwd_attr)
                #           if result:
                #               self.logger.debug(
                #                   "Changing attr %s from %s to %s",
                #                   attr, unicode2str(ad_fwd_attr),
                #                   unicode2str(cb_fwd_attr))
                #               cb_user.add_change(attr, result)
                #       elif cb_fwd_attr:
                #           # attribute is not in AD and cerebrum value is set
                #           # => update AD
                #           cb_user.add_change(attr, cb_fwd_attr)
                #       elif ad_fwd_attr:
                #           # value only in ad => delete value in ad
                #           # TBD: is this correct behavior?
                #           cb_user.add_change(attr, "")

            # Remaining contacts in AD should be deleted
            for ad_fwd in ad_contacts.itervalues():
                self.delete_contact()

    def get_default_ou(self):
        "Return default user ou"
        return cereconf.AD_USER_OU

    def get_deleted_ou(self):
        "Return deleted ou"
        return cereconf.AD_LOST_AND_FOUND

    def get_default_contacts_ou(self):
        "Return default contact ou"
        return cereconf.AD_CONTACT_OU

    def store_ext_sid(self, account_id, sid):
        self.ac.clear()
        self.ac.find(account_id)
        self.ac.affect_external_id(self.co.system_ad,
                                   self.co.externalid_accountsid)
        self.ac.populate_external_id(self.co.system_ad,
                                     self.co.externalid_accountsid, sid)
        self.logger.debug("Storing sid %r for %r", sid, account_id)
        self.ac.write_db()


class GroupSync(ADGroupUtils):

    def __init__(self, db, logger, host, port, ad_domain_admin):
        """
        Connect to AD agent on host:port and initialize group sync.

        :type db: Cerebrum.CLDatabase.CLDatabase
        :type logger: Cerebrum.logutils.loggers.CerebrumLogger
        :param str host: Server where xmlrpc AD agent runs
        :param int port: port number
        :param str ad_domain_admin: The user we connect to the AD agent as
        """
        ADGroupUtils.__init__(self, db, logger, host, port, ad_domain_admin)
        self.groups = dict()
        self.dist_groups = list()

    def configure(self, config_args):
        """
        Read configuration options from args and cereconf to decide
        which data to sync.

        @param config_args: Configuration data from cereconf and/or
                            command line options.
        @type config_args: dict
        """
        self.logger.info("Starting group-sync")
        # Sync settings for this module
        for k in ("sec_group_spread", "dist_group_spread", "user_spread"):
            # Group.search() must have spread constant or int to work,
            # unlike Account.search()
            if k in config_args:
                setattr(self, k, self.co.Spread(config_args[k]))
        for k in ("exchange_sync", "delete_groups", "dryrun", "store_sid",
                  "ad_ldap", "ad_domain", "subset", "name_prefix",
                  "first_run"):
            setattr(self, k, config_args[k])

        # Set which attrs that are to be compared with AD
        self.sync_attrs = cereconf.AD_GRP_ATTRIBUTES
        self.logger.info("Configuration done. Will compare attributes: %r",
                         self.sync_attrs)

    def fullsync(self):
        """
        This method defines what will be done in the sync.
        """
        # Fetch AD-data
        self.logger.debug("Fetching AD group data...")
        addump = self.fetch_ad_data()
        if addump is None or addump is False:
            self.logger.critical("No data from AD. Something's wrong!")
            return
        self.logger.info("Fetched %i AD groups", len(addump))

        # Fetch cerebrum data.
        self.logger.debug("Fetching cerebrum data...")
        self.fetch_cerebrum_data()

        # Compare AD data with Cerebrum data (not members)
        for gname, ad_group in addump.iteritems():
            if gname in self.groups:
                self.groups[gname].ad_dn = ad_group["distinguishedName"]
                self.groups[gname].in_ad = True
                self.compare(ad_group, self.groups[gname])
            elif gname in self.dist_groups:
                self.logger.debug("Group %s is a dist group. Ignore", gname)
            else:
                self.logger.debug("Group %s in AD, but not in Cerebrum", gname)
                # Group in AD, but not in Cerebrum:
                if self.delete_groups:
                    self.delete_group(ad_group["distinguishedName"])

        # Create group if it exists in Cerebrum but is not in AD
        for grp in self.groups.itervalues():
            if grp.in_ad is False and grp.quarantined is False:
                sid = self.create_ad_group(grp.ad_attrs,
                                           self.get_default_ou())
                if sid and self.store_sid:
                    self.store_ext_sid(grp.group_id, sid)

        # Syncing group members
        self.logger.info("Starting sync of group members")
        self.sync_group_members()

        # Commiting changes to DB (SID external ID) or not.
        if self.store_sid:
            if self.dryrun:
                self.db.rollback()
            else:
                self.db.commit()
        self.logger.info("Finished group-sync")

    def store_ext_sid(self, group_id, sid):
        self.group.clear()
        self.group.find(group_id)
        self.group.affect_external_id(self.co.system_ad,
                                      self.co.externalid_groupsid)
        self.group.populate_external_id(self.co.system_ad,
                                        self.co.externalid_groupsid, sid)
        self.group.write_db()

    def fetch_ad_data(self):
        """Get list of groups with  attributes from AD

        @return: group name -> group info mapping
        @rtype: dict
        """
        self.server.setGroupAttributes(self.sync_attrs)
        ret = self.server.listObjects('group', True, self.ad_ldap)
        # Check if we get any dat from AD. If no data the AD service
        # returns None. If we actually expect no data (the option
        # first_run is given), then we want an empty dict rather than
        # None
        if ret is None and self.first_run:
            ret = dict()
        return ret

    def fetch_cerebrum_data(self):
        """
        Fetch relevant cerebrum data for groups with the given spread.
        Create CerebrumGroup instances and store in self.groups.
        """
        # Fetch name, id and description for security groups
        for row in self.group.search(spread=self.sec_group_spread):
            gname = row["name"]
            self.groups[gname] = self.cb_group(gname, row["group_id"],
                                               row["description"])
        self.logger.info("Fetched %i groups with spread %s",
                         len(self.groups), self.sec_group_spread)
        # Set attr values for comparison with AD
        for g in self.groups.itervalues():
            g.calc_ad_attrs()

        # Fetch name for distribution groups
        for row in self.group.search(spread=self.dist_group_spread):
            self.dist_groups.append(row["name"])
        self.logger.info("Fetched %i groups with spread %s",
                         len(self.dist_groups), self.dist_group_spread)

    def cb_group(self, gname, group_id, description):
        "wrapper func for easier subclassing"
        return CerebrumGroup(gname, group_id, description, self.ad_domain,
                             self.get_default_ou())

    def compare(self, ad_group, cb_group):
        """
        Compare Cerebrum group with the AD attributes listed in
        self.sync_attrs and decide if AD should be updated or not.

        @param ad_group: attributes for a group fetched from AD
        @type ad_group: dict
        @param cb_group: CerebrumGroup instance
        @type cb_group: CerebrumGroup
        """
        for attr in self.sync_attrs:
            cb_attr = cb_group.ad_attrs.get(attr)
            ad_attr = ad_group.get(attr)
            if cb_attr and ad_attr:
                # value both in ad and cerebrum => compare
                result = self.attr_cmp(cb_attr, ad_attr)
                if result:
                    self.logger.debug("Changing attr %s from %r to %r",
                                      attr, ad_attr, cb_attr)
                    cb_group.add_change(attr, result)
            elif cb_attr:
                # attribute is not in AD and cerebrum value is set => update AD
                cb_group.add_change(attr, cb_attr)
            elif ad_attr:
                # value only in ad => delete value in ad
                cb_group.add_change(attr, "")

        # Commit changes
        if cb_group.changes:
            self.commit_changes(ad_group["distinguishedName"],
                                **cb_group.changes)

    def get_default_ou(self):
        """
        Return default OU for groups.
        """
        return cereconf.AD_GROUP_OU

    def sync_group_members(self):
        """
        Update group memberships in AD.
        """
        # TBD: Should we compare before sending members or just send them all?
        # Check all cerebrum groups with given spread
        for grp in self.groups.itervalues():
            # Find account members
            members = list()
            for usr in self.group.search_members(
                    group_id=grp.group_id,
                    member_spread=self.user_spread,
                    include_member_entity_name=True):
                uname = usr['member_name']
                if uname:
                    members.append(uname)

            # Find group members
            # TBD: also allow dist groups
            for memgrp in self.group.search_members(
                    group_id=grp.group_id,
                    member_spread=self.sec_group_spread):
                gname = memgrp.get('member_name')
                if gname:
                    members.append(gname)

            # Sync members
            if members:
                self.sync_members(grp.ad_dn, members)


class DistGroupSync(GroupSync):
    """
    Methods for dist group sync
    """
    def configure(self, config_args):
        """
        Read configuration options from args and cereconf to decide
        which data to sync.

        @param config_args: Configuration data from cereconf and/or
                            command line options.
        @type config_args: dict
        """
        self.logger.info("Starting group-sync")
        # Sync settings for this module
        for k in ("sec_group_spread", "dist_group_spread", "user_spread"):
            # Group.search() must have spread constant or int to work,
            # unlike Account.search()
            if k in config_args:
                setattr(self, k, self.co.Spread(config_args[k]))
        for k in ("exchange_sync", "delete_groups", "dryrun", "store_sid",
                  "ad_ldap", "ad_domain", "subset", "name_prefix",
                  "first_run"):
            setattr(self, k, config_args[k])

        # Set which attrs that are to be compared with AD
        self.sync_attrs = cereconf.AD_DIST_GRP_ATTRIBUTES
        self.logger.info("Configuration done. Will compare attributes: %r",
                         self.sync_attrs)

    def fullsync(self):
        """
        This method defines what will be done in the sync.
        """
        # Fetch AD-data
        self.logger.debug("Fetching AD group data...")
        addump = self.fetch_ad_data()
        if addump is None or addump is False:
            self.logger.critical("No data from AD. Something's wrong!")
            return
        self.logger.info("Fetched %i AD groups", len(addump))

        # Fetch cerebrum data.
        self.logger.debug("Fetching cerebrum data...")
        self.fetch_cerebrum_data()

        # Compare AD data with Cerebrum data (not members)
        for gname, ad_group in addump.iteritems():
            if gname in self.groups:
                self.groups[gname].ad_dn = ad_group["distinguishedName"]
                self.groups[gname].in_ad = True
                self.compare(ad_group, self.groups[gname])
            else:
                self.logger.debug("Group %r in AD, but not in Cerebrum", gname)
                # Group in AD, but not in Cerebrum:
                if self.delete_groups:
                    self.delete_group(ad_group["distinguishedName"])

        # Create group if it exists in Cerebrum but is not in AD
        for grp in self.groups.itervalues():
            if grp.in_ad is False and grp.quarantined is False:
                sid = self.create_ad_group(grp.ad_attrs,
                                           self.get_default_ou())
                if sid and self.store_sid:
                    self.store_ext_sid(grp.group_id, sid)

        # Update Exchange if needed
        self.logger.debug("Sleeping for 5 seconds to give ad-ldap time to"
                          " update")
        time.sleep(5)
        for grp in self.groups.itervalues():
            if grp.update_recipient:
                self.update_Exchange(grp.gname)

        # Syncing group members
        self.logger.info("Starting sync of group members")
        self.sync_group_members()

        # Commiting changes to DB (SID external ID) or not.
        if self.store_sid:
            if self.dryrun:
                self.db.rollback()
            else:
                self.db.commit()

        self.logger.info("Finished group-sync")

    def fetch_ad_data(self):
        """
        Returns full LDAP path to AD objects of type 'group' and prefix
        indicating it is to hold forward contact objects.

        @rtype: dict
        @return: a dict of dict wich maps distribution group names to
                 distribution groupproperties (dict)
        """
        ret = dict()
        attrs = tuple(itertools.chain(cereconf.AD_DIST_GRP_ATTRIBUTES,
                                      cereconf.AD_DIST_GRP_DEFAULTS.keys()))
        self.server.setGroupAttributes(attrs)
        ad_dist_grps = self.server.listObjects('group', True, self.ad_ldap)
        # Check if we get any dat from AD. If no data the AD service
        # returns None. If we actually expect no data (the option
        # first_run is given), then we want an empty dict rather than
        # None
        if ad_dist_grps is None and self.first_run:
            return ret
        if ad_dist_grps:
            # Only deal with distribution groups. Groupsync deals with security
            # groups.
            dist_group_types = (
                # Global distribution group
                '2',
                # Universal distribution group
                '8',
                # Universal distribution group, security enabled
                '2147483656')
            for grp_name, properties in ad_dist_grps.iteritems():
                if 'groupType' not in properties:
                    continue
                if str(properties['groupType']) in dist_group_types:
                    ret[grp_name] = properties
        return ret

    def fetch_cerebrum_data(self):
        """
        Fetch relevant cerebrum data for groups with the given spread.
        Create CerebrumGroup instances and store in self.groups.
        """
        # Fetch name, id and description for security groups
        for row in self.group.search(spread=self.dist_group_spread):
            gname = row["name"]
            self.groups[gname] = self.cb_group(gname, row["group_id"],
                                               row["description"])
        self.logger.info("Fetched %i groups with spread %s",
                         len(self.groups), self.dist_group_spread)
        # Set attr values for comparison with AD
        for g in self.groups.itervalues():
            g.calc_ad_attrs()

    def cb_group(self, gname, group_id, description):
        "wrapper func for easier subclassing"
        return CerebrumDistGroup(gname, group_id, description, self.ad_domain,
                                 self.get_default_ou())
