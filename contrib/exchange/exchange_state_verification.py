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
from Cerebrum.modules.Email import EmailQuota, EmailAddress
from Cerebrum.modules.exchange.CerebrumUtils import CerebrumUtils
from Cerebrum import Utils

logger = Utils.Factory.get_logger('cronjob')

class StateChecker(object):
    def __init__(self, logger, conf):
        self.db = Factory.get('Database')(client_encoding='UTF-8')
        self.co = Factory.get('Constants')(self.db)
        self.dg = Factory.get('DistributionGroup')(self.db)
        self.ac = Factory.get('Account')(self.db)
        self.pe = Factory.get('Person')(self.db)
        self.gr = Factory.get('Group')(self.db)
        self.et = Factory.get('EmailTarget')(self.db)
        self.ea = EmailAddress(self.db)
        self.eq = EmailQuota(self.db)
        self.ut = CerebrumUtils()

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

###
# Group related fetching & comparison
###
    def collect_exchange_group_memberships(self, group):
        try:
            return self.ec.get_group_members(group)
        except ExchangeException, e:
            logger.warn(str(e))
            return []

    def collect_exchange_group_info(self, ou):
        attributes = ['ManagedBy', 'ModeratedBy', 'MemberJoinRestriction',
                      'MemberDepartRestriction', 'DisplayName',
                      'EmailAddresses', 'HiddenFromAddressListsEnabled',
                      'ModerationEnabled', 'Name']
        exgrinfo = self.ec.get_group_info(attributes, ou)

        exgrdesc = {}
        for x in  self.ec.get_group_description(ou):
            try:
                exgrdesc[x['Name']] = x['Notes']
            except Exception, e:
                logger.info('Could not handle the description %s: %s' % \
                        (str(x), str(e)))

        tmp = {}
        for group in exgrinfo:
            tmp.setdefault(group['Name'], {})
            for attr in attributes:
                if attr == 'EmailAddresses':
                    addrs = []
                    for addr in group[attr]:
                        if addr[:4] == 'SMTP':
                            tmp[group['Name']]['Primary'] = addr[5:]
                        if not \
                            cereconf.EXCHANGE_DEFAULT_ADDRESS_PLACEHOLDER \
                                in addr:
                            addrs += [addr[5:]]
                    tmp[group['Name']]['Aliases'] = sorted(addrs)
                elif attr == 'ModeratedBy':
                    # Strip of all that prefix stuff on moderators names
                    mods = []
                    for mod in group[attr]:
                        mods += [ mod.split('/')[-1] ]
                    tmp[group['Name']][attr] = sorted(mods)
                elif attr == 'ManagedBy':
                    try:
                        mans = []
                        for x in group[attr]:
                            mans += [ x.split('/')[-1] ]
                        tmp[group['Name']][attr] = sorted(mans)
                    except IndexError:
                        tmp[group['Name']][attr] = group[attr]
                elif 'Restriction' in attr:
                    # So, 'Value' is a string, 'value' is an int in this
                    # context. So very nice.
                    tmp[group['Name']][attr] = group[attr]['Value']
                else:
                   tmp[group['Name']][attr] = group[attr]
            try:
                desc = exgrdesc[group['Name']]
            except KeyError:
                # Probably not set. We set it! :D
                desc = 'Undefined'
            tmp[group['Name']]['Description'] = desc

            # Mix in group members in the dict
            # TODO: Should we do this another way? This takes time
            tmp[group['Name']]['Members'] = \
                sorted(self.collect_exchange_group_memberships(group['Name']))
        return tmp            

    def collect_cerebrum_group_info(self, mb_spread, ad_spread):
        # TODO: This entire function is so darn ugly. Rewrite EVERYTHING related
        # to Exchange some day!

        mb_spread = self.co.Spread(mb_spread)
        ad_spread = self.co.Spread(ad_spread)

        def _true_or_false(val):
            # Yes, we know...
            if val == 'T':
                return True
            elif val == 'F':
                return False
            else:
                return None

        tmp = {}
        for dg in self.dg.list_distribution_groups():
            self.dg.clear()
            self.dg.find(dg['group_id'])
            roomlist = _true_or_false(self.dg.roomlist)
            data = self.dg.get_distgroup_attributes_and_targetdata(
                                                            roomlist=roomlist)

            # Yes. We must look up the user/group name......!!11
            try:
                self.ea.clear()
                self.ea.find_by_address(data['mngdby_address'])
                self.et.clear()
                self.et.find(self.ea.get_target_id())
                if self.et.email_target_entity_type == self.co.entity_group:
                    self.gr.clear()
                    self.gr.find(self.et.email_target_entity_id)
                    manager = self.gr.group_name
                elif self.et.email_target_entity_type == self.co.entity_account:
                    self.ac.clear()
                    self.ac.find(self.et.email_target_entity_id)
                    manager = self.ac.account_name
                else:
                    raise Exception
            except:
                manager = u'Unknown'


            tmp[self.dg.group_name] = {
                        'Name': self.dg.group_name,
                        'Description': self.dg.description,
                        'DisplayName': data['displayname'],
                        'ManagedBy': [manager],
                        'MemberDepartRestriction': data['deprestr'],
                        'MemberJoinRestriction': data['joinrestr'],
            }

            if not roomlist:
                tmp[self.dg.group_name].update({
                            'ModerationEnabled': \
                                    _true_or_false(data['modenable']),
                            'ModeratedBy': sorted(data['modby']),
                            'HiddenFromAddressListsEnabled': \
                                    _true_or_false(data['hidden']),
                            'Primary': data['primary'],
                            'Aliases': sorted(data['aliases'])
                })

            # Collect members
            membs_unfiltered = self.ut.get_group_members(self.dg.entity_id,
                                                        spread=mb_spread,
                                                        filter_spread=ad_spread)
            members = [member['name'] for member in membs_unfiltered]
            tmp[self.dg.group_name].update({'Members': sorted(members)})
        return tmp

    def compare_group_state(self, ex_group_info, cere_group_info, state,
                                config):
        # TODO: This is mostly copypasta fra compare_mailbox_state, refactor
        # and generalize
        
        s_ce_keys = set(cere_group_info.keys())
        s_ex_keys = set(ex_group_info.keys())
        diff_group = {}
        diff_stale = {}
        diff_new = {}

        ##
        # Populate some structures with information we need

        # Groups in Exchange, but not in Cerebrum
        stale_keys = list(s_ex_keys - s_ce_keys)
        for ident in stale_keys:
            if state and ident in state['stale_group']:
                diff_stale[ident] = state['stale_group'][ident]
            else:
                diff_stale[ident] = time.time()
        
        # Groups in Cerebrum, but not in Exchange
        new_keys = list(s_ce_keys - s_ex_keys)
        for ident in new_keys:
            if state and ident in state['new_group']:
                diff_new[ident] = state['new_group'][ident]
            else:
                diff_new[ident] = time.time()

        # Check groups that exists in both Cerebrum and Exchange for
        # difference (& is union, in case you wondered). If an attribute is not
        # in it's desired state in both this and the last run, save the
        # timestamp from the last run. This is used for calculating when we nag
        # to someone about stuff not beeing in sync.
        for key in s_ex_keys & s_ce_keys:
            for attr in cere_group_info[key]:
                if state and key in state['group'] and \
                        attr in state['group'][key]:
                    t_0 = state['group'][key][attr]['Time']
                else:
                    t_0 = time.time()
                diff_group.setdefault(key, {})
                if attr not in ex_group_info[key]:
                    diff_group[key][attr] = {
                         'Exchange': None,
                         'Cerebrum': cere_group_info[key][attr],
                         'Time': t_0
                        }
                elif cere_group_info[key][attr] != ex_group_info[key][attr]:
                    diff_group[key][attr] = {
                         'Exchange': ex_group_info[key][attr],
                         'Cerebrum': cere_group_info[key][attr],
                         'Time': t_0
                        }

        ret = { 'new_group': diff_new,
                'stale_group':diff_stale,
                'group': diff_group }

        if not state:
            return ret, []

        now = time.time()
        # By now, we have three different dicts. Loop trough them and check if
        # we should report 'em
        report = ['\n\n# Group Attribute Since Cerebrum_value:Exchange_value']

        # Report attribute mismatches for groups
        for key in diff_group:
            for attr in diff_group[key]:
                delta = config.get(attr) if attr in config else \
                                                config.get('UndefinedAttribute')
                if diff_group[key][attr]['Time'] < now - delta:
                    t = time.strftime('%d%m%Y-%H:%M', time.localtime(
                        diff_group[key][attr]['Time']))
                    if attr in ('ModeratedBy', 'Aliases', 'Members',):
                        # We report the difference for these types, for
                        # redability
                        s_ce_attr = set(diff_group[key][attr]['Cerebrum'])
                        s_ex_attr = set(diff_group[key][attr]['Exchange'])
                        new_attr = list(s_ce_attr - s_ex_attr)
                        stale_attr = list(s_ex_attr - s_ce_attr)
                        tmp = '%-10s %-30s %s +%s:-%s' % (key, attr, t,
                                                          str(new_attr),
                                                          str(stale_attr))
                    else:
                        tmp = '%-10s %-30s %s %s:%s' % (key, attr, t,
                                        repr(diff_group[key][attr]['Cerebrum']),
                                        repr(diff_group[key][attr]['Exchange']))
                    report += [tmp]


        # Report uncreated groups
        report += ['\n# Uncreated groups (uname, time)']
        attr = 'UncreatedGroup'
        delta = config.get(attr) if attr in config else \
                                                config.get('UndefinedAttribute')
        for key in diff_new:
            if diff_new[key] < now - delta:
                t = time.strftime('%d%m%Y-%H:%M', time.localtime(
                    diff_new[key]))
                report += ['%-10s %s' % (key, t)]

        # Report stale groups
        report += ['\n# Stale groups (uname, time)']
        attr = 'StaleGroup'
        delta = config.get(attr) if attr in config else \
                                                config.get('UndefinedAttribute')
        for key in diff_stale:
            t = time.strftime('%d%m%Y-%H:%M', time.localtime(
                diff_stale[key]))
            if diff_stale[key] < now - delta:
                report += ['%-10s %s' % (key, t)]

        return ret, report


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
            tmp['EmailAddresses'] = sorted(addrs)

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
            hard = self.eq.get_quota_hard() * 1024 * 1024
            soft = self.eq.get_quota_soft()
            tmp['ProhibitSendQuota'] = str(hard)
            tmp['ProhibitSendReceiveQuota'] = str(hard)
            tmp['IssueWarningQuota'] = str(int(hard * soft / 100.))

            # Fetch hidden
            hide = self.pe.has_e_reservation() or \
                    not self.ac.entity_id == self.pe.get_primary_account()

            tmp['HiddenFromAddressListsEnabled'] = hide

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
                      'EmailAddressPolicyEnabled',
                      'CustomAttribute1',
                      'IsLinked']
        return self.ec.get_mailbox_info(attributes)

    def collect_exchange_user_info(self):
        attributes = ['FirstName',
                      'Lastname',
                      'SamAccountName']
        return self.ec.get_user_info(attributes)

    def parse_mailbox_info(self, raw_mb, raw_user):
        ret = {}

        # Data about mailboxes
        for mb in raw_mb:
            if mb['CustomAttribute1'] == 'not migrated':
                continue

            tmp = {}
            # str / none
            for key in ('DisplayName',):
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
                if not cereconf.EXCHANGE_DEFAULT_ADDRESS_PLACEHOLDER in addr:
                    addrs += [addr[5:]]
            tmp['EmailAddresses'] = sorted(addrs)

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
            ret[acc['SamAccountName']]['FirstName'] = acc['FirstName']
            ret[acc['SamAccountName']]['LastName']  = acc['LastName']

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
                    # For quotas, we only want to report mismatches if the
                    # difference is between the quotas in Cerebrum and Exchange
                    # is greater than 1% on either side. Hope this is an
                    # appropriate value to use ;)
                    try:
                        if 'Quota' in attr:
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
                         'Exchange': ex_state[key][attr],
                         'Cerebrum': ce_state[key][attr],
                         'Time': t_0
                        }

        ret = { 'new_mb': diff_new, 'stale_mb':diff_stale, 'mb': diff_mb }

        if not state:
            return ret, []

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
                    if attr == 'EmailAddresses':
                        # We report the difference for email addresses, for
                        # redability
                        s_ce_addr = set(diff_mb[key][attr]['Cerebrum'])
                        s_ex_addr = set(diff_mb[key][attr]['Exchange'])
                        new_addr = list(s_ce_addr - s_ex_addr)
                        stale_addr = list(s_ex_addr - s_ce_addr)
                        tmp = '%-10s %-30s %s +%s:-%s' % (key, attr, t,
                                                          str(new_addr),
                                                          str(stale_addr))
                    else:
                        tmp = '%-10s %-30s %s %s:%s' % (key, attr, t,
                                            repr(diff_mb[key][attr]['Cerebrum']),
                                            repr(diff_mb[key][attr]['Exchange']))
                    report += [tmp]


        # Report uncreated mailboxes
        report += ['\n# Uncreated mailboxes (uname, time)']
        delta = config.get('UncreatedMailbox') if attr in config else \
                                        config.get('UndefinedAttribute')
        for key in diff_new:
            if diff_new[key] < now - delta:
                t = time.strftime('%d%m%Y-%H:%M', time.localtime(
                    diff_new[key]))
                report += ['%-10s %s' % (key, t)]

        # Report stale mailboxes
        report += ['\n# Stale mailboxes (uname, time)']
        delta = config.get('StaleMailbox') if attr in config else \
                                        config.get('UndefinedAttribute')
        for key in diff_stale:
            t = time.strftime('%d%m%Y-%H:%M', time.localtime(
                diff_stale[key]))
            if diff_stale[key] < now - delta:
                report += ['%-10s %s' % (key, t)]

        return ret, report

###
# Main control flow or something
###
if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                    't:f:s:m:',
                                    ['type=',
                                     'file=',
                                     'sender=',
                                     'mail='])
    except getopt.GetoptError, err:
        logger.warn(str(err))

    state_file = None
    mail = None
    sender = None

    for opt, val in opts:
        if opt in ('-t', '--type'):
            conf = eventconf.CONFIG[val]
        if opt in ('-f', '--file',):
            state_file = val
        if opt in ('-m', '--mail',):
            mail = val
        if opt in ('-s', '--sender',):
            sender = val

    attr_config = conf['state_check_conf']
    group_ou = conf['group_ou']

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
        logger.warn(str(e))
        sys.exit(1)

    mb_info = sc.parse_mailbox_info(raw_mb_info, raw_user_info)

    # Collect mail-data from Cerebrum
    cere_mb_info = sc.collect_cerebrum_mail_info()

    # Compare mailbox state between Cerebrum and Exchange
    new_state, report = sc.compare_mailbox_state(mb_info, cere_mb_info,
                                                 state, attr_config)

    # Collect group infor from Cerebrum and Exchange
    try:
        ex_group_info = sc.collect_exchange_group_info(group_ou)
        cere_group_info = sc.collect_cerebrum_group_info(conf['mailbox_spread'],
                                                         conf['ad_spread'])
    except ExchangeException, e:
        logger.warn(str(e))
        sys.exit(1)
    sc.close()

    # Compare group state
    new_group_state, group_report = sc.compare_group_state(ex_group_info,
                                                           cere_group_info,
                                                           state,
                                                           attr_config)
    # Join state dicts
    new_state.update(new_group_state)
    
    # Concat reports
    report += group_report

    # Send a report by mail
    if mail and sender:
        Utils.sendmail(mail, sender, 'Exchange state report', '\n'.join(report))

    # TODO: Exceptions?
    f = open(state_file, 'w')
    pickle.dump(new_state, f)
    f.close()

