#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014-2018 University of Oslo, Norway
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
"""Script that checks the state of dist.groups between Cerebrum and Exchange.

This is done by:
    - Pulling out all related attributes from Exchange, via LDAP.
    - Pulling out all related information from Cerebrum, via API.
    - Compare the two above.
    - Send a report by mail/file.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import argparse
import itertools
import logging
import pickle
import time

import ldap
from six import text_type

import cereconf
import eventconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Utils
from Cerebrum.Utils import Factory
from Cerebrum.Utils import read_password
from Cerebrum.modules.Email import EmailAddress
from Cerebrum.modules.exchange.CerebrumUtils import CerebrumUtils
from Cerebrum.utils.email import sendmail
from Cerebrum.utils.ldaputils import decode_attrs
from Cerebrum.utils.file_stream import get_input_context, get_output_context

logger = logging.getLogger(__name__)


def text_decoder(encoding, allow_none=True):
    def to_text(value):
        if allow_none and value is None:
            return None
        if isinstance(value, bytes):
            return value.decode(encoding)
        return text_type(value)
    return to_text


class StateChecker(object):

    """Wrapper class for state-checking functions.

    The StateChecker class wraps all the functions we need in order to
    verify and report deviances between Cerebrum and Exchange.
    """

    # Connect params
    LDAP_RETRY_DELAY = 60
    LDAP_RETRY_MAX = 5

    # Search and result params
    LDAP_COM_DELAY = 30
    LDAP_COM_MAX = 3

    def __init__(self, conf):
        """Initzialize a new instance of out state-checker.

        :param logger logger: The logger to use.
        :param dict conf: Our StateCheckers configuration.
        """
        self.db = Factory.get('Database')(client_encoding='UTF-8')
        self.co = Factory.get('Constants')(self.db)
        self.dg = Factory.get('DistributionGroup')(self.db)
        self.ac = Factory.get('Account')(self.db)
        self.gr = Factory.get('Group')(self.db)
        self.et = Factory.get('EmailTarget')(self.db)
        self.ea = EmailAddress(self.db)
        self.ut = CerebrumUtils()

        self.config = conf

        self._ldap_page_size = 1000

    def u(self, db_value):
        """ Decode bytestring from database. """
        if isinstance(db_value, bytes):
            return db_value.decode(self.db.encoding)
        return text_type(db_value)

    def init_ldap(self):
        """Initzialize LDAP connection."""
        self.ldap_srv = ldap.ldapobject.ReconnectLDAPObject(
            '%s://%s/' % (self.config['ldap_proto'],
                          self.config['ldap_server']),
            retry_max=self.LDAP_RETRY_MAX,
            retry_delay=self.LDAP_RETRY_DELAY)
        usr = self.config['ldap_user'].split('\\')[1]
        self.ldap_srv.bind_s(
            self.config['ldap_user'],
            read_password(usr, self.config['ldap_server']))

        self.ldap_lc = ldap.controls.SimplePagedResultsControl(
            True, self._ldap_page_size, '')

    def _searcher(self, ou, scope, attrs, ctrls):
        """ Perform ldap.search(), but retry in the event of an error.

        This wraps the search with error handling, so that the search is
        repeated with a delay between attempts.
        """
        for attempt in itertools.count(1):
            try:
                return self.ldap_srv.search_ext(
                    ou, scope, attrlist=attrs, serverctrls=ctrls)
            except ldap.LDAPError as e:
                if attempt < self.LDAP_COM_MAX:
                    logger.debug('Caught %r in _searcher on attempt %d',
                                 e, attempt)
                    time.sleep(self.LDAP_COM_DELAY)
                    continue
                raise

    def _recvr(self, msgid):
        """ Perform ldap.result3(), but retry in the event of an error.

        This wraps the result fetching with error handling, so that the fetch
        is repeated with a delay between attempts.

        It also decodes all attributes and attribute text values.
        """
        for attempt in itertools.count(1):
            try:
                # return self.ldap_srv.result3(msgid)
                rtype, rdata, rmsgid, sc = self.ldap_srv.result3(msgid)
                return rtype, decode_attrs(rdata), rmsgid, sc
            except ldap.LDAPError as e:
                if attempt < self.LDAP_COM_MAX:
                    logger.debug('Caught %r in _recvr on attempt %d',
                                 e, attempt)
                    time.sleep(self.LDAP_COM_DELAY)
                    continue
                raise

    # This is a paging searcher, that should be used for large amounts of data
    def search(self, ou, attrs, scope=ldap.SCOPE_SUBTREE):
        """Wrapper for the search- and result-calls.

        Implements paged searching.

        :param str ou: The OU to search in.
        :param list attrs: The attributes to fetch.
        :param int scope: Our search scope, default is subtree.
        :rtype: list
        :return: List of objects.
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
                logger.warn('Server ignores RFC 2696 control.')
                break
        # Skip the OU itself, only return objects in the OU
        return data[1:]

    # This search wrapper should be used for fetching members
    def member_searcher(self, dn, scope, attrs):
        """Utility method for searching for group members.

        :param str dn: The groups distinguished name.
        :param int scope: Which scope to search by, should be BASE.
        :param list attrs: A list of attributes to fetch.
        :rtype: tuple
        :return: The return-type and the result.
        """
        # Wrapping the search, try three times
        for attempt in itertools.count(1):
            try:
                # Search
                msgid = self.ldap_srv.search(dn, scope, attrlist=attrs)
                # Fetch
                rtype, r = self.ldap_srv.result(msgid)
                return rtype, r
            except ldap.LDAPError as e:
                if attempt < self.LDAP_COM_MAX:
                    logger.debug('Caught %r in member_searcher on attempt %d',
                                 e, attempt)
                    time.sleep(self.LDAP_COM_DELAY)
                    continue
                raise

    # We need to implement a special function to pull out all the members from
    # a group, since the idiots at M$ forces us to select a range...
    # Fucking asswipes will burn in hell.
    def collect_members(self, dn):
        """Fetch a groups members.

        This method picks out members in slices, since AD LDAP won't give us
        more than 1500 users at a time. If the range-part of the attribute name
        ends with a star, we know that we need to look for more members...

        :param str dn: The groups distinguished name.
        :rtype: list
        :return: A list of the members.
        """
        # We are searching trough a range. 0 is the start point.
        low = str(0)
        members = []
        end = False
        while not end:
            # * means that we search for as many attributes as possible, from
            # the start point defined by the low-param
            attr = ['member;range=%s-*' % low]
            # Search'n fetch
            time.sleep(1)  # Be polite
            rtype, r = self.member_searcher(dn, ldap.SCOPE_BASE, attr)
            # If this shit hits, no members exists. Break of.
            if not r[0][1]:
                end = True
                break
            # Dig out the data
            r = r[0][1]
            # Extract key
            key = list(r.keys())[0]
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
        """Close the connection to the LDAP server."""
        self.ldap_srv.unbind_s()

    ###
    # Group related fetching & comparison
    ###

    def collect_exchange_group_info(self, group_ou):
        """Collect group-information from Exchange, via LDAP.

        :param str group_ou: The OrganizationalUnit to search for groups.
        :rtype: dict
        :return: A dict with the group attributes. The key is the group name.
        """
        attrs = ['displayName',
                 'info',
                 'proxyAddresses',
                 'msExchHideFromAddressLists']
        r = self.search(group_ou, attrs)
        ret = {}
        for cn, data in r:
            tmp = {}
            name = cn[3:].split(',')[0]
            for key in data:
                if key == 'info':
                    tmp[u'Description'] = data[key][0]
                elif key == 'displayName':
                    tmp[u'DisplayName'] = data[key][0]
                elif key == 'proxyAddresses':
                    addrs = []
                    for addr in data[key]:
                        if addr.startswith('SMTP:'):
                            tmp[u'Primary'] = addr[5:]
                        # TODO: Correct var?
                        if (cereconf.EXCHANGE_DEFAULT_ADDRESS_PLACEHOLDER not
                                in addr):
                            addrs.append(addr[5:])
                    tmp[u'Aliases'] = sorted(addrs)
                elif key == 'managedBy':
                    tmp_man = data[key][0][3:].split(',')[0]
                    if tmp_man == 'Default group moderator':
                        tmp_man = u'groupadmin'
                    tmp[u'ManagedBy'] = [tmp_man]

            # Skip reporting memberships for roomlists, since we don't manage
            # those memberships.
            # TODO: Generalize this
            if name.startswith('rom-'):
                tmp['Members'] = []
            else:
                # Pulling 'em out the logical way... S..
                tmp['Members'] = sorted([str(m[3:]).split(',')[0] for m in
                                        self.collect_members(cn)])

            # Non-existent attribute means that the value is false. Fuckers.
            if 'msExchHideFromAddressLists' in data:
                tmp_key = 'msExchHideFromAddressLists'
                tmp[u'HiddenFromAddressListsEnabled'] = (
                    True if data[tmp_key][0] == 'TRUE' else False)
            else:
                tmp[u'HiddenFromAddressListsEnabled'] = False
            ret[name] = tmp
        return ret

    def collect_cerebrum_group_info(self, mb_spread, ad_spread):
        """Collect distgroup related information from Cerebrum.

        :param int/str mb_spread: Spread of mailboxes in exchange.
        :param int/str ad_spread: Spread of accounts in AD.
        :rtype: dict
        :return: A dict of users attributes. Uname is key.
        """
        mb_spread = self.co.Spread(mb_spread)
        ad_spread = self.co.Spread(ad_spread)

        u = text_decoder(self.db.encoding)

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

            tmp[u(self.dg.group_name)] = {
                u'Description': u(self.dg.description),
                u'DisplayName': u(data['displayname']),
            }

            if not roomlist:
                # Split up the moderated by field, and resolve group members
                # from groups if there are groups in the moderated by field!
                tmp[u(self.dg.group_name)].update({
                    u'HiddenFromAddressListsEnabled':
                        _true_or_false(data['hidden']),
                    u'Primary': u(data['primary']),
                    u'Aliases': [u(v) for v in sorted(data['aliases'])]
                })

            # Collect members
            membs_unfiltered = self.ut.get_group_members(
                self.dg.entity_id,
                spread=mb_spread,
                filter_spread=ad_spread
            )
            members = [u(member['name']) for member in membs_unfiltered]
            tmp[u(self.dg.group_name)].update({u'Members': sorted(members)})

        return tmp

    def compare_group_state(self, ex_group_info, cere_group_info, state,
                            config):
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
        # difference (& is union, in case you wondered). If an attribute is
        # not in it's desired state in both this and the last run, save the
        # timestamp from the last run. This is used for calculating when we
        # nag to someone about stuff not beeing in sync.
        for key in s_ex_keys & s_ce_keys:
            for attr in cere_group_info[key]:
                tmp = {}
                if state and key in state['group'] and \
                        attr in state['group'][key]:
                    t_0 = state['group'][key][attr][u'Time']
                else:
                    t_0 = time.time()

                if attr not in ex_group_info[key]:
                    tmp = {
                        u'Exchange': None,
                        u'Cerebrum': cere_group_info[key][attr],
                        u'Time': t_0
                        }
                elif cere_group_info[key][attr] != ex_group_info[key][attr]:
                    tmp = {
                        u'Exchange': ex_group_info[key][attr],
                        u'Cerebrum': cere_group_info[key][attr],
                        u'Time': t_0
                        }

                if tmp:
                    diff_group.setdefault(key, {})[attr] = tmp

        ret = {
            'new_group': diff_new,
            'stale_group': diff_stale,
            'group': diff_group,
        }

        if not state:
            return ret, []

        now = time.time()
        # By now, we have three different dicts. Loop trough them and check if
        # we should report 'em
        report = ['\n\n# Group Attribute Since Cerebrum_value:Exchange_value']

        # Report attribute mismatches for groups
        for key in diff_group:
            for attr in diff_group[key]:
                delta = (config.get(attr) if attr in config else
                         config.get('UndefinedAttribute'))
                if diff_group[key][attr][u'Time'] < now - delta:
                    t = time.strftime(u'%d%m%Y-%H:%M', time.localtime(
                        diff_group[key][attr][u'Time']))
                    if attr in (u'Aliases', u'Members',):
                        # We report the difference for these types, for
                        # redability
                        s_ce_attr = set(diff_group[key][attr][u'Cerebrum'])
                        try:
                            s_ex_attr = set(diff_group[key][attr][u'Exchange'])
                        except TypeError:
                            s_ex_attr = set([])
                        new_attr = list(s_ce_attr - s_ex_attr)
                        stale_attr = list(s_ex_attr - s_ce_attr)
                        if new_attr == stale_attr:
                            continue
                        tmp = u'%-10s %-30s %s +%s:-%s' % (key, attr, t,
                                                           str(new_attr),
                                                           str(stale_attr))
                    else:
                        tmp = u'%-10s %-30s %s %s:%s' % (
                            key, attr, t,
                            repr(diff_group[key][attr][u'Cerebrum']),
                            repr(diff_group[key][attr][u'Exchange']))
                    report += [tmp]

        # Report uncreated groups
        report += ['\n# Uncreated groups (uname, time)']
        attr = 'UncreatedGroup'
        delta = (config.get(attr) if attr in config else
                 config.get('UndefinedAttribute'))
        for key in diff_new:
            if diff_new[key] < now - delta:
                t = time.strftime(u'%d%m%Y-%H:%M', time.localtime(
                    diff_new[key]))
                report += [u'%-10s uncreated_group %s' % (key, t)]

        # Report stale groups
        report += ['\n# Stale groups (uname, time)']
        attr = 'StaleGroup'
        delta = (config.get(attr) if attr in config else
                 config.get('UndefinedAttribute'))
        for key in diff_stale:
            t = time.strftime(u'%d%m%Y-%H:%M', time.localtime(
                diff_stale[key]))
            if diff_stale[key] < now - delta:
                report += [u'%-10s stale_group %s' % (key, t)]

        return ret, report


def eventconf_type(value):
    try:
        return eventconf.CONFIG[value]
    except KeyError as e:
        raise ValueError(e)


def main(inargs=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-t', '--type',
        dest='config',
        type=eventconf_type,
        required=True,
        help="Sync type (a valid entry in eventconf.CONFIG)")

    parser.add_argument(
        '-f', '--file',
        dest='state',
        required=True,
        help="read and write state to %(metavar)s")

    parser.add_argument(
        '-m', '--mail',
        help="Send reports to %(metavar)s")

    parser.add_argument(
        '-s', '--sender',
        help="Send reports from %(metavar)s")

    parser.add_argument(
        '-r', '--report-file',
        dest='report',
        help="Write the report to %(metavar)s")

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    if bool(args.mail) ^ bool(args.sender):
        raise ValueError("Must give both mail and sender")

    Cerebrum.logutils.autoconf('cronjob', args)

    attr_config = args.config['state_check_conf']
    group_ou = args.config['group_ou']

    try:
        with get_input_context(args.state, encoding=None, stdin=None) as f:
            state = pickle.load(f)
    except IOError:
        logger.warning('No existing state file %s', args.state)
        state = None

    sc = StateChecker(args.config)
    # Collect group info from Cerebrum and Exchange
    sc.init_ldap()
    ex_group_info = sc.collect_exchange_group_info(group_ou)
    sc.close()

    cere_group_info = sc.collect_cerebrum_group_info(
        args.config['mailbox_spread'],
        args.config['ad_spread'])

    # Compare group state
    new_state, report = sc.compare_group_state(ex_group_info,
                                               cere_group_info,
                                               state,
                                               attr_config)

    try:
        rep = u'\n'.join(report)
    except UnicodeError as e:
        logger.warning('Bytestring data in report: %r', e)
        tmp = []
        for x in report:
            tmp.append(x.decode('UTF-8'))
        rep = u'\n'.join(tmp)

    # Send a report by mail
    if args.mail and args.sender:
        sendmail(args.mail, args.sender,
                       'Exchange group state report',
                       rep.encode('utf-8'))

    # Write report to file
    if args.report:
        with get_output_context(args.report, encoding=None, stdout=None, stderr=None) as f:
            f.write(rep.encode('utf-8'))

    with get_output_context(args.state, encoding=None, stdout=None, stderr=None) as f:
        pickle.dump(new_state, f)


if __name__ == '__main__':
    main()
