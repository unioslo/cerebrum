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

import time
import pickle
import getopt
import sys

from Cerebrum.Utils import Factory
from Cerebrum.modules.Email import EmailAddress
from Cerebrum.modules.exchange.CerebrumUtils import CerebrumUtils
from Cerebrum import Utils
from Cerebrum.Utils import read_password
import ldap

logger = Utils.Factory.get_logger('cronjob')

class StateChecker(object):
    def __init__(self, logger, conf):
        self.db = Factory.get('Database')(client_encoding='UTF-8')
        self.co = Factory.get('Constants')(self.db)
        self.dg = Factory.get('DistributionGroup')(self.db)
        self.ac = Factory.get('Account')(self.db)
        self.gr = Factory.get('Group')(self.db)
        self.et = Factory.get('EmailTarget')(self.db)
        self.ea = EmailAddress(self.db)
        self.ut = CerebrumUtils()

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

    # Wrapping the search with retries if the server is busy or similar errors
    def _searcher(self, ou, scope, attrs, ctrls):
        c_fail = 0
        e_save = None
        while c_fail <= 3:
            try:
                return self.ldap_srv.search_ext(ou, scope,
                                attrlist=attrs, serverctrls=ctrls)
                c_fail = 0
                e_save = None
            except (ldap.LDAPError, e):
                c_fail = c_fail + 1
                e_save = e
                self.logger.debug('Caught %s in _searcher' % str(e))
                time.sleep(14)
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
            except (ldap.LDAPError, e):
                c_fail = c_fail + 1
                e_save = e
                self.logger.debug('Caught %s in _recvr' % str(e))
                time.sleep(14)
        if e_save:
            raise e_save 

    # This is a paging searcher, that should be used for large amounts of data
    def search(self, ou, attrs, scope=ldap.SCOPE_SUBTREE):
        # Implementing paging, taken from
        # http://www.novell.com/coolsolutions/tip/18274.html
        msgid = self._searcher(ou, scope, attrs, [self.ldap_lc])

        data = []
        while True:
            rtype, rdata, rmsgid, sc = self._recvr(msgid)
            data.extend(rdata)
            pctrls = [c for c in sc if \
                    c.controlType == ldap.LDAP_CONTROL_PAGE_OID]
            if pctrls:
                est, cookie = pctrls[0].controlValue
                if cookie:
                    self.ldap_lc.controlValue = (self._ldap_page_size, cookie)
                    msgid = self._searcher(ou, scope, attrs, [self.ldap_lc])
                else:
                    break
            else:
                self.logger.warn('Server ignores RFC 2696 control.')
                break
        return data[1:]

    # This search wrapper should be used for fetching members
    def member_searcher(self, dn, scope, attrs):
        # Wrapping the search, try three times
        c_fail = 0
        e_save = None
        while c_fail <= 3:
            try:
                # Search
                msgid = self.ldap_srv.search(dn, scope, attrlist=attrs)
                # Fetch
                rtype, r = self.ldap_srv.result(msgid)
                return rtype, r
            except (ldap.LDAPError, e):
                c_fail = c_fail + 1
                e_save = e
                self.logger.debug('Caught %s in member_searcher' % str(e))
                time.sleep(14)
        raise e_save 

    # We need to implement a special function to pull out all the members from
    # a group, since the idiots at M$ forces us to select a range...
    # Fucking asswipes will burn in hell.
    def collect_members(self, dn):
        # We are searching trough a range. 0 is the start point.
        low = str(0)
        members = []
        end = False
        while not end:
            # * means that we search for as many attributes as possible, from
            # the start point defined by the low-param
            attr = ['member;range=%s-*' % low]
            # Search'n fetch
            rtype, r = self.member_searcher(dn, ldap.SCOPE_BASE, attr)
            # If this shit hits, no members exists. Break of.
            if not r[0][1]:
                end = True
                break
            # Dig out the data
            r = r[0][1]
            # Extract key
            key = r.keys()[0]
            # Store members
            members.extend(r[key])
            # If so, we have reached the end of the range
            # (i.e. key is 'member;range=7500-*')
            if '*' in key:
                end = True
            # Extract the new start point from the key
            # (i.e. key is 'member;range=0-1499')
            else:
                low = str(int(key.split('-')[-1]) + 1)
        return members

    def close(self):
        self.ldap_srv.unbind()

###
# Group related fetching & comparison
###
    def collect_exchange_group_info(self, group_ou):
        attrs = ['displayName',
                 'info',
                 'proxyAddresses',
                 'managedBy',
                 'msExchHideFromAddressLists',
                 'msExchModeratedByLink',
                 'msExchEnableModeration']
        
        r = self.search(group_ou, attrs)
        
        ret = {}
        for cn, data in r:
            tmp = {}
            name = cn[3:].split(',')[0]
            for key in data:
                if key == 'info':
                    tmp[u'Description'] = data[key][0].decode('UTF-8')
                elif key == 'displayName':
                    tmp[u'DisplayName'] = data[key][0].decode('UTF-8')
                elif key == 'proxyAddresses':
                    addrs = []
                    for addr in data[key]:
                        if addr.startswith('SMTP:'):
                            tmp[u'Primary'] = addr[5:].decode('UTF-8')
                        # TODO: Correct var?
                        if not cereconf.EXCHANGE_DEFAULT_ADDRESS_PLACEHOLDER \
                                in addr:
                            addrs.append(addr[5:].decode('UTF-8'))
                    tmp[u'Aliases'] = sorted(addrs)
                elif key == 'managedBy':
                    tmp_man = data[key][0][3:].split(',')[0].decode('UTF-8')
                    if tmp_man == 'Default group moderator':
                        tmp_man = u'groupadmin'
                    tmp[u'ManagedBy'] = [tmp_man]
                elif key == 'msExchModeratedByLink':
                    mods = []
                    for mod in data[key]:
                        mods.append(mod[3:].split(',')[0].decode('UTF-8'))
                    tmp[u'ModeratedBy'] = sorted(mods)
                elif key == 'msExchEnableModeration':
                    tmp[u'ModerationEnabled'] = True if \
                            data[key][0].decode('UTF-8') == 'TRUE' else False

            # Pulling 'em out the logical way... S..
            tmp['Members'] = [ m[3:].split(',')[0] for m in \
                                                    self.collect_members(cn) ]

            # Non-existent attribute means that the value is false. Fuckers.
            if data.has_key('msExchHideFromAddressLists'):
                tmp_key = 'msExchHideFromAddressLists'
                tmp[u'HiddenFromAddressListsEnabled'] = True if \
                        data[tmp_key][0].decode('UTF-8') == 'TRUE' else False
            else:
                tmp[u'HiddenFromAddressListsEnabled'] = False

            ret[name] = tmp
        return ret

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
                        u'Description': self.dg.description,
                        u'DisplayName': data['displayname'],
                        u'ManagedBy': [manager],
            }

            if not roomlist:
                tmp[self.dg.group_name].update({
                            u'ModerationEnabled': \
                                    _true_or_false(data['modenable']),
                            u'ModeratedBy': sorted(data['modby']),
                            u'HiddenFromAddressListsEnabled': \
                                    _true_or_false(data['hidden']),
                            u'Primary': data['primary'],
                            u'Aliases': sorted(data['aliases'])
                })

            # Collect members
            membs_unfiltered = self.ut.get_group_members(self.dg.entity_id,
                                                        spread=mb_spread,
                                                        filter_spread=ad_spread)
            members = [member['name'] for member in membs_unfiltered]
            tmp[self.dg.group_name].update({u'Members': sorted(members)})
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
                    t_0 = state['group'][key][attr][u'Time']
                else:
                    t_0 = time.time()
                diff_group.setdefault(key, {})
                if attr not in ex_group_info[key]:
                    diff_group[key][attr] = {
                         u'Exchange': None,
                         u'Cerebrum': cere_group_info[key][attr],
                         u'Time': t_0
                        }
                elif cere_group_info[key][attr] != ex_group_info[key][attr]:
                    diff_group[key][attr] = {
                         u'Exchange': ex_group_info[key][attr],
                         u'Cerebrum': cere_group_info[key][attr],
                         u'Time': t_0
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
                if diff_group[key][attr][u'Time'] < now - delta:
                    t = time.strftime(u'%d%m%Y-%H:%M', time.localtime(
                        diff_group[key][attr][u'Time']))
                    if attr in (u'ModeratedBy', u'Aliases', u'Members',):
                        # We report the difference for these types, for
                        # redability
                        s_ce_attr = set(diff_group[key][attr][u'Cerebrum'])
                        try:
                            s_ex_attr = set(diff_group[key][attr][u'Exchange'])
                        except TypeError:
                            s_ex_attr = set([])
                        new_attr = list(s_ce_attr - s_ex_attr)
                        stale_attr = list(s_ex_attr - s_ce_attr)
                        tmp = u'%-10s %-30s %s +%s:-%s' % (key, attr, t,
                                                          str(new_attr),
                                                          str(stale_attr))
                    else:
                        tmp = u'%-10s %-30s %s %s:%s' % (key, attr, t,
                                    repr(diff_group[key][attr][u'Cerebrum']),
                                    repr(diff_group[key][attr][u'Exchange']))
                    report += [tmp]


        # Report uncreated groups
        report += ['\n# Uncreated groups (uname, time)']
        attr = 'UncreatedGroup'
        delta = config.get(attr) if attr in config else \
                                                config.get('UndefinedAttribute')
        for key in diff_new:
            if diff_new[key] < now - delta:
                t = time.strftime(u'%d%m%Y-%H:%M', time.localtime(
                    diff_new[key]))
                report += [u'%-10s uncreated_group %s' % (key, t)]

        # Report stale groups
        report += ['\n# Stale groups (uname, time)']
        attr = 'StaleGroup'
        delta = config.get(attr) if attr in config else \
                                                config.get('UndefinedAttribute')
        for key in diff_stale:
            t = time.strftime(u'%d%m%Y-%H:%M', time.localtime(
                diff_stale[key]))
            if diff_stale[key] < now - delta:
                report += [u'%-10s stale_group %s' % (key, t)]

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

    # Collect group infor from Cerebrum and Exchange
    sc.init_ldap()
    ex_group_info = sc.collect_exchange_group_info(group_ou)
    sc.close()

    cere_group_info = sc.collect_cerebrum_group_info(conf['mailbox_spread'],
                                                     conf['ad_spread'])

    # Compare group state
    new_state, report = sc.compare_group_state(ex_group_info,
                                               cere_group_info,
                                               state,
                                               attr_config)
    
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
        Utils.sendmail(mail, sender, 'Exchange group state report',
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

