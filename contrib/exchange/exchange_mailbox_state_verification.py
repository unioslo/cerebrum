#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014 University of Oslo, Norway
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
"""Script that checks the state of mailboxes between Cerebrum and Exchange"""

import cerebrum_path
import cereconf
import eventconf

import time
import pickle
import getopt
import sys

from Cerebrum.Utils import Factory
from Cerebrum.modules.Email import EmailQuota
from Cerebrum import Utils
from Cerebrum.Utils import read_password
import ldap

logger = Utils.Factory.get_logger('cronjob')

class StateChecker(object):
    def __init__(self, logger, conf):
        self.db = Factory.get('Database')(client_encoding='UTF-8')
        self.co = Factory.get('Constants')(self.db)
        self.ac = Factory.get('Account')(self.db)
        self.pe = Factory.get('Person')(self.db)
        self.et = Factory.get('EmailTarget')(self.db)
        self.eq = EmailQuota(self.db)

        self.config = conf
        self.logger = logger
        
        self._ldap_page_size = 1000

    def init_ldap(self):
        self.ldap_srv = ldap.ldapobject.ReconnectLDAPObject(
                                'ldap://%s/' % self.config['ldap_server'])
        usr = self.config['ldap_user'].split('\\')[1]
        self.ldap_srv.bind(self.config['ldap_user'], read_password(usr,
                                                    self.config['ldap_server']))

        self.ldap_lc = ldap.controls.SimplePagedResultsControl(
                ldap.LDAP_CONTROL_PAGE_OID, True, (self._ldap_page_size, ''))

    def search(self, ou, attrs, scope=ldap.SCOPE_SUBTREE):
        # Implementing paging, taken from
        # http://www.novell.com/coolsolutions/tip/18274.html
        msgid = self.ldap_srv.search_ext(ou, scope,
                        attrlist=attrs, serverctrls=[self.ldap_lc])
        data = []
        while True:
            rtype, rdata, rmsgid, sc = self.ldap_srv.result3(msgid)
            data.extend(rdata)
            pctrls = [c for c in sc if \
                    c.controlType == ldap.LDAP_CONTROL_PAGE_OID]
            if pctrls:
                est, cookie = pctrls[0].controlValue
                if cookie:
                    self.ldap_lc.controlValue = (self._ldap_page_size, cookie)
                    msgid = self.ldap_srv.search_ext(ou, ldap.SCOPE_SUBTREE,
                                attrlist=attrs, serverctrls=[self.ldap_lc])
                else:
                    break
            else:
                self.logger.warn('Server ignores RFC 2696 control.')
                break
        return data[1:]

    def close(self):
        self.ldap_srv.unbind()

###
# Mailbox related state fetching & comparison
###
    def collect_cerebrum_mail_info(self):
        # TODO: Cache stuff?
        res = {}
        # TODO: Move spread out
        for acc in self.ac.search(spread=self.co.spread_exchange_account):
            tmp = {}
            self.ac.clear()
            self.ac.find(acc['account_id'])
            self.et.clear()
            self.et.find_by_target_entity(self.ac.entity_id)

            # Fetch addresses
            addrs = []
            for addr in self.et.get_addresses():
                addrs += [u'%s@%s' % (addr['local_part'], addr['domain'])]
            tmp[u'EmailAddresses'] = sorted(addrs)

            # Fetch primary address
            pea = self.et.list_email_target_primary_addresses(
                                        target_entity_id=self.ac.entity_id)[0]
            tmp[u'PrimaryAddress'] = u'%s@%s' % (pea['local_part'],
                                                 pea['domain'])

            # Fetch names
            if self.ac.owner_type == self.co.entity_person:
                self.pe.clear()
                self.pe.find(self.ac.owner_id)
                tmp[u'FirstName'] = self.pe.get_name(self.co.system_cached,
                                                    self.co.name_first)
                tmp[u'LastName'] = self.pe.get_name(self.co.system_cached,
                                                    self.co.name_last)
                tmp[u'DisplayName'] = self.pe.get_name(self.co.system_cached,
                                                    self.co.name_full)
            else:
                tmp[u'FirstName'] = ''
                tmp[u'LastName'] = ''
                tmp[u'DisplayName'] = ''

            # Fetch quotas
            self.eq.clear()
            self.eq.find(self.et.entity_id)
            #hard = self.eq.get_quota_hard() * 1024 * 1024
            hard = self.eq.get_quota_hard() * 1024
            soft = self.eq.get_quota_soft()
            tmp[u'ProhibitSendQuota'] = str(hard)
            tmp[u'ProhibitSendReceiveQuota'] = str(hard)
            tmp[u'IssueWarningQuota'] = str(int(hard * soft / 100.))

            # Fetch hidden
            hide = self.pe.has_e_reservation() or \
                    not self.ac.entity_id == self.pe.get_primary_account()

            tmp[u'HiddenFromAddressListsEnabled'] = hide

            res[self.ac.account_name] = tmp

        return res

    def collect_exchange_mail_info(self, mb_ou):
        attrs = ['proxyAddresses',
                 'displayName',
                 'givenName',
                 'sn',
                 'msExchHideFromAddressLists',
                 'extensionAttribute1',
                 'mDBUseDefaults',
                 'mDBOverQuotaLimit',
                 'mDBOverHardQuotaLimit',
                 'mDBStorageQuota']

        r = self.search(mb_ou, attrs)
        ret = {}
        for cn, data in r:
            if data.has_key('extensionAttribute1') and \
                    data['extensionAttribute1'] == ['not migrated'] or \
                    'ExchangeActiveSyncDevices' in cn:
                continue
            tmp = {}
            name = cn[3:].split(',')[0].decode('UTF-8')
            for key in data:
                if key == 'proxyAddresses':
                    addrs = []
                    for addr in data[key]:
                        if addr.startswith('SMTP:'):
                            tmp[u'PrimaryAddress'] = addr[5:].decode('UTF-8')
                        if not cereconf.EXCHANGE_DEFAULT_ADDRESS_PLACEHOLDER \
                                in addr:
                            addrs.append(addr[5:].decode('UTF-8'))
                    tmp[u'EmailAddresses'] = sorted(addrs)
                elif key == 'displayName':
                    tmp[u'DisplayName'] = data[key][0].decode('UTF-8')
                elif key == 'givenName':
                    tmp[u'FirstName'] = data[key][0].decode('UTF-8')
                elif key == 'sn':
                    tmp[u'LastName'] = data[key][0].decode('UTF-8')
                elif key == 'mDBUseDefaults':
                    tmp[u'UseDatabaseQuotaDefaults'] = True if \
                            data[key][0].decode('UTF-8') == 'TRUE' else False
                elif key == 'mDBOverQuotaLimit':
                    q = data[key][0]
                    tmp[u'ProhibitSendQuota'] = q
                elif key == 'mDBOverHardQuotaLimit':
                    q = data[key][0]
                    tmp[u'ProhibitSendReceiveQuota'] = q
                elif key == 'mDBStorageQuota':
                    q = data[key][0]
                    tmp[u'IssueWarningQuota'] = q

            # Non-existent attribute means that the value is false. Fuckers.
            if data.has_key('msExchHideFromAddressLists'):
                tmp_key = 'msExchHideFromAddressLists'
                tmp[u'HiddenFromAddressListsEnabled'] = True if \
                        data[tmp_key][0].decode('UTF-8') == 'TRUE' else False
            else:
                tmp[u'HiddenFromAddressListsEnabled'] = False

            ret[name] = tmp
        return ret

    def compare_mailbox_state(self, ex_state, ce_state, state, config):
        s_ce_keys = set(ce_state.keys())
        s_ex_keys = set(ex_state.keys())
        diff_mb = {}
        diff_stale = {}
        diff_new = {}

        ##
        # Populate some structures with information we need

        # Mailboxes in Exchange, but not in Cerebrum
        stale_keys = list(s_ex_keys - s_ce_keys)
        for ident in stale_keys:
            if state and ident in state['stale_mb']:
                diff_stale[ident] = state['stale_mb'][ident]
            else:
                diff_stale[ident] = time.time()
        
        # Mailboxes in Cerebrum, but not in Exchange
        new_keys = list(s_ce_keys - s_ex_keys)
        for ident in new_keys:
            if state and ident in state['new_mb']:
                diff_new[ident] = state['new_mb'][ident]
            else:
                diff_new[ident] = time.time()

        # Check mailboxes that exists in both Cerebrum and Exchange for
        # difference (& is union, in case you wondered). If an attribute is not
        # in it's desired state in both this and the last run, save the
        # timestamp from the last run. This is used for calculating when we nag
        # to someone about stuff not beeing in sync.
        for key in s_ex_keys & s_ce_keys:
            for attr in ce_state[key]:
                if state and key in state['mb'] and \
                        attr in state['mb'][key]:
                    t_0 = state['mb'][key][attr][u'Time']
                else:
                    t_0 = time.time()
                diff_mb.setdefault(key, {})
                if attr not in ex_state[key]:
                    diff_mb[key][attr] = {
                         u'Exchange': None,
                         u'Cerebrum': ce_state[key][attr],
                         u'Time': t_0
                        }
                elif ce_state[key][attr] != ex_state[key][attr]:
                    # For quotas, we only want to report mismatches if the
                    # difference is between the quotas in Cerebrum and Exchange
                    # is greater than 1% on either side. Hope this is an
                    # appropriate value to use ;)
                    try:
                        if u'Quota' in attr:
                            exq = ex_state[key][attr]
                            ceq = ce_state[key][attr]
                            diff = abs(int(exq) - int(ceq))
                            avg = (int(exq) + int(ceq)) / 2
                            one_p = avg * 0.01
                            if avg + diff < avg + one_p and \
                                    avg - diff > avg - one_p:
                                continue
                    except TypeError:
                        pass

                    diff_mb[key][attr] = {
                         u'Exchange': ex_state[key][attr],
                         u'Cerebrum': ce_state[key][attr],
                         u'Time': t_0
                        }

        ret = { 'new_mb': diff_new, 'stale_mb':diff_stale, 'mb': diff_mb }

        if not state:
            return ret, []

        now = time.time()
        # By now, we have three different dicts. Loop trough them and check if
        # we should report 'em
        report = [u'# User Attribute Since Cerebrum_value:Exchange_value']
        # Report attribute mismatches
        for key in diff_mb:
            for attr in diff_mb[key]:
                delta = config.get(attr) if attr in config else \
                                                config.get('UndefinedAttribute')
                if diff_mb[key][attr][u'Time'] < now - delta:
                    t = time.strftime(u'%d%m%Y-%H:%M', time.localtime(
                        diff_mb[key][attr][u'Time']))
                    if attr == u'EmailAddresses':
                        # We report the difference for email addresses, for
                        # redability
                        s_ce_addr = set(diff_mb[key][attr][u'Cerebrum'])
                        s_ex_addr = set(diff_mb[key][attr][u'Exchange'])
                        new_addr = list(s_ce_addr - s_ex_addr)
                        stale_addr = list(s_ex_addr - s_ce_addr)
                        tmp = u'%-10s %-30s %s +%s:-%s' % (key, attr, t,
                                                          str(new_addr),
                                                          str(stale_addr))
                    else:
                        tmp = u'%-10s %-30s %s %s:%s' % (key, attr, t,
                                        repr(diff_mb[key][attr][u'Cerebrum']),
                                        repr(diff_mb[key][attr][u'Exchange']))
                    report += [tmp]


        # Report uncreated mailboxes
        report += [u'\n# Uncreated mailboxes (uname, time)']
        delta = config.get('UncreatedMailbox') if attr in config else \
                                        config.get('UndefinedAttribute')
        for key in diff_new:
            if diff_new[key] < now - delta:
                t = time.strftime(u'%d%m%Y-%H:%M', time.localtime(
                    diff_new[key]))
                report += [u'%-10s uncreated_mb %s' % (key, t)]

        # Report stale mailboxes
        report += [u'\n# Stale mailboxes (uname, time)']
        delta = config.get('StaleMailbox') if attr in config else \
                                        config.get('UndefinedAttribute')
        for key in diff_stale:
            t = time.strftime(u'%d%m%Y-%H:%M', time.localtime(
                diff_stale[key]))
            if diff_stale[key] < now - delta:
                report += [u'%-10s stale_mb %s' % (key, t)]

        return ret, report

###
# Main control flow or something
###
if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                    't:f:s:m:r:',
                                    ['type=',
                                     'file=',
                                     'sender=',
                                     'mail=',
                                     'report-file='])
    except getopt.GetoptError, err:
        logger.warn(str(err))

    state_file = None
    mail = None
    sender = None
    repfile = None

    for opt, val in opts:
        if opt in ('-t', '--type'):
            conf = eventconf.CONFIG[val]
        if opt in ('-f', '--file',):
            state_file = val
        if opt in ('-m', '--mail',):
            mail = val
        if opt in ('-s', '--sender',):
            sender = val
        if opt in ('-r', '--report-file',):
            repfile = val

    attr_config = conf['state_check_conf']
    mb_ou = conf['mailbox_ou']

    # TODO: Check if state file is defined here. If it does not contain any
    # data, or it is not defined trough the command line, create an empty data
    # structure
    
    try:
        f = open(state_file, 'r')
        state = pickle.load(f)
        f.close()
    except IOError:
        # First run, can't read state
        state = None

    sc = StateChecker(logger, conf)

# Mailboxes
    # Collect and parse mailbox and user data from Exchange
    sc.init_ldap()
    mb_info = sc.collect_exchange_mail_info(mb_ou)
    sc.close()

    # Collect mail-data from Cerebrum
    cere_mb_info = sc.collect_cerebrum_mail_info()

    # Compare mailbox state between Cerebrum and Exchange
    new_state, report = sc.compare_mailbox_state(mb_info, cere_mb_info,
                                                 state, attr_config)

    try:
        rep = u'\n'.join(report)
    except UnicodeDecodeError, e:
        print(str(e))
        tmp = []
        for x in report:
            tmp.append(x.decode('UTF-8'))
        rep = u'\n'.join(tmp)
    # Send a report by mail
    if mail and sender:
        Utils.sendmail(mail, sender, 'Exchange mailbox state report',
                        rep.encode('utf-8'))

    # Write report to file
    if repfile:
        f = open(repfile, 'w')
        f.write(rep.encode('utf-8'))
        f.close()

    # TODO: Exceptions?
    f = open(state_file, 'w')
    pickle.dump(new_state, f)
    f.close()

