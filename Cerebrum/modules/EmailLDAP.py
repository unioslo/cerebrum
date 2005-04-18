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

"""."""

import os
import re
import time
import string
import mx

from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.Utils import Factory, mark_update
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.LDIFutils import iso2utf

class EmailLDAP(DatabaseAccessor):
    """The EmailLDAP class is used to gather methodes used to generate
    an ldif for mail-backends."""
    
    __metaclass__ = mark_update

    __write_attr__ = ('aid2addr', 'targ2addr', 'targ2prim', 'targ2spam',
                      'targ2quota', 'targ2virus', 'serv_id2server',
                      'targ2server_id', 'targ2forward', 'targ2vacation',
                      'acc2name', 'pending', 'e_id2passwd')


    def __init__(self, db):
        super(EmailLDAP, self).__init__(db)
        self.const = Factory.get('Constants')(db)
        # Internal structure:
        self.aid2addr = {}
        self.targ2addr = {}
        self.targ2prim = {}
        self.targ2spam = {}
        self.targ2quota = {}
        self.targ2virus = {}
        self.serv_id2server = {}
        self.targ2server_id = {}
        self.targ2forward = {}
        self.targ2vacation = {}
        self.acc2name = {}
        self.pending = {}
        self.e_id2passwd = {}
       

    def _build_addr(self, local_part, domain):
        return '@'.join((local_part, domain))


    def get_targettype(self, targettype):
        return str(targettype)

    def get_target(self, entity_id, target_id):
        return self.acc2name[entity_id][0]

    def get_server_info(self, target, entity, home, path):
        # Find mail-server settings:
        uname = self.acc2name[entity][0]
        sinfo = ""
        if self.targ2server_id.has_key(target):
            type, name = self.serv_id2server[int(self.targ2server_id[target])]
            if type == self.const.email_server_type_nfsmbox:
                if not home:
                    home = "/home/%s" % uname
                maildrop = "/var/spool/mail"
                sinfo += "spoolInfo: home=%s maildrop=%s/%s\n" % (
                    home, maildrop, uname)
            elif type == self.const.email_server_type_cyrus:
                sinfo += "IMAPserver: %s\n" % name
        return sinfo
    
    
    def read_addr(self):
        mail_dom = Email.EmailDomain(self._db)
        mail_addr = Email.EmailAddress(self._db)
        for row in mail_addr.list_email_addresses_ext():
            a_id, t_id = int(row['address_id']), int(row['target_id'])
            lp, dom = row['local_part'], row['domain']
            addr = self._build_addr(lp, dom)
            self.targ2addr.setdefault(t_id, []).append(addr)
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

        
    def read_virus(self):
        mail_virus = Email.EmailVirusScan(self._db)
        for row in mail_virus.list_email_virus_ext():
            self.targ2virus[int(row['target_id'])] = [row['found_str'],
                                                      row['removed_str'],
                                                      row['enable']]


    def read_server(self, spread):
        mail_serv = Email.EmailServer(self._db)
        for row in mail_serv.list_email_server_ext():
            self.serv_id2server[int(row['server_id'])] = [row['server_type'],
                                                          row['name']]
        mail_targ_serv = Email.EmailServerTarget(self._db)
        for row in mail_targ_serv.list_email_server_targets():
            self.targ2server_id[int(row['target_id'])] = int(row['server_id'])

            
    def read_forward(self):
        mail_forw = Email.EmailForward(self._db)
        for row in mail_forw.list_email_forwards():
            self.targ2forward.setdefault(int(row['target_id']),
                                         []).append([row['forward_to'],
                                                     row['enable']])

        
    def read_vacation(self):
        mail_vaca = Email.EmailVacation(self._db)
        cur = mx.DateTime.now()
        def prefer_row(row, oldval):
            o_txt, o_sdate, o_edate, o_enable = oldval
            txt, sdate, edate, enable = [row[x]
                                         for x in ('vacation_text',
                                                   'start_date',
                                                   'end_date', 'enable')]
            spans_now = (sdate <= cur and (edate is None or edate >= cur))
            o_spans_now = (o_sdate <= cur and (o_edate is None or o_edate >= cur))
            row_is_newer = sdate > o_sdate
            if spans_now:
                if enable == 'T' and o_enable == 'F': return True
                elif enable == 'T' and o_enable == 'T':
                    if o_spans_now:
                        return row_is_newer
                    else: return True
                elif enable == 'F' and o_enable == 'T':
                    if o_spans_now: return False
                    else: return True
                else:
                    if o_spans_now: return row_is_newer
                    else: return True
            else:
                if o_spans_now: return False
                else: return row_is_newer

        for row in mail_vaca.list_email_vacations():
            t_id = int(row['target_id'])
            insert = False
            if self.targ2vacation.has_key(t_id):
                if prefer_row(row, self.targ2vacation[t_id]):
                    insert = True
            else:
                insert = True
            if insert:
                # Make sure vacations that doesn't span now aren't marked
                # as active, even though they might be registered as
                # 'enabled' in the database.
                enable = False
                if row['start_date'] <= cur and (row['end_date'] is None
                                                 or row['end_date'] >= cur):
                    enable = (row['enable'] == 'T')
                self.targ2vacation[t_id] = (iso2utf(row['vacation_text']),
                                            row['start_date'],
                                            row['end_date'],
                                            enable)


    def read_accounts(self, spread):
        acc = Factory.get('Account')(self._db)
        # Since get_target() can be called for target type "deleted",
        # we need to include expired accounts.
        for row in acc.list_account_home(home_spread=spread,
                                         include_nohome=True,
                                         filter_expired=False):
            self.acc2name[int(row['account_id'])] = [row['entity_name'],
                                                     row['home'],
                                                     row['path']]


    def read_pending_moves(self):
        br = BofhdRequests(self._db, self.const)
        for op in (self.const.bofh_email_create,
                   self.const.bofh_email_move,
                   self.const.bofh_email_convert):
            for r in br.get_requests(operation=op):
                self.pending[int(r['entity_id'])] = True


    def read_multi_target(self, group_id):
        mail_targ = Email.EmailTarget(self._db)
        grp = Factory.get('Group')(self._db)
        acc = Factory.get('Account')(self._db)
        grp.clear()
        try:
            grp.find(group_id)
        except Errors.NotFoundError:
            raise ValueError, "no group found: %d" % group_id
        member_addrs = []
        for member_id in grp.get_members():
            acc.clear()
            acc.find(member_id)
            if acc.is_reserved():
                continue
            # The address selected for the target will become the
            # envelope recipient address after expansion, so it must
            # be a value the user expects.  Use primary address rather
            # than random element from targ2addr.
            try:
                member_addrs.append(acc.get_primary_mailaddress())
            except Errors.NotFoundError:
                raise ValueError, ("%s in group %s has no primary address" %
                                   (acc.account_name, grp.group_name))
        return member_addrs


    def read_target_auth_data(self):
        a = Factory.get('Account')(self._db)
        # For the time being, remove passwords for all quarantined
        # accounts, regardless of quarantine type.
        quarantines = {}
        now = mx.DateTime.now()
        for row in a.list_entity_quarantines(
                entity_types = self.const.entity_account):
            if (row['start_date'] <= now
                and (row['end_date'] is None or row['end_date'] >= now)
                and (row['disable_until'] is None
                     or row['disable_until'] < now)):
                # The quarantine in this row is currently active.
                quarantines[int(row['entity_id'])] = "*locked"
        for row in a.list_account_authentication():
            account_id = int(row['account_id'])
            self.e_id2passwd[account_id] = (
                row['entity_name'],
                quarantines.get(account_id) or row['auth_data'])
        for row in a.list_account_authentication(self.const.auth_type_crypt3_des):
            # *sigh* Special-cases do exist. If a user is created when the
            # above for-loop runs, this loop gets a row more. Before I ignored
            # this, and the whole thing went BOOM on me.
            account_id = int(row['account_id'])
            if not self.e_id2passwd.get(account_id, (0, 0))[1]:
                self.e_id2passwd[account_id] = (
                    row['entity_name'],
                    quarantines.get(account_id) or row['auth_data'])


    def read_misc_target(self):
        # Dummy method for Mixin-classes. By default it generates a hash with
        # nothing, but one could populate non-default attributes using this
        # method(in a Mixin-class). Entry per target. If more than one attribute
        # should be populated, cat it to the string in this hash with a '\n'
        # between them.
        pass

    def get_misc(self, entity_id, target_id, email_target_type):
        # Return optional strings to the script.
        pass
    
# arch-tag: ec5fc24f-7ccb-415c-a0f9-c87c7230a2cb
