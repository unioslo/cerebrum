# -*- coding: iso-8859-1 -*-
# Copyright 2003-2005 University of Oslo, Norway
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

""""""

import cerebrum_path
import cereconf

import re
import time

from Cerebrum import Account
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum import Errors
from Cerebrum.modules import PasswordHistory

class AccountHiOfMixin(Account.Account):
    """Account mixin class providing functionality specific to HiOf.

    The methods of the core Account class that are overridden here,
    ensure that any Account objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies at HiOf.

    """

    def illegal_name(self, name):
        # Avoid circular import dependency
        from Cerebrum.modules.PosixUser import PosixUser

        if isinstance(self, PosixUser):
            # TODO: Kill the ARsystem user to limit range og legal characters
            if len(name) > 8:
                return "too long (%s)" % name
            if re.search("^[^A-Za-z]", name):
                return "must start with a character (%s)" % name
            if re.search("[^A-Za-z0-9\-_]", name):
                return "contains illegal characters (%s)" % name
        return False

    def update_email_addresses(self):
        # Find, create or update a proper EmailTarget for this
        # account.
        et = Email.EmailTarget(self._db)
        old_server = None
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
        old_server = et.email_server_id
        acc_types = self.get_account_types()
        if not old_server:
            # we should update servers for employees as well, but we
            # cannot do that for now as there are no clear criteria
            # for when we should consider someone av fag-employee or
            # adm-employee. we will therefor update servers for students
            # only
            # if self.is_fag_employee():
            #    self._update_email_server('mail.fag.hiof.no')
            # elif self.is_adm_employee():
            #    self._update_email_server('mail.adm.hiof.no')
            if self.is_student():
                self._update_email_server('mail.stud.hiof.no')
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
        if cereconf.EMAIL_DEFAULT_DOMAIN not in domains:
            domains.append(cereconf.EMAIL_DEFAULT_DOMAIN)
        # Iterate over the available domains, testing various
        # local_parts for availability.  Set user's primary address to
        # the first one found to be available.
        try:
            self.get_primary_mailaddress()
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

    def _update_email_server(self, server_name):
        es = Email.EmailServer(self._db)
        et = Email.EmailTarget(self._db)
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
        et.email_server_id = es.entity_id
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

    def is_employee(self):
        for r in self.get_account_types():
            if r['affiliation'] == self.const.affiliation_ansatt:
                return True
        return False

    def is_fag_employee(self):
        person = Factory.get("Person")(self._db)
        person.clear()
        person.find(self.owner_id)
        for a in person.get_affiliations():
            if a['status'] == self.const.affiliation_status_ansatt_vitenskapelig:
                return True
        return False
    
    def is_adm_employee(self):
        person = Factory.get("Person")(self._db)
        person.clear()
        person.find(self.owner_id)
        for a in person.get_affiliations():
            if a['status'] == self.const.affiliation_status_ansatt_tekadm:
                return True
        return False

    def is_student(self):
        person = Factory.get("Person")(self._db)
        person.clear()
        person.find(self.owner_id)
        for a in person.get_affiliations():
            if a['affiliation'] == self.const.affiliation_student:
                return True
        return False            
