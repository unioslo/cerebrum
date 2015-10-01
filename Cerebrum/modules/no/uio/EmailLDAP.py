# -*- coding: iso-8859-1 -*-
# Copyright 2003, 2004 University of Oslo, Norway
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

import os
import re
import sys
import string
import time
import mx

from collections import defaultdict

from Cerebrum import Errors
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.EmailLDAP import EmailLDAP
from Cerebrum.modules.LDIFutils import iso2utf


class EmailLDAPUiOMixin(EmailLDAP):
    """Methods specific for UiO."""

    def __init__(self, db):
        self.__super.__init__(db)
        self.mail_dom = Email.EmailDomain(self._db)
        # mapping between a target id and its ulrik.uio.no-address. This is
        # required for account email_targets at postmasters' request.
        self.targ2ulrik_addr = {}
        # exchange-relatert-jazz
        # will use this list to exclude forwards and vacation messages for
        # accounts with Exchange-mailbox
        self.targ2spread = self.target2spread_populate()

        # keys: account email target ids with pending 'email_primary_address' events
        # values: list of event ids
        # read_pending_primary_email() is called by read_addr()
        self.pending_primary_email = defaultdict(list)
    # end __init__

    spam_act2dig = {'noaction':   '0',
                    'spamfolder': '1',
                    'dropspam':   '2',
                    'greylist':   '3'}
    db_tt2ldif_tt = {'account': 'user',
                     'forward': 'forwardAddress'}



    def get_targettype(self, targettype):
        return self.db_tt2ldif_tt.get(str(targettype), str(targettype))

    def get_server_info(self, row):
        """Return additional mail server info for EmailLDAP-entry derived
        from row.

        Return additional mail server information for certain
        EmailTargets. Specifically, server info is gathered for
        email_target_account only (the rest we don't care about).

        @param row: cf. L{get_target_info}

        @rtype: dict (basestring to basestring)
        @return:
          A dictionary with additional attributes for the EmailLDAP-entry
          based on L{row}. 
        """

        result = dict()
        target_id = int(row["target_id"])
        ei = row['target_entity_id']
        if ei is not None:
            ei = int(ei)
        # Unless we have information on that account, we are done.
        if ei not in self.acc2name:
            return result

        if target_id not in self.targ2server_id:
            return result

        server_type, server_name = self.serv_id2server[
                                       int(self.targ2server_id[target_id])]
        result["IMAPserver"] = server_name
        # jsama says that we disable this for nao..!
        #if server_type == self.const.email_server_type_cyrus:
        #    result["IMAPserver"] = server_name
        #elif server_type == self.const.email_server_type_exchange:
        #    result["Exchangeserver"] = server_name
        return result
    # end get_server_info

    def get_target_info(self, row):
        """Return additional EmailLDAP-entry derived from L{row}.

        Return site-specific mail-ldap-information pertaining to the
        EmailTarget info in L{row}.

        @type row: db-row instance
        @param row:
          A db-row holding one result of L{list_email_targets_ext}.

        @rtype: dict
        @return:
          A dictinary mapping attributes to values for the specified
          EmailTarget in L{row}. 
        """

        sdict = super(EmailLDAPUiOMixin, self).get_target_info(row)
        target_type = self.const.EmailTarget(int(row['target_type']))
        target_id = int(row["target_id"])
        if target_type in (self.const.email_target_Sympa,):
            # host info
            # IVR 2008-07-24 FIXME: This is really ugly. For now there is no
            # connection between email server and its name in the DNS
            # module. We have to hack our way around it. For UiO, simply
            # appending ".uio.no" should work, but this is a highly
            # unnecessary assumption. When the DNS module is revamped, we
            # should be able to replace this ugliness.
            server_id = row["server_id"]
            if server_id is None:
                return sdict

            # Let's try locating the bugger:
            host = Factory.get("Host")(self._db)
            try:
                host.find(server_id)
                sdict["commandHost"] = host.name + ".uio.no"
            except Errors.NotFoundError:
                # IVR 2008-07-24 TBD: What to do? Can we have an LDIF-entry
                # for sympa without the host part?
                pass
        elif target_type == self.const.email_target_account:
            if target_id in self.targ2ulrik_addr:
                sdict["stableMailAddress"] = self.targ2ulrik_addr[target_id]
            
        return sdict
    # end get_target_info

    def _build_addr(self, local_part, domain):
        domain = self.mail_dom.rewrite_special_domains(domain)
        return '@'.join((local_part, domain))

    def read_spam(self):
        mail_spam = Email.EmailSpamFilter(self._db)
        for row in mail_spam.list_email_spam_filters_ext():
            self.targ2spam[int(row['target_id'])] = [
                row['level'], self.spam_act2dig.get(row['code_str'], '0')]

    def read_addr(self):
        mail_addr = Email.EmailAddress(self._db)
        # Handle "magic" domains.
        #   local_part@magic_domain
        # defines
        #   local_part@[all domains with category magic_domains],
        # overriding any entry for that local_part in any of those
        # domains.
        glob_addr = {}
        for dom_catg in (self.const.email_domain_category_uio_globals,):
            domain = str(dom_catg)
            lp_dict = {}
            glob_addr[domain] = lp_dict
            # Fill glob_addr[magic domain][local_part]
            for row in mail_addr.list_email_addresses_ext(domain):
                lp_dict[row['local_part']] = row
            for row in self.mail_dom.list_email_domains_with_category(dom_catg):
                # Alias glob_addr[domain name] to glob_addr[magic domain],
                # for later "was local_part@domain overridden" check.
                glob_addr[row['domain']] = lp_dict
                # Update dicts 'targ2addr' and 'aid2addr' with the
                # override addresses.
                for lp, row2 in lp_dict.items():
                    # Use 'row', and not 'row2', for domain.  Using 'dom2'
                    # would give us 'UIO_GLOBALS'.
                    addr = self._build_addr(lp, row['domain'])
                    t_id = int(row2['target_id'])
                    self.targ2addr[t_id].add(addr)
                    # Note: We don't need to update aid2addr here, as
                    # addresses @UIO_GLOBALS aren't allowed to be primary
                    # addresses.
        for row in mail_addr.list_email_addresses_ext():
            lp, dom = row['local_part'], row['domain']
            if (dom == "ulrik.uio.no"):
                self.targ2ulrik_addr[int(row["target_id"])] = lp + "@" + dom
                
            # If this address is in a domain that is subject to overrides
            # from "magic" domains, and the local_part was overridden, skip
            # this row from being added to targ2addr.
            addr = self._build_addr(lp, dom)
            a_id, t_id = [int(row[x]) for x in ('address_id', 'target_id')]
            self.aid2addr[a_id] = addr
            if glob_addr.has_key(dom) and glob_addr[dom].has_key(lp):
                continue
            self.targ2addr[t_id].add(addr)

        # look for primary email changes that are still pending in the event log
        self.read_pending_primary_email()

    def read_target_auth_data(self):
        a = Factory.get('Account')(self._db)
        # Same as default, but omit co.quarantine_auto_emailonly
        quarantines = dict(
            [(x, "*locked") for x in
             QuarantineHandler.get_locked_entities(
             self._db,
             entity_types=self.const.entity_account,
             ignore_quarantine_types=self.const.quarantine_auto_emailonly)])
        for row in a.list_account_authentication():
            a_id = int(row['account_id'])
            self.e_id2passwd[a_id] = quarantines.get(a_id) or row['auth_data']

    # exchange-relatert-jazz
    # hardcoding exchange spread since there is no case for any other
    # known spreads at this point
    def target2spread_populate(self):
        a = Factory.get('Account')(self._db)
        exspread = self.const.spread_exchange_account
        ttype = self.const.email_target_account
        et = Email.EmailTarget(self._db)
        exchangeaccounts = set()
        ret = set()
        for row in a.search(expire_start=None, spread=exspread):
            exchangeaccounts.add(int(row['account_id']))
        for row in et.list_email_targets_ext(target_type=ttype):
            if int(row['target_entity_id']) in exchangeaccounts:
                ret.add(int(row['target_id']))
        return ret
                
    # exchange-relatert-jazz
    # 
    # it would have been more elegant to split read_forward
    # into more managable parts and reduce the code that
    # needs to be doubled in that manner, but no time for 
    # such things now (Jazz, 2013-12)
    # overriding read forward locally in order to be able to 
    # exclude forward for accounts with exchange_spread
    def read_forward(self):
        mail_forw = Email.EmailForward(self._db)
        for row in mail_forw.search(enable=True):
            # if the target is recorded as having spread_exchange_acc
            # the whole row is skipped because we don't want to
            # export forwards for such targets to LDAP
            t_id = int(row['target_id'])
            if t_id not in self.targ2spread:
                self.targ2forward[t_id].append(row['forward_to'])
    # exchange-relatert-jazz
    # 
    # it would have been more elegant to split read_vacation
    # into more managable parts and reduce the code that
    # needs to be doubled in that manner, but no time for 
    # such things now (Jazz, 2013-12)
    # overriding read_vacation locally in order to be able to 
    # exclude vacation messages for accounts with exchange_spread
    def read_vacation(self):
        mail_vaca = Email.EmailVacation(self._db)
        for row in mail_vaca.list_email_active_vacations():
            t_id = int(row['target_id'])
            # exchange-relatert-jazz
            # if the target is recorded as having spread_exchange_acc
            # the whole row is skipped because we don't want to
            # export vacation messages for such targets to LDAP
            if t_id in self.targ2spread:
                continue
            insert = False
            if t_id in self.targ2vacation:
                if row['start_date'] > self.targ2vacation[t_id][1]:
                    insert = True
            else:
                insert = True
            if insert:
                self.targ2vacation[t_id] = (iso2utf(row['vacation_text']),
                                            row['start_date'],
                                            row['end_date'])

    def read_pending_primary_email(self):
        """Fetches the subject ids (email target ids) that have unprocessed
        email_primary_address events for target system Exchange."""
        # fetch event ids
        pending_events = [int(row['event_id']) for row in self._db.search_events(
            type=(self.const.email_primary_address_mod,
                  self.const.email_primary_address_add,
                  self.const.email_primary_address_rem),
            target_system=self.const.target_system_exchange)]

        # add each email target id to our list of pending targets
        for event_id in pending_events:
            try:
                event = self._db.get_event(event_id=event_id)
                target = int(event['subject_entity'])
                self.pending_primary_email[target].append(event_id)
            except Errors.NotFoundError:
                continue
