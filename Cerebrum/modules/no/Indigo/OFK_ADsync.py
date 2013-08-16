#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2006, 2007, 2013 University of Oslo, Norway
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

"""Module with functions for cerebrum export to Active Directory at OFK

Extends the functionality provided in the general AD-export module
ADutilMixIn.py to work with the setup at Ostfold Fylkes Kommune
with Active Directory and Exchange 2007.
"""

import cerebrum_path
import cereconf

from Cerebrum import Utils
from Cerebrum import QuarantineHandler
from Cerebrum.modules import ADutilMixIn
from Cerebrum import Errors
import copy
import time


class ADFullUserSync(ADutilMixIn.ADuserUtil):

    def _filter_quarantines(self, user_dict):
        """Filter quarantined accounts

        Removes all accounts that are quarantined from export to AD

        @param user_dict: account_id -> account info mapping
        @type user_dict: dict
        """
        def apply_quarantines(entity_id, quarantines):
            q_types = []
            for q in quarantines:
                q_types.append(q['quarantine_type'])
            if not user_dict.has_key(entity_id):
                return
            qh = QuarantineHandler.QuarantineHandler(self.db, q_types)
            if qh.should_skip():
                del(user_dict[entity_id])
            if qh.is_locked():
                user_dict[entity_id]['ACCOUNTDISABLE'] = True

        prev_user = None
        user_rows = []
        for row in self.ac.list_entity_quarantines(only_active=True):
            if prev_user != row['entity_id'] and prev_user is not None:
                apply_quarantines(prev_user, user_rows)
                user_rows = [row]
            else:
                user_rows.append(row)
            prev_user = row['entity_id']
        else:
            if user_rows:
                apply_quarantines(prev_user, user_rows)

    def _update_mail_info(self, user_dict):
        """Get email info about a user from cerebrum

        Fetch primary email address and all valid addresses
        for users in user_dict.
        Add info to user_dict from cerebrum. For the AD 'mail' attribute
        add key/value pair 'mail'/<primary address>. For the
        AD 'proxyaddresses' attribute add key/value pair
        'proxyaddresses'/<list of all valid addresses>. The addresses
        in the proxyaddresses list are preceded by address type. In
        capital letters if it is the default address.

        Also write Exchange attributes for those accounts that have
        that spread.

        user_dict is established in the fetch_cerebrum_data function, and
        this function populates the following values:
        mail, proxyAddresses, mDBOverHardQuotaLimit, mDBOverQuotaLimit,
        mDBStorageQuota and homeMDB.

        @param user_dict: account_id -> account information
        @type user_dict: dict
        """

        # Find primary addresses and set mail attribute
        uname2primary_mail = self.ac.getdict_uname2mailaddr(
            filter_expired=True, primary_only=True)
        for uname, prim_mail in uname2primary_mail.iteritems():
            if user_dict.has_key(uname):
                if (user_dict[uname]['Exchange']):
                    user_dict[uname]['mail'] = prim_mail

        # Find all valid addresses and set proxyaddresses attribute
        uname2all_mail = self.ac.getdict_uname2mailaddr(
            filter_expired=True, primary_only=False)
        for uname, all_mail in uname2all_mail.iteritems():
            if user_dict.has_key(uname):
                if (user_dict[uname]['Exchange']):
                    user_dict[uname]['proxyAddresses'].insert(
                        0, ("SMTP:" + user_dict[uname]['mail']))
                    for alias_addr in all_mail:
                        if alias_addr == user_dict[uname]['mail']:
                            pass
                        else:
                            user_dict[uname]['proxyAddresses'].append(
                                ("smtp:" + alias_addr))

        # get traits for x.400 address and homeMDB
        for k, v in user_dict.iteritems():
            self.ac.clear()
            if v['Exchange']:
                try:
                    self.ac.find_by_name(k)
                except Errors.NotFoundError:
                    continue

                # Some accounts have an old X.400 address
                x400_trait = self.ac.get_trait(self.co.trait_x400_addr)
                if x400_trait and x400_trait["strval"]:
                    v['proxyAddresses'].append(
                        ("X400:" + x400_trait["strval"]))
                # Some accounts have an old X.400 address
                x500_trait = self.ac.get_trait(self.co.trait_x500_addr)
                if x500_trait and x500_trait["strval"]:
                    v['proxyAddresses'].append(
                        ("X500:" + x500_trait["strval"]))

                # Set homeMDB for Exchange users.
                # We need to differ between those migrated to a newer version of
                # Exchange and not, as Exchange' attribute format changes from
                # version to version.
                # 
                # TODO: We are here expecting that all the MDB values listed in
                # cereconf.EXCHANGE_HOMEMDB_VALID is for Exchange 2010. All
                # values that is not in the cereconf list is expected to be from
                # Exchange 2007. This might change in the future.
                mdb_trait = self.ac.get_trait(self.co.trait_homedb_info)

                # Find the server name of where the MDB is put:
                exchangeserver = ""
                for servername in cereconf.AD_EX_MDB_SERVER:
                    if mdb_trait["strval"] in cereconf.AD_EX_MDB_SERVER[servername]:
                        exchangeserver = servername

                # Migrated users:
                if (mdb_trait and mdb_trait['strval'] in
                                            cereconf.EXCHANGE_HOMEMDB_VALID):
                    self.logger.debug2("Account %s migrated", k)
                    # User is migrated:
                    v['homeMDB'] = "CN=%s,%s" % (mdb_trait["strval"],
                                                 cereconf.AD_EX_MDB_DN_2010)
                    #v['msExchHomeServerName'] = cereconf.AD_EXC_HOME_SERVER

                    # The homeMTA value, just to be able to make the sync work
                    # with both 2007 and 2010. Might be removed in the future.
                    if exchangeserver:
                        v['homeMTA'] = cereconf.EXCHANGE_HOMEMTA % {'server': exchangeserver}
                        self.logger.debug2('HomeMTA: %s', v['homeMTA'])
                elif mdb_trait and mdb_trait["strval"]:
                    # Non-migrated user:
                    v['homeMDB'] = "CN=%s,CN=SG_%s,CN=InformationStore,CN=%s,%s" % (mdb_trait["strval"],
                                                                                    mdb_trait[
                                                                                    "strval"],
                                                                                    exchangeserver,
                                                                                    cereconf.AD_EX_MDB_DN)
                else:
                    v['homeMDB'] = ""
                    self.logger.warning("Error getting homeMDB"
                                        " for account %s (id: %i)" % (k, int(k)))

    def _update_contact_info(self, user_dict):
        """
        Get contact info: phonenumber.

        @param user_dict: account_id -> account info mapping
        @type user_dict: dict
        """
        for v in user_dict.itervalues():
            self.person.clear()
            try:
                self.person.find(v['TEMPownerId'])
            except Errors.NotFoundError:
                self.logger.warning("Getting contact info: Skipping ownerid=%s,"
                                    "no valid account found", v['TEMPownerId'])
                continue
            phones = self.person.get_contact_info(type=self.co.contact_phone)
            if not phones:
                v['telephoneNumber'] = ''
            else:
                v['telephoneNumber'] = phones[0]['contact_value']
            phones = self.person.get_contact_info(
                type=self.co.contact_mobile_phone)
            if not phones:
                v['mobile'] = ''
            else:
                v['mobile'] = phones[0]['contact_value']

    def _update_extensionAttributes(self, user_dict):
        """
        Will update the three extionAttributes that ØFK uses to generate
        addresslists in Exchange based on affiliation

        @param user_dict: account_id -> account info mapping
        @type user_dict: dict
        """
        # These are the strings ØFK wants in the Attributes according to the spec
        # if user have affiliation_ansatt
        extAttr1 = "Employee"
        # if user have affiliation_tilknyttet
        extAttr2 = "Affiliate"
        # if user have affiliation_elev
        extAttr3 = "Pupil"

        # Get dicts of accounts with the different affiliations
        employe_dict = self.ac.list_accounts_by_type(
            affiliation=self.co.affiliation_ansatt)
        affiliate_dict = self.ac.list_accounts_by_type(
            affiliation=self.co.affiliation_tilknyttet)
        pupil_dict = self.ac.list_accounts_by_type(
            affiliation=self.co.affiliation_elev)

        for row in employe_dict:
            if user_dict.has_key(row['account_id']):
                user_dict[row['account_id']]['extensionAttribute1'] = extAttr1
        for row in affiliate_dict:
            if user_dict.has_key(row['account_id']):
                user_dict[row['account_id']]['extensionAttribute2'] = extAttr2
        for row in pupil_dict:
            if user_dict.has_key(row['account_id']):
                user_dict[row['account_id']]['extensionAttribute3'] = extAttr3

    def get_default_ou(self):
        """
        Return default OU for users.
        """
        return "OU=%s,%s" % (cereconf.AD_USER_OU, self.ad_ldap)

    def fetch_cerebrum_data(self, spread, exchange_spread):
        """
        Fetch relevant cerebrum data for users with the given spread.
        One spread indicating export to AD, and one spread indicating
        that is should also be prepped and activated for Exchange 2007.

        @param spread: ad account spread for a domain
        @type spread: _SpreadCode
        @param exchange_spread: exchange account spread
        @type exchange_spread: _SpreadCode
        @rtype: dict
        @return: a dict {uname: {'adAttrib': 'value'}} for all users
        of relevant spread. Typical attributes::

          # canonicalName er et 'constructed attribute' (fra dn)
          'displayName': String,          # Fullt navn
          'givenName': String,            # fornavn
          'sn': String,                   # etternavn
          'Exchange' : Bool,              # Flag - skal i Exchange eller ikke
          'msExchPoliciesExcluded' : int, # Exchange verdi
          'msExchHideFromAddressLists' : Bool, # Exchange verdi
          'userPrincipalName' : String    # brukernavn@domene
          'telephoneNumber' : String      # tlf
          'mobile' : String               # mobil nr
          'mailNickname' : String         # brukernavn
          'proxyAddresses' : Array        # Alle gyldige epost adresser
          'ACCOUNTDISABLE'                # Flag, used by ADutilMixIn
          'extensionAttribute1' : String  # Om brukeren har ansatt affiliation
          'extensionAttribute2' : String  # Om brukeren er tilknyttet affiliation
          'extensionAttribute3' : String  # Om brukeren har elev affiliation
        """
        self.person = Utils.Factory.get('Person')(self.db)

        # Users under migration, tagged by trait_exchange_under_migration,
        # should get ignored by the sync until the trait is removed.
        self.accountid2name = dict((r['account_id'], r['name']) for r in
                                   self.ac.search(spread=spread))
        self.under_migration = set()
        for row in self.ac.list_traits(code=self.co.trait_exchange_under_migration):
            if row['entity_id'] in self.accountid2name:
                self.under_migration.add(self.accountid2name[row['entity_id']])
        self.logger.debug("Accounts under migration: %d",
                          len(self.under_migration))

        #
        # Find all users with relevant spread
        #
        tmp_ret = {}
        for row in self.ac.search(spread=spread):
            # Don't sync accounts that are being migrated (exchange)
            if row['name'] in self.under_migration:
                self.logger.debug("Account %s being migrated in exchange."
                                  " Not syncing. ", row['name'])
                continue

            tmp_ret[int(row['account_id'])] = {
                'Exchange': False,
                'msExchPoliciesExcluded': cereconf.AD_EX_POLICIES_EXCLUDED,
                'msExchHideFromAddressLists':
                cereconf.AD_EX_HIDE_FROM_ADDRESS_LIST,
                'TEMPownerId': row['owner_id'],
                'TEMPuname': row['name'],
                'ACCOUNTDISABLE': False,
                'proxyAddresses': [],
                'extensionAttribute1': '',
                'extensionAttribute2': '',
                'extensionAttribute3': ''}
        self.logger.info("Fetched %i accounts with spread %s"
                         % (len(tmp_ret), spread))

        set1 = set(tmp_ret.keys())
        set2 = set([row['account_id'] for row in
                    list(self.ac.search(spread=exchange_spread))])
        set_res = set1.intersection(set2)
        for row_account_id in set_res:
            tmp_ret[int(row_account_id)]['Exchange'] = True
        self.logger.info("Fetched %i accounts with both spread %s and %s" %
                         (len(set_res), spread, exchange_spread))

        #
        # Remove/mark quarantined users
        #
        self.logger.debug("..filtering quarantined users..")
        self._filter_quarantines(tmp_ret)
        self.logger.info("%i accounts with spread %s after filter"
                         % (len(tmp_ret), spread))

        #
        # Set person names
        #
        self.logger.debug("..setting names..")
        pid2names = {}
        for row in self.person.search_person_names(
                source_system=self.co.system_cached,
                name_variant=[self.co.name_first,
                              self.co.name_last]):
            pid2names.setdefault(int(row['person_id']), {})[
                int(row['name_variant'])] = row['name']
        for v in tmp_ret.values():
            names = pid2names.get(v['TEMPownerId'])
            if names:
                firstName = unicode(names.get(int(self.co.name_first), ''),
                                    'ISO-8859-1')
                lastName = unicode(names.get(int(self.co.name_last), ''),
                                   'ISO-8859-1')
                v['givenName'] = firstName.strip()
                v['sn'] = lastName.strip()
                v['displayName'] = "%s %s" % (firstName, lastName)
        self.logger.info("Fetched %i person names" % len(pid2names))

        #
        # Set contact info: phonenumber and title
        #
        self.logger.debug("..setting contact info..")
        self._update_contact_info(tmp_ret)

        #
        # Set extensionAttributes with affiliations
        #
        self.logger.debug("..setting extensionAttributes with affiliations..")
        self._update_extensionAttributes(tmp_ret)

        #
        # Indexing user dict on username instead of entity id
        #
        userdict_ret = {}
        for k, v in tmp_ret.iteritems():
            userdict_ret[v['TEMPuname']] = v
            v['account_id'] = k
            del(v['TEMPuname'])
            del(v['TEMPownerId'])

        #
        # Set mail info
        #
        self.logger.debug("..setting mail info..")
        self._update_mail_info(userdict_ret)

        #
        # Assign derived attributes
        #
        for k, v in userdict_ret.iteritems():
            # TODO: derive domain part from LDAP DC components
            v['userPrincipalName'] = k + "@ostfoldfk.no"
            v['mailNickname'] = k

        return userdict_ret

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
        return self.server.listObjects('user', True, search_ou)

    def write_sid(self, objtype, name, sid, dry_run):
        """Store AD object SID to cerebrum database for given user

        @param objtype: type of AD object
        @type objtype: String
        @param name: user name
        @type name: String
        @param sid: SID from AD
        @type sid: String
        """
        # husk aa definere AD som kildesystem
        # TBD: Check if we create a new object for a entity that already
        # have a externalid_accountsid defined in the db and delete old?
        self.logger.debug(
            "Writing Sid for %s %s to database" %
            (objtype, name))
        if objtype == 'account' and not dry_run:
            self.ac.clear()
            self.ac.find_by_name(name)
            self.ac.affect_external_id(self.co.system_ad,
                                       self.co.externalid_accountsid)
            self.ac.populate_external_id(self.co.system_ad,
                                         self.co.externalid_accountsid, sid)
            self.ac.write_db()

    def perform_changes(self, changelist, dry_run, store_sid):
        """
        Binds to AD object and perform changes such as
        updates to attributes or move and/or disabling.

        @param changelist: user name -> changes mapping
        @type changelist: array of dict
        @param dry_run: Flag
        @param store_sid: Flag
        """
        for chg in changelist:
            self.logger.debug("Process change: %s" % repr(chg))
            if chg['type'] == 'create_object':
                self.create_object(chg, dry_run, store_sid)
            else:
                ret = self.run_cmd('bindObject', dry_run,
                                   chg['distinguishedName'])
                if not ret[0]:
                    self.logger.warning("bindObject on %s failed: %r" %
                                       (chg['distinguishedName'], ret))
                else:
                    exec('self.' + chg['type'] + '(chg, dry_run)')

    def create_object(self, chg, dry_run, store_sid):
        """
        Creates AD account object and populates given attributes

        @param chg: account_id -> account info mapping
        @type chg: dict
        @param dry_run: Flag to decide if changes arecommited to AD and Cerebrum
        """
        ou = chg.get("OU", self.get_default_ou())
        ret = self.run_cmd('createObject', dry_run, 'User', ou,
                           chg['sAMAccountName'])
        if not ret[0]:
            self.logger.warning("create user %s failed: %r",
                                chg['sAMAccountName'], ret)
        else:
            self.logger.info("created user %s" % ret)
            if store_sid:
                self.write_sid(
                    'account',
                    chg['sAMAccountName'],
                    ret[2],
                    dry_run)
            self.ac.clear()
            self.ac.find_by_name(str(chg['sAMAccountName']))
            pw = unicode(
                self.ac.get_account_authentication(
                    self.co.auth_type_plaintext),
                'iso-8859-1')
            ret = self.run_cmd('setPassword', dry_run, pw)
            if not ret[0]:
                self.logger.warning("setPassword on %s failed: %s",
                                    chg['sAMAccountName'], ret)
            else:
                # Important not to enable a new account if setPassword
                # fail, it will have a blank password.
                uname = ""
                del chg['type']
                if chg.has_key('distinguishedName'):
                    del chg['distinguishedName']
                if chg.has_key('sAMAccountName'):
                    uname = chg['sAMAccountName']
                    del chg['sAMAccountName']
                # Setting default for undefined AD_ACCOUNT_CONTROL values.
                for acc, value in cereconf.AD_ACCOUNT_CONTROL.items():
                    if not chg.has_key(acc):
                        chg[acc] = value
                ret = self.run_cmd('putProperties', dry_run, chg)
                if not ret[0]:
                    self.logger.warning("putproperties on user %s failed: %r",
                                        uname, ret)
                ret = self.run_cmd('setObject', dry_run)
                if not ret[0]:
                    self.logger.warning(
                        "setObject on %s failed: %r",
                        uname,
                        ret)

    def compare(self, delete_users, cerebrumusrs, adusrs, exch_users):
        """
        Check if any values for account need be updated in AD

        @param cerebrumusers: account_id -> account info mapping
        @type cerebrumusers: dict
        @param adusers: account_id -> account info mapping
        @type adusers: dict
        @param delete_users: Delete or move unwanted users
        @type delete_users: Flag
        @rtype: list
        @return: a list over dicts with changes to AD objects
        """
        # Keys in dict from cerebrum must match fields to be populated in AD.

        changelist = []

        for usr, dta in adusrs.iteritems():
            # Ignore accounts under migration:
            if usr in self.under_migration:
                self.logger.debug2("Ignoring migration user: %s", usr)
                continue

            changes = {}
            if cerebrumusrs.has_key(usr):
                # User is both places, we want to check correct data.

                # Checking for correct OU.
                ou = cerebrumusrs.get("OU", self.get_default_ou())
                if adusrs[usr]['distinguishedName'] != 'CN=%s,%s' % (usr, ou):
                    changes['type'] = 'move_object'
                    changes['OU'] = ou
                    changes['distinguishedName'] = \
                        adusrs[usr]['distinguishedName']
                    # Submit list and clean.
                    changelist.append(changes)
                    changes = {}

                for attr in cereconf.AD_ATTRIBUTES:
                    # Catching special cases.
                    # xmlrpclib appends chars [' and '] to
                    # this attribute for some reason
                    if attr == 'msExchPoliciesExcluded':
                        if adusrs[usr].has_key('msExchPoliciesExcluded'):
                            tempstring = str(adusrs[usr]
                                             ['msExchPoliciesExcluded']).replace("['", "")
                            tempstring = tempstring.replace("']", "")
                            if (tempstring != cerebrumusrs[usr]
                               ['msExchPoliciesExcluded']):
                                changes['msExchPoliciesExcluded'] = \
                                    cerebrumusrs[usr]['msExchPoliciesExcluded']
                        else:
                            changes['msExchPoliciesExcluded'] = \
                                cerebrumusrs[usr]['msExchPoliciesExcluded']
                    elif attr == 'Exchange':
                        pass
                    # Treating general cases
                    else:
                        if cerebrumusrs[usr].has_key(attr) and \
                                adusrs[usr].has_key(attr):
                            if isinstance(cerebrumusrs[usr][attr], (list)):
                                # Multivalued, it is assumed that a
                                # multivalue in cerebrumusrs always is
                                # represented as a list.
                                Mchange = False

                                if (isinstance(adusrs[usr][attr],
                                               (str, int, long, unicode))):
                                    # Transform single-value to a list for
                                    # comp.
                                    val2list = []
                                    val2list.append(adusrs[usr][attr])
                                    adusrs[usr][attr] = val2list

                                for val in cerebrumusrs[usr][attr]:
                                    if val not in adusrs[usr][attr]:
                                        Mchange = True

                                if Mchange:
                                    changes[attr] = cerebrumusrs[usr][attr]

                            else:
                                if adusrs[usr][attr] != cerebrumusrs[usr][attr]:
                                    changes[attr] = cerebrumusrs[usr][attr]
                                    self.logger.debug2("Change %s: '%s'->'%s'",
                                                       attr,
                                                       adusrs[usr][attr],
                                                       cerebrumusrs[usr][attr])
                        else:
                            if cerebrumusrs[usr].has_key(attr):
                                # A blank value in cerebrum and <not
                                # set> in AD -> do nothing.
                                if cerebrumusrs[usr][attr] != "":
                                    changes[attr] = cerebrumusrs[usr][attr]
                            elif adusrs[usr].has_key(attr):
                                # HomeMTA should not be removed for those we
                                # don't know about, as they are most likely
                                # under Exchange 2007 is about to be migrated.
                                if attr == 'homeMTA':
                                    pass # Do nothing
                                else:
                                    # Delete value
                                    changes[attr] = ''

                for acc, value in cereconf.AD_ACCOUNT_CONTROL.items():

                    if cerebrumusrs[usr].has_key(acc):
                        if adusrs[usr].has_key(acc) and \
                                adusrs[usr][acc] == cerebrumusrs[usr][acc]:
                            pass
                        else:
                            changes[acc] = cerebrumusrs[usr][acc]
                    else:
                        if adusrs[usr].has_key(acc) and adusrs[usr][acc] == \
                                value:
                            pass
                        else:
                            changes[acc] = value

                # Submit if any changes.
                if changes:
                    changes['distinguishedName'] = 'CN=%s,%s' % (usr, ou)
                    changes['type'] = 'alter_object'
                    exchange_change = False
                    for attribute in changes:
                        if attribute in cereconf.AD_EXCHANGE_RELATED_ATTRIBUTES:
                            exchange_change = True
                    if exchange_change and cerebrumusrs[usr]['Exchange']:
                        exch_users.append(usr)
                        self.logger.info(
                            "Added to run Update-Recipient list: %s" %
                            usr)

                # after processing we delete from array.
                del cerebrumusrs[usr]

            else:
                # Account not in Cerebrum, but in AD.
                if [s for s in cereconf.AD_DO_NOT_TOUCH if
                        adusrs[usr]['distinguishedName'].upper().find(s.upper()) >= 0]:
                    pass
                elif (adusrs[usr]['distinguishedName'].upper().find(
                        cereconf.AD_PW_EXCEPTION_OU.upper()) >= 0):
                    # Account do not have AD_spread, but is in AD to
                    # register password changes, do nothing.
                    pass
                else:
                    # ac.is_deleted() or ac.is_expired() pluss a small rest of
                    # accounts created in AD, but that do not have AD_spread.
                    if bool(delete_users):
                        changes['type'] = 'delete_object'
                        changes['distinguishedName'] = (adusrs[usr]
                                                        ['distinguishedName'])
                    else:
                        # Disable account.
                        if not bool(adusrs[usr]['ACCOUNTDISABLE']):
                            changes['distinguishedName'] = (adusrs[usr]
                                   ['distinguishedName'])
                            changes['type'] = 'alter_object'
                            changes['ACCOUNTDISABLE'] = True
                            # commit changes
                            changelist.append(changes)
                            changes = {}
                        # Hide Account from Exchange
                        hideAddr = False
                        if adusrs[usr].has_key('msExchHideFromAddressLists'):
                            if not bool(adusrs[usr]['msExchHideFromAddressLists']):
                                hideAddr = True
                        else:
                            hideAddr = True
                        if hideAddr:
                            changes['distinguishedName'] = (adusrs[usr]
                                   ['distinguishedName'])
                            changes['type'] = 'alter_object'
                            changes['msExchHideFromAddressLists'] = True
                            # commit changes
                            changelist.append(changes)
                            changes = {}
                            if (not usr in exch_users) and (cerebrumusrs.has_key(usr) and cerebrumusrs[usr]['Exchange']):
                                exch_users.append(usr)
                                self.logger.info(
                                    "Added to run Update-Recipient list: %s" %
                                    usr)
                        # Moving account.
                        if (adusrs[usr]['distinguishedName'] !=
                            "CN=%s,OU=%s,%s" %
                                (usr, cereconf.AD_LOST_AND_FOUND, self.ad_ldap)):
                            changes['type'] = 'move_object'
                            changes['distinguishedName'] = (adusrs[usr]
                                   ['distinguishedName'])
                            changes['OU'] = ("OU=%s,%s" %
                                             (cereconf.AD_LOST_AND_FOUND, self.ad_ldap))

            # Finished processing user, register changes if any.
            if changes:
                changelist.append(changes)

        # The remaining items in cerebrumusrs is not in AD, create user.
        for cusr, cdta in cerebrumusrs.items():
            changes = {}
            # New user, create.
            if cerebrumusrs[cusr]['Exchange']:
                exch_users.append(cusr)
                self.logger.info(
                    "Added to run Update-Recipient list: %s" %
                    cusr)
            changes = cdta
            changes['type'] = 'create_object'
            changes['sAMAccountName'] = cusr
            if changes.has_key('Exchange'):
                del changes['Exchange']
            changelist.append(changes)

        return changelist

    def update_Exchange(self, dry_run, exch_users):
        """
        Telling the AD-service to start the Windows Power Shell command
        Update-Recipient on object in order to prep them for Exchange.

        @param exch_users : user to run command on
        @type  exch_users: list
        @param dry_run : Flag
        """
        self.logger.debug(
            "Sleeping for 5 seconds to give ad-ldap time to update")
        time.sleep(5)
        for usr in exch_users:
            self.logger.info("Running Update-Recipient for user '%s'"
                             " against Exchange" % usr)
            if cereconf.AD_DC:
                ret = self.run_cmd(
                    'run_UpdateRecipient',
                    dry_run,
                    usr,
                    cereconf.AD_DC)
            else:
                ret = self.run_cmd('run_UpdateRecipient', dry_run, usr)
            if not ret[0]:
                self.logger.warning("run_UpdateRecipient on %s failed: %r",
                                    usr, ret)
        self.logger.info("Ran Update-Recipient against Exchange for %i users",
                         len(exch_users))

    def full_sync(self, delete=False, spread=None,
                  dry_run=True, store_sid=False, exchange_spread=None):

        self.logger.info("Starting user-sync(spread = %s, exchange_spread = %s, delete = %s, dry_run = %s, store_sid = %s)" %
                        (spread, exchange_spread, delete, dry_run, store_sid))

        # Fetch cerebrum data.
        self.logger.debug("Fetching cerebrum data...")
        cerebrumdump = self.fetch_cerebrum_data(spread, exchange_spread)
        self.logger.info("Fetched %i cerebrum users" % len(cerebrumdump))

        # Fetch AD-data.
        self.logger.debug("Fetching AD data...")
        addump = self.fetch_ad_data(self.ad_ldap)
        if addump:
            self.logger.info("Fetched %i ad-users" % len(addump))
        else:
            self.logger.info("Fetched 0 ad-users")

        # compare cerebrum and ad-data.
        exch_users = []
        changelist = self.compare(delete, cerebrumdump, addump, exch_users)
        self.logger.info("Found %i number of changes" % len(changelist))
        self.logger.info(
            "Will run Update-Recipient against Exchange for %i users",
            len(exch_users))

        # Perform changes.
        self.perform_changes(changelist, dry_run, store_sid)

        # updating Exchange
        self.logger.info(
            "Will run Update-Recipient against Exchange for %i users",
            len(exch_users))
        self.update_Exchange(dry_run, exch_users)

        # Cleaning up.
        addump = None
        cerebrumdump = None

        # Commiting changes to DB (SID external ID) or not.
        if dry_run:
            self.db.rollback()
        else:
            self.db.commit()

        self.logger.info("Finished user-sync")


#
class ADFullGroupSync(ADutilMixIn.ADgroupUtil):

    def fetch_cerebrum_data(self, spread):
        """
        Fetch relevant cerebrum data for groups of the three
        group types that shall be exported to AD. They are
        assigned OU according to group type.

        @rtype: dict
        @return: a dict {grpname: {'adAttrib': 'value'}} for all groups
        of relevant spread. Typical attributes::

        'displayName': String,          # gruppenavn
        'msExchPoliciesExcluded' : int, # Exchange verdi
        'displayNamePrintable' : String # gruppenavn
        'description' : String          # beskrivelse
        'groupType' : Int               # type gruppe
        'OU' : String                   # OU for gruppe i AD
        """
        #
        # Get groups with spread
        #
        grp_dict = {}
        spread_res = list(
            self.group.search(spread=int(self.co.Spread(spread))))
        for row in spread_res:
            gname = cereconf.AD_GROUP_PREFIX + \
                unicode(row["name"], 'ISO-8859-1')
            # sAMAccount cannot contain certain symbols so we manipulate names
            # use '#' instead of ':'
            gname = gname.replace(':', '#')
            # use '_' for all other illegal chars
            for char in ['/', '\\', '[', ']', ';', '|', '=', ',', '+', '?', '<', '>', '"', '*']:
                gname = gname.replace(char, '_')
            grp_dict[gname] = {
                'groupType': cereconf.AD_GROUP_TYPE,
                'description': unicode(row["name"], 'ISO-8859-1'),
                'msExchPoliciesExcluded': cereconf.AD_EX_POLICIES_EXCLUDED,
                'grp_id': row["group_id"],
                'displayName': gname,
                'displayNamePrintable': gname,
                'OU': self.get_default_ou(),
                'crb_gname': unicode(row["name"], 'ISO-8859-1')
            }
        self.logger.info("Fetched %i groups with spread %s",
                         len(grp_dict), spread)

        #
        # Assign OU to groups based on entity_traits
        #
        for k, v in grp_dict.items():
            self.group.clear()
            try:
                self.group.find(v['grp_id'])
            except Errors.NotFoundError:
                continue
            if self.group.get_trait(self.co.trait_shdw_undv):
                v['OU'] = "OU=UNDV,OU=Groups,%s" % self.ad_ldap
            elif self.group.get_trait(self.co.trait_shdw_kls):
                v['OU'] = "OU=BASIS,OU=Groups,%s" % self.ad_ldap
            elif self.group.get_trait(self.co.trait_auto_aff):
                v['OU'] = "OU=VIRK,OU=Groups,%s" % self.ad_ldap
            else:
                del grp_dict[k]
                self.logger.info("Error getting group type for group: "
                                 "%s (id:%s). Not syncing this group"
                                 % (k, v['grp_id']))

        return grp_dict

    def delete_and_filter(
            self, ad_dict, cerebrum_dict, dry_run, delete_groups):
        """Filter out groups in AD that shall not be synced from cerebrum

        Goes through the dict of the groups in AD, and checks if it is
        a group that shall be synced from cerebrum. If it is not we remove
        it from the dict so we will pay no attention to the group when we sync,
        but only after checking if it is in our OU. If it is we delete it.

        @param ad_dict : account_id -> account info mapping
        @type ad_dict : dict
        @param cerebrum_dict : account_id -> account info mapping
        @type cerebrum_dict : dict
        @param delete_users: Delete or not unwanted groups
        @type delete_users: Flag
        @param dry_run: Flag
        """

        for grp_name, v in ad_dict.items():
            if not cerebrum_dict.has_key(grp_name):
                if self.ad_ldap in ad_dict[grp_name]['OU']:
                    match = False
                    for dont in cereconf.AD_DO_NOT_TOUCH:
                        if dont.upper() in ad_dict[grp_name]['OU'].upper():
                            match = True
                            break
                    # an unknown group in OUs under our control
                    # and not i DO_NOT_TOUCH -> delete
                    if not match:
                        if not delete_groups:
                            self.logger.debug("delete is False."
                                              "Don't delete group: %s", grp_name)
                        else:
                            self.logger.info(
                                "delete_groups = %s, deleting group %s",
                                delete_groups, grp_name)
                            self.run_cmd('bindObject', dry_run,
                                         ad_dict[grp_name]['distinguishedName'])
                            self.delete_object(ad_dict[grp_name], dry_run)
                # does not concern us (anymore), delete from dict.
                del ad_dict[grp_name]

    def fetch_ad_data(self):
        """Get list of groups with  attributes from AD

        Dict with data from AD with sAMAccountName as index:
        'displayName': String,          # gruppenavn
        'msExchPoliciesExcluded' : int, # Exchange verdi
        'displayNamePrintable' : String # gruppenavn
        'description' : String          # beskrivelse
        'groupType' : Int               # type gruppe
        'distinguishedName' : String    # AD-LDAP path to object
        'OU' : String                   # Full LDAP path to OU of object in AD

        @returm ad_dict : group name -> group info mapping
        @type ad_dict : dict
        """

        self.server.setGroupAttributes(cereconf.AD_GRP_ATTRIBUTES)
        search_ou = self.ad_ldap
        ad_dict = self.server.listObjects('group', True, search_ou)
        # extracting OU from distinguished name
        if ad_dict:
            for grp in ad_dict:
                part = ad_dict[grp]['distinguishedName'].split(",", 1)
                if part[1] and part[0].find("CN=") > -1:
                    ad_dict[grp]['OU'] = part[1]
                else:
                    ad_dict[grp]['OU'] = self.get_default_ou()
                # descritpion is list from AD. Only want to check first string
                # with ours
                if ad_dict[grp].has_key('description'):
                    if isinstance(ad_dict[grp]['description'], (list)):
                        ad_dict[
                            grp][
                                'description'] = ad_dict[
                                    grp][
                                        'description'][
                                            0]
        else:
            ad_dict = {}
        return ad_dict

    def sync_group_info(self, ad_dict, cerebrum_dict, dry_run):
        """ Sync group info with AD

        Check if any values about groups other than group members
        should be updated in AD

        @param ad_dict : account_id -> account info mapping
        @type ad_dict : dict
        @param cerebrum_dict : account_id -> account info mapping
        @type cerebrum_dict : dict
        @param dry_run: Flag
        """
        # Keys in dict from cerebrum must match fields to be populated in AD.
        # Already removed groups from ad_dict not i cerebrum_dict
        changelist = []

        for grp in cerebrum_dict:
            changes = {}
            if ad_dict.has_key(grp):
                # group in both places, we want to check correct data

                # Checking for correct OU.
                if cerebrum_dict[grp].has_key('OU'):
                    ou = cerebrum_dict[grp]['OU']
                else:
                    ou = self.get_default_ou()
                if ad_dict[grp]['OU'] != ou:
                    changes['type'] = 'move_object'
                    changes['OU'] = ou
                    changes['distinguishedName'] = \
                        ad_dict[grp]['distinguishedName']
                    # Submit list and clean.
                    changelist.append(changes)
                    changes = {}

                # Comparing group info
                for attr in cereconf.AD_GRP_ATTRIBUTES:
                    # Catching special cases.
                    # xmlrpclib appends chars [' and ']
                    # to this attribute for some reason
                    if attr == 'msExchPoliciesExcluded':
                        if ad_dict[grp].has_key('msExchPoliciesExcluded'):
                            tempstring = str(ad_dict[grp]
                                             ['msExchPoliciesExcluded']).replace("['", "")
                            tempstring = tempstring.replace("']", "")
                            if (tempstring == cerebrum_dict[grp]
                                    ['msExchPoliciesExcluded']):
                                pass
                            else:
                                changes[
                                    'msExchPoliciesExcluded'] = cerebrum_dict[
                                        grp][
                                            'msExchPoliciesExcluded']
                        else:
                            changes[
                                'msExchPoliciesExcluded'] = cerebrum_dict[
                                    grp][
                                        'msExchPoliciesExcluded']
                    elif attr == 'member':
                        pass
                    # Treating general cases
                    else:
                        if cerebrum_dict[grp].has_key(attr) and \
                                ad_dict[grp].has_key(attr):
                            if isinstance(cerebrum_dict[grp][attr], (list)):
                                # Multivalued, it is assumed that a
                                # multivalue in cerebrumusrs always is
                                # represented as a list.
                                Mchange = False

                                if (isinstance(ad_dict[grp][attr],
                                               (str, int, long, unicode))):
                                    # Transform single-value to a list for
                                    # comp.
                                    val2list = []
                                    val2list.append(ad_dict[grp][attr])
                                    ad_dict[grp][attr] = val2list

                                for val in cerebrum_dict[grp][attr]:
                                    if val not in ad_dict[grp][attr]:
                                        Mchange = True

                                if Mchange:
                                    changes[attr] = cerebrum_dict[grp][attr]
                            else:
                                if ad_dict[grp][attr] != cerebrum_dict[grp][attr]:
                                    changes[attr] = cerebrum_dict[grp][attr]
                        else:
                            if cerebrum_dict[grp].has_key(attr):
                                # A blank value in cerebrum and <not
                                # set> in AD -> do nothing.
                                if cerebrum_dict[grp][attr] != "":
                                    changes[attr] = cerebrum_dict[grp][attr]
                            elif ad_dict[grp].has_key(attr):
                                # Delete value
                                changes[attr] = ''

                # Submit if any changes.
                if len(changes):
                    changes['distinguishedName'] = 'CN=%s,%s' % (grp, ou)
                    changes['type'] = 'alter_object'
                    changelist.append(changes)
                    changes = {}
            else:
                # The remaining items in cerebrum_dict is not in AD, create
                # group.
                changes = {}
                changes = copy.copy(cerebrum_dict[grp])
                changes['type'] = 'create_object'
                changes['sAMAccountName'] = grp
                del changes['grp_id']
                changelist.append(changes)

        return changelist

    def get_default_ou(self):
        """
        Return default OU for groups.
        """
        return "OU=%s,%s" % (cereconf.AD_GROUP_OU, self.ad_ldap)

    def write_sid(self, objtype, crbname, sid, dry_run):
        """
        Store AD object SID to cerebrum database for given group

        @param objtype: type of AD object
        @type objtype: String
        @param name: group name
        @type name: String
        @param sid: SID from AD
        @type sid: String
        """
        # TBD: Check if we create a new object for a entity that already
        # have an externalid_groupsid defined in the db and delete old?
        self.logger.debug(
            "Writing Sid for %s %s to database" %
            (objtype, crbname))
        if objtype == 'group' and not dry_run:
            self.group.clear()
            self.group.find_by_name(crbname)
            self.group.affect_external_id(self.co.system_ad,
                                          self.co.externalid_groupsid)
            self.group.populate_external_id(self.co.system_ad,
                                            self.co.externalid_groupsid, sid)
            self.group.write_db()

    def perform_changes(self, changelist, dry_run, store_sid):
        """
        Binds to AD object and perform changes such as
        updates to attributes or move or deleting.

        @param changelist: group name -> changes mapping
        @type changelist: array of dict
        @param dry_run: Flag
        @param store_sid: Flag
        """
        for chg in changelist:
            self.logger.debug("Process change: %s" % repr(chg))
            if chg['type'] == 'create_object':
                self.create_object(chg, dry_run, store_sid)
            else:
                ret = self.run_cmd('bindObject', dry_run,
                                   chg['distinguishedName'])
                if not ret[0]:
                    self.logger.warning("bindObject on %s failed: %r" %
                                       (chg['distinguishedName'], ret))
                else:
                    exec('self.' + chg['type'] + '(chg, dry_run)')

    def create_object(self, chg, dry_run, store_sid):
        """
        Creates AD group object and populates given attributes

        @param chg: group_name -> group info mapping
        @type chg: dict
        @param dry_run: Flag
        @param store_sid: Flag
        """
        ou = chg.get("OU", self.get_default_ou())
        self.logger.info('Create group %s', chg)
        ret = self.run_cmd('createObject', dry_run, 'Group', ou,
                           chg['sAMAccountName'])
        if not ret[0]:
            self.logger.warning("create group %s failed: %r",
                                chg['sAMAccountName'], ret[1])
        elif not dry_run:
            if store_sid:
                self.write_sid('group', chg['crb_gname'], ret[2], dry_run)
            del chg['type']
            del chg['OU']
            del chg['crb_gname']
            gname = ''
            if chg.has_key('distinguishedName'):
                del chg['distinguishedName']
            if chg.has_key('sAMAccountName'):
                gname = chg['sAMAccountName']
                del chg['sAMAccountName']
            ret = self.server.putGroupProperties(chg)
            if not ret[0]:
                self.logger.warning("putproperties on group %s failed: %r",
                                    gname, ret)
            else:
                ret = self.run_cmd('setObject', dry_run)
                if not ret[0]:
                    self.logger.warning("setObject on %s failed: %r",
                                        gname, ret)

    def alter_object(self, chg, dry_run):
        """
        Binds to AD group objects and updates given attributes

        @param chg: group_name -> group info mapping
        @type chg: dict
        @param dry_run: Flag
        """
        distName = chg['distinguishedName']
        # Already binded
        del chg['type']
        del chg['distinguishedName']

        # ret = self.run_cmd('putGroupProperties', dry_run, chg)
        # run_cmd in ADutilMixIn.py not written for group updates
        if not dry_run:
            ret = self.server.putGroupProperties(chg)
        else:
            ret = (True, 'putGroupProperties')
        if not ret[0]:
            self.logger.warning("putGroupProperties on %s failed: %r",
                                distName, ret)
        else:
            ret = self.run_cmd('setObject', dry_run)
            if not ret[0]:
                self.logger.warning("setObject on %s failed: %r",
                                    distName, ret)

    def compare_members(self, cerebrum_dict, ad_dict,
                        group_spread, user_spread, dry_run, sendDN_boost):
        """
        Update group memberships in AD by comparing memberlists for groups
        in AD and Cerebrum.

        @param cerebrum_dict : group_name -> group info mapping
        @type cerebrum_dict : dict
        @param ad_dict : group_name -> group info mapping
        @type ad_dict : dict
        @param spread: ad group spread for a domain
        @type spread: _SpreadCode
        @param user_spread: ad account spread for a domain
        @type user_spread: _SpreadCode
        @param dry_run: Flag
        @param sendDN_boost: Flag to determine if we should use fully qualified
                             domain named for users
        """
        # sendDN_boost is always "on" for now, i.e. always using full dn names
        # for members

        entity2name = dict([(x["entity_id"], x["entity_name"]) for x in
                            self.group.list_names(self.co.account_namespace)])
        entity2name.update([(x["entity_id"], x["entity_name"]) for x in
                            self.group.list_names(self.co.group_namespace)])

        for grp in cerebrum_dict:
            if cerebrum_dict[grp].has_key('grp_id'):
                grp_id = cerebrum_dict[grp]['grp_id']
                self.logger.debug("Comparing group %s" % grp)

                # TODO: How to treat quarantined users???, some exist in AD,
                # others do not. They generate errors when not in AD. We still
                # want to update group membership if in AD.
                members = list()
                for usr in (self.group.search_members(
                    group_id=grp_id,
                            member_spread=int(self.co.Spread(user_spread)))):
                    user_id = usr["member_id"]
                    if user_id not in entity2name:
                        self.logger.debug("Missing name for account id=%s",
                                          user_id)
                        continue
                    members.append(("CN=%s,OU=%s,%s" % (entity2name[user_id],
                                                        cereconf.AD_USER_OU,
                                                        self.ad_ldap)))

                for grp in (self.group.search_members(
                        group_id=grp_id,
                        member_spread=int(self.co.Spread(group_spread)))):
                    group_id = grp["member_id"]
                    if group_id not in entity2name:
                        self.logger.debug(
                            "Missing name for group id=%s",
                            group_id)
                        continue
                    members.append(
                        ("CN=%s%s,OU=%s,%s" % (cereconf.AD_GROUP_PREFIX,
                                               entity2name[
                                               group_id],
                                               cereconf.AD_GROUP_OU,
                                               self.ad_ldap)))

                members_in_ad = ad_dict.get(grp, {}).get("member", [])
                members_add = [
                    userdn for userdn in members if userdn not in members_in_ad]
                members_remove = [
                    userdn for userdn in members_in_ad if userdn not in members]

                if members_add or members_remove:
                    dn = self.server.findObject(grp)
                    if not dn:
                        self.logger.warning(
                            "Not able to bind to group %s in AD",
                            grp)
                    elif dry_run:
                        self.logger.debug("Dryrun: don't sync members")
                    else:
                        self.server.bindObject(dn)
                        # True in these functions means sendDN_boost on.
                        if members_add:
                            self.logger.debug(
                                "Adding members to group %s (%s)",
                                grp, members_add)
                            res = self.server.addMembers(members_add, True)
                            if not res[0]:
                                self.logger.warning("Adding members for group %s failed: %r" %
                                                    (dn, res[1:]))
                        if members_remove:
                            self.logger.debug(
                                "Removing members from group %s (%s)",
                                grp, members_remove)
                            res = self.server.removeMembers(
                                members_remove, True)
                            if not res[0]:
                                self.logger.warning("Removing members for group %s failed: %r" %
                                                    (dn, res[1:]))
            else:
                self.logger.warning("Group %s has no group_id. Not syncing members." %
                                   (grp))

    def sync_group_members(
            self, cerebrum_dict, group_spread, user_spread, dry_run, sendDN_boost):
        """
        Update group memberships in AD

        @param cerebrum_dict : group_name -> group info mapping
        @type cerebrum_dict : dict
        @param spread: ad group spread for a domain
        @type spread: _SpreadCode
        @param user_spread: ad account spread for a domain
        @type user_spread: _SpreadCode
        @param dry_run: Flag
        """
        # To reduce traffic, we send current list of groupmembers to AD, and the
        # server ensures that each group have correct members.

        entity2name = dict([(x["entity_id"], x["entity_name"]) for x in
                           self.group.list_names(self.co.account_namespace)])
        entity2name.update([(x["entity_id"], x["entity_name"]) for x in
                           self.group.list_names(self.co.group_namespace)])

        for grp in cerebrum_dict:
            if cerebrum_dict[grp].has_key('grp_id'):
                grp_name = grp.replace(cereconf.AD_GROUP_PREFIX, "")
                grp_id = cerebrum_dict[grp]['grp_id']
                self.logger.debug("Sync group %s" % grp_name)

                # TODO: How to treat quarantined users???, some exist in AD,
                # others do not. They generate errors when not in AD. We still
                # want to update group membership if in AD.
                members = list()
                for usr in (self.group.search_members(
                        group_id=grp_id,
                        member_spread=int(self.co.Spread(user_spread)))):
                    user_id = usr["member_id"]
                    if user_id not in entity2name:
                        self.logger.debug("Missing name for account id=%s",
                                          user_id)
                        continue
                    if sendDN_boost:
                        members.append(
                            ("CN=%s,OU=%s,%s" % (entity2name[user_id],
                                                 cereconf.AD_USER_OU,
                                                 self.ad_ldap)))
                    else:
                        members.append(entity2name[user_id])
                    self.logger.debug(
                        "Try to sync member account id=%s, name=%s",
                        user_id, entity2name[user_id])

                for grp in (self.group.search_members(
                        group_id=grp_id,
                        member_spread=int(self.co.Spread(group_spread)))):
                    group_id = grp["member_id"]
                    if group_id not in entity2name:
                        self.logger.debug(
                            "Missing name for group id=%s",
                            group_id)
                        continue
                    if sendDN_boost:
                        members.append(
                            ("CN=%s%s,OU=%s,%s" % (cereconf.AD_GROUP_PREFIX,
                                                   entity2name[
                                                   group_id],
                                                   cereconf.AD_GROUP_OU,
                                                   self.ad_ldap)))
                    else:
                        members.append('%s%s' % (cereconf.AD_GROUP_PREFIX,
                                                 entity2name[group_id]))
                    self.logger.debug(
                        "Try to sync member group id=%s, name=%s",
                        group_id, entity2name[group_id])

                dn = self.server.findObject('%s%s' %
                                            (cereconf.AD_GROUP_PREFIX, grp_name))
                if not dn:
                    self.logger.debug("unknown group: %s%s",
                                      cereconf.AD_GROUP_PREFIX, grp_name)
                elif dry_run:
                    self.logger.debug("Dryrun: don't sync members")
                else:
                    self.server.bindObject(dn)
                    if sendDN_boost:
                        res = self.server.syncMembers(members, True, False)
                    else:
                        res = self.server.syncMembers(members, False, False)
                    if not res[0]:
                        self.logger.warning("syncMembers %s failed for:%r" %
                                            (dn, res[1:]))
            else:
                self.logger.warning("Group %s has no group_id. Not syncing members." %
                                    (grp))

    def full_sync(self, delete=False, dry_run=True, store_sid=False,
                  user_spread=None, group_spread=None, sendDN_boost=False,
                  full_membersync=False):

        self.logger.info("Starting group-sync(group_spread = %s, "
                         "user_spread = %s, delete = %s, dry_run = %s, "
                         "store_sid = %s, sendDN_boost = %s, "
                         "full_membersync = %s)" %
                         (group_spread, user_spread, delete, dry_run,
                          store_sid, sendDN_boost, full_membersync))

        # Fetch cerebrum data.
        self.logger.debug("Fetching cerebrum data...")
        cerebrumdump = self.fetch_cerebrum_data(group_spread)
        self.logger.info("Fetched %i cerebrum groups" % len(cerebrumdump))

        # Fetch AD data
        self.logger.debug("Fetching AD data...")
        addump = self.fetch_ad_data()
        self.logger.info("Fetched %i ad-groups" % len(addump))

        # Filter AD-list
        self.logger.debug("Filtering list of AD groups...")
        self.delete_and_filter(addump, cerebrumdump, dry_run, delete)
        self.logger.info("Updating %i ad-groups after filtering" % len(addump))

        # Compare groups and attributes (not members)
        self.logger.info("Syncing group info...")
        changelist = self.sync_group_info(addump, cerebrumdump, dry_run)

        # Perform changes
        self.perform_changes(changelist, dry_run, store_sid)

        # Syncing group members
        if full_membersync:
            self.logger.info(
                "Starting sync of group members using full member sync")
            self.sync_group_members(
                cerebrumdump,
                group_spread,
                user_spread,
                dry_run,
                sendDN_boost)
        else:
            self.logger.info(
                "Starting sync of group members using differential member sync")
            self.compare_members(
                cerebrumdump,
                addump,
                group_spread,
                user_spread,
                dry_run,
                sendDN_boost)

        # Cleaning up.
        addump = None
        cerebrumdump = None

        # Commiting changes to DB (SID external ID) or not.
        if dry_run:
            self.db.rollback()
        else:
            self.db.commit()

        self.logger.info("Finished group-sync")
