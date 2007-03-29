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

import random
import string
import sys
import os

import re
import cereconf
from mx import DateTime
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import PasswordHistory
from Cerebrum.modules import Email
from Cerebrum.Utils import Factory

class AccountIndigoMixin(Account.Account):
    """Account mixin class providing functionality specific to Indigo.
    The methods of the core Account class that are overridden here,
    ensure that any Account objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies as stated by the Indigo-project.
    """
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

    def enc_auth_type_pgp_crypt(self, plaintext, salt=None):
        return pgp_encrypt(plaintext, cereconf.PGPID)


class AccountGiskeMixin(Account.Account):
    def populate(self, name, owner_type, owner_id, np_type, creator_id,
                 expire_date, parent=None):
        if parent is not None:
            self.__xerox__(parent)
        # Override Account.populate in order to register 'primary e-mail
        # address
        self.__super.populate(name, owner_type, owner_id, np_type, creator_id,
                              expire_date)
        # register "primary" e-mail address as entity_contact
        c_val = name + '@' + cereconf.EMAIL_DEFAULT_DOMAIN
        desc = "E-mail address exported to LDAP"
        self.populate_contact_info(self.const.system_cached,
                                   type=self.const.contact_email,
                                   value=c_val, description=desc)

    def make_passwd(self, uname):
        words = []
        pwd = []
        passwd = ""
        for fname in cereconf.PASSPHRASE_DICTIONARIES:
            f = file(fname, 'r')
            for l in f:
                words.append(l.rstrip())
        while(1): 
            pwd.append(words[random.randint(0, len(words)-1)])
            passwd = ' '.join([a for a in pwd])
            if len(passwd) >= 14 and len(pwd) > 2:               
                if len(passwd) <= 20:
                    return passwd
                else:
                    pwd.pop(0)


class AccountGiskeEmailMixin(Account.Account):
    def get_primary_mailaddress(self):
        primary = self.get_contact_info(type=self.const.contact_email)
        return primary[0]['contact_value']


class AccountOfkMixin (Account.Account):
    def make_passwd(self, uname):
        pot = string.ascii_letters + string.digits
        count = 0
        pwd = []
        while count < 2:
            pwd.append(string.digits[random.randint(0, len(string.digits)-1)])
            count += 1
        while count < 8:
            pwd.append(string.ascii_letters[random.randint(0, len(string.ascii_letters)-1)])
            count += 1
        random.shuffle(pwd)
        return string.join(pwd,'')

    def suggest_unames(self, domain, fname, lname, maxlen=8):
        """Returns a tuple with 15 (unused) username suggestions based
        on the person's first and last name.
        
        domain: value domain code
        fname:  first name (and any middle names)
        lname:  last name
        maxlen: maximum length of a username
        """
        goal = 15       # We may return more than this
        prim = ""
        potuname = ()
        
        lastname = self.simplify_name(lname, alt=1)
        if lastname == "":
            raise ValueError,\
                  "Must supply last name, got '%s', '%s'" % (fname, lname)
    
        firstname = self.simplify_name(fname, alt=1)
        if firstname == "":
            raise ValueError,\
                  "Must supply first name, got '%s', '%s'" % (fname, lname)

        fname = firstname
        fname = fname.replace('-', '').replace(' ', '')        
        lname = lastname
        lname = lname.replace('-', '').replace(' ', '')
        
        if len(fname) >= 3:
            if len(lname) >= 3:
                prim = fname[0:3] + lname[0:3]
            else:
                prim = fname[0:3] + lname
        elif len(fname) < 3:
            if len(lname) < 3:
                prim = fname + lname
            else:
                max_len_lname = 6 - len(fname)
                prim = fname + lname[0:max_len_lname]

        if self.validate_new_uname(domain, prim):            
            potuname += (prim, )

        i = 1
        prefix = prim
        
        while len(potuname) < goal and i < 100:
            un = prefix + str(i)
            i += 1
            if self.validate_new_uname(domain, un):
                potuname += (un, )
                
        return potuname

    def update_email_addresses(self):
        # Find, create or update a proper EmailTarget for this
        # account.
        et = Email.EmailTarget(self._db)
        target_type = self.const.email_target_account
        if self.is_expired():
            target_type = self.const.email_target_deleted
        changed = False
        try:
            et.find_by_email_target_attrs(entity_id = self.entity_id)
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
            if ed.email_domain_name <> domain:
                ed.clear()
                ed.find_by_domain(domain)
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
                    ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
                    if ea.email_addr_target_id <> et.email_target_id:
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
