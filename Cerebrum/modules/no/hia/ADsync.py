#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2006-2011 University of Oslo, Norway
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

"""Module with functions for cerebrum export to Active Directory at UiA

Extends the functionality provided in the general AD-export module
ADutilMixIn.py to work with the setup at UiA with Active Directory
and Exchange 2007.
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

    # Default OU in AD. Could be set to override the returned value from
    # .get_default_ou():
    default_ou = None

    # What user OUs that should be affected by the sync. If set, only users in
    # these OUs will for instance be deactivated/deleted.
    only_ous = None

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
        from Cerebrum.modules.Email import EmailQuota
        equota = EmailQuota(self.db)

        # Find primary addresses and set mail attribute
        uname2primary_mail = self.ac.getdict_uname2mailaddr(
            filter_expired=True, primary_only=True)
        for uname, prim_mail in uname2primary_mail.iteritems():
            if user_dict.has_key(uname):
                if (user_dict[uname]['imap'] or user_dict[uname]['Exchange']):
                    user_dict[uname]['mail'] = prim_mail

        # Find all valid addresses and set proxyaddresses attribute
        uname2all_mail = self.ac.getdict_uname2mailaddr(
            filter_expired=True, primary_only=False)
        for uname, all_mail in uname2all_mail.iteritems():
            if user_dict.has_key(uname):
                if (user_dict[uname]['imap'] or user_dict[uname]['Exchange']):
                    user_dict[uname]['proxyAddresses'].insert(
                        0, ("SMTP:" + user_dict[uname]['mail']))
                    for alias_addr in all_mail:
                        if alias_addr == user_dict[uname]['mail']:
                            pass
                        else:
                            user_dict[uname]['proxyAddresses'].append(
                                ("smtp:" + alias_addr))

        # Set homeMDB and Quota-info for Exchange users
        # TBD: Will probably be slow with many Exchange users..
        for k, v in user_dict.iteritems():
            self.ac.clear()
            if v['Exchange']:
                try:
                    self.ac.find_by_name(k)
                except Errors.NotFoundError:
                    continue

                mdb_trait = self.ac.get_trait(self.co.trait_exchange_mdb)
                # Migrated users
                v['msExchHomeServerName'] = cereconf.AD_EX_HOME_SERVER
                v['homeMDB'] = "CN=%s,%s" % (mdb_trait["strval"],
                                             cereconf.AD_EX_HOME_MDB)

                equota.clear()
                equota.find_by_target_entity(v['entity_id'])
                try:
                    q_soft = equota.get_quota_soft()
                    q_hard = equota.get_quota_hard()
                except Errors.NotFoundError:
                    self.logger.warning("Error finding EmailQuota for "
                                        "accountid:%i. Setting default." % int(k))
                # set a default quota
                if (q_soft is None or q_hard is None):
                    self.logger.warning("Error getting EmailQuota for "
                                        "accountid:%i. Setting default." % int(k))
                    if q_soft is None:
                        q_soft = cereconf.AD_EX_QUOTA_SOFT_DEFAULT
                    if q_hard is None:
                        q_hard = cereconf.AD_EX_QUOTA_HARD_DEFAULT
                # Mailquota in Cerebrum is in MB, Exchange wants KB.
                # mDBStorageQuota is set to 90% of mDBOverQuotaLimit
                v['mDBOverHardQuotaLimit'] = q_hard * 1024
                v['mDBOverQuotaLimit'] = (v['mDBOverHardQuotaLimit']
                                          * q_soft // 100)
                v['mDBStorageQuota'] = v['mDBOverQuotaLimit'] * 90 // 100
                # We or Exchange shall decide quotas:
                v['mDBUseDefaults'] = cereconf.AD_EX_MDB_USE_DEFAULTS

    def _update_contact_info(self, user_dict):
        """Get contact info from Cerebrum and update the L{user_dict}
        directly.

        Retrieved info: phonenumber, mobile, SIP phone, title and addresses.
        Personal title takes precedence over work title.

        Note that only mobile numbers registered in SAP are used.

        @param user_dict: account_id -> account info mapping
        @type user_dict: dict
        """
        for ac_id, v in user_dict.iteritems():
            self.person.clear()
            try:
                self.person.find(v['TEMPownerId'])
            except Errors.NotFoundError:
                self.logger.debug("Getting contact info: Skipping user=%s,"
                                  "owner (id=%s) is not a person entity."
                                  % (v['TEMPuname'], v['TEMPownerId']))
                continue
            phones = self.person.get_contact_info(type=self.co.contact_phone)
            v['ipPhone'] = ''
            v['telephoneNumber'] = ''
            if phones:
                v['telephoneNumber'] = phones[0]['contact_value']
                # SIP phones: only last 4 digits in phone numbers, if the
                # phone number is in a defined SIP serie.
                if any(v['telephoneNumber'].startswith(pre) for pre in
                       ('37233', '38141', '38142')):
                    if ac_id == self.person.get_primary_account():
                        v['ipPhone'] = v['telephoneNumber'][-4:]

            # If person has a personal_title, it should be used;
            # otherwise go for worktitle
            v["title"] = u""
            work_title = unicode(self.person.get_name_with_language(
                name_variant=self.co.work_title,
                name_language=self.co.language_nb,
                default=""), "ISO-8859-1")

            personal_title = unicode(self.person.get_name_with_language(
                name_variant=self.co.personal_title,
                name_language=self.co.language_nb,
                default=""), "ISO-8859-1")

            if personal_title:
                v["title"] = personal_title
            else:
                v["title"] = work_title

            # mobile
            mobiles = self.person.get_contact_info(
                type=self.co.contact_mobile_phone,
                source=self.co.system_sap)
            v['mobile'] = ''
            if mobiles:
                v['mobile'] = mobiles[0]['contact_value']

            # Street address
            street = self.person.get_entity_address(source=self.co.system_sap,
                                                    type=self.co.address_street)
            for s in ('streetAddress', 'postalCode', 'l', 'co'):
                v[s] = ''
            if street:
                street = street[0]
                v['streetAddress'] = ', '.join(str(street[s]) for s in
                                               ('address_text', 'p_o_box')
                                               if street.get(s, None))
                v['postalCode'] = str(street['postal_number'])
                v['l'] = str(street['city'])
                if street['country']:
                    v['co'] = self.co.Country(street['country']).country
            # Room number
            roomnumber = self.person.get_contact_info(
                type=self.co.contact_office,
                source=self.co.system_sap)
            v['roomNumber'] = ''
            v['physicalDeliveryOfficeName'] = ''
            if roomnumber:
                v['roomNumber'] = [r['contact_alias'] for r in roomnumber]
                v['physicalDeliveryOfficeName'] = v['roomNumber']

    def _update_posix_id(self, user_dict):
        """Get POSIX account ids (uid, gid) from Cerebrum and update the
        L{user_dict} directly, with the keys uidNumber <int> and gidNumber
        <int>.

        @type  user_dict: dict
        @param user_dict: account_id or username -> account info mapping
        """
        pu = Utils.Factory.get('PosixUser')(self.db)
        pg = Utils.Factory.get('PosixGroup')(self.db)

        # Mapping <group entity_id> => <posix GID>
        eid2gid = dict((int(eid), int(gid))
                       for eid, gid in pg.list_posix_groups())

        # Mapping <Account entity_id> => {'uid' => <posix UID>, 'gid' => <posix
        # GID>}
        eid2posix = {}
        for row in pu.list_posix_users():
            eid2posix[int(row['account_id'])] = {
                'uid': int(row['posix_uid']) or '',
                'gid': eid2gid.get(int(row['gid']), '')
            }

        for id, data in user_dict.iteritems():
            if eid2posix.has_key(id):
                # user_dict with account_id as key (before key switch)
                data['uidNumber'] = eid2posix[id]['uid']
                data['gidNumber'] = eid2posix[id]['gid']
            else:
                self.logger.debug('Account id %d is not a posix account' % id)

    def _exchange_addresslist(self, user_dict):
        """Enabling Exchange address list visibility to only primary accounts

        @param user_dict: account_id -> account info mapping
        @type user_dict: dict
        """

        primary_res = list(self.ac.list_accounts_by_type(primary_only=True))
        for row in primary_res:
            if user_dict.has_key(row['account_id']):
                user_dict[row['account_id']][
                    'msExchHideFromAddressLists'] = False

    def get_default_ou(self):
        """Return default OU for users in AD. Note that self.default_ou could
        be set to override this, otherwise cereconf.AD_USER_OU is used. Note
        that self.ad_ldap (cereconf.AD_LDAP) is always appended.

        """
        if self.default_ou:
            ou = self.default_ou
        else:
            ou = cereconf.AD_USER_OU
        return "OU=%s,%s" % (ou, self.ad_ldap)

    def fetch_cerebrum_data(self, spread, exchange_spread, imap_spread):
        """Fetch relevant cerebrum data for users with the given spread.
        One spread indicating export to AD, and one spread indicating that it
        should also be prepped and activated for Exchange 2007.

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
          'mail': String,                 # default e-post adresse
          'Exchange' : Bool,              # Flag - skal i Exchange eller ikke
          'msExchPoliciesExcluded' : int, # Exchange verdi
          'deliverAndRedirect' : Bool,    # Exchange verdi
          'mDBUseDefaults' : Bool,         # Exchange verdi
          'msExchHideFromAddressLists' : Bool, # Exchange verdi
          'userPrincipalName' : String    # brukernavn@domene
          'telephoneNumber' : String      # tlf
          'ipPhone' : String              # SIP phone numbers - 4 digits
          'mobile' : String               # mobile number (from SAP)
          'title' : String                # tittel
          'mailNickname' : String         # brukernavn
          'targetAddress' : String        # ekstern adresse
          'streetAddress' : String        # kontoradresse
          'postalCode' : String           # postnummer til kontoradresse
          'l': String                     # By for kontoradresse
          'co': String                    # Land for kontoradresse
          'mDBOverHardQuotaLimit' : int   # epostkvote
          'mDBOverQuotaLimit' : int       # epostkvote
          'mDBStorageQuota' : int         # epostkvote
          'proxyAddresses' : Array        # Alle gyldige epost adresser
          'ACCOUNTDISABLE'                # Flag, used by ADutilMixIn
        """

        self.person = Utils.Factory.get('Person')(self.db)

        #
        # Find all users with relevant spread
        #
        tmp_ret = {}
        for row in self.ac.search(spread=spread):
            tmp_ret[int(row['account_id'])] = {
                'Exchange': False,
                'imap': False,
                'msExchPoliciesExcluded': cereconf.AD_EX_POLICIES_EXCLUDED,
                'deliverAndRedirect': cereconf.AD_DELIVER_AND_REDIRECT,
                #'mDBUseDefaults' : cereconf.AD_EX_MDB_USE_DEFAULTS,
                'msExchHideFromAddressLists':
                cereconf.AD_EX_HIDE_FROM_ADDRESS_LIST,
                'TEMPownerId': row['owner_id'],
                'TEMPuname': row['name'],
                'ACCOUNTDISABLE': False,
                # empty default values in case of changes to imap and exchange
                # spread
                'mail': "",
                'mailNickname': "",
                'targetAddress': "",
                'proxyAddresses': []
            }
        self.logger.info("Fetched %i accounts with spread %s"
                         % (len(tmp_ret), spread))

        set_res = set(tmp_ret.keys()) & set([int(row['account_id']) for row in
                                             self.ac.search(spread=exchange_spread)])
        for count, row_account_id in enumerate(set_res):
            tmp_ret[int(row_account_id)]['Exchange'] = True
        self.logger.info("Fetched %i accounts with both spread %s and %s" %
                         (len(set_res), spread, exchange_spread))
        set_res = set(tmp_ret.keys()) & set([int(row['account_id']) for row in
                                             self.ac.search(spread=imap_spread)])
        for count, row_account_id in enumerate(set_res):
            tmp_ret[int(row_account_id)]['imap'] = True
        self.logger.info("Fetched %i accounts with both spread %s and %s" %
                         (len(set_res), spread, imap_spread))

        #
        # Remove/mark quarantined users
        #
        self.logger.debug("..filtering quarantined users..")
        self._filter_quarantines(tmp_ret)

        #
        # Make primary users visible in Exchange address list
        #
        self.logger.debug("..setting address list visibility..")
        self._exchange_addresslist(tmp_ret)

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
            else:
                v['displayName'] = v['TEMPuname']
        self.logger.info("Fetched %i person names" % len(pid2names))

        #
        # Set contact info: phonenumber and title
        #
        self.logger.debug("..setting contact info..")
        self._update_contact_info(tmp_ret)

        #
        # Set posix info
        #
        self.logger.debug("..setting posix info..")
        self._update_posix_id(tmp_ret)

        #
        # Set employee number
        #
        self.logger.debug("..setting employee numbers..")
        pid2employee = {}
        for row in self.person.list_external_ids(
                source_system=self.co.system_sap,
                id_type=self.co.externalid_sap_ansattnr,
                entity_type=self.co.entity_person):
            pid2employee[row['entity_id']] = str(row['external_id'])

        for v in tmp_ret.values():
            if pid2employee.has_key(v['TEMPownerId']):
                v['employeenumber'] = pid2employee[v['TEMPownerId']]

        #
        # Indexing dict on username instead of account id
        #
        userdict_ret = {}
        for k, v in tmp_ret.iteritems():
            userdict_ret[v['TEMPuname']] = v
            del(v['TEMPuname'])
            del(v['TEMPownerId'])
            v['entity_id'] = k

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
            v['userPrincipalName'] = k + "@uia.no"
            if (v['imap'] or v['Exchange']):
                v['mailNickname'] = k
            else:
                del(v['proxyAddresses'])
            if v['imap'] and not v['Exchange']:
                v['targetAddress'] = v['mail']
            else:
                v['targetAddress'] = ""

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
        self.logger.debug('fetch_ad_data from search_ou: %s', search_ou)
        return self.server.listObjects('user', True, search_ou)

    def store_sid(self, objtype, name, sid, dry_run):
        """Store AD object SID to cerebrum database for given user

        @param objtype: type of AD object
        @type objtype: String
        @param name: user name
        @type name: String
        @param sid: SID from AD
        @type sid: String
        """
        # TBD: Check if we create a new object for a entity that already
        # have a externalid_accountsid defined in the db and delete old?
        if objtype == 'account' and not dry_run:
            self.ac.clear()
            self.ac.find_by_name(name)
            self.ac.affect_external_id(self.co.system_ad,
                                       self.co.externalid_accountsid)
            self.ac.populate_external_id(self.co.system_ad,
                                         self.co.externalid_accountsid, sid)
            self.ac.write_db()

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
            self.logger.error("create user %s failed: %r",
                              chg['sAMAccountName'], ret)
        else:
            if not dry_run:
                self.logger.info("created user %s" % ret)
            if store_sid:
                self.store_sid(
                    'account',
                    chg['sAMAccountName'],
                    ret[2],
                    dry_run)
            pw = unicode(self.ac.make_passwd(chg['sAMAccountName']),
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
                if chg.has_key('entity_id'):
                    del chg['entity_id']
                if chg.has_key('sAMAccountName'):
                    uname = chg['sAMAccountName']
                    del chg['sAMAccountName']
                # Setting default for undefined AD_ACCOUNT_CONTROL values.
                for acc, value in cereconf.AD_ACCOUNT_CONTROL.items():
                    if not chg.has_key(acc):
                        chg[acc] = value
                ret = self.run_cmd('putProperties', dry_run, chg)
                if not ret[0]:
                    self.logger.warning("putproperties on %s failed: %r",
                                        uname, ret)
                ret = self.run_cmd('setObject', dry_run)
                if not ret[0]:
                    self.logger.warning(
                        "setObject on %s failed: %r",
                        uname,
                        ret)

    def compare(self, delete_users, cerebrumusrs, adusrs, exch_users,
                forwarding_sync):
        """
        Check if any values for account need be updated in AD by comparing
        current values in AD and cerebrum. Also checks accounts for disabling
        if they are noe longer supposed to be exported to AD, or checks for
        accounts that need to be created in AD.

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

        # Override of what OUs that should be touched:
        all_cerebrum_ous = cereconf.AD_ALL_CEREBRUM_OU
        if self.only_ous:
            all_cerebrum_ous = self.only_ous

        for usr, ad_user in adusrs.iteritems():
            changes = {}
            if cerebrumusrs.has_key(usr):
                cere_user = cerebrumusrs[usr]
                # User is both places, we want to check correct data.
                # Checking for correct OU.
                ou = cerebrumusrs.get("OU", self.get_default_ou())
                if ad_user['distinguishedName'] != 'CN=%s,%s' % (usr, ou):
                    changes['type'] = 'move_object'
                    changes['OU'] = ou
                    changes['distinguishedName'] = ad_user['distinguishedName']
                    # Submit list and clean.
                    changelist.append(changes)
                    changes = {}

                for attr in cereconf.AD_ATTRIBUTES:

                    # Special case for UiA, probably others too - proxyAddresses
                    # would sometimes contain x500 addresses that Cerebrum
                    # hasn't set, and will be added back in when Cerebrum
                    # removes them. Such addresses will therefore be ignored
                    # from the sync. Idealistically, Cerebrum should have either
                    # full control of an attribute, or not sync it at all, so
                    # this is only a compromise. Example on x500 addresses:
                    # 
                    #   x500:/o=ExchangeLabs/ou=Exchange Administrative Group (FYDIBOHF23SPDLT)/cn=Recipients/cn=ff65cb19e68d447eb89a3c0f357359e2-lpbrov10
                    if attr == 'proxyAddresses':
                        if attr in ad_user:
                            ad_user[attr] = [x for x in ad_user[attr] if not
                                    x.startswith('x500:/')]

                    # Catching special cases.
                    if attr == 'msExchPoliciesExcluded':
                        # xmlrpclib appends chars [' and '] to
                        # this attribute for some reason
                        if attr not in ad_user:
                            changes[attr] = cere_user[attr]
                        else:
                            tmpstring = str(ad_user[attr]).replace("['", "")
                            tmpstring = tmpstring.replace("']", "")
                            if tmpstring != cere_user[attr]:
                                changes[attr] = cere_user[attr]
                    # only change these attributes if forward sync has been run
                    elif attr in ('altRecipient', 'deliverAndRedirect'):
                        if forwarding_sync:
                            if attr in cere_user and attr in ad_user:
                                if ad_user[attr] != cere_user[attr]:
                                    changes[attr] = cere_user[attr]
                            elif attr in cere_user:
                                if cere_user[attr] != "":
                                    changes[attr] = cere_user[attr]
                            elif attr in ad_user:
                                changes[attr] = ''
                    # Treating general cases
                    else:
                        if attr in cere_user and attr in ad_user:
                            if isinstance(cere_user[attr], (list)):
                                # Multivalued, it is assumed that a
                                # multivalue in cerebrumusrs always is
                                # represented as a list.h
                                if (isinstance(ad_user[attr],
                                               (str, int, long, unicode))):
                                    # Transform single-value to a list for
                                    # comp.
                                    val2list = []
                                    val2list.append(ad_user[attr])
                                    ad_user[attr] = val2list

                                # sort and compare
                                cere_user[attr].sort()
                                ad_user[attr].sort()
                                if cere_user[attr] != ad_user[attr]:
                                    changes[attr] = cere_user[attr]
                            else:
                                if ad_user[attr] != cere_user[attr]:
                                    changes[attr] = cere_user[attr]
                        elif attr in cere_user:
                            # A blank value in cerebrum and <not set>
                            # in AD -> do nothing.
                            if cere_user[attr] != "":
                                changes[attr] = cere_user[attr]
                        elif attr in ad_user:
                            # Delete value
                            changes[attr] = ''

                for attr, value in cereconf.AD_ACCOUNT_CONTROL.items():
                    if attr in cere_user:
                        if attr not in ad_user or ad_user[attr] != cere_user[attr]:
                            changes[attr] = cere_user[attr]
                    elif attr not in ad_user or ad_user[attr] != value:
                        changes[attr] = value

                # Submit if any changes.
                if len(changes):
                    changes['distinguishedName'] = 'CN=%s,%s' % (usr, ou)
                    changes['type'] = 'alter_object'
                    exchange_change = False
                    for attribute in changes:
                        if attribute in cereconf.AD_EXCHANGE_RELATED_ATTRIBUTES:
                            exchange_change = True
                    if (exchange_change and (not usr in exch_users)
                            and (cere_user['Exchange'] or cere_user['imap'])):
                        exch_users.append(usr)
                        self.logger.debug(
                            "Added to run Update-Recipient list: %s" %
                            usr)

                # after processing we delete from array.
                del cerebrumusrs[usr]

            else:
                # Account not in Cerebrum, but in AD.
                if [s for s in all_cerebrum_ous if
                        ad_user['distinguishedName'].upper().find(s.upper()) >= 0]:
                    # ac.is_deleted() or ac.is_expired() pluss a small rest of
                    # accounts created in AD, but that do not have AD_spread.
                    if bool(delete_users):
                        changes['type'] = 'delete_object'
                        changes[
                            'distinguishedName'] = ad_user[
                                'distinguishedName']
                    else:
                        # Disable account.
                        if not bool(ad_user['ACCOUNTDISABLE']):
                            changes[
                                'distinguishedName'] = ad_user[
                                    'distinguishedName']
                            changes['type'] = 'alter_object'
                            changes['ACCOUNTDISABLE'] = True
                            # commit changes
                            changelist.append(changes)
                            changes = {}
                        # Hide Account from Exchange?
                        hideAddr = ad_user.get('msExchHideFromAddressLists')
                        if hideAddr is None or hideAddr is False:
                            # msExchHideFromAddressLists is either not set or
                            # False
                            changes[
                                'distinguishedName'] = ad_user[
                                    'distinguishedName']
                            changes['type'] = 'alter_object'
                            changes['msExchHideFromAddressLists'] = True
                            # commit changes
                            changelist.append(changes)
                            changes = {}
                            exch_users.append(usr)
                            self.logger.info(
                                "Added to run Update-Recipient list: %s" %
                                usr)
                        # Moving account.
                        if (ad_user['distinguishedName'] != "CN=%s,OU=%s,%s" %
                                (usr, cereconf.AD_LOST_AND_FOUND, self.ad_ldap)):
                            changes['type'] = 'move_object'
                            changes[
                                'distinguishedName'] = ad_user[
                                    'distinguishedName']
                            changes['OU'] = ("OU=%s,%s" %
                                             (cereconf.AD_LOST_AND_FOUND, self.ad_ldap))

            # Finished processing user, register changes if any.
            if changes:
                changelist.append(changes)

        # The remaining items in cerebrumusrs is not in AD, create user.
        for cusr, cdta in cerebrumusrs.items():
            changes = {}
            if (not cusr in exch_users) and (cerebrumusrs[cusr]['Exchange']
                                             or cerebrumusrs[cusr]['imap']):
                exch_users.append(cusr)
                self.logger.info(
                    "Added to run Update-Recipient list: %s" %
                    cusr)
            # New user, create.
            changes = cdta
            changes['type'] = 'create_object'
            changes['sAMAccountName'] = cusr
            if changes.has_key('Exchange'):
                del changes['Exchange']
            if changes.has_key('imap'):
                del changes['imap']
            changelist.append(changes)

        return changelist

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
                    # TODO. Don't exec. Get method from self. call
                    # method with args.
                    exec('self.' + chg['type'] + '(chg, dry_run)')

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
            self.logger.info("Running Update-Recipient for object '%s'"
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
                self.logger.error("run_UpdateRecipient on %s failed: %r",
                                  usr, ret)
        self.logger.info(
            "Ran Update-Recipient against Exchange for %i objects",
            len(exch_users))

    def fetch_forwardinfo_cerebrum_data(
            self, ad_spread, exchange_spread, cerebrumdump):
        """
        Getting information about forwarding from cerebrum, and updating the
        user dict from cerebrum to include forwarding info.

        @param cerebrumdump: account_name -> account info mapping
        @type cerebrumusers: dict
        @param ad_spread: spread for ad users
        @type ad_spread: string
        @param exchange_spread: spread for exchange users
        @type exchange_spread: string
        @rtype: dict
        @return: a dict with forwarding information
        """
        exch_users = {}
        # Getting entity_id and user name for all users with both spreads
        set1 = set([(row['account_id'], row['name']) for row in
                    list(self.ac.search(spread=ad_spread))])
        set2 = set([(row['account_id'], row['name']) for row in
                    list(self.ac.search(spread=exchange_spread))])
        entity_id2uname = set1.intersection(set2)
        for entity_id, username in entity_id2uname:
            exch_users[entity_id] = {'uname': username,
                                     'forward_addresses': []}

        # Getting alle forwards in database and the entity id they belong to
        from Cerebrum.modules.Email import EmailDomain, EmailTarget, EmailForward
        etarget = EmailTarget(self.db)
        rewrite = EmailDomain(self.db).rewrite_special_domains
        eforward = EmailForward(self.db)

        target_id2target_entity_id = {}
        for row in etarget.list_email_targets_ext():
            if row['target_entity_id']:
                target_id2target_entity_id[int(row['target_id'])] = {
                    'target_ent_id': int(row['target_entity_id'])}

        for row in eforward.list_email_forwards():
            if target_id2target_entity_id.has_key(int(row['target_id'])):
                te_id = target_id2target_entity_id[
                    int(row['target_id'])]['target_ent_id']
            else:
                continue
            exch_user = exch_users.get(te_id)
            if not exch_user:
                continue
            if not cerebrumdump.has_key(exch_user['uname']):
                del exch_users[te_id]
            else:
                cerebrumdump[exch_user['uname']]['deliverAndRedirect'] = False
                if row['enable'] == 'T':
                    #
                    # In AD, a contact object name may only contain 64
                    # characters. The existing namin convention uses
                    # the forwarding address as a part of the name,
                    # which creates problems for the sync (AD will
                    # not register any contact objects with names longer
                    # than 64 character. In order to fix this, we suggest
                    # that the naming convention is changed to
                    # the relevant user name and the entity_id of the
                    # the forward target. The suggestion has been made
                    # by UiA on 2014-01-29. (Jazz)
                    # 
                    # NB! this will only work if we assume that no address
                    # contain a ;, which should be the case anyway as
                    # the standards do not allow such use
                    forw_addr_entid = "%s;%d" % (row['forward_to'],int(row['target_id']))
                    exch_user['forward_addresses'].append(forw_addr_entid)

        # Make dict with attributes for AD
        forwards = {}
        for values in exch_users.itervalues():
            for tmp_addr in values['forward_addresses']:
                
                fwrd_addr, fwrd_target_id = tmp_addr.split(';')
                fwrd_addr.strip()
                fwrd_target_id.strip()
                SMTP = "SMTP:%s" % fwrd_addr
                smtp = "smtp:%s" % fwrd_addr
                if (SMTP in cerebrumdump[values['uname']]['proxyAddresses']
                        or smtp in cerebrumdump[values['uname']]['proxyAddresses']):
                    cerebrumdump[values['uname']]['deliverAndRedirect'] = True
                else:
                    # using the established naming convention
                    objectname = "Forward_for_%s__%s" % (values['uname'], fwrd_addr)
                    if len(objectname) > 64:
                        # the name is too long, and the alternative
                        # naming convention kicks in
                        objectname = "Forward_for_%s__%d" % (values['uname'], fwrd_target_id)
                    forwards[objectname] = {
                        "displayName":
                        "Forward for %s (%s)" % (
                        values['uname'],
                        fwrd_addr),
                        "targetAddress": "%s" % SMTP,
                        "proxyAddresses": [("%s" % SMTP)],
                        "mail": fwrd_addr,
                        "msExchPoliciesExcluded":
                        cereconf.AD_EX_POLICIES_EXCLUDED,
                        "msExchHideFromAddressLists": True,
                        "mailNickname": "%s_forward=%s" %
                        (values['uname'], fwrd_addr.replace("@", ".")),
                        "owner_uname": values['uname']}

        return forwards

    def make_cerebrum_dist_grps_dict(self, forwards, cerebrumdump):
        """
        Constructing a dict for distribution groups in ad that will be used for
        holding all forwarding objects for a given user.

        @param cerebrumdump: account_name -> account info mapping
        @type cerebrumusers: dict
        @param forwards: forwarding info from cerebrum
        @type forwards: dict
        @rtype: dict
        @return: a dict with forward distribution group information
        """
        cerebrum_dist_grps_dict = {}
        # make a dict with all addresses and owner user for faster search
        addr2user = {}
        for usr, val in cerebrumdump.items():
            if val.has_key('proxyAddresses'):
                for eaddr in val['proxyAddresses']:
                    addr2user[eaddr.lower()] = usr

        for key, value in forwards.items():
            objectname = cereconf.AD_FORWARD_GROUP_PREFIX + \
                value['owner_uname']
            # check if the forward address belongs to a user in AD
            if addr2user.has_key(value['targetAddress'].lower()):
                # serverside find function does not support contact objects
                # so we provide full LDAP path to member objects.
                forwardobject_dn = "CN=%s,OU=%s,%s" % (
                    addr2user[value['targetAddress'].lower()],
                    cereconf.AD_USER_OU, self.ad_ldap)
                del forwards[key]
            else:
                forwardobject_dn = "CN=%s,OU=%s,%s" % (
                    key, cereconf.AD_CONTACT_OU, self.ad_ldap)

            if cerebrum_dist_grps_dict.has_key(objectname):
                cerebrum_dist_grps_dict[
                    objectname][
                        'members'].append(
                            forwardobject_dn)
            else:
                cerebrum_dist_grps_dict[objectname] = {
                    "displayName": objectname,
                    "mailNickname": objectname,
                    "msExchPoliciesExcluded":
                    cereconf.AD_EX_POLICIES_EXCLUDED,
                    "msExchHideFromAddressLists": True,
                    "description":
                    ["Samlegruppe for brukerens forwardadresser"],
                    "groupType": cereconf.AD_DISTRIBUTION_GROUP_TYPE,
                    "proxyAddresses": [("SMTP:%s@uia.no" % objectname)],
                    "mail": ("%s@uia.no" % objectname),
                    "members": [forwardobject_dn]
                }
                ou = "OU=%s,%s" % (cereconf.AD_CONTACT_OU, self.ad_ldap)
                cerebrumdump[value['owner_uname']]['altRecipient'] = \
                    'CN=%s,%s' % (objectname, ou)

        return cerebrum_dist_grps_dict

    def fetch_ad_data_contacts(self):
        """
        Returns full LDAP path to AD objects of type 'contact' and prefix
        indicating it is used for forwarding.

        @rtype: dict
        @return: a dict of dict wich maps contact obects name to
                 objects properties (dict)
        """
        self.server.setContactAttributes(
            cereconf.AD_CONTACT_FORWARD_ATTRIBUTES)
        search_ou = self.ad_ldap
        ad_contacts = self.server.listObjects('contact', True, search_ou)
        # Only deal with forwarding contact objects.
        # Contact sync deals with mailman objects.
        for object_name, value in ad_contacts.items():
            if not object_name.startswith("Forward_for_"):
                del ad_contacts[object_name]
        return ad_contacts

    def fetch_ad_data_distribution_groups(self):
        """
        Returns full LDAP path to AD objects of type 'group' and prefix
        indicating it is to hold forward contact objects.

        @rtype: dict
        @return: a dict of dict wich maps distribution group names to
                 distribution groupproperties (dict)
        """
        self.server.setGroupAttributes(cereconf.AD_DIST_GRP_ATTRIBUTES)
        search_ou = self.ad_ldap
        ad_grps = self.server.listObjects('group', True, search_ou)
        # Only deal with forwarding groups. Groupsync deals with other groups.
        for grp_name, value in ad_grps.items():
            if not grp_name.startswith(cereconf.AD_FORWARD_GROUP_PREFIX):
                del ad_grps[grp_name]
        return ad_grps

    def compare_forwards(self, cerebrum_forwards, ad_contacts,
                         up_rec):
        """ Sync forwarding contact objects in AD

        @param ad_contacts : dict with contacts and attributes from AD
        @type ad_contacts : dict
        @param cerebrum_maillists : dict with forwards and info from cerebrum
        @type cerebrum_maillists : dict
        @param dry_run: Flag
        """
        # Keys in dict from cerebrum must match fields to be populated in AD.
        changelist = []

        for frwd in cerebrum_forwards:
            changes = {}
            if ad_contacts.has_key(frwd):
                # contact in both places, we want to check correct data

                # Checking for correct OU.
                ou = "OU=%s,%s" % (cereconf.AD_CONTACT_OU, self.ad_ldap)
                if ad_contacts[frwd]['distinguishedName'] != 'CN=%s,%s' % (frwd, ou):
                    changes['type'] = 'move_object'
                    changes['OU'] = ou
                    changes['distinguishedName'] = \
                        ad_contacts[frwd]['distinguishedName']
                    # Submit list and clean.
                    changelist.append(changes)
                    changes = {}

                # Comparing contact info
                for attr in cereconf.AD_CONTACT_FORWARD_ATTRIBUTES:
                    # Catching special cases.
                    # xmlrpclib appends chars [' and ']
                    # to this attribute for some reason
                    if attr == 'msExchPoliciesExcluded':
                        if ad_contacts[frwd].has_key('msExchPoliciesExcluded'):
                            tempstring = str(ad_contacts[frwd]
                                             ['msExchPoliciesExcluded']).replace("['", "")
                            tempstring = tempstring.replace("']", "")
                            if (tempstring == cerebrum_forwards[frwd]
                                    ['msExchPoliciesExcluded']):
                                pass
                            else:
                                changes['msExchPoliciesExcluded'] = \
                                    cerebrum_forwards[frwd][
                                        'msExchPoliciesExcluded']
                        else:
                            changes['msExchPoliciesExcluded'] = \
                                cerebrum_forwards[frwd][
                                    'msExchPoliciesExcluded']
                    # Treating general cases
                    else:
                        if cerebrum_forwards[frwd].has_key(attr) and \
                                ad_contacts[frwd].has_key(attr):
                            if isinstance(cerebrum_forwards[frwd][attr], (list)):
                                # Multivalued, it is assumed that a
                                # multivalue in cerebrumusrs always is
                                # represented as a list.
                                Mchange = False

                                if (isinstance(ad_contacts[frwd][attr],
                                               (str, int, long, unicode))):
                                    # Transform single-value to a list for
                                    # comp.
                                    val2list = []
                                    val2list.append(ad_contacts[frwd][attr])
                                    ad_contacts[frwd][attr] = val2list

                                for val in cerebrum_forwards[frwd][attr]:
                                    if val not in ad_contacts[frwd][attr]:
                                        Mchange = True

                                if Mchange:
                                    changes[
                                        attr] = cerebrum_forwards[
                                            frwd][
                                                attr]
                            else:
                                if ad_contacts[frwd][attr] != cerebrum_forwards[frwd][attr]:
                                    changes[
                                        attr] = cerebrum_forwards[
                                            frwd][
                                                attr]
                        else:
                            if cerebrum_forwards[frwd].has_key(attr):
                                # A blank value in cerebrum and <not
                                # set> in AD -> do nothing.
                                if cerebrum_forwards[frwd][attr] != "":
                                    changes[
                                        attr] = cerebrum_forwards[
                                            frwd][
                                                attr]
                            elif ad_contacts[frwd].has_key(attr):
                                # Delete value
                                changes[attr] = ''

                # Submit if any changes.
                if changes:
                    changes['distinguishedName'] = 'CN=%s,%s' % (frwd, ou)
                    changes['type'] = 'alter_forward_contact_object'
                    changelist.append(changes)
                    changes = {}
                    up_rec.append(frwd)
                    self.logger.info(
                        "Added to run Update-Recipient list: %s" %
                        frwd)
                del(ad_contacts[frwd])

            else:
                # The remaining items in cerebrum_dict is not in AD, create
                # object
                changes = {}
                changes = cerebrum_forwards[frwd]
                changes['type'] = 'create_object'
                changes['name'] = frwd
                if changes.has_key('owner_uname'):
                    del changes['owner_uname']
                changelist.append(changes)
                changes = {}
                up_rec.append(frwd)
                self.logger.info(
                    "Added to run Update-Recipient list: %s" %
                    frwd)

        # Remaining objects in ad_contacts should not be in AD anymore
        for frwd in ad_contacts:
            changes = {}
            changes['type'] = 'delete_object'
            changes['distinguishedName'] = (ad_contacts[frwd]
                                            ['distinguishedName'])
            changelist.append(changes)

        return changelist

    def compare_distgrps(self, cerebrum_dist_grps, ad_dist_groups, up_rec):
        """ Sync distribution groups used to contain a users forward
        contact objects in AD

        @param ad_contacts : dict with dist groups and attributes from AD
        @type ad_contacts : dict
        @param cerebrum_maillists : dict with dist groups and info from cerebrum
        @type cerebrum_maillists : dict
        @param dry_run: Flag
        """
        # Keys in dict from cerebrum must match fields to be populated in AD.
        changelist = []

        for distgrp in cerebrum_dist_grps:
            changes = {}
            if ad_dist_groups.has_key(distgrp):
                # group in both places, we want to check correct data

                # Checking for correct OU.
                ou = "OU=%s,%s" % (cereconf.AD_CONTACT_OU, self.ad_ldap)
                if ad_dist_groups[distgrp]['distinguishedName'] != 'CN=%s,%s' % (distgrp, ou):
                    changes['type'] = 'move_object'
                    changes['OU'] = ou
                    changes['distinguishedName'] = \
                        ad_dist_groups[distgrp]['distinguishedName']
                    # Submit list and clean.
                    changelist.append(changes)
                    changes = {}

                # Comparing group info
                for attr in cereconf.AD_DIST_GRP_ATTRIBUTES:
                    # Catching special cases.
                    # xmlrpclib appends chars [' and ']
                    # to this attribute for some reason
                    if attr == 'msExchPoliciesExcluded':
                        if ad_dist_groups[distgrp].has_key('msExchPoliciesExcluded'):
                            tempstring = str(ad_dist_groups[distgrp]
                                             ['msExchPoliciesExcluded']).replace("['", "")
                            tempstring = tempstring.replace("']", "")
                            if (tempstring == cerebrum_dist_grps[distgrp]
                                    ['msExchPoliciesExcluded']):
                                pass
                            else:
                                changes['msExchPoliciesExcluded'] = \
                                    cerebrum_dist_grps[
                                        distgrp][
                                            'msExchPoliciesExcluded']
                        else:
                            changes['msExchPoliciesExcluded'] = \
                                cerebrum_dist_grps[
                                    distgrp][
                                        'msExchPoliciesExcluded']
                    elif attr == 'members':
                        pass
                    # Treating general cases
                    else:
                        if cerebrum_dist_grps[distgrp].has_key(attr) and \
                                ad_dist_groups[distgrp].has_key(attr):
                            if isinstance(cerebrum_dist_grps[distgrp][attr], (list)):
                                # Multivalued, it is assumed that a
                                # multivalue in cerebrumusrs always is
                                # represented as a list.
                                Mchange = False

                                if (isinstance(ad_dist_groups[distgrp][attr],
                                               (str, int, long, unicode))):
                                    # Transform single-value to a list for
                                    # comp.
                                    val2list = []
                                    val2list.append(
                                        ad_dist_groups[distgrp][attr])
                                    ad_dist_groups[distgrp][attr] = val2list

                                for val in cerebrum_dist_grps[distgrp][attr]:
                                    if val not in ad_dist_groups[distgrp][attr]:
                                        Mchange = True

                                if Mchange:
                                    changes[
                                        attr] = cerebrum_dist_grps[
                                            distgrp][
                                                attr]
                            else:
                                if ad_dist_groups[distgrp][attr] != cerebrum_dist_grps[distgrp][attr]:
                                    changes[
                                        attr] = cerebrum_dist_grps[
                                            distgrp][
                                                attr]
                        else:
                            if cerebrum_dist_grps[distgrp].has_key(attr):
                                # A blank value in cerebrum and <not
                                # set> in AD -> do nothing.
                                if cerebrum_dist_grps[distgrp][attr] != "":
                                    changes[
                                        attr] = cerebrum_dist_grps[
                                            distgrp][
                                                attr]
                            elif ad_dist_groups[distgrp].has_key(attr):
                                # Delete value
                                changes[attr] = ''

                # Submit if any changes.
                if changes:
                    changes['distinguishedName'] = 'CN=%s,%s' % (distgrp, ou)
                    changes['type'] = 'alter_forward_distgrp_object'
                    changelist.append(changes)
                    changes = {}
                    up_rec.append(distgrp)
                    self.logger.info(
                        "Added to run Update-Recipient list: %s" %
                        distgrp)

                del(ad_dist_groups[distgrp])

            else:
                # The item in cerebrum_dict is not in AD, create object
                changes = {}
                changes = copy.copy(cerebrum_dist_grps[distgrp])
                changes['type'] = 'create_object'
                changes['sAMAccountName'] = distgrp
                changelist.append(changes)
                changes = {}
                # Shall run Update-Recipient
                up_rec.append(distgrp)
                self.logger.info(
                    "Added to run Update-Recipient list: %s" %
                    distgrp)

        # Remaining objects in ad_dist_groups should not be in AD anymore
        for distgrp in ad_dist_groups:
            changes = {}
            changes['type'] = 'delete_object'
            changes['distinguishedName'] = (ad_dist_groups[distgrp]
                                            ['distinguishedName'])
            changelist.append(changes)

        return changelist

    def perform_forward_contact_changes(self, changelist, dry_run):
        """
        Binds to AD object and perform changes such as
        updates to attributes or deleting.

        @param changelist: SAMAccountname -> changes mapping
        @type changelist: array of dict
        @param dry_run: Flag
        @param store_sid: Flag
        """
        for chg in changelist:
            self.logger.debug("Process change: %s" % repr(chg))
            if chg['type'] == 'create_object':
                self.create_forward_contact_object(chg, dry_run)
            else:
                ret = self.run_cmd('bindObject', dry_run,
                                   chg['distinguishedName'])
                if not ret[0]:
                    self.logger.warning("bindObject on %s failed: %r" %
                                       (chg['distinguishedName'], ret))
                else:
                    exec('self.' + chg['type'] + '(chg, dry_run)')

    def create_forward_contact_object(self, chg, dry_run):
        """
        Creates AD contact object and populates given attributes

        @param chg: object_name and attributes
        @type chg: dict
        @param dry_run: Flag
        """
        ou = chg.get("OU", "OU=%s,%s" % (cereconf.AD_CONTACT_OU, self.ad_ldap))
        self.logger.info('Create forward contact object %s', chg)
        ret = self.run_cmd('createObject', dry_run, 'contact', ou,
                           chg['name'])
        if not ret[0]:
            self.logger.error("create forward contact %s failed: %r",
                              chg['name'], ret[1])
        elif not dry_run:
            name = chg['name']
            del chg['name']
            del chg['type']
            if chg.has_key('distinguishedName'):
                del chg['distinguishedName']
            ret = self.server.putContactProperties(chg)
            if not ret[0]:
                self.logger.warning("putproperties on %s failed: %r",
                                    name, ret)
            else:
                ret = self.run_cmd('setObject', dry_run)
                if not ret[0]:
                    self.logger.warning("setObject on %s failed: %r",
                                        name, ret)

    def alter_forward_contact_object(self, chg, dry_run):
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

        if not dry_run:
            ret = self.server.putContactProperties(chg)
        else:
            ret = (True, 'putContactProperties')
        if not ret[0]:
            self.logger.warning("putContactProperties on %s failed: %r",
                                distName, ret)
        else:
            ret = self.run_cmd('setObject', dry_run)
            if not ret[0]:
                self.logger.warning("setObject on %s failed: %r",
                                    distName, ret)

    def perform_forward_distgrp_changes(self, changelist, dry_run):
        """
        Binds to AD object and perform changes such as
        updates to attributes or deleting.

        @param changelist: SAMAccountname -> changes mapping
        @type changelist: array of dict
        @param dry_run: Flag
        @param store_sid: Flag
        """
        for chg in changelist:
            self.logger.debug("Process change: %s" % repr(chg))
            if chg['type'] == 'create_object':
                self.create_forward_distgrp_object(chg, dry_run)
            else:
                ret = self.run_cmd('bindObject', dry_run,
                                   chg['distinguishedName'])
                if not ret[0]:
                    self.logger.warning("bindObject on %s failed: %r" %
                                       (chg['distinguishedName'], ret))
                else:
                    exec('self.' + chg['type'] + '(chg, dry_run)')

    def create_forward_distgrp_object(self, chg, dry_run):
        """
        Creates AD group object and populates given attributes

        @param chg: group_name -> group info mapping
        @type chg: dict
        @param dry_run: Flag
        """
        groupname = chg.get('sAMAccountName', "Unknown!")
        del chg['sAMAccountName']
        ou = chg.get("OU", "OU=%s,%s" % (cereconf.AD_CONTACT_OU, self.ad_ldap))
        if chg.has_key('OU'):
            del chg['OU']
        del chg['type']
        if chg.has_key('members'):
                del chg['members']
        if chg.has_key('distinguishedName'):
            del chg['distinguishedName']

        self.logger.info('Create forward distgroup %s', chg)
        ret = self.run_cmd('createObject', dry_run, 'Group', ou,
                           groupname)
        if not ret[0]:
            self.logger.error("create dist_group %s failed: %r",
                              groupname, ret[1])
        elif not dry_run:
            ret = self.server.putGroupProperties(chg)
            if not ret[0]:
                self.logger.warning("putproperties on %s failed: %r",
                                    groupname, ret)
            else:
                ret = self.run_cmd('setObject', dry_run)
                if not ret[0]:
                    self.logger.warning("setObject on %s failed: %r",
                                        groupname, ret)

    def alter_forward_distgrp_object(self, chg, dry_run):
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

    def sync_members_forward_distgrp(self, cerebrum_dist_grps, dry_run):
        """
        Syncing forward conctact objects members of forward dist group.

        @param cerebrum_dist_grps: dist group info
        @type cerebrum_dist_grps: dict
        @param dry_run: Flag
        @param store_sid: Flag
        """
        for key, value in cerebrum_dist_grps.items():
            if cerebrum_dist_grps[key].has_key('members'):
                self.logger.debug("Syncing members for %s dist group", key)
                dn = self.server.findObject(key)
                if not dn:
                    self.logger.debug("unknown dist group: %s", key)
                elif dry_run:
                    self.logger.debug("Dryrun: don't sync members")
                else:
                    self.server.bindObject(dn)
                    res = self.server.syncMembers(
                        value['members'], True, False)
                    if not res[0]:
                        self.logger.warning("syncMembers %s failed for:%r" %
                                            (dn, res[1:]))
            else:
                self.logger.warning(
                    "Error: Group %s has no members key" %
                    (key))

    def full_sync(self, delete=False, spread=None, dry_run=True,
                  store_sid=False, exchange_spread=None, imap_spread=None,
                  forwarding_sync=False):

        exch_changes = []
        self.logger.info("Starting user-sync(forwarding_sync = %s, spread = %s, exchange_spread = %s, imap_spread = %s, delete = %s, dry_run = %s, store_sid = %s)" %
                        (forwarding_sync, spread, exchange_spread, imap_spread, delete, dry_run, store_sid))

        # Fetch cerebrum data for users.
        self.logger.debug("Fetching cerebrum user data...")
        cerebrumdump = self.fetch_cerebrum_data(
            spread, exchange_spread, imap_spread)
        self.logger.info("Fetched %i cerebrum users" % len(cerebrumdump))

        # Fetch AD-data for users.
        self.logger.debug("Fetching AD user data...")
        addump = self.fetch_ad_data(self.ad_ldap)
        self.logger.info("Fetched %i AD users" % len(addump))

        if forwarding_sync:
            # Fetch cerebrum forwarding data.
            self.logger.debug("Fetching forwardinfo from cerebrum...")
            cerebrum_forwards = self.fetch_forwardinfo_cerebrum_data(
                spread, exchange_spread, cerebrumdump)
            self.logger.info(
                "Fetched %i cerebrum forwards" %
                len(cerebrum_forwards))
            # Make dict for distribution groups
            cerebrum_dist_grps = self.make_cerebrum_dist_grps_dict(
                cerebrum_forwards, cerebrumdump)

            # Fetch ad data
            self.logger.debug("Fetching ad data about contact objects...")
            ad_contacts = self.fetch_ad_data_contacts()
            self.logger.info("Fetched %i ad forwards" % len(ad_contacts))
            self.logger.debug("Fetching ad data about distrubution groups...")
            ad_dist_groups = self.fetch_ad_data_distribution_groups()

            # compare cerebrum and ad-data for forward-objects
            changelist_forwards = self.compare_forwards(
                cerebrum_forwards, ad_contacts, exch_changes)
            self.logger.info("Found %i number of forward contact object changes"
                             % len(changelist_forwards))
            # compare cerebrum and ad-data for dist-grp objects
            changelist_distgrp = self.compare_distgrps(cerebrum_dist_grps,
                                                       ad_dist_groups, exch_changes)
            self.logger.info("Found %i number of forward dist_grp object changes"
                             % len(changelist_distgrp))

            # perform changes for forwarding things
            self.perform_forward_contact_changes(changelist_forwards, dry_run)
            self.perform_forward_distgrp_changes(changelist_distgrp, dry_run)
            self.sync_members_forward_distgrp(cerebrum_dist_grps, dry_run)

        # compare cerebrum and ad-data for users.
        changelist = self.compare(
            delete,
            cerebrumdump,
            addump,
            exch_changes,
            forwarding_sync)
        self.logger.info("Found %i number of user changes" % len(changelist))
        self.logger.info(
            "Will run Update-Recipient against Exchange for %i objects",
            len(exch_changes))

        # Perform changes for users.
        self.perform_changes(changelist, dry_run, store_sid)

        # updating Exchange
        self.logger.info(
            "Will run Update-Recipient against Exchange for %i objects",
            len(exch_changes))
        self.update_Exchange(dry_run, exch_changes)

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

    def fetch_cerebrum_data(self, spread, exchange_spread):
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
        #
        # Get groups with the  spreads
        #
        # Hvorfor maa jeg gjoere dette med constants og int?
        # Maa ikke gjoeres i andre AD sync..
        grp_dict = {}
        spread_res = list(
            self.group.search(spread=int(self.co.Spread(spread))))
        for row in spread_res:
            gname = unicode(row["name"], 'ISO-8859-1')
            grp_dict[cereconf.AD_GROUP_PREFIX + gname] = {
                'groupType': cereconf.AD_GROUP_TYPE,
                'Exchange': False,
                'description': unicode(row["description"], 'ISO-8859-1'),
                'msExchPoliciesExcluded': cereconf.AD_EX_POLICIES_EXCLUDED,
                'OU': self.get_default_ou(),
                'grp_id': row["group_id"],
                'msExchHideFromAddressLists': False
            }
        self.logger.info("Fetched %i groups with spread %s",
                         len(grp_dict), spread)
        set1 = set([row["name"] for row in spread_res])
        set2 = set([row["name"] for row in list(self.group.search(
                    spread=int(self.co.Spread(exchange_spread))))])
        set_res = set1.intersection(set2)
        for row_set_res in set_res:
            grp_dict[cereconf.AD_GROUP_PREFIX + row_set_res]['Exchange'] = True
        self.logger.info("Fetched %i groups with both spread %s and %s" %
                         (len(set_res), spread, exchange_spread))

        #
        # Assign derived attributes
        #
        for grp_name in grp_dict:
            v = grp_dict[grp_name]
            v['displayName'] = grp_name
            v['displayNamePrintable'] = grp_name
            if v['description'] is None:
                v['description'] = "Not available"
            if v['Exchange'] is True:
                v['proxyAddresses'] = []
                v['proxyAddresses'].append("SMTP:" + grp_name + "@"
                                           + cereconf.AD_GROUP_EMAIL_DOMAIN)
                v['mailNickname'] = grp_name
                v['mail'] = grp_name + "@" + cereconf.AD_GROUP_EMAIL_DOMAIN

        return grp_dict

    def delete_and_filter(
            self, ad_dict, cerebrum_dict, dry_run, delete_groups):
        """Filter out groups in AD that shall not be synced from cerebrum

        Goes through the dict of the groups in AD, and checks if it is
        a group that shall be synced from cerebrum. If it is, but the group
        is not in our defult OU we will move it there. If it is not we remove
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
            # Leave forwarding groups for contactsync to deal with
            if grp_name.startswith(cereconf.AD_FORWARD_GROUP_PREFIX):
                del ad_dict[grp_name]
            elif not cerebrum_dict.has_key(grp_name):
                # an unknown group in OUs under our control -> delete
                if [s for s in cereconf.AD_ALL_CEREBRUM_OU if
                        ad_dict[grp_name]['OU'].upper().find(s.upper()) >= 0]:
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
        'mail': String,                 # default e-post adresse
        'Exchange' : Bool,              # Flag - skal i Exchange eller ikke
        'msExchPoliciesExcluded' : int, # Exchange verdi
        'msExchHideFromAddressLists' : Bool, # Exchange verdi
        'mailNickname' : String         # gruppenavn
        'proxyAddresses' : String       # default e-post adresse
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
        for grp in ad_dict:
            part = ad_dict[grp]['distinguishedName'].split(",", 1)
            if part[1] and part[0].find("CN=") > -1:
                ad_dict[grp]['OU'] = part[1]
            else:
                ad_dict[grp]['OU'] = self.get_default_ou()
            # descritpion is list from AD. Only want to check first string with
            # ours
            if ad_dict[grp].has_key('description'):
                if isinstance(ad_dict[grp]['description'], (list)):
                    ad_dict[
                        grp][
                            'description'] = ad_dict[
                                grp][
                                    'description'][
                                        0]
        return ad_dict

    def sync_group_info(self, ad_dict, cerebrum_dict, dry_run, exch_changes):
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
                ou = cerebrum_dict[grp].get("OU", self.get_default_ou())
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
                    elif attr == 'Exchange':
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
                    if cerebrum_dict[grp]['Exchange']:
                        exch_changes.append(grp)
                        self.logger.info(
                            "Added to run Update-Recipient list: %s" %
                            grp)
                    changelist.append(changes)
                    changes = {}
            else:
                # The remaining items in cerebrum_dict is not in AD, create
                # group.
                changes = {}
                changes = copy.copy(cerebrum_dict[grp])
                changes['type'] = 'create_object'
                changes['sAMAccountName'] = grp
                if changes['Exchange']:
                    exch_changes.append(grp)
                    self.logger.info(
                        "Added to run Update-Recipient list: %s" %
                        grp)
                del changes['Exchange']
                changelist.append(changes)

        return changelist

    def get_default_ou(self):
        """
        Return default OU for groups. Burde vaere i cereconf?
        """
        return "OU=%s,%s" % (cereconf.AD_GROUP_OU, self.ad_ldap)

    def store_sid(self, objtype, name, sid, dry_run):
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
        if objtype == 'group' and not dry_run:
            crbname = name.replace(cereconf.AD_GROUP_PREFIX, "")
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
        updates to attributes or deleting.

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
        Creates AD group object and populates given attributes

        @param chg: group_name -> group info mapping
        @type chg: dict
        @param dry_run: Flag
        """
        groupname = chg.get('sAMAccountName', "Unknown!")
        del chg['sAMAccountName']
        ou = chg.get("OU", self.get_default_ou())
        del chg['OU']
        del chg['type']
        del chg['grp_id']
        if chg.has_key('distinguishedName'):
            del chg['distinguishedName']

        self.logger.info('Create group %s', chg)
        ret = self.run_cmd('createObject', dry_run, 'Group', ou,
                           groupname)
        if not ret[0]:
            self.logger.error("create group %s failed: %r",
                              groupname, ret[1])
        elif not dry_run:
            if store_sid:
                self.store_sid('group', groupname, ret[2], dry_run)
            ret = self.server.putGroupProperties(chg)
            if not ret[0]:
                self.logger.warning("putproperties on %s failed: %r",
                                    groupname, ret)
            else:
                ret = self.run_cmd('setObject', dry_run)
                if not ret[0]:
                    self.logger.warning("setObject on %s failed: %r",
                                        groupname, ret)

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

    def update_Exchange(self, dry_run, exch_grps):
        """
        Telling the AD-service to start the Windows Power Shell command
        Update-Recipient on object in order to prep them for Exchange.

        @param exch_grps : user to run command on
        @type  exch_grps: list
        @param dry_run : Flag
        """
        self.logger.debug(
            "Sleeping for 5 seconds to give ad-ldap time to update")
        time.sleep(5)
        for grp in exch_grps:
            self.logger.info("Running Update-Recipient for group object '%s'"
                             " against Exchange" % grp)
            if cereconf.AD_DC:
                ret = self.run_cmd(
                    'run_UpdateRecipient',
                    dry_run,
                    grp,
                    cereconf.AD_DC)
            else:
                ret = self.run_cmd('run_UpdateRecipient', dry_run, grp)
            if not ret[0]:
                self.logger.error("run_UpdateRecipient on %s failed: %r",
                                  grp, ret)
        self.logger.info(
            "Ran Update-Recipient against Exchange for %i group objects",
            len(exch_grps))

    def sync_group_members(
            self, cerebrum_dict, group_spread, user_spread, dry_run):
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

        entity = Utils.Factory.get('Entity')(self.db)
        person = Utils.Factory.get('Person')(self.db)

        for grp in cerebrum_dict:
            if cerebrum_dict[grp].has_key('grp_id'):
                grp_name = grp.replace(cereconf.AD_GROUP_PREFIX, "")
                grp_id = cerebrum_dict[grp]['grp_id']
                self.logger.debug("Sync group %s" % grp_name)

                # TODO: How to treat quarantined users???, some exist in AD,
                # others do not. They generate errors when not in AD. We still
                # want to update group membership if in AD.
                members = list()
                for usr in (self.group.search_members(group_id=grp_id)):
                        # cannot use:
                        # member_spread=int(self.co.Spread(user_spread))))
                        # because we now want to sync groups with
                        # person-members. this may cause some errors
                        # if accounts found do not have spread to AD
                        # and group-member have to be filtered in other
                        # ways
                    user_id = usr["member_id"]
                    # TODO: this should be solved by the API, but we are not
                    # sure how exactly at this point (Jazz, 2011-05-29)
                    try:
                        entity.clear()
                        entity.find(user_id)
                    except Errors.NotFoundError:
                        self.logger.error(
                            "No entity with id %s found, skipping (this should not occur!)",
                            user_id)
                    if entity.entity_type == self.co.entity_group:
                        self.logger.debug(
                            "%s is a group, will be handled later on, skipping",
                            user_id)
                        continue
                    if entity.entity_type == self.co.entity_person:
                        # TODO: alternatively a dict
                        # personid2primaryaccount can be initialized
                        # and used. will look at this option later on
                        # (Jazz, 2011-05-29)
                        person.clear()
                        person.find(user_id)
                        user_id = person.get_primary_account()
                        if user_id is None:
                            self.logger.debug(
                                "Person %s has no valid primary account, skipping",
                                usr["member_id"])
                            continue
                    if user_id not in entity2name:
                        self.logger.warning("Missing name for account id=%s " % user_id +
                                            "(group: '%s'; member: '%s')" % (grp_name, usr["member_id"]))
                        continue
                    members.append(entity2name[user_id])
                    self.logger.debug(
                        "Try to sync member account id=%s, name=%s",
                        user_id, entity2name[user_id])

                for medlemgrp in (self.group.search_members(
                        group_id=grp_id, member_spread=int(
                            self.co.Spread(group_spread)))):
                    group_id = medlemgrp["member_id"]
                    if group_id not in entity2name:
                        self.logger.warning(
                            "Missing name for group id=%s",
                            group_id)
                        continue
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
                    res = self.server.syncMembers(members, False, False)
                    if not res[0]:
                        self.logger.warning("syncMembers %s failed for:%r" %
                                           (dn, res[1:]))
            else:
                self.logger.warning("Group %s has no group_id. Not syncing members." %
                                   (grp))

    def full_sync(self, delete=False, group_spread=None, dry_run=True,
                  store_sid=False, user_spread=None, exchange_spread=None):

        self.logger.info("Starting group-sync(group_spread = %s, exchange_spread = %s, user_spread = %s, delete = %s, dry_run = %s, store_sid = %s)" %
                        (group_spread, exchange_spread, user_spread, delete, dry_run, store_sid))

        exch_changes = []
        # Fetch cerebrum data.
        self.logger.debug("Fetching cerebrum data...")
        cerebrumdump = self.fetch_cerebrum_data(group_spread, exchange_spread)
        self.logger.info("Fetched %i cerebrum groups" % len(cerebrumdump))

        # Fetch AD data
        self.logger.debug("Fetching AD data...")
        addump = self.fetch_ad_data()
        self.logger.info("Fetched %i ad-groups" % len(addump))

        # Filter AD-list
        self.logger.debug("Filtering list of AD groups...")
        self.delete_and_filter(addump, cerebrumdump, dry_run, delete)
        self.logger.info("Have %i ad-groups after filtering" % len(addump))

        # Compare groups and attributes (not members)
        self.logger.debug("Syncing group info...")
        changelist = self.sync_group_info(
            addump,
            cerebrumdump,
            dry_run,
            exch_changes)
        self.logger.info("%i number of changes" % len(changelist))

        # Perform changes
        self.perform_changes(changelist, dry_run, store_sid)

        # Syncing group members
        self.logger.info("Starting sync of group members")
        self.sync_group_members(
            cerebrumdump,
            group_spread,
            user_spread,
            dry_run)

        # updating Exchange
        self.logger.info(
            "Will run Update-Recipient against Exchange for %i group objects",
            len(exch_changes))
        self.update_Exchange(dry_run, exch_changes)

        # Cleaning up.
        addump = None
        cerebrumdump = None

        # Commiting changes to DB (SID external ID) or not.
        if dry_run:
            self.db.rollback()
        else:
            self.db.commit()

        self.logger.info("Finished group-sync")


class ADFullContactSync(ADutilMixIn.ADutil):

    def __init__(self, *args, **kwargs):
        super(ADFullContactSync, self).__init__(*args, **kwargs)

    def fetch_mail_lists_cerebrum_data(self):
        """
        Fetch relevant cerebrum data for mailmanlists. Only primary
        address of the list is exported to AD/Exchange.

        @rtype: dict
        @return: a dict {name: {'adAttrib': 'value'}} for all maillists
        Typical attributes::

          # canonicalName er et 'constructed attribute' (fra dn)
          "displayName" : String,         #Epostliste - <listenavn>
          "targetAddress" : String,       #SMTP: <listeadresse>
          "proxyAddresses" : Array,       #SMTP: <listeadresse>
          "mailNickname" : String,        #mailman.<listenavn uten @>
          "mail" : String                 #listeadresse
          "msExchPoliciesExcluded" : Bool,
          "msExchHideFromAddressLists" : Bool,
        """
        from Cerebrum.modules.Email import EmailDomain, EmailTarget
        etarget = EmailTarget(self.db)
        rewrite = EmailDomain(self.db).rewrite_special_domains
        mail_lists = []
        # find primary address for all Mailman lists
        for row in etarget.list_email_target_primary_addresses(
                target_type=self.co.email_target_Mailman):
            try:
                mail_lists.append("@".join(
                    (row['local_part'], rewrite(row['domain']))))
            except TypeError:
                pass  # Silently ignore

        maillists_dict = {}
        for liste in mail_lists:
            objectname = "mailman.%s" % liste
            # According to RFC 5322 the length og the local_part may
            # be up to 64 characters. Thus check that maillists we
            # export are no longer than 64 - len('mailman.')
            # Seems like the limit is less for Exchange, but can't
            # find the excact limit. Let's do som (un)qualified
            # guessing.
            local_part = liste.split('@')[0]
            if len(local_part) > 51:
                self.logger.debug("Localpart too long for %s. Skipping this list" %
                                  liste)
                continue
            maillists_dict[objectname] = {
                "displayName": "Epostliste - %s" % liste,
                "targetAddress": "SMTP:%s" % liste,
                "proxyAddresses": [("SMTP:%s" % liste)],
                "mail": liste,
                "mailNickname": "mailman.%s" % liste.replace("@", "."),
                "msExchPoliciesExcluded": cereconf.AD_EX_POLICIES_EXCLUDED,
                "msExchHideFromAddressLists": False
            }

        # Filter -admin and request email addresses (not a pretty hack)
        for email_address in maillists_dict.keys():
            local_part, domain = email_address.rsplit('@')
            if local_part.endswith('-admin'):
                # local_part is on the form foo-admin. if also foo-request
                # and foo exists, filter foo-admin and foo-request.
                tmp = '@'.join((local_part.rsplit('-admin')[0], domain))
                tmp_r = email_address.replace('-admin', '-request')
                if tmp in maillists_dict.keys() and tmp_r in maillists_dict.keys():
                    maillists_dict.pop(email_address)
                    maillists_dict.pop(tmp_r)

        return maillists_dict

    def fetch_ad_data_contacts(self):
        """
        Returns full LDAP path to AD objects of type 'contact' and prefix
        indicating it is used for mailman lists.

        @rtype: list
        @return: a list with LDAP paths to found AD objects
        """
        self.server.setContactAttributes(
            cereconf.AD_CONTACT_MAILMANLIST_ATTRIBUTES)
        search_ou = self.ad_ldap
        ad_contacts = self.server.listObjects('contact', True, search_ou)
        # Only deal with mailman lists contact objects.
        # User sync deals with forward objects.
        for object_name, value in ad_contacts.items():
            if not object_name.startswith("mailman."):
                del ad_contacts[object_name]
        return ad_contacts

    def compare_maillists(
            self, ad_contacts, cerebrum_maillists, dry_run, up_rec):
        """ Sync maillists contact objects in AD

        @param ad_contacts : dict with contacts and attributes from AD
        @type ad_contacts : dict
        @param cerebrum_maillists : dict with maillists and info from cerebrum
        @type cerebrum_maillists : dict
        @param dry_run: Flag
        """
        # Keys in dict from cerebrum must match fields to be populated in AD.
        changelist = []

        for mlist in cerebrum_maillists:
            changes = {}
            if ad_contacts.has_key(mlist):
                # conatct in both places, we want to check correct data

                # Checking for correct OU.
                ou = self.get_default_ou()
                if ad_contacts[mlist]['distinguishedName'] != 'CN=%s,%s' % (mlist, ou):
                    changes['type'] = 'move_object'
                    changes['OU'] = ou
                    changes['distinguishedName'] = \
                        ad_contacts[mlist]['distinguishedName']
                    # Submit list and clean.
                    changelist.append(changes)
                    changes = {}

                # Comparing contact info
                for attr in cereconf.AD_CONTACT_MAILMANLIST_ATTRIBUTES:
                    # Catching special cases.
                    # xmlrpclib appends chars [' and ']
                    # to this attribute for some reason
                    if attr == 'msExchPoliciesExcluded':
                        if ad_contacts[mlist].has_key('msExchPoliciesExcluded'):
                            tempstring = str(ad_contacts[mlist]
                                             ['msExchPoliciesExcluded']).replace("['", "")
                            tempstring = tempstring.replace("']", "")
                            if (tempstring == cerebrum_maillists[mlist]
                                    ['msExchPoliciesExcluded']):
                                pass
                            else:
                                changes[
                                    'msExchPoliciesExcluded'] = cerebrum_maillists[
                                        mlist][
                                            'msExchPoliciesExcluded']
                        else:
                            changes[
                                'msExchPoliciesExcluded'] = cerebrum_maillists[
                                    mlist][
                                        'msExchPoliciesExcluded']
                    # Treating general cases
                    else:
                        if cerebrum_maillists[mlist].has_key(attr) and \
                                ad_contacts[mlist].has_key(attr):
                            if isinstance(cerebrum_maillists[mlist][attr], (list)):
                                # Multivalued, it is assumed that a
                                # multivalue in cerebrumusrs always is
                                # represented as a list.
                                Mchange = False

                                if (isinstance(ad_contacts[mlist][attr],
                                               (str, int, long, unicode))):
                                    # Transform single-value to a list for
                                    # comp.
                                    val2list = []
                                    val2list.append(ad_contacts[mlist][attr])
                                    ad_contacts[mlist][attr] = val2list

                                for val in cerebrum_maillists[mlist][attr]:
                                    if val not in ad_contacts[mlist][attr]:
                                        Mchange = True

                                if Mchange:
                                    changes[
                                        attr] = cerebrum_maillists[
                                            mlist][
                                                attr]
                            else:
                                if ad_contacts[mlist][attr] != cerebrum_maillists[mlist][attr]:
                                    changes[
                                        attr] = cerebrum_maillists[
                                            mlist][
                                                attr]
                        else:
                            if cerebrum_maillists[mlist].has_key(attr):
                                # A blank value in cerebrum and <not
                                # set> in AD -> do nothing.
                                if cerebrum_maillists[mlist][attr] != "":
                                    changes[
                                        attr] = cerebrum_maillists[
                                            mlist][
                                                attr]
                            elif ad_contacts[mlist].has_key(attr):
                                # Delete value
                                changes[attr] = ''

                # Submit if any changes.
                if changes:
                    changes['distinguishedName'] = 'CN=%s,%s' % (mlist, ou)
                    changes['type'] = 'alter_object'
                    changelist.append(changes)
                    changes = {}
                    up_rec.append(mlist)
                    self.logger.info(
                        "Added to run Update-Recipient list: %s" %
                        mlist)

                del(ad_contacts[mlist])

            else:
                # The remaining items in cerebrum_dict is not in AD, create
                # object
                changes = {}
                changes = cerebrum_maillists[mlist]
                changes['type'] = 'create_object'
                changes['name'] = mlist
                changelist.append(changes)
                changes = {}
                up_rec.append(mlist)
                self.logger.info(
                    "Added to run Update-Recipient list: %s" %
                    mlist)

        # Remaining objects in ad_contacts should not be in AD anymore
        for mlist in ad_contacts:
            changes['type'] = 'delete_object'
            changes['distinguishedName'] = (ad_contacts[mlist]
                                            ['distinguishedName'])
            changelist.append(changes)
            changes = {}

        return changelist

    def get_default_ou(self, change=None):
        """
        Return default OU for mailman lists contact objects.
        """
        return "OU=Contacts,%s" % self.ad_ldap

    def create_object(self, chg, dry_run):
        """
        Creates AD contact object and populates given attributes

        @param chg: object_name and attributes
        @type chg: dict
        @param dry_run: Flag
        """
        ou = chg.get("OU", self.get_default_ou())
        self.logger.info('Create maillist AD contact object %s', chg)
        ret = self.run_cmd('createObject', dry_run, 'contact', ou,
                           chg['name'])
        if not ret[0]:
            self.logger.error("create maillist contact %s failed: %r",
                              chg['name'], ret[1])
        elif not dry_run:
            name = chg['name']
            del chg['name']
            del chg['type']
            if chg.has_key('distinguishedName'):
                del chg['distinguishedName']
            ret = self.server.putContactProperties(chg)
            if not ret[0]:
                self.logger.warning("putproperties on %s failed: %r",
                                    name, ret)
            else:
                ret = self.run_cmd('setObject', dry_run)
                if not ret[0]:
                    self.logger.warning("setObject on %s failed: %r",
                                        name, ret)

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

        if not dry_run:
            ret = self.server.putContactProperties(chg)
        else:
            ret = (True, 'putContactProperties')
        if not ret[0]:
            self.logger.warning("putContactProperties on %s failed: %r",
                                distName, ret)
        else:
            ret = self.run_cmd('setObject', dry_run)
            if not ret[0]:
                self.logger.warning("setObject on %s failed: %r",
                                    distName, ret)

    def update_Exchange(self, dry_run, up_rec):
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
        for name in up_rec:
            self.logger.info("Running Update-Recipient for contact object '%s'"
                             " against Exchange" % name)
            if cereconf.AD_DC:
                ret = self.run_cmd(
                    'run_UpdateRecipient',
                    dry_run,
                    name,
                    cereconf.AD_DC)
            else:
                ret = self.run_cmd('run_UpdateRecipient', dry_run, name)
            if not ret[0]:
                self.logger.error("run_UpdateRecipient on %s failed: %r",
                                  name, ret)
        self.logger.info(
            "Ran Update-Recipient against Exchange for %i contact objects",
            len(up_rec))

    def full_sync(self, dry_run=True):

        self.logger.info("Starting contact-sync for maillists (dry_run = %s)" %
                        (dry_run))

        # Fetch ad data
        self.logger.debug("Fetching ad data about contact objects...")
        ad_contacts = self.fetch_ad_data_contacts()
        self.logger.info("Fetched %i ad contact objects" % len(ad_contacts))

        # Fetch cerebrum data
        self.logger.debug("Fetching cerebrum data about mail lists...")
        cerebrum_maillists = self.fetch_mail_lists_cerebrum_data()
        self.logger.info(
            "Fetched %i cerebrum contact objects" %
            len(cerebrum_maillists))

        # Comparing
        needs_updateRecipient = []
        changelist = self.compare_maillists(ad_contacts, cerebrum_maillists,
                                            dry_run, needs_updateRecipient)
        self.logger.info("Found %i number of changes", len(changelist))
        self.logger.info(
            "Will run Update-Recipient against Exchange for %i contact objects", 
            len(needs_updateRecipient))

        # Perform changes
        self.perform_changes(changelist, dry_run)

        # Running Update Recipient
        self.update_Exchange(dry_run, needs_updateRecipient)

        self.logger.info("Finished contact-sync for maillists.")
