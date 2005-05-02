# -*- coding: iso-8859-1 -*-
# Copyright 2004, 2005 University of Oslo, Norway
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

class AccountHiAMixin(Account.Account):
    def update_email_addresses(self, set_primary = False):
        # Find, create or update a proper EmailTarget for this
        # account.
        et = Email.EmailTarget(self._db)
        target_type = self.const.email_target_account
        if self.is_deleted() or self.is_reserved():
            target_type = self.const.email_target_deleted
        try:
            et.find_by_email_target_attrs(entity_id = self.entity_id)
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
                                                 60 * 60 * 24 * 180)
            for row in et.get_addresses():
                ea.clear()
                ea.find(row['address_id'])
                if ea.email_addr_expire_date is None:
                    ea.email_addr_expire_date = expire_date
                ea.write_db()
            return
        # if an account without email_server_target is found assign
        # the appropriate server
        est = Email.EmailServerTarget(self._db)
        try:
            est.find(et.email_target_id)
        except Errors.NotFoundError:
            est = self._update_email_server()
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
		    ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
		    if ea.email_addr_target_id <> et.email_target_id:
			# Address already exists, and points to a
			# target not owned by this Account.
                        continue
		    # Address belongs to this account; make sure
		    # there's no expire_date set on it.
		    ea.email_addr_expire_date = None
		except Errors.NotFoundError:
		    # Address doesn't exist; create it.
		    ea.populate(lp, ed.email_domain_id, et.email_target_id,
				expire=None)
		ea.write_db()
                if not primary_set:
                    epat.clear()
                    try:
                        epat.find(ea.email_addr_target_id)
                        epat.populate(ea.email_addr_id)
                    except Errors.NotFoundError:
                        epat.clear()
                        epat.populate(ea.email_addr_id, parent = et)
                    epat.write_db()
                    primary_set = True
		self.update_email_quota()

    # TODO: check this method, may probably be done better
    def _update_email_server(self):
        est = Email.EmailServerTarget(self._db)
        es = Email.EmailServer(self._db)
        et = Email.EmailTarget(self._db)
        if self.is_employee():
            server_name = 'mail-imap1'
        else:
            server_name = 'mail-imap2'
        es.find_by_name(server_name)
        try:
            et.find_by_email_target_attrs(entity_id = self.entity_id)
        except Errors.NotFoundError:
            # Not really sure about this. it is done at UiO, but maybe it is not
            # right to make en email_target if one is not found??
            et.clear()
            et.populate(self.const.email_target_account,
                        self.entity_id,
                        self.const.entity_account)
            et.write_db()
        try:
            est.find_by_entity(self.entity_id)
            if est.server_id == es.entity_id:
                return est
        except:
            est.clear()
            est.populate(es.entity_id, parent = et)
            est.write_db()
        return est

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

# arch-tag: e0828813-9221-4e43-96f0-0194d131e683
