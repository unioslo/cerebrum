# -*- coding: utf-8 -*-
# Copyright 2010-2018 University of Oslo, Norway
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

import io
import random
import re
import time

import six

import cereconf

from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email


class AccountNIHMixin(Account.Account):
    """Account mixin class providing functionality specific to NIH."""
    def add_spread(self, spread):
        if spread == self.const.spread_exchange_account:
            if not self.has_spread(self.const.spread_ad_account):
                self.add_spread(self.const.spread_ad_account)
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
        if spread not in spreads:  # user doesn't have this spread
            return

        # (Try to) perform the actual spread removal.
        ret = self.__super.delete_spread(spread)
        # Post-removal clean up
        if spread == self.const.spread_exchange_account:
            try:
                self.delete_trait(self.const.trait_exchange_mdb)
                self.write_db()
            except Errors.NotFoundError:
                pass
            try:
                et = Email.EmailTarget(self._db)
                et.find_by_target_entity(self.entity_id)
                et.email_target_type = self.const.email_target_deleted
                et.write_db()
            except Errors.NotFoundError:
                pass
        return ret

    def illegal_name(self, name):
        """ NIH can only allow max 10 characters in usernames.

        """
        # Max len should be 10; set to 30 to proceed with testing
        if len(name) > 30:
            return "too long (%s); max 10 chars allowed" % name
        if re.search("[^a-z0-9._-]", name):
            return "contains illegal characters (%s); only a-z allowed" % name

        return super(AccountNIHMixin, self).illegal_name(name)

    def is_employee(self, person):
        for r in person.get_affiliations():
            if r['affiliation'] == self.const.affiliation_ansatt:
                return True
        return False

    def is_affiliate(self, person):
        for r in person.get_affiliations():
            if r['affiliation'] == self.const.affiliation_tilknyttet:
                return True
        return False

    def is_student(self, person):
        for r in person.get_affiliations():
            if r['affiliation'] == self.const.affiliation_student:
                return True
        return False

    def suggest_unames(self, domain, fname, lname, maxlen=8, suffix=""):
        # Override Account.suggest_unames as HiHH allows up to 10 chars
        # in unames
        return self.__super.suggest_unames(domain, fname, lname, maxlen=10)

    def update_email_addresses(self):
        # Overriding default update_email_addresses as NIH does not require
        # email_server, Jazz, 2011-05-22
        # Find, create or update a proper EmailTarget for this
        # account.
        et = Email.EmailTarget(self._db)
        target_type = self.const.email_target_account
        if self.is_expired() or self.is_reserved():
            target_type = self.const.email_target_deleted
        changed = False
        try:
            et.find_by_email_target_attrs(target_entity_id = self.entity_id)
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
        self._update_email_address_domains(et)

    def _update_email_address_domains(self, et):
        # Figure out which domain(s) the user should have addresses
        # in.  Primary domain should be at the front of the resulting
        # list.
        ed = Email.EmailDomain(self._db)
        ea = Email.EmailAddress(self._db)
        try:
            ed.find(self.get_primary_maildomain(use_default_domain=False))
        except Errors.NotFoundError:
            # no appropriate primary domain was found, no valid address may
            # be generated
            return
        domains = self.get_prospect_maildomains(use_default_domain=False)
        # Iterate over the available domains, testing various
        # local_parts for availability.  Set user's primary address to
        # the first one found to be available.
        primary_set = False
        # Never change any existing email addresses
        try:
            self.get_primary_mailaddress()
            primary_set = True
        except Errors.NotFoundError:
            pass
        epat = Email.EmailPrimaryAddressTarget(self._db)
        if not domains:
            # no valid domain has been found and no e-mail address
            # can be assigned
            return
        for domain in domains:
            if ed.entity_id != domain:
                ed.clear()
                ed.find(domain)
            # Check for 'cnaddr' category before 'uidaddr', to prefer
            # 'cnaddr'-style primary addresses for users in
            # maildomains that have both categories.
            ctgs = [int(r['category']) for r in ed.get_categories()]
            local_parts = []
            if int(self.const.email_domain_category_cnaddr) in ctgs:
                local_parts.append(self.get_email_cn_local_part())
                local_parts.append(self.account_name)
            elif int(self.const.email_domain_category_uidaddr) in ctgs:
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

    def _autopick_homeMDB(self):
        mdb_choice = None
        person = Factory.get("Person")(self._db)
        person.clear()
        try:
            person.find(int(self.owner_id))
        except Errors.NotFoundError:
            raise self._db.IntegrityError, \
                'No personal owner found'
            return
        if self.is_employee(person) or self.is_affiliate(person):
            mdb_choice = 'DB03-Ansatt'
        elif self.is_student(person):
            mdb_choice = 'DB02-Student'
        else:
            mdb_choice = 'DB03-Ansatt'
        if mdb_choice is None:
            raise self._db.IntegrityError, \
                  "Cannot assign mdb"
        return mdb_choice

    def make_passwd(self, uname):
        words = []
        pwd = []
        passwd = ""
        for fname in cereconf.PASSPHRASE_DICTIONARIES:
            with io.open(fname, mode='r', encoding='ascii') as f:
                for l in f:
                    words.append(l.rstrip())
        while(1):
            pwd.append(words[random.randint(0, len(words)-1)])
            passwd = ' '.join([a for a in pwd])
            if len(passwd) >= 12 and len(pwd) > 1:
                # do not generate passwords longer than 20 chars
                if len(passwd) <= 20:
                    return six.text_type(passwd)
                else:
                    pwd.pop(0)
