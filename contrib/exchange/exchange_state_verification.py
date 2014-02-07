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
"""Script that checks the state between Cerebrum and Exchange"""

import cerebrum_path
import cereconf
import eventconf

import random
import time
import pickle
import getopt
import sys
import re

from Cerebrum.Utils import Factory
from Cerebrum.modules.exchange.v2013.ExchangeClient import ExchangeClient
from Cerebrum.modules.exchange.Exceptions import ExchangeException
from Cerebrum.modules.Email import EmailQuota
from Cerebrum import Utils

logger = Utils.Factory.get_logger('console')

class StateChecker(object):
    def __init__(self, logger, conf):
        self.db = Factory.get('Database')(client_encoding='UTF-8')
        self.co = Factory.get('Constants')(self.db)
        self.dg = Factory.get('DistributionGroup')(self.db)
        self.ac = Factory.get('Account')(self.db)
        self.pe = Factory.get('Person')(self.db)
        self.et = Factory.get('EmailTarget')(self.db)
        self.eq = EmailQuota(self.db)

        self.config = conf
        self.logger = logger
        gen_key = lambda: 'CB%s' \
                % hex(random.randint(0xF00000,0xFFFFFF))[2:].upper()
        self.ec = ExchangeClient(logger=self.logger,
                     host=self.config['server'],
                     port=self.config['port'],
                     auth_user=self.config['auth_user'],
                     domain_admin=self.config['domain_admin'],
                     ex_domain_admin=self.config['ex_domain_admin'],
                     management_server=self.config['management_server'],
                     encrypted=self.config['encrypted'],
                     session_key=gen_key())


    def close(self):
        self.ec.kill_session()
        self.ec.close()

    def collect_cerebrum_distgroup_info(self):
        pass

    def collect_cerebrum_secgroup_info(self):
        pass

    def collect_exchange_distgroup_info(self):
        """
ManagedBy                              : {exutv.uio.no/Users/groupadmin}
ModeratedBy                            : {}
MemberJoinRestriction                  : Closed
MemberDepartRestriction                : Closed
DisplayName                            : Fjasemikk
EmailAddresses                         : {SMTP:dl-fjas@groups.uio.no}
HiddenFromAddressListsEnabled          : False
ModerationEnabled                      : False
Name                                   : dl-fjas
        """
        attributes = ['ManagedBy', 'ModeratedBy', 'MemberJoinRestriction',
                      'MemberDepartRestriction', 'DisplayName',
                      'EmailAddresses', 'HiddenFromAddressListsEnabled',
                      'ModerationEnabled', 'Name']
        return self.ec.get_distgroup_info(attributes)

    def collect_exchange_secgroup_info(self, ou):
        """
GroupCategory      : Security
GroupScope         : DomainLocal
Name               : SG-julenissen
        """
        attributes = ['GroupCategory', 'GroupScope', 'Name']
        return self.ec.get_secgroup_info(attributes, ou)

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
                addrs += ['%s@%s' % (addr['local_part'], addr['domain'])]
            tmp['EmailAddresses'] = addrs

            # Fetch primary address
            pea = self.et.list_email_target_primary_addresses(
                                        target_entity_id=self.ac.entity_id)[0]
            tmp['PrimaryAddress'] = '%s@%s' % (pea['local_part'], pea['domain'])

            # Fetch names
            if self.ac.owner_type == self.co.entity_person:
                self.pe.clear()
                self.pe.find(self.ac.owner_id)
                tmp['FirstName'] = self.pe.get_name(self.co.system_cached,
                                                    self.co.name_first)
                tmp['LastName'] = self.pe.get_name(self.co.system_cached,
                                                   self.co.name_last)
                tmp['DisplayName'] = self.pe.get_name(self.co.system_cached,
                                                   self.co.name_full)
            else:
                tmp['FirstName'] = ''
                tmp['LastName'] = ''
                tmp['DisplayName'] = ''

            # Fetch quotas
                self.eq.clear()
                self.eq.find(self.et.entity_id)
                hard = str(self.eq.get_quota_hard() * 1024 * 1024)
                soft = self.eq.get_quota_soft()
                tmp['ProhibitSendQuota'] = hard
                tmp['ProhibitSendReceiveQuota'] = hard
                tmp['IssueWarningQuota'] = int(hard * soft / 100.)

            # Fetch hidden
                tmp['HiddenFromAddressListsEnabled'] = \
                        self.pe.has_e_reservation()
            
            res[self.ac.account_name] = tmp

        return res


    def collect_exchange_mail_info(self):
         # TODO: Make me pretty or something
        attributes = ['Identity',
                      'EmailAddresses',
                      'DisplayName',
                      'HiddenFromAddressListsEnabled',
                      'ProhibitSendQuota',
                      'ProhibitSendReceiveQuota',
                      'IssueWarningQuota',
                      'UseDatabaseQuotaDefaults',
                      'FirstName',
                      'LastName',
                      'EmailAddressPolicyEnabled',
                      'IsLinked']
        return self.ec.get_mailbox_info(attributes)

    def collect_exchange_user_info(self):
        attributes = ['GivenName',
                      'Surname',
                      'SamAccountName']
        return self.ec.get_user_info(attributes)

    def parse_mailbox_info(self, raw_mb, raw_user):
        ret = {}

        # Data about mailboxes
        for mb in raw_mb:
            tmp = {}
            # str / none
            for key in ('DisplayName',): # 'FirstName', 'LastName',):
                tmp[key] = mb[key]

            # bool
            for key in ('IsLinked',
                        'HiddenFromAddressListsEnabled',
                        'EmailAddressPolicyEnabled',
                        'UseDatabaseQuotaDefaults',):
                tmp[key] = mb[key]

            # list [u'smtp:jsama@usit.uio.no', u'SMTP:lurv@usit.no']
            addrs = []
            for addr in mb['EmailAddresses']:
                # Handle primary address
                if addr[:4].isupper():
                    tmp['PrimaryAddress'] = addr[5:]
                addrs += [addr[5:]]
            tmp['EmailAddresses'] = addrs

            size_pat = re.compile('[0-9.GMKB\s]+\(([0-9,]+) bytes\)')
            for key in ('ProhibitSendQuota',
                        'ProhibitSendReceiveQuota',
                        'IssueWarningQuota',):
                try:
                    m = re.match(size_pat, mb[key]['Value'])
                    if m:
                        g = m.groups()[0]
                    tmp[key] = g.replace(',', '')
                except KeyError:
                    # When we end up here, quota is unlimited
                    # This is a nasty way of representing, but what the heck..
                    tmp[key] = None

            ret[mb['Identity']['Name']] = tmp

        for acc in raw_user:
            if not ret.has_key(acc['SamAccountName']):
                continue
            if acc['GivenName']:
                ret[acc['SamAccountName']]['FirstName'] = acc['GivenName']
            if acc['Surname']:
                ret[acc['SamAccountName']]['LastName']  = acc['Surname']

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
        stale_keys = list(s_ce_keys - s_ex_keys)
        for ident in stale_keys:
            if state and ident in state['stale_mb']:
                diff_stale[ident] = state['stale_mb'][ident]
            else:
                diff_stale[ident] = time.time()
        
        # Mailboxes in Cerebrum, but not in Exchange
        new_keys = list(s_ex_keys - s_ce_keys)
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
                if state and attr in state['mb'][key]:
                    t_0 = state['mb'][key][attr]['Time']
                else:
                    t_0 = time.time()
                diff_mb.setdefault(key, {})
                if attr not in ex_state[key]:
                    diff_mb[key][attr] = {
                         'Exchange': None,
                         'Cerebrum': ce_state[key][attr],
                         'Time': t_0
                        }
                elif ce_state[key][attr] != ex_state[key][attr]:
                    diff_mb[key][attr] = {
                         'Exchange': ex_state[key][attr],
                         'Cerebrum': ce_state[key][attr],
                         'Time': t_0
                        }

        ret = { 'new_mb': diff_new, 'stale_mb':diff_stale, 'mb': diff_mb }

        if not state:
            return ret

        now = time.time()
        # By now, we have three different dicts. Loop trough them and check if
        # we should report 'em
        report = ['# User Attribute Since Cerebrum_value:Exchange_value']
        # Report attribute mismatches
        for key in diff_mb:
            for attr in diff_mb[key]:
                delta = config.get(attr) if attr in config else \
                                                config.get('UndefinedAttribute')
                if diff_mb[key][attr]['Time'] < now - delta:
                    t = time.strftime('%d%m%Y-%H:%M', time.localtime(
                        diff_mb[key][attr]['Time']))
                    tmp = '%-8s %-20s %s %s:%s' % (key, attr, t,
                                            str(diff_mb[key][attr]['Cerebrum']),
                                            str(diff_mb[key][attr]['Exchange']))
                    report += [tmp]


        # Report uncreated mailboxes
        report += ['\n# Uncreated mailboxes (uname, time)']
        delta = config.get('UncreatedMailbox')
        for key in diff_new:
            if diff_new[key] < now - delta:
                t = time.strftime('%d%m%Y-%H:%M', time.localtime(
                    diff_new[key]))
                report += ['%-8s %s' % (key, t)]

        # Report stale mailboxes
        report += ['\n# Stale mailboxes (uname, time)']
        delta = config.get('StaleMailbox')
        for key in diff_stale:
            t = time.strftime('%d%m%Y-%H:%M', time.localtime(
                diff_stale[key]))
            if diff_stale[key] < now - delta:
                report += ['%-8s %s' % (key, t)]

        return ret, report

###
# Main control flow or something
###
if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                    'g:crt:f:s:m:',
                                    ['groups=', 'commit',
                                     'remove', 'type=',
                                     'file=', 'sender=',
                                     'mail='])
    except getopt.GetoptError, err:
        print err

    groups = None
    commit = False
    remove_mode = False
    state_file = None
    mail = None
    sender = None

    for opt, val in opts:
        if opt in ('-t', '--type'):
            conf = eventconf.CONFIG[val]
        if opt in ('-g', '--groups',):
            groups = val.split(',')
        if opt in ('-c', '--commit',):
            commit = True
        if opt in ('-r', '--remove',):
            remove_mode = True
        if opt in ('-f', '--file',):
            state_file = val
        if opt in ('-m', '--mail',):
            mail = val
        if opt in ('-s', '--sender',):
            sender = val

    # TODO: Move this out in another file or something
    config = {'UndefinedAttribute': 3*60,
              'UncreatedMailbox': 3*60,
              'StaleMailbox': 3*60,
              'EmailAddress': 3*60}
    secgroup_ou = 'OU=securitygroups,OU=cerebrum,DC=exutv,DC=uio,DC=no'


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
    try:
        raw_mb_info = sc.collect_exchange_mail_info()
        raw_user_info = sc.collect_exchange_user_info()
    except ExchangeException, e:
        print(str(e))
    sc.close()
    mb_info = sc.parse_mailbox_info(raw_mb_info, raw_user_info)

    # Collect mail-data from Cerebrum
    cere_mb_info = sc.collect_mail_info()

    # Compare mailbox state between Cerebrum and Exchange
    new_state, report = sc.compare_mailbox_state(mb_info, cere_mb_info,
                                                 state, config)

    # Send a report by mail
    if mail and sender:
        Utils.sendmail(mail, sender, 'Exchange state report', '\n'.join(report))

    # TODO: Exceptions?
    f = open(state_file, 'w')
    pickle.dump(new_state, f)
    f.close()

