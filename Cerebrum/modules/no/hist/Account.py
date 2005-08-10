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

import re
import cereconf
import time

import random
from Cerebrum.Entity import EntityName
from Cerebrum import Account
from Cerebrum.modules import Email
from Cerebrum import Errors
from Cerebrum.modules import PasswordHistory



class AccountHiSTMixin(Email.AccountEmailMixin):
    """Delete an account, does not handle group memberships""" 
    def delete(self):
        for s in self.get_account_types():
          self.del_account_type(s['ou_id'], s['affiliation'])
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=account_authentication]
        WHERE account_id=:acc_id""", {'acc_id' : self.entity_id})
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=password_history]
        WHERE entity_id=:acc_id""", {'acc_id' : self.entity_id})
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=homedir]
        WHERE account_id=:acc_id""", {'acc_id' : self.entity_id})
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=account_home]
        WHERE account_id=:acc_id""", {'acc_id' : self.entity_id})
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=account_type]
        WHERE account_id=:acc_id""", {'acc_id' : self.entity_id})
        self.execute("""  
        DELETE FROM [:table schema=cerebrum name=account_info] 
        WHERE account_id=:acc_id""", {'acc_id' : self.entity_id})
        self.__super.delete()
     

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
            if self.get_account_types():
                est = self._update_email_server()
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
		local_parts.append(self.get_email_cn_local_part(given_names=1,
			max_initials=1))
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
#                self.update_email_quota()


	 
     
    def _update_email_server(self):
        est = Email.EmailServerTarget(self._db) 
        es = Email.EmailServer(self._db) 
        old_server = srv_id = None 
        try:
            est.find_by_entity(self.entity_id) 
            old_server = est.email_server_id 
            es.find(est.email_server_id) 
            if es.email_server_type == self.const.email_server_type_shist:
                return est 
	except Errors.NotFoundError: 
            pass
       
        # Choose a server..
        if old_server is None:
            srvlist = es.list_email_server_ext()
	    for svr in srvlist:
                if svr['server_type'] == self.const.email_server_type_shist:
		    srv_id = svr['server_id']
                try:
                    et = Email.EmailTarget(self._db)
                    et.find_by_email_target_attrs(entity_id = self.entity_id)
                except Errors.NotFoundError:
                    et.clear()
                    et.populate(self.const.email_target_account,
                                self.entity_id,
                                self.const.entity_account)
                    et.write_db()
            if srv_id == None:
                raise RuntimeError, "srv_id is not set."
            est.clear()
	    est.populate(srv_id, parent = et)
            est.write_db()
	else:
	    est.populate(srv_id)
        return est   
 

  
    def make_passwd(self, uname):
        vowels = 'aeiouyAEIOUY'
	consonants = 'bdghjlmnpqrstvwxzBDGHJLMNPQRSTVWXZ0123456789'
	r = ''
	alt = random.randint(0, 1)
	while len(r) < 8:
    	  if alt is 1:
            r += consonants[random.randint(0, len(consonants)-1)]
            alt = 0;
          else:
            r += vowels[random.randint(0, len(vowels)-1)]
            alt = 1;
        return r


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


    def validate_new_uname(self, domain, uname):
        """Check that the requested username is legal and free"""
        try:
            # We instantiate EntityName directly because find_by_name
            # calls self.find() whose result may depend on the class
            # of self
            lc_name = uname.lower()
            en = EntityName(self._db)
            en.find_by_name(lc_name, domain)
            return False
        except Errors.NotFoundError:
            if lc_name == uname:
              return True
            else:
              return False

# arch-tag: 05b5d29d-ad03-42c6-a193-90d7a2606d95
