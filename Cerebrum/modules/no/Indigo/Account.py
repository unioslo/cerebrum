# -*- coding: utf-8 -*-
# Copyright 2003-2018 University of Oslo, Norway
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
import base64
import random
import string
import time

import six

import cereconf

from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.utils import json
from Cerebrum.Utils import Factory
from Cerebrum.Utils import pgp_encrypt


class AccountIndigoMixin(Account.Account):
    """Account mixin class providing functionality specific to Indigo.
    The methods of the core Account class that are overridden here,
    ensure that any Account objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies as stated by the Indigo-project.
    """

    def is_affiliate(self, uname):
        db = Factory.get('Database')()
        person = Factory.get('Person')(db)
        account = Factory.get('Account')(db)
        account.clear()
        try:
            account.find_by_name(uname)
        except Errors.NotFoundError:
            return False
        person.clear()
        try:
            person.find(account.owner_id)
        except Errors.NotFoundError:
            return False
        for r in person.get_affiliations():
            if r['affiliation'] == self.const.affiliation_tilknyttet:
                return True
        return False

    def is_employee(self, uname):
        db = Factory.get('Database')()
        person = Factory.get('Person')(db)
        account = Factory.get('Account')(db)
        account.clear()
        try:
            account.find_by_name(uname)
        except Errors.NotFoundError:
            return False
        person.clear()
        try:
            person.find(account.owner_id)
        except Errors.NotFoundError:
            return False
        for r in person.get_affiliations():
            if r['affiliation'] == self.const.affiliation_ansatt:
                return True
        return False

    def enc_auth_type_pgp_crypt(self, plaintext, salt=None):
        return pgp_encrypt(plaintext, cereconf.PGPID)


class AccountOfkMixin(Account.Account):

    def add_spread(self, spread):
        #
        # Pre-add checks
        #
        if spread == self.const.spread_ad_acc:
            mdb = self._autopick_homeMDB()
            self.populate_trait(self.const.trait_homedb_info, strval=mdb)
            self.write_db()
            # This should be removed after the migration to Exchange 2010 is
            # done:
            self.populate_trait(self.const.trait_exchange_migrated)
            self.write_db()
        #
        # (Try to) perform the actual spread addition.
        ret = self.__super.add_spread(spread)

        return ret

    def delete_spread(self, spread):
        #
        # Pre-remove checks
        #
        spreads = [int(r['spread']) for r in self.get_spread()]
        if spread not in spreads:  # user doesn't have this spread
            return
        if spread == self.const.spread_ad_acc:
            self.delete_trait(self.const.trait_homedb_info)
            self.write_db()

        # (Try to) perform the actual spread removal.
        ret = self.__super.delete_spread(spread)
        return ret

    def make_passwd(self, uname):
        count = 0
        pwd = []
        while count < 2:
            pwd.append(string.digits[random.randint(0, len(string.digits)-1)])
            count += 1
        while count < 8:
            idx = random.randint(0, len(string.ascii_letters)-1)
            pwd.append(string.ascii_letters[idx])
            count += 1
        random.shuffle(pwd)
        return six.text_type(string.join(pwd, ''))

    def verify_password(self, method, plaintext, cryptstring):
        """Returns True if the plaintext matches the cryptstring,
        False if it doesn't.  If the method doesn't support
        verification, NotImplemented is returned.
        """
        if method not in (self.const.auth_type_md5_crypt,
                          self.const.auth_type_md5_unsalt,
                          self.const.auth_type_ha1_md5,
                          self.const.auth_type_crypt3_des,
                          self.const.auth_type_md4_nt,
                          self.const.auth_type_ssha,
                          self.const.auth_type_sha256_crypt,
                          self.const.auth_type_sha512_crypt,
                          self.const.auth_type_plaintext):
            raise ValueError('Unknown method {method}'.format(method=method))
        salt = cryptstring
        if method == self.const.auth_type_ssha:
            salt = base64.decodestring(str(cryptstring))[20:].decode()
        return (self.encrypt_password(method,
                                      plaintext,
                                      salt=salt) == cryptstring)

    def _get_old_homeMDB(self):
        """
        If account once had homeMDB try to find the old value. If more
        than one old value, return the most recent.
        """
        # homeMDB values are stored as EntityTraits. After 2009-08-XX
        # the traits values are stored in ChangeLog when deleted. Try
        # to fetch that value if it exists.
        res = {}
        for row in self._db.get_log_events(subject_entity=self.entity_id,
                                           types=(self.const.trait_del,)):
            if row['change_params']:
                try:
                    params = json.loads(row['change_params'])
                    if params['code'] != self.const.trait_homedb_info:
                        continue
                    val = params.get('strval')
                    if val:
                        # There might be more than one hit.
                        res[row['tstamp']] = val
                except Exception:
                    continue
        if res:
            keys = res.keys()
            # when sorting tstamps, most recent will be last in the list
            keys.sort()
            return res[keys[-1]]
        return None

    def _autopick_homeMDB(self):
        """Return a valid homeMDB value to be used for the account.

        If the account has previously had a HomeMDB, this is reused, but only
        as long the MDB value is valid today, see
        L{cereconf.EXCHANGE_HOMEMDB_VALID}. Otherwise a random HomeMDB is
        selected. We don't care about the weight of the MDBs, ØFK wants
        everyone to be equally assigned.

        @rtype: string
        @return: One of the HomeMDB values from
            L{cereconf.EXCHANGE_HOMEMDB_VALID}.

        """
        mdb_candidates = cereconf.EXCHANGE_HOMEMDB_VALID
        # Check if account had homeMDB earlier. If so use that, as long as it
        # is in one of today's valid MDBs.
        mdb_choice = self._get_old_homeMDB()
        if mdb_choice and mdb_choice in mdb_candidates:
            return mdb_choice
        # Choose a random HomeMDB, and don't care about weights:
        mdb_choice = random.choice(mdb_candidates.keys())
        if mdb_choice is None:
            raise Errors.CerebrumError("Couldn't assign mdb for %s" %
                                       self.entity_id)
        return mdb_choice

    #
    # TBD: Should we change this method globally?
    # see argum. below, Jazz 2009-05-10
    def get_primary_maildomain(self):
        """Return correct `domain_id' for account's primary address."""
        dom = Email.EmailDomain(self._db)
        dom.find_by_domain(cereconf.EMAIL_DEFAULT_DOMAIN)
        entdom = Email.EntityEmailDomain(self._db)
        # Find OU and affiliation for this user's best-priority
        # account_type entry.
        for row in self.get_account_types():
            ou, aff = row['ou_id'], row['affiliation']
            # If a maildomain is associated with this (ou, aff)
            # combination, then that is the user's default maildomain.
            entdom.clear()
            try:
                entdom.find(ou, affiliation=aff)
                #
                # This if-test assumes that the cereconf.EMAIL_DEFAULT_DOMAIN
                # cannot be considered as a primary domain if another
                # valid domain is found for an account. The behaviour is wrong
                # for ØFK as quite av few of the accounts should have primary
                # addresses in default domain while they have other domains
                # Jazz
                #
                # If the default domain is specified, ignore this
                # affiliation.
                #     if entdom.entity_email_domain_id == dom.entity_id:
                #         continue
                return entdom.entity_email_domain_id
            except Errors.NotFoundError:
                pass
            # Otherwise, try falling back to tha maildomain associated
            # with (ou, None).
            entdom.clear()
            try:
                entdom.find(ou)
                if entdom.entity_email_domain_id == dom.entity_id:
                    continue
                return entdom.entity_email_domain_id
            except Errors.NotFoundError:
                pass
        # Still no proper maildomain association has been found; fall
        # back to default maildomain.
        return dom.entity_id

    def update_email_addresses(self):
        # Find, create or update a proper EmailTarget for this
        # account.
        et = Email.EmailTarget(self._db)
        target_type = self.const.email_target_account
        if self.is_expired():
            target_type = self.const.email_target_deleted
        changed = False
        try:
            et.find_by_email_target_attrs(target_entity_id=self.entity_id)
            if et.email_target_type != target_type:
                changed = True
                et.email_target_type = target_type
        except Errors.NotFoundError:
            # We don't want to create e-mail targets for reserved or
            # deleted accounts, but we do convert the type of existing
            # e-mail targets above.
            if target_type == self.const.email_target_deleted:
                return
            et.populate(target_type, self.entity_id, self.const.entity_account)
        et.write_db()
        # For deleted/reserved users, set expire_date for all of the
        # user's addresses, and don't allocate any new addresses.
        ea = Email.EmailAddress(self._db)
        if changed and cereconf.EMAIL_EXPIRE_ADDRESSES is not False:
            if target_type == self.const.email_target_deleted:
                seconds = cereconf.EMAIL_EXPIRE_ADDRESSES * 86400
                expire_date = self._db.DateFromTicks(time.time() + seconds)
            else:
                expire_date = None
            for row in et.get_addresses():
                ea.clear()
                ea.find(row['address_id'])
                ea.email_addr_expire_date = expire_date
                ea.write_db()
        # Active accounts shouldn't have an alias value (it is used
        # for failure messages)
        if changed and target_type == self.const.email_target_account:
            if et.email_target_alias is not None:
                et.email_target_alias = None
                et.write_db()

        if target_type == self.const.email_target_deleted:
            return
        # Figure out which domain(s) the user should have addresses
        # in.  Primary domain should be at the front of the resulting
        # list.
        ed = Email.EmailDomain(self._db)
        ed.find(self.get_primary_maildomain())
        domains = [ed.email_domain_name]
        if cereconf.EMAIL_DEFAULT_DOMAIN not in domains:
            domains.append(cereconf.EMAIL_DEFAULT_DOMAIN)
        # Iterate over the available domains, testing various
        # local_parts for availability.  Set user's primary address to
        # the first one found to be available.
        primary_set = False
        epat = Email.EmailPrimaryAddressTarget(self._db)
        for domain in domains:
            if ed.email_domain_name != domain:
                ed.clear()
                ed.find_by_domain(domain)
            # Check for 'uidaddr' category before 'cnaddr', to prefer
            # 'uidaddr'-style primary addresses for users in
            # maildomains that have both categories.
            ctgs = [int(r['category']) for r in ed.get_categories()]
            local_parts = []
            if int(self.const.email_domain_category_uidaddr) in ctgs:
                local_parts.append(self.account_name)
            elif int(self.const.email_domain_category_cnaddr) in ctgs:
                local_parts.append(self.get_email_cn_local_part())
                local_parts.append(self.account_name)
            for lp in local_parts:
                lp = self.wash_email_local_part(lp)
                # Is the address taken?
                ea.clear()
                try:
                    ea.find_by_local_part_and_domain(lp, ed.entity_id)
                    if ea.email_addr_target_id != et.entity_id:
                        # Address already exists, and points to a
                        # target not owned by this Account.
                        #
                        # TODO: An expired address gets removed by a
                        # database cleaning job, and when it's gone,
                        # the address will eventually be recreated
                        # connected to this target.
                        continue
                except Errors.NotFoundError:
                    # Address doesn't exist; create it.
                    ea.populate(lp, ed.entity_id, et.entity_id,
                                expire=None)
                ea.write_db()
                if not primary_set:
                    epat.clear()
                    try:
                        epat.find(ea.email_addr_target_id)
                        epat.populate(ea.entity_id)
                    except Errors.NotFoundError:
                        epat.clear()
                        epat.populate(ea.entity_id, parent=et)
                    epat.write_db()
                    primary_set = True
