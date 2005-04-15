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
        # Until a user's email target is associated with an email
        # server, the mail system won't know where to deliver mail for
        # that user.  Hence, we return early (thereby avoiding
        # creation of email addresses) for such users.
        # For the time being we do not have to check this at HiA
        # It is, however, possible that HiA will require this at
        # a later point so we will not take it away just yet
        #est = Email.EmailServerTarget(self._db)
        #try:
        #    est.find(et.email_target_id)
        #except Errors.NotFoundError:
        #    return
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

    def update_email_quota(self, force=False):
        """Set e-mail quota in Cerebrum"""
        change = force
        quota = 300
        eq = Email.EmailQuota(self._db)
        try:
            eq.find_by_entity(self.entity_id)
        except Errors.NotFoundError:
            change = True
            eq.populate(90, quota)
            eq.write_db()
        else:
            # We never decrease the quota, to allow for manual overrides
            if quota > eq.email_quota_hard:
                change = True
                eq.email_quota_hard = quota
                eq.write_db()

# arch-tag: e0828813-9221-4e43-96f0-0194d131e683
