# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Troms�, Norway
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
import string
import sys
import traceback
import getopt
import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum.database import postgres
from Cerebrum import Utils
from Cerebrum import Account
from Cerebrum import Person
from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.modules.no.uit.ad_email import AdEmail

from Cerebrum.modules.Email import AccountEmailMixin
import re

class UiTAccountEmailMixin(AccountEmailMixin):

    def get_email_cn_local_part(self, given_names=-1, max_initials=None, keep_dash=True):
        """
        Construct a "pretty" local part.

        If given_names=-1, keep the given name if the person has only
        one, but reduce them to initials only when the person has more
        than one.
           "John"                  -> "john"
           "John Doe"              -> "john.doe"
           "John Ronald Doe"       -> "j.r.doe"
           "John Ronald Reuel Doe" -> "j.r.r.doe"

        If given_names=0, only initials are included
           "John Ronald Doe"       -> "j.r.doe"

        If given_names=1, the first given name will always be included
           "John Ronald Doe"       -> "john.r.doe"

        If max_initials is set, no more than this number of initials
        will be included.  With max_initials=1 and given_names=-1
           "John Doe"              -> "john.doe"
           "John Ronald Reuel Doe" -> "j.doe"

        With max_initials=1 and given_names=1
           "John Ronald Reuel Doe" -> "john.r.doe"
        """

        assert(given_names >= -1)
        assert(max_initials is None or max_initials >= 0)

        try:
            full = self.get_fullname()
        except Errors.NotFoundError:
            full = self.account_name
        names = [x.lower() for x in re.split(r'\s+', full)]
        last = names.pop(-1)
        if not keep_dash:
            names = [x for x in '-'.join(names).split('-') if x]

        if given_names == -1:
            if len(names) == 1:
                # Person has only one name, use it in full
                given_names = 1
            else:
                # Person has more than one name, only use initials
                given_names = 0

        if len(names) > given_names:
            initials = [x[0] for x in names[given_names:]]
            if max_initials is not None:
                initials = initials[:max_initials]
            names = names[:given_names] + initials
        names.append(last)
        return self.wash_email_local_part(".".join(names))



    def getdict_uname2mailinfo(self, filter_expired_accounts=True, filter_expired_emails=True):
        ret = {}
        target_type = int(self.const.email_target_account)
        namespace = int(self.const.account_namespace)
        where = "en.value_domain = :namespace"

        if filter_expired_accounts:
            where += " AND (ai.expire_date IS NULL OR ai.expire_date > [:now])"

        if filter_expired_emails:
            where += " AND (ea.expire_date IS NULL OR ea.expire_date > [:now])"

        for row in self.query("""
        SELECT en.entity_name, ea.local_part, ed.domain, ea.create_date, ea.change_date, ea.expire_date
        FROM [:table schema=cerebrum name=account_info] ai
        JOIN [:table schema=cerebrum name=entity_name] en
          ON en.entity_id = ai.account_id
        JOIN [:table schema=cerebrum name=email_target] et
          ON et.target_type = :targ_type AND
             et.target_entity_id = ai.account_id
        JOIN [:table schema=cerebrum name=email_address] ea
          ON ea.target_id = et.target_id
        JOIN [:table schema=cerebrum name=email_domain] ed
          ON ed.domain_id = ea.domain_id
        WHERE """ + where,
                              {'targ_type': target_type,
                               'namespace': namespace}):

            addresses = ret.get(row['entity_name'])
            if addresses is None:
               addresses = []

            mailinfo = {}
            mailinfo['local_part'] = row['local_part']
            mailinfo['domain'] = row['domain']
            mailinfo['create_date'] = row['create_date']
            mailinfo['change_date'] = row['change_date']
            mailinfo['expire_date'] = row['expire_date']

            addresses.append(mailinfo)

            ret[row['entity_name']] = addresses
            
        return ret


class email_address:

    def __init__(self, db, logger=None):
        self.db = db
        self.account = Factory.get("Account")(db)
        self.constants = Factory.get("Constants")(db)
        self.person = Factory.get("Person")(db)
        self.ou = Factory.get("OU")(db)
        self.ad_email = AdEmail(db)
        self.et = Email.EmailTarget(db)
        self.ea = Email.EmailAddress(db)
        self.edom = Email.EmailDomain(db)
        self.epat = Email.EmailPrimaryAddressTarget(db)
        if logger == None:
            self.logger = Factory.get_logger("cronjob")
        else:
            self.logger = logger

    def build_email_list(self):
        email_list = {}
        res = self.ad_email.search_ad_email()
        for entity in res:
            email = "%s@%s" % (entity['local_part'], entity['domain_part'])
            email_list[entity['account_name']] = email
        return email_list

    def get_employee_email(self, account_name):
        email_list = {}
        res = self.ad_email.search_ad_email(account_name=account_name)
        for entity in res:
            email = "%s@%s" % (entity['local_part'], entity['domain_part'])
            email_list[entity['account_name']] = email
        return email_list

    def process_mail(self, account_id, addr, is_primary=False,expire_date = None):
        self.logger.debug("account_id to email.process_mail = %s" % account_id)
        if (addr==None):
            #this account has no email address attached to it.
            # return None to the calling process
            return None
        addr = addr.lower()
        fld = addr.split('@')
        if len(fld) != 2:
            self.logger.error("Bad address: %s. Skipping", addr)
            return None
        lp, dom = fld

        try:
            self.logger.debug("ld = %s,dom = %s" % (lp,dom))
            self.edom.find_by_domain(dom)
            self.logger.debug("Domain found: %s: %d", dom, self.edom.entity_id)
        except Errors.NotFoundError:
            self.edom.populate(dom, "Generated by no.uit.process_mail.")
            self.edom.write_db()
            self.logger.debug("Domain created: %s: %d", dom, self.edom.entity_id)

        try:
            self.et.find_by_target_entity(int(account_id))
            self.logger.debug("EmailTarget found(account): %s: %d",
                         account_id, self.et.entity_id)
        except Errors.NotFoundError:
            self.et.populate(self.constants.email_target_account, 
                             target_entity_id=int(account_id),
                             target_entity_type=self.constants.entity_account)
            self.et.write_db()
            self.logger.debug("EmailTarget created: %s: %d",
                         account_id, self.et.entity_id)

        try:
            self.ea.find_by_address(addr)
            self.logger.debug("EmailAddress found: addr='%s': ea_id:%d", addr, self.ea.entity_id)
        except Errors.NotFoundError:
            self.ea.populate(lp, self.edom.entity_id, self.et.entity_id,expire_date)
            self.ea.write_db()
            self.logger.debug("EmailAddress created: addr='%s': ea_id='%d'", addr, self.ea.entity_id)

        try:
            self.epat.find(self.et.entity_id)
            self.logger.debug("EmailPrimary found: addr=%s,et=%d ea=%d" ,
                               addr, self.epat.entity_id, self.epat.email_primaddr_id)
            if (is_primary and (self.epat.email_primaddr_id != self.ea.entity_id)):
                self.logger.info("EmailPrimary NOT equal to this email id (%d), updating..." % self.ea.entity_id)

                try:
                    self.epat.delete()  # deletes old emailprimary, ready to create new
                    self.epat.clear()
                    self.epat.populate(self.ea.entity_id, parent=self.et)
                    self.epat.write_db()
                    self.logger.debug("EmailPrimary created: addr='%s'(ea_id=%d): et_id%d", addr, self.ea.entity_id, self.epat.entity_id)
                except Exception, msg:
                    self.logger.error("EmailPrimaryAddess Failed to set for %s: ea: %d, et: %d! Reason:%s",
                                       addr, self.ea.entity_id, self.et.entity_id,str(msg).replace('\n','--'))    
        except Errors.NotFoundError:
            if self.ea.email_addr_target_id == self.et.entity_id:
                if(is_primary):
                    self.epat.clear()
                    self.epat.populate(self.ea.entity_id, parent=self.et)
                    self.epat.write_db()
                    self.logger.debug("EmailPrimary created: addr='%s': et_id='%d', ea_id='%d'",
                                      addr, self.epat.entity_id,self.ea.entity_id)
            else:
                self.logger.error("EmailTarget mismatch: ea: %d, et: %d: EmailPrimary not set",
                             self.ea.email_addr_target_id, self.et.entity_id)
    
        self.et.clear()
        self.ea.clear()
        self.edom.clear()
        self.epat.clear()
