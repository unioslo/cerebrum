# -*- coding: utf-8 -*-
#
# Copyright 2003-2019 University of Tromsø, Norway
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
import logging
import re

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.Email import AccountEmailMixin
from Cerebrum.modules.no.uit.ad_email import AdEmail

logger = logging.getLogger(__name__)


class UiTAccountEmailMixin(AccountEmailMixin):
    """
    Account-mixin for email functionality @ UiT.
    """
    def get_email_cn_local_part(self, given_names=-1, max_initials=None,
                                keep_dash=True):
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

        assert (given_names >= -1)
        assert (max_initials is None or max_initials >= 0)

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

    def getdict_uname2mailinfo(self, filter_expired_accounts=True,
                               filter_expired_emails=True):
        ret = {}
        target_type = int(self.const.email_target_account)
        namespace = int(self.const.account_namespace)
        where = ["en.value_domain = :namespace"]

        if filter_expired_accounts:
            where.append("(ai.expire_date IS NULL OR ai.expire_date > [:now])")

        if filter_expired_emails:
            where.append("(ea.expire_date IS NULL OR ea.expire_date > [:now])")

        stmt = """
          SELECT en.entity_name, ea.local_part, ed.domain, ei.created_at,
                 ea.change_date, ea.expire_date
          FROM [:table schema=cerebrum name=account_info] ai
          JOIN [:table schema=cerebrum name=entity_name] en
            ON en.entity_id = ai.account_id
          JOIN [:table schema=cerebrum name=entity_info] ei
            ON ei.entity_id = en.entity_id
          JOIN [:table schema=cerebrum name=email_target] et
            ON et.target_type = :targ_type AND
               et.target_entity_id = ai.account_id
          JOIN [:table schema=cerebrum name=email_address] ea
            ON ea.target_id = et.target_id
          JOIN [:table schema=cerebrum name=email_domain] ed
            ON ed.domain_id = ea.domain_id
          WHERE {where}
        """

        for row in self.query(
                stmt.format(where=' AND '.join(where)),
                {'targ_type': target_type, 'namespace': namespace}):
            addresses = ret.setdefault(row['entity_name'], [])
            mailinfo = {
                'local_part': row['local_part'],
                'domain': row['domain'],
                'create_date': row['created_at'],
                'change_date': row['change_date'],
                'expire_date': row['expire_date'],
            }
            addresses.append(mailinfo)
        return ret


class PrimaryAddressUtil(object):

    def __init__(self, db, **kwargs):
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

    def build_email_list(self):
        email_list = {}
        for row in self.ad_email.search_ad_email():
            email = "%s@%s" % (row['local_part'], row['domain_part'])
            email_list[row['account_name']] = email
        return email_list

    def get_employee_email(self, account_name):
        email_list = {}
        for row in self.ad_email.search_ad_email(account_name=account_name):
            email = "%s@%s" % (row['local_part'], row['domain_part'])
            email_list[row['account_name']] = email
        return email_list

    def process_mail(self, account_id, addr, is_primary=False,
                     expire_date=None):
        logger.debug("Processing primary address for account_id=%r",
                     account_id)
        if addr is None:
            # this account has no email address attached to it.
            # return None to the calling process
            return None
        lp, _, dom = addr.lower().partition('@')
        if not lp or not dom:
            logger.error("Bad email address=%r, not processing", addr)
            return None

        try:
            logger.debug("localpart=%r, domain=%r", lp, dom)
            self.edom.find_by_domain(dom)
            logger.debug("Found domain=%r, entity_id=%r",
                         dom, self.edom.entity_id)
        except Errors.NotFoundError:
            self.edom.populate(dom, "Generated by no.uit.process_mail.")
            self.edom.write_db()
            logger.debug("Created domain=%r, entity_id=%r",
                         dom, self.edom.entity_id)

        try:
            self.et.find_by_target_entity(int(account_id))
            logger.debug("EmailTarget found for account_id=%r, et_id=%r",
                         account_id, self.et.entity_id)
        except Errors.NotFoundError:
            self.et.populate(self.constants.email_target_account,
                             target_entity_id=int(account_id),
                             target_entity_type=self.constants.entity_account)
            self.et.write_db()
            logger.debug("EmailTarget created for account_id=%r, et_id=%r",
                         account_id, self.et.entity_id)

        try:
            self.ea.find_by_address(addr)
            logger.debug("EmailAddress found, addr=%r, ea_id=%r",
                         addr, self.ea.entity_id)
        except Errors.NotFoundError:
            self.ea.populate(lp, self.edom.entity_id, self.et.entity_id,
                             expire_date)
            self.ea.write_db()
            logger.debug("EmailAddress created, addr=%r, ea_id=%r",
                         addr, self.ea.entity_id)

        try:
            self.epat.find(self.et.entity_id)
            logger.debug("EmailPrimary found, addr=%r, et_id=%r, ea_id=%r",
                         addr, self.epat.entity_id,
                         self.epat.email_primaddr_id)
            if (is_primary and
                    self.epat.email_primaddr_id != self.ea.entity_id):
                logger.info("EmailPrimary is out of date (%r != %r), updating",
                            self.epat.email_primaddr_id, self.ea.entity_id)

                try:
                    # deletes old emailprimary, ready to create new
                    self.epat.delete()
                    self.epat.clear()
                    self.epat.populate(self.ea.entity_id, parent=self.et)
                    self.epat.write_db()
                    logger.debug("EmailPrimary created, addr=%r, et_id=%r, "
                                 "ea_id=%r",
                                 addr, self.epat.entity_id,
                                 self.ea.entity_id)
                except Exception:
                    logger.error("Failed to set EmailPrimaryAddess for "
                                 "addr=%r, ea_id=%r, et_id=%r",
                                 addr, self.ea.entity_id, self.et.entity_id,
                                 exc_info=True)
        except Errors.NotFoundError:
            if self.ea.email_addr_target_id == self.et.entity_id:
                if is_primary:
                    self.epat.clear()
                    self.epat.populate(self.ea.entity_id, parent=self.et)
                    self.epat.write_db()
                    logger.debug("EmailPrimary created, addr=%r, et_id=%r, "
                                 "ea_id=%r",
                                 addr, self.epat.entity_id,
                                 self.ea.entity_id)
            else:
                logger.error("Mismatch on EmailPrimary, primary address not "
                             "updated (existing et_id=%r, new et_id=%r)",
                             self.ea.email_addr_target_id, self.et.entity_id)

        self.et.clear()
        self.ea.clear()
        self.edom.clear()
        self.epat.clear()


# For legacy support
email_address = PrimaryAddressUtil
