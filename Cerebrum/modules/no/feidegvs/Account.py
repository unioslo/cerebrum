# -*- coding: iso-8859-1 -*-
# Copyright 2004 University of Oslo, Norway
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

import cerebrum_path
import cereconf
from Cerebrum import Account
from Cerebrum import Disk
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum import Errors
from Cerebrum.modules import PasswordHistory
import re
import time

class AccountFeideGvsMixin(Account.Account):

    def update_email_addresses(self, set_primary = False):
        # Find, create or update a proper EmailTarget for this
        # account.
        et = Email.EmailTarget(self._db)
        target_type = self.const.email_target_account
        if self.is_deleted():
            target_type = self.const.email_target_deleted
            # If the account is deleted set in a request for
            # mailbox removal
            self._reg_bofhd_request(req_type='delete')
        try:
            et.find_by_email_target_attrs(target_entity_id = self.entity_id)
            et.email_target_type = target_type
        except Errors.NotFoundError:
            # We don't want to create e-mail targets for reserved or
            # deleted accounts, but we do convert the type of existing
            # e-mail targets above.
            if target_type == self.const.email_target_deleted:
                return
            # A new target is registered in cerebrum
            et.populate(target_type, self.entity_id, self.const.entity_account)
        et.write_db()
        # For deleted users, set expire_date for all of the
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
        if not et.email_server_id:
            et = self._update_email_server()

        # Add a request for mailbox creation
        if et.email_target_type != self.const.email_target_deleted: 
            self._reg_bofhd_request()                         

        #Figure out which domain(s) the user should have addresses
        # in.  Primary domain should be at the front of the resulting
        # list.
        primary_set = False
        ed = Email.EmailDomain(self._db)
        ed.find(self.get_primary_maildomain())
        domains = [ed.email_domain_name]
	epat = Email.EmailPrimaryAddressTarget(self._db)
        # Iterate over the available domains, testing various
        # local_parts for availability.  Set user's primary address to
        # the first one found to be available.
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



    def _update_email_server(self):
        es = Email.EmailServer(self._db)
        et = Email.EmailTarget(self._db)
        server_name = cereconf.EMAIL_DEFAULT_SERVER
        es.find_by_name(server_name)
        try:
            et.find_by_email_target_attrs(target_entity_id = self.entity_id)
        except Errors.NotFoundError:
            et.populate(self.const.email_target_account,
                        self.entity_id,
                        self.const.entity_account)
            et.write_db()
        if not et.email_server_id:
            et.email_server_id = es.entity_id
            et.write_db()
        return et

    def _reg_bofhd_request(self, req_type='create'):
        et = Email.EmailTarget(self._db)
        try:
            et.find_by_target_entity(self.entity_id)
            if not et.email_server_id:
                return
            br = BofhdRequests(self._db, self.const)
            if req_type=='create' and not br.get_requests(entity_id=self.entity_id,
                                                          operation=self.const.bofh_email_create):
                # Register a BofhdRequest to create the mailbox
                reqid = br.add_request(None,        # Requestor
                                       br.now, self.const.bofh_email_create,
                                       self.entity_id, et.email_server_id)
            elif req_type=='delete':
                 # Register a BofhdRequest to delete the mailbox
                reqid = br.add_request(None,        # Requestor
                                       br.now, self.const.bofh_email_delete,
                                       self.entity_id, et.email_server_id)
        except Errors.NotFoundError:
            return

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

# arch-tag: 1d947ef8-15c7-11da-8378-c95d5955533b
