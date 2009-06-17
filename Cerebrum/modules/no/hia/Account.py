# -*- coding: iso-8859-1 -*-
# Copyright 2004, 2005, 2006, 2007, 2008, 2009 University of Oslo, Norway
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

import re
import cereconf
import time

from Cerebrum import Account
from Cerebrum.modules import Email
from Cerebrum import Errors
from Cerebrum.modules import PasswordHistory

class AccountHiAMixin(Account.Account):
    def add_spread(self, spread):
        if spread == self.const.spread_nis_user or spread == self.const.spread_ans_nis_user:
            if self.illegal_name(self.account_name):
                raise self._db.IntegrityError, \
                      "Can't add NIS spread to an account with illegal name."
            
        if spread == self.const.spread_exchange_account:
            if self.has_spread(self.const.spread_hia_email):
                raise Errors.CerebrumError("Cannot add Exchange-spread to an IMAP-account, use 'email exchange_migrate'")
            if not self.has_spread(self.const.spread_hia_ad_account):
                self.add_spread(self.const.spread_hia_ad_account)
            mdb = self._autopick_homeMDB()
            self.populate_trait(self.const.trait_exchange_mdb, strval=mdb)
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
        if not spread in spreads:  # user doesn't have this spread
            return
        if spread == self.const.spread_exchange_account:
            self.delete_trait(self.const.trait_exchange_mdb)
            self.write_db()

        # (Try to) perform the actual spread removal.
        ret = self.__super.delete_spread(spread)
        return ret

    def _autopick_homeMDB(self):
        mdb_candidates = set(cereconf.EXCHANGE_HOMEMDB_VALID.keys())
        mdb_count = dict()
        for candidate in mdb_candidates:
            mdb_count[candidate] = len(self.list_traits(code=self.const.trait_exchange_mdb,
                                                        strval=candidate, fetchall=True))
        mdb_choice, smallest_mdb_weight = None, 1.0
        for m in mdb_candidates:
            m_weight = (mdb_count.get(m, 0)*1.0)/cereconf.EXCHANGE_HOMEMDB_VALID[m]
            if m_weight < smallest_mdb_weight:
                mdb_choice, smallest_mdb_weight = m, m_weight
        if mdb_choice is None:
            raise Errors.CerebrumError("Cannot assign mdb")
        return mdb_choice
    
    def update_email_addresses(self, set_primary = False):
        # Find, create or update a proper EmailTarget for this
        # account.
        et = Email.EmailTarget(self._db)
        target_type = self.const.email_target_account
        if self.is_deleted() or self.is_reserved():
            target_type = self.const.email_target_deleted
        try:
            et.find_by_email_target_attrs(target_entity_id = self.entity_id)
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
        if target_type == self.const.email_target_deleted:
            expire_date = self._db.DateFromTicks(time.time() +
                                                 60 * 60 * 24 * 1)
            for row in et.get_addresses():
                ea.clear()
                ea.find(row['address_id'])
                if ea.email_addr_expire_date is None:
                    ea.email_addr_expire_date = expire_date
                ea.write_db()
            return
        # if an account email_target without email_server is found assign
        # the appropriate server
        if not et.email_server_id:
            if self.get_account_types() or self.owner_type == self.const.entity_group:
                et = self._update_email_server()
            else:
                # do not set email_server_target until account_type is registered
                return
        # Figure out which domain(s) the user should have addresses
        # in.  Primary domain should be at the front of the resulting
        # list.
	# if the only address found is in EMAIL_DEFAULT_DOMAIN
        # don't set default address. This is done in order to prevent
        # adresses in default domain being sat as primary 
	# TODO: account_types affiliated to OU's  without connected
	# email domain don't get a default address
        primary_set = False
        ed = Email.EmailDomain(self._db)
        ed.find(self.get_primary_maildomain())
        domains = [ed.email_domain_name]
	if ed.email_domain_name == cereconf.EMAIL_DEFAULT_DOMAIN:
            if not self.owner_type == self.const.entity_group:
                primary_set = True
        if cereconf.EMAIL_DEFAULT_DOMAIN not in domains:
            domains.append(cereconf.EMAIL_DEFAULT_DOMAIN)
        # Iterate over the available domains, testing various
        # local_parts for availability.  Set user's primary address to
        # the first one found to be available.
	# Never change any existing email addresses
        try:
            self.get_primary_mailaddress()
	    primary_set = True
        except Errors.NotFoundError:
            pass
	epat = Email.EmailPrimaryAddressTarget(self._db)
        for domain in domains:
            if ed.email_domain_name <> domain:
                ed.clear()
                ed.find_by_domain(domain)
            # Check for 'cnaddr' category before 'uidaddr', to prefer
            # 'cnaddr'-style primary addresses for users in
            # maildomains that have both categories.
            ctgs = [int(r['category']) for r in ed.get_categories()]
            local_parts = []
            if int(self.const.email_domain_category_cnaddr) in ctgs:
                local_parts.append(self.get_email_cn_local_part(given_names=1, max_initials=1))
                local_parts.append(self.account_name)
            elif int(self.const.email_domain_category_uidaddr) in ctgs:
                local_parts.append(self.account_name)
	    for lp in local_parts:
		lp = self.wash_email_local_part(lp)
		# Is the address taken?
 		ea.clear()
		try:
		    ea.find_by_local_part_and_domain(lp, ed.entity_id)
		    if ea.email_addr_target_id <> et.entity_id:
			# Address already exists, and points to a
			# target not owned by this Account.
                        continue
		    # Address belongs to this account; make sure
		    # there's no expire_date set on it.
		    ea.email_addr_expire_date = None
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
                        epat.populate(ea.entity_id, parent = et)
                    epat.write_db()
                    primary_set = True
		self.update_email_quota()

    # TODO: check this method, may probably be done better
    def _update_email_server(self):
        es = Email.EmailServer(self._db)
        et = Email.EmailTarget(self._db)
        if self.is_employee() or self.is_affiliate():
            #server_name = 'exchkrs01.uia.no'
            server_name = 'mail-imap1'
        else:
            server_name = 'mail-imap2'
        es.find_by_name(server_name)
        try:
            et.find_by_email_target_attrs(target_entity_id = self.entity_id)
        except Errors.NotFoundError:
            # Not really sure about this. it is done at UiO, but maybe it is not
            # right to make en email_target if one is not found??
            et.clear()
            et.populate(self.const.email_target_account,
                        self.entity_id,
                        self.const.entity_account)
            et.write_db()
        if not et.email_server_id:
            et.email_server_id=es.entity_id
            et.write_db()
        return et

    def set_password(self, plaintext):
        # Override Account.set_password so that we get a copy of the
        # plaintext password
        self.__plaintext_password = plaintext
        self.__super.set_password(plaintext)

    def write_db(self):
        try:
            plain = self.__plaintext_password
        except AttributeError:
            plain = None
        ret = self.__super.write_db()
        if plain is not None:
            ph = PasswordHistory.PasswordHistory(self._db)
            ph.add_history(self, plain)
        return ret

    def suggest_unames(self, domain, fname, lname, maxlen=8, suffix=""):
        from time import localtime
        t = localtime()[0:2]
        year = str(t[0])[2:]
        return self.__super.suggest_unames(domain, fname, lname, maxlen,
                                           suffix=year)

    def is_employee(self):
        for r in self.get_account_types():
            if r['affiliation'] == self.const.affiliation_ansatt:
                return True
        return False

    def is_affiliate(self):
        for r in self.get_account_types():
            if r['affiliation'] == self.const.affiliation_tilknyttet:
                return True
        return False    

# arch-tag: e0828813-9221-4e43-96f0-0194d131e683
