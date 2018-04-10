# -*- coding: utf-8 -*-
# Copyright 2003-2018 University of Oslo, Norway
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

"""Generates a mail tree for LDAP."""

from __future__ import unicode_literals

import mx

from collections import defaultdict

from Cerebrum import Errors
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.modules import Email
from Cerebrum.Utils import Factory, mark_update
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.modules.bofhd.utils import BofhdRequests


class EmailLDAP(DatabaseAccessor):
    """The EmailLDAP class is used to gather methodes used to generate
    an ldif for mail-backends."""

    __metaclass__ = mark_update

    __write_attr__ = ('aid2addr', 'targ2addr', 'targ2prim', 'targ2spam',
                      'targ2quota', 'serv_id2server', 'targ2server_id',
                      'targ2forward', 'targ2vacation', 'acc2name', 'pending',
                      'e_id2passwd')

    def __init__(self, db):
        super(EmailLDAP, self).__init__(db)
        self.acc = Factory.get('Account')(db)
        self.const = Factory.get('Constants')(db)
        self.grp = Factory.get('Group')(db)
        # Internal structure:
        self.aid2addr = {}
        self.targ2addr = defaultdict(set)
        self.targ2prim = {}
        self.targ2spam = {}
        self.targ2filter = defaultdict(list)
        self.targ2quota = {}
        self.serv_id2server = {}
        self.targ2server_id = {}
        self.targ2forward = defaultdict(list)
        self.targ2localdelivery = set()
        self.targ2vacation = {}
        self.acc2name = {}
        self.pending = {}
        self.e_id2passwd = {}
        # Used by multi
        self.group2addr = defaultdict(set)
        self.group2missing = defaultdict(set)
        self.multi_addr_cache = {}
        self.multi_missing_cache = {}
        self.multi_reserved_cache = {}

    def _build_addr(self, local_part, domain):
        return '@'.join((local_part, domain))

    def get_targettype(self, targettype):
        return str(targettype)

    def get_target_info(self, row):
        """Return additional EmailLDAP-entry derived from L{row}.

        Return site-specific mail-ldap-information pertaining to the EmailTarget info in L{row}.

        @type row: db-row instance
        @param row: A db-row holding one result of L{list_email_targets_ext}.

        @rtype: dict
        @return: A dictinary mapping attributes to values for the specified EmailTarget in L{row}.
        """

        co = self.const
        target_type = co.EmailTarget(int(row["target_type"]))
        alias = row['alias_value']
        ei = row['target_entity_id']
        if ei is not None:
            ei = int(ei)
        et = row['target_entity_type']
        if et is not None:
            et = int(et)

        result = {"targetType": self.get_targettype(target_type)}
        if target_type in (co.email_target_pipe, co.email_target_file,
                           co.email_target_Sympa, co.email_target_RT):
            result["target"] = alias
        elif target_type in (co.email_target_account, co.email_target_deleted):
            if et == co.entity_account and ei in self.acc2name:
                result["target"] = self.acc2name[ei]

        return result

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

        target = int(row["target_id"])
        ei = row['target_entity_id']
        if ei is not None:
            ei = int(ei)
        result = dict()

        if target not in self.targ2server_id:
            return result

        server_type, server_name = self.serv_id2server[
                                       int(self.targ2server_id[target])]
        if server_type == self.const.email_server_type_exchange:
            result["ExchangeServer"] = server_name
        elif server_type == self.const.email_server_type_cyrus:
            result["IMAPserver"] = server_name

        return result

    def read_addr(self):
        mail_addr = Email.EmailAddress(self._db)
        for row in mail_addr.list_email_addresses_ext():
            a_id, t_id = int(row['address_id']), int(row['target_id'])
            lp, dom = row['local_part'], row['domain']
            addr = self._build_addr(lp, dom)
            self.targ2addr[t_id].add(addr)
            self.aid2addr[a_id] = addr

    def read_prim(self):
        mail_prim = Email.EmailPrimaryAddressTarget(self._db)
        for row in mail_prim.list_email_primary_address_targets():
            self.targ2prim[int(row['target_id'])] = int(row['address_id'])

    def read_spam(self):
        mail_spam = Email.EmailSpamFilter(self._db)
        for row in mail_spam.list_email_spam_filters_ext():
            self.targ2spam[int(row['target_id'])] = [row['level'],
                                                     row['code_str']]

    def read_quota(self):
        mail_quota = Email.EmailQuota(self._db)
        for row in mail_quota.list_email_quota_ext():
            self.targ2quota[int(row['target_id'])] = [row['quota_soft'],
                                                      row['quota_hard']]

    def read_target_filter(self):
        const2str = {}
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, Email._EmailTargetFilterCode):
                const2str[int(tmp)] = str(tmp)

        mail_target_filter = Email.EmailTargetFilter(self._db)
        for row in mail_target_filter.list_email_target_filter():
            t_id = int(row['target_id'])
            f_id = int(row['filter'])
            self.targ2filter[t_id].append(const2str[f_id])

    # why is spread sent as a parameter here and then not used?
    # should probably remove the option (Jazz, 2013-12)
    def read_server(self, spread):
        mail_serv = Email.EmailServer(self._db)
        for row in mail_serv.list_email_server_ext():
            self.serv_id2server[int(row['server_id'])] = [row['server_type'],
                                                          row['name']]
        mail_targ = Email.EmailTarget(self._db)
        for row in mail_targ.list_email_server_targets():
            self.targ2server_id[int(row['target_id'])] = int(row['server_id'])

    def read_forward(self):
        mail_forw = Email.EmailForward(self._db)
        for row in mail_forw.search(enable=True):
            self.targ2forward[int(row['target_id'])].append(row['forward_to'])

    def read_local_delivery(self):
        mail_forw = Email.EmailForward(self._db)
        self.targ2localdelivery = set([x['target_id'] for x in mail_forw.list_local_delivery()])

    def read_vacation(self):
        mail_vaca = Email.EmailVacation(self._db)
        for row in mail_vaca.list_email_active_vacations():
            t_id = int(row['target_id'])
            insert = False
            if t_id in self.targ2vacation:
                if row['start_date'] > self.targ2vacation[t_id][1]:
                    insert = True
            else:
                insert = True
            if insert:
                self.targ2vacation[t_id] = (row['vacation_text'],
                                            row['start_date'],
                                            row['end_date'])

    def read_accounts(self, spread):
        # Since get_target() can be called for target type "deleted",
        # we need to include expired accounts.
        for row in self.acc.list_names(self.const.account_namespace):
            self.acc2name[int(row['entity_id'])] = row['entity_name']

    def read_pending_moves(self):
        br = BofhdRequests(self._db, self.const)
        # We define near future as 15 minutes from now.
        near_future = mx.DateTime.now() + mx.DateTime.DateTimeDelta(0, 0, 15)
        for op in (self.const.bofh_email_create,
                   self.const.bofh_email_convert):
            for r in br.get_requests(operation=op):
                if r['run_at'] < near_future:
                    self.pending[int(r['entity_id'])] = True

    def get_multi_target(self, group_id, ignore_missing=False):
        member_addrs = list(self.group2addr[group_id])
        if ignore_missing:
            return member_addrs, list(self.group2missing[group_id])
        else:
            return member_addrs

    def read_multi_data(self, ignore_missing=False):
        et = Email.EmailTarget(self._db)
        multi_groups = set()
        for row in et.list_email_targets_ext(target_type=
                                             self.const.email_target_multi):
            multi_groups.add(row['target_entity_id'])

        group2groupmembers = defaultdict(set)
        for row in self.grp.search_members(group_id=multi_groups,
                                           indirect_members=True):
            member_id = int(row['member_id'])
            member_type = row['member_type']
            # Note group_id is the actual group the member is a member of, not
            # necessarily any of those given as argument to search_members.
            group_id = int(row['group_id'])
            if member_type == self.const.entity_group:
                group2groupmembers[group_id].add(member_id)
            elif member_type == self.const.entity_account:
                if member_id in self.multi_addr_cache:
                    self.group2addr[group_id].add(self.multi_addr_cache[member_id])
                elif member_id in self.multi_missing_cache:
                    self.group2missing[group_id].add(self.multi_missing_cache[member_id])
                elif member_id in self.multi_reserved_cache:
                    continue
                else:
                    self.acc.clear()
                    self.acc.find(member_id)
                    if self.acc.is_reserved():
                        self.multi_reserved_cache.add(member_id)
                        continue
                    # The address selected for the target will become the
                    # envelope recipient address after expansion, so it must
                    # be a value the user expects.  Use primary address rather
                    # than random element from targ2addr.
                    try:
                        tmp = self.acc.get_primary_mailaddress()
                        self.multi_addr_cache[member_id] = tmp
                        self.group2addr[group_id].add(tmp)
                    except Errors.NotFoundError:
                        self.group2missing[group_id].add(self.acc.account_name)
                        self.multi_missing_cache[member_id] = self.acc.account_name
                        if not ignore_missing:
                            raise ValueError('%s in group %s has no primary address' %
                                             (self.acc.account_name, group_id))

        def update_addr_and_missing(m_group, group_id):
            if group_id in self.group2addr:
                self.group2addr[m_group].update(self.group2addr[group_id])
            if group_id in self.group2missing:
                self.group2missing[m_group].update(self.group2missing[group_id])
            if group_id in group2groupmembers:
                for g in group2groupmembers[group_id]:
                    update_addr_and_missing(m_group, g)

        # Make sure to add any members from indirect members
        for m_group in multi_groups:
            if m_group in group2groupmembers:
                for group_id in group2groupmembers[m_group]:
                    update_addr_and_missing(m_group, group_id)

    def read_target_auth_data(self):
        # For the time being, remove passwords for all quarantined
        # accounts, regardless of quarantine type.
        quarantines = dict([(x, "*locked") for x in
                            QuarantineHandler.get_locked_entities(
                            self._db, entity_types=self.const.entity_account)])
        for row in self.acc.list_account_authentication():
            a_id = int(row['account_id'])
            self.e_id2passwd[a_id] = quarantines.get(a_id) or row['auth_data']

    def read_misc_target(self):
        # Dummy method for Mixin-classes. By default it generates a hash with
        # nothing, but one could populate non-default attributes using this
        # method(in a Mixin-class). Entry per target. If more than one attribute
        # should be populated, cat it to the string in this hash with a '\n'
        # between them.
        pass

    def get_misc(self, row):
        """Return optional strings to the script."""
        return dict()
