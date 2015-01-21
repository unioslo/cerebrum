# -*- coding: iso-8859-1 -*-
# Copyright 2003-2009 University of Oslo, Norway
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

try:
    set()
except NameError:
    from sets import Set as set

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
        self.targ2filter = {}
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

        co = self.const
        target_type = co.EmailTarget(int(row["target_type"]))
        alias = row['alias_value']
        ei = row['target_entity_id']
        if ei is not None:
            ei = int(ei)
        et = row['target_entity_type']
        if et is not None:
            et = int(et)

        result = {"targetType": self.get_targettype(target_type),}
        if target_type in (co.email_target_Mailman, co.email_target_Sympa,
                           co.email_target_pipe, co.email_target_RT,
                           co.email_target_file):
            result["target"] = alias
        elif target_type in (co.email_target_account, co.email_target_deleted):
            if et == co.entity_account and ei in self.acc2name:
                target, junk = self.acc2name[ei]
                result["target"] = target

        return result
    # end get_target_info

        
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
        uname, home = self.acc2name.get(ei, (None, None))
        result = dict()

        if target not in self.targ2server_id:
            return result

        server_type, server_name = self.serv_id2server[
                                       int(self.targ2server_id[target])]
        if server_type == self.const.email_server_type_nfsmbox:
            if not home:
                home = "/home/%s" % uname
            maildrop = "/var/spool/mail"
            result["spoolInfo"] = "home=%s maildrop=%s/%s" % (home,
                                                              maildrop,
                                                              uname)
        elif server_type == self.const.email_server_type_exchange:
            result["ExchangeServer"] = server_name
        elif server_type == self.const.email_server_type_cyrus:
            result["IMAPserver"] = server_name

        return result
    # end get_server_info
    
    
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
            self.targ2filter.setdefault(t_id, []).append(const2str[f_id])

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
        for row in mail_forw.list_email_forwards():
            self.targ2forward.setdefault(int(row['target_id']),
                                         []).append([row['forward_to'],
                                                     row['enable']])

    def read_vacation(self):
        mail_vaca = Email.EmailVacation(self._db)
        cur = mx.DateTime.today()
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
            home = acc.resolve_homedir(account_name=row['entity_name'],
                                       home=row['home'],
                                       disk_path=row['path'])
            self.acc2name[int(row['account_id'])] = [row['entity_name'], home]


    def read_pending_moves(self):
        br = BofhdRequests(self._db, self.const)
        # We define near future as 15 minutes from now.
        near_future = mx.DateTime.now() + mx.DateTime.DateTimeDelta(0, 0, 15)
        for op in (self.const.bofh_email_create,
                   self.const.bofh_email_move,
                   self.const.bofh_email_convert):
            for r in br.get_requests(operation=op):
                if r['run_at'] < near_future:
                    self.pending[int(r['entity_id'])] = True


    def read_multi_target(self, group_id, ignore_missing=False):
        mail_targ = Email.EmailTarget(self._db)
        grp = Factory.get('Group')(self._db)
        acc = Factory.get('Account')(self._db)
        grp.clear()
        try:
            grp.find(group_id)
        except Errors.NotFoundError:
            raise ValueError, "no group found: %d" % group_id
        member_addrs = set()
        missing_addrs = set()
        for member in grp.search_members(group_id=grp.entity_id,
                                         indirect_members=True,
                                         member_type=self.const.entity_account):
            acc.clear()
            acc.find(member["member_id"])
            if acc.is_reserved():
                continue
            # The address selected for the target will become the
            # envelope recipient address after expansion, so it must
            # be a value the user expects.  Use primary address rather
            # than random element from targ2addr.
            try:
                member_addrs.add(acc.get_primary_mailaddress())
            except Errors.NotFoundError:
                missing_addrs.add(acc.account_name)
                if not ignore_missing:
                    raise ValueError, ("%s in group %s has no primary address" %
                                        (acc.account_name, grp.group_name))
        if ignore_missing:
            return list(member_addrs), list(missing_addrs)
        else:
            return list(member_addrs)


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

    def get_misc(self, row):
        """Return optional strings to the script."""
        return dict()
    # end get_misc

# end class EmailLDAP

