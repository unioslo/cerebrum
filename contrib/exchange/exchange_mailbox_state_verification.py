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
"""Script that checks the state of mailboxes between Cerebrum and Exchange.

This is done by:
    - Pulling out all related attributes from Exchange, via LDAP.
    - Pulling out all related information from Cerebrum, via API.
    - Compare the two above.
    - Send a report by mail/file.
"""

import eventconf

import time
import pickle
import getopt
import sys

from Cerebrum.Utils import Factory, read_password
from Cerebrum.utils.email import sendmail
from Cerebrum.modules.Email import EmailQuota, EmailAddress, EmailForward
from Cerebrum.modules.exchange.CerebrumUtils import CerebrumUtils
import ldap

logger = Factory.get_logger('cronjob')


class StateChecker(object):

    """Wrapper class for state-checking functions.

    The StateChecker class wraps all the functions we need in order to
    verify and report deviances between Cerebrum and Exchange.
    """

    def __init__(self, logger, conf):
        """Initzialize a new instance of out state-checker.

        :param logger logger: The logger to use.
        :param dict conf: Our StateCheckers configuration.
        """
        self.db = Factory.get('Database')(client_encoding='UTF-8')
        self.co = Factory.get('Constants')(self.db)
        self.ac = Factory.get('Account')(self.db)
        self.pe = Factory.get('Person')(self.db)
        self.gr = Factory.get('Group')(self.db)
        self.et = Factory.get('EmailTarget')(self.db)
        self.eq = EmailQuota(self.db)
        self.ea = EmailAddress(self.db)
        self.ef = EmailForward(self.db)
        self.cu = CerebrumUtils()

        self.config = conf
        self.logger = logger

        self._ldap_page_size = 1000

        self._cache_randzone_users = self._populate_randzone_cache(
            self.config['randzone_unreserve_group'])
        self._cache_accounts = self._populate_account_cache(
            self.co.spread_exchange_account)
        self._cache_addresses = self._populate_address_cache()
        self._cache_local_delivery = self._populate_local_delivery_cache()
        self._cache_forwards = self._populate_forward_cache()
        self._cache_quotas = self._populate_quota_cache()
        self._cache_targets = self._populate_target_cache()
        self._cache_names = self._populate_name_cache()
        self._cache_group_names = self._populate_group_name_cache()
        self._cache_no_reservation = self._populate_no_reservation_cache()
        self._cache_primary_accounts = self._populate_primary_account_cache()

    def init_ldap(self):
        """Initzialize LDAP connection."""
        self.ldap_srv = ldap.ldapobject.ReconnectLDAPObject(
            '%s://%s/' % (self.config['ldap_proto'],
                          self.config['ldap_server']),
            retry_max=5, retry_delay=60)

        usr = self.config['ldap_user'].split('\\')[1]
        self.ldap_srv.bind_s(self.config['ldap_user'], read_password(
            usr, self.config['ldap_server']))

        self.ldap_lc = ldap.controls.SimplePagedResultsControl(
            True, self._ldap_page_size, '')

    # Wrapping the search with retries if the server is busy or similar errors
    def _searcher(self, ou, scope, attrs, ctrls):
        c_fail = 0
        e_save = None
        while c_fail <= 3:
            try:
                return self.ldap_srv.search_ext(ou, scope,
                                                attrlist=attrs,
                                                serverctrls=ctrls)
                c_fail = 0
                e_save = None
            except ldap.LDAPError, e:
                c_fail = c_fail + 1
                e_save = e
                self.logger.debug('Caught %s in _searcher' % str(e))
                time.sleep(30)
        if e_save:
            raise e_save

    # Wrapping the fetch with retries if the server is busy or similar errors
    def _recvr(self, msgid):
        c_fail = 0
        e_save = None
        while c_fail <= 3:
            try:
                return self.ldap_srv.result3(msgid)
                c_fail = 0
                e_save = None
            except ldap.LDAPError, e:
                c_fail = c_fail + 1
                e_save = e
                self.logger.debug('Caught %s in _recvr' % str(e))
                time.sleep(30)
        if e_save:
            raise e_save

    def search(self, ou, attrs, scope=ldap.SCOPE_SUBTREE):
        """Wrapper for the search- and result-calls.

        Implements paged searching.

        :param str ou: The OU to search in.
        :param list attrs: The attributes to fetch.
        :param int scope: Our search scope, default is subtree.
        """
        # Implementing paging, taken from
        # http://www.novell.com/coolsolutions/tip/18274.html
        msgid = self._searcher(ou, scope, attrs, [self.ldap_lc])

        data = []

        ctrltype = ldap.controls.SimplePagedResultsControl.controlType
        while True:
            time.sleep(1)
            rtype, rdata, rmsgid, sc = self._recvr(msgid)
            data.extend(rdata)
            pctrls = [c for c in sc if c.controlType == ctrltype]
            if pctrls:
                cookie = pctrls[0].cookie
                if cookie:
                    self.ldap_lc.cookie = cookie
                    time.sleep(1)
                    msgid = self._searcher(ou, scope, attrs, [self.ldap_lc])
                else:
                    break
            else:
                self.logger.warn('Server ignores RFC 2696 control.')
                break
        return data[1:]

    def close(self):
        """Close the LDAP connection."""
        self.ldap_srv.unbind_s()

#
# Various cache-generating functions.
#
    def _populate_randzone_cache(self, randzone):
        self.gr.clear()
        self.gr.find_by_name(randzone)
        return [x['name'] for x in self.cu.get_group_members(
            self.gr.entity_id)]

    def _populate_account_cache(self, spread):
        return self.ac.search(spread=spread)

    def _populate_address_cache(self):
        tmp = {}
        # TODO: Implement fetchall?
        for addr in self.ea.list_email_addresses_ext():
            tmp.setdefault(
                addr['target_id'], []).append(u'%s@%s' %
                                              (addr['local_part'],
                                               addr['domain']))
        return tmp

    def _populate_local_delivery_cache(self):
        r = {}
        for ld in self.ef.list_local_delivery():
            r[ld['target_id']] = ld['local_delivery']
        return r

    def _populate_forward_cache(self):
        tmp = {}
        for fwd in self.ef.list_email_forwards():
            if fwd['enable'] == 'T':
                tmp.setdefault(
                    fwd['target_id'], []).append(fwd['forward_to'])
        return tmp

    def _populate_quota_cache(self):
        tmp = {}
        # TODO: Implement fetchall?
        for quota in self.eq.list_email_quota_ext():
            tmp.setdefault(
                quota['target_id'], {})['soft'] = quota['quota_soft']
            tmp.setdefault(
                quota['target_id'], {})['hard'] = quota['quota_hard']
        return tmp

    def _populate_target_cache(self):
        tmp = {}
        for targ in self.et.list_email_target_primary_addresses(
                target_type=self.co.email_target_account):
            tmp.setdefault(targ['target_entity_id'], {})['target_id'] = \
                targ['target_id']
            tmp.setdefault(targ['target_entity_id'], {})['primary'] = \
                u'%s@%s' % (targ['local_part'], targ['domain'])
        return tmp

    def _populate_name_cache(self):
        tmp = {}
        for name in self.pe.search_person_names(
            name_variant=[self.co.name_first,
                          self.co.name_last,
                          self.co.name_full],
                source_system=self.co.system_cached):
                tmp.setdefault(
                    name['person_id'], {})[name['name_variant']] = name['name']
        return tmp

    def _populate_group_name_cache(self):
        tmp = {}
        for eid, dom, name in self.gr.list_names(self.co.group_namespace):
            tmp[eid] = name
        return tmp

    def _populate_no_reservation_cache(self):
        unreserved = []
        for r in self.pe.list_traits(self.co.trait_public_reservation,
                                     fetchall=True):
            if r['numval'] == 0:
                unreserved.append(r['entity_id'])
        return unreserved

    def _populate_primary_account_cache(self):
        primary = []
        for acc in self.ac.list_accounts_by_type(primary_only=True):
            primary.append(acc['account_id'])
        return primary
###
# Mailbox related state fetching & comparison
###

    def collect_cerebrum_mail_info(self):
        """Collect E-mail related information from Cerebrum.

        :rtype: dict
        :return: A dict of users attributes. Uname is key.
        """
        res = {}
        for acc in self._cache_accounts:
            tmp = {}
            try:
                tid = self._cache_targets[acc['account_id']]['target_id']
            except KeyError:
                self.logger.warn('Could not find account with id:%d in list '
                                 'of targets, skipping..' % acc['account_id'])
                continue
            # Fetch addresses
            tmp[u'EmailAddresses'] = sorted(self._cache_addresses[tid])
            # Fetch primary address
            tmp[u'PrimaryAddress'] = \
                self._cache_targets[acc['account_id']]['primary']

            # Fetch names
            if acc['owner_type'] == self.co.entity_person:
                tmp[u'FirstName'] = \
                    self._cache_names[acc['owner_id']][int(self.co.name_first)]
                tmp[u'LastName'] = \
                    self._cache_names[acc['owner_id']][int(self.co.name_last)]
                tmp[u'DisplayName'] = \
                    self._cache_names[acc['owner_id']][int(self.co.name_full)]
            else:
                fn, ln, dn = self.cu.construct_group_names(
                    acc['name'], self._cache_group_names.get(acc['owner_id'],
                                                             None))
                tmp[u'FirstName'] = fn
                tmp[u'LastName'] = ln
                tmp[u'DisplayName'] = dn

            # Fetch quotas
            hard = self._cache_quotas[tid]['hard'] * 1024
            soft = self._cache_quotas[tid]['soft']

            tmp[u'ProhibitSendQuota'] = str(hard)
            tmp[u'ProhibitSendReceiveQuota'] = str(hard)
            tmp[u'IssueWarningQuota'] = str(int(hard * soft / 100.))

            # Randzone users will always be shown. This overrides everything
            # else.
            if acc['name'] in self._cache_randzone_users:
                hide = False
            elif acc['owner_id'] in self._cache_no_reservation and \
                    acc['account_id'] in self._cache_primary_accounts:
                hide = False
            else:
                hide = True

            tmp[u'HiddenFromAddressListsEnabled'] = hide

            # Collect local delivery status
            tmp[u'DeliverToMailboxAndForward'] = \
                self._cache_local_delivery.get(tid, False)

            # Collect forwarding address
            # We do this by doing a difference operation on the forwards and
            # the addresses, so we only end up with "external" addresses.
            s_fwds = set(self._cache_forwards.get(tid, []))
            s_addrs = set(self._cache_addresses.get(tid, []))
            ext_fwds = list(s_fwds - s_addrs)
            if ext_fwds:
                tmp[u'ForwardingSmtpAddress'] = ext_fwds[0]
            else:
                tmp[u'ForwardingSmtpAddress'] = None

            res[acc['name']] = tmp

        return res

    def collect_exchange_mail_info(self, mb_ou):
        """Collect mailbox-information from Exchange, via LDAP.

        :param str mb_ou: The OrganizationalUnit to search for mailboxes.
        :rtype: dict
        :return: A dict with the mailboxes attributes. The key is the account
            name.
        """
        attrs = ['proxyAddresses',
                 'displayName',
                 'givenName',
                 'sn',
                 'msExchHideFromAddressLists',
                 'extensionAttribute1',
                 'mDBUseDefaults',
                 'mDBOverQuotaLimit',
                 'mDBOverHardQuotaLimit',
                 'mDBStorageQuota',
                 'deliverAndRedirect',
                 'msExchGenericForwardingAddress']

        r = self.search(mb_ou, attrs)
        ret = {}
        for cn, data in r:
            if 'extensionAttribute1'in data and \
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
            # Collect status about if the mbox is hidden or not
            tmp[u'HiddenFromAddressListsEnabled'] = False
            if 'msExchHideFromAddressLists' in data:
                val = (True if
                       data['msExchHideFromAddressLists'][0].decode('UTF-8')
                       == 'TRUE' else False)
                tmp[u'HiddenFromAddressListsEnabled'] = val

            # Collect local delivery status
            tmp[u'DeliverToMailboxAndForward'] = False
            if 'deliverAndRedirect' in data:
                val = (True if data['deliverAndRedirect'][0].decode('UTF-8')
                       == 'TRUE' else False)
                tmp[u'DeliverToMailboxAndForward'] = val

            # Collect forwarding address
            tmp[u'ForwardingSmtpAddress'] = None
            if 'msExchGenericForwardingAddress' in data:
                val = data['msExchGenericForwardingAddress'][0].decode('UTF-8')
                # We split of smtp:, and store
                tmp[u'ForwardingSmtpAddress'] = val.split(':')[1]

            ret[name] = tmp
        return ret

    def compare_mailbox_state(self, ex_state, ce_state, state, config):
        """Compare the information fetched from Cerebrum and Exchange.

        This method produces a dict with the state between the systems,
        and a report that will be sent to the appropriate target system
        administrators.

        :param dict ex_state: The state in Exchange.
        :param dict ce_state: The state in Cerebrum.
        :param dict state: The previous state generated by this method.
        :param dict config: Configuration of reporting delays for various
            attributes.
        :rtype: tuple
        :return: A tuple consisting of the new difference-state and a
            human-readable report of differences.
        """
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

        ret = {'new_mb': diff_new, 'stale_mb': diff_stale, 'mb': diff_mb}

        if not state:
            return ret, []

        now = time.time()
        # By now, we have three different dicts. Loop trough them and check if
        # we should report 'em
        report = [u'# User Attribute Since Cerebrum_value:Exchange_value']
        # Report attribute mismatches
        for key in diff_mb:
            for attr in diff_mb[key]:
                delta = (config.get(attr) if attr in config else
                         config.get('UndefinedAttribute'))
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
                        tmp = (u'%-10s %-30s %s %s:%s' %
                               (key, attr, t,
                                repr(diff_mb[key][attr][u'Cerebrum']),
                                repr(diff_mb[key][attr][u'Exchange']))
                               )
                    report += [tmp]

        # Report uncreated mailboxes
        report += [u'\n# Uncreated mailboxes (uname, time)']
        delta = (config.get('UncreatedMailbox') if 'UncreatedMailbox' in config
                 else config.get('UndefinedAttribute'))
        for key in diff_new:
            if diff_new[key] < now - delta:
                t = time.strftime(u'%d%m%Y-%H:%M', time.localtime(
                    diff_new[key]))
                report += [u'%-10s uncreated_mb %s' % (key, t)]

        # Report stale mailboxes
        report += [u'\n# Stale mailboxes (uname, time)']
        delta = (config.get('StaleMailbox') if 'StaleMailbox' in config else
                 config.get('UndefinedAttribute'))
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

    # Load config
    attr_config = conf['state_check_conf']
    mb_ou = conf['mailbox_ou']

    # TODO: Check if state file is defined here. If it does not contain any
    # data, or it is not defined trough the command line, create an empty data
    # structure

    # Load state file
    try:
        f = open(state_file, 'r')
        state = pickle.load(f)
        f.close()
    except IOError:
        # First run, can't read state
        state = None

    # Init our state checker
    sc = StateChecker(logger, conf)

    # Collect and parse mailbox and user data from Exchange
    sc.init_ldap()
    mb_info = sc.collect_exchange_mail_info(mb_ou)
    sc.close()

    # Collect mail-data from Cerebrum
    cere_mb_info = sc.collect_cerebrum_mail_info()

    # Compare mailbox state between Cerebrum and Exchange
    new_state, report = sc.compare_mailbox_state(mb_info, cere_mb_info,
                                                 state, attr_config)

    # Join the report together
    try:
        rep = u'\n'.join(report)
    except UnicodeDecodeError, e:
        print(str(e))
        tmp = []
        for x in report:
            tmp.append(x.decode('UTF-8'))
        rep = u'\n'.join(tmp)

    # Send the report by mail
    if mail and sender:
        sendmail(mail, sender, 'Exchange mailbox state report',
                 rep.encode('utf-8'))

    # Write the report to file
    if repfile:
        f = open(repfile, 'w')
        f.write(rep.encode('utf-8'))
        f.close()

    # TODO: Exceptions?
    # Overwrite the old state with the new one.
    f = open(state_file, 'w')
    pickle.dump(new_state, f)
    f.close()
