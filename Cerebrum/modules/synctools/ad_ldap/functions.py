#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2017 University of Oslo, Norway
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
from Cerebrum.modules.synctools.ad_ldap import data_fetchers as df
from Cerebrum.modules.synctools import base_data_fetchers as base_df
from Cerebrum.modules.synctools.ad_ldap import mappers
from Cerebrum.modules.synctools.ad_ldap.compare import equal
from Cerebrum.Utils import Factory


def build_event_dict(entity_id, entity_type, event_type, attrs=None):
    event_dict = {
        'entity_id': entity_id,
        'entity_type': entity_type,
        'event_type': event_type
    }
    if attrs:
        event_dict['attrs'] = attrs
    return event_dict


def generate_stats(logger, entity_type, desynced, not_in_ad,
                   not_in_crb=None, skipped=None):
    if skipped:
        logger.info('# of {0} that were skipped: {1}'.format(entity_type,
                                                             skipped))
    logger.info('# of {0} that are desynced: {1}'.format(
        entity_type, desynced
    ))
    logger.info('# of {0} present in Cerebrum, but not in AD: {1}'.format(
        entity_type, not_in_ad
    ))
    if not_in_crb:
        logger.info('# of {0} present in AD, but not in Cerebrum: {1}'.format(
            entity_type, not_in_crb
        ))


def build_all_account_events(db,
                             client,
                             ad_acc_spread,
                             ad_grp_spread,
                             group_postfix,
                             path_req_disks,
                             acc_attrs,
                             show_diff,
                             password_sync=False):
    logger = Factory.get_logger("console")
    logger.info('Getting account data from Cerebrum...')
    all_crb_accs_data = df.get_all_crb_accounts_data(db,
                                                     ad_acc_spread,
                                                     ad_grp_spread)
    crb_acc_ad_values = [
        mappers.crb_acc_values_to_ad_values(crb_acc_data,
                                            path_req_disks,
                                            client.config.nis_domain,
                                            group_postfix)
        for crb_acc_data in all_crb_accs_data]
    skipped = len(all_crb_accs_data) - len(crb_acc_ad_values)
    desynced_accounts = []
    accounts_not_in_ad = []
    events = []
    if not password_sync:
        logger.info('Getting account data from AD-LDAP....')
        ad_ldap_acc_values = mappers.format_ldap_acc_data(
            df.get_all_ad_ldap_acc_values(client),
            acc_attrs
        )
        logger.info('Diffing account data...')
        for crb_acc in crb_acc_ad_values:
            if crb_acc['username'] not in ad_ldap_acc_values:
                accounts_not_in_ad.append(crb_acc['account_id'])
                continue
            if not equal(crb_acc,
                         ad_ldap_acc_values[crb_acc['username']],
                         acc_attrs,
                         show_diff=show_diff,
                         entity_id=crb_acc['account_id'],
                         entity_type='account'):
                desynced_accounts.append(crb_acc['account_id'])
            # Remove from dict to get number of accounts not present in AD,
            # but not Cerebrum when this for-loop is done.
            ad_ldap_acc_values.pop(crb_acc['username'])
        accs_not_in_crb = [base_df.get_account_id_by_username(db, username)
                           for username in ad_ldap_acc_values.keys()]

        for crb_acc in accs_not_in_crb:
            events.append(build_event_dict(crb_acc, 'account', 'remove'))
        generate_stats(logger,
                       'accounts',
                       len(desynced_accounts),
                       len(accounts_not_in_ad),
                       len(ad_ldap_acc_values),
                       skipped)
        logger.info('Building account events...')
        for crb_acc in desynced_accounts:
            events.append(build_event_dict(crb_acc, 'account', 'modify'))

        for crb_acc in accounts_not_in_ad:
            events.append(build_event_dict(crb_acc, 'account', 'add'))
    else:
        for crb_acc in crb_acc_ad_values:
            events.append(build_event_dict(crb_acc['account_id'],
                                           'account',
                                           'modify',
                                           attrs=['password']))
        logger.info('Generated # of password events: {}'
                    ''.format(len(crb_acc_ad_values)))
    return events


def build_all_group_events(db,
                           client,
                           ad_acc_spread,
                           ad_grp_spread,
                           group_postfix,
                           grp_attrs,
                           show_diff):
    logger = Factory.get_logger("console")
    logger.info('Getting group data from AD-LDAP....')
    all_ad_ldap_grp_values = mappers.format_ldap_grp_data(
        df.get_all_ad_ldap_grp_values(client),
        grp_attrs
    )
    logger.info('Getting group data from Cerebrum...')
    all_crb_groups_data = df.get_all_groups_values(db,
                                                   ad_grp_spread,
                                                   ad_acc_spread)
    all_crb_groups_values = {}
    for grp_name, grp_data in all_crb_groups_data.items():
        values = mappers.crb_grp_values_to_ad_values(grp_data,
                                                     client.config.users_dn,
                                                     client.config.groups_dn,
                                                     client.config.nis_domain,
                                                     group_postfix)
        grp_value_key = ''.join([grp_data['name'], group_postfix])
        all_crb_groups_values[grp_value_key] = values

    not_in_ad = []
    desynced_groups = []

    logger.info('Diffing group data...')
    for grp, group_data in all_crb_groups_values.items():
        if grp not in all_ad_ldap_grp_values:
            not_in_ad.append(group_data['group_id'])
            continue
        ad_values = all_ad_ldap_grp_values[grp]
        if not equal(group_data, ad_values, grp_attrs,
                     show_diff=show_diff,
                     entity_id=group_data['group_id'],
                     entity_type='group'):
            desynced_groups.append(group_data['group_id'])
        all_ad_ldap_grp_values.pop(grp)

    logger.info('Building group events...')
    events = []
    for crb_grp_id in desynced_groups:
        events.append(build_event_dict(crb_grp_id, 'group', 'modify'))

    for crb_grp_id in not_in_ad:
        events.append(build_event_dict(crb_grp_id, 'group', 'add'))

    grps_not_in_crb = [base_df.get_group_id_by_name(db, group_name)
                       for group_name in all_ad_ldap_grp_values.keys()]

    generate_stats(logger,
                   'groups',
                   len(desynced_groups),
                   len(not_in_ad),
                   len(grps_not_in_crb))

    for crb_grp in grps_not_in_crb:
        events.append(build_event_dict(crb_grp, 'group', 'remove'))

    return events


def build_account_events(db,
                         client,
                         account_ids,
                         ad_acc_spread,
                         group_postfix,
                         path_req_disks,
                         acc_attrs,
                         show_diff,
                         password_sync=False):
    crb_accs_data = [
        df.get_crb_account_data(db, acc_id, ad_acc_spread)
        for acc_id in account_ids
    ]
    crb_acc_ad_values = [
        mappers.crb_acc_values_to_ad_values(crb_acc_data,
                                            path_req_disks,
                                            client.config.nis_domain,
                                            group_postfix)
        for crb_acc_data in crb_accs_data]
    logger = Factory.get_logger("console")
    events = []
    if not password_sync:
        skipped = 0
        desynced = []
        not_in_ad = []
        for crb_acc in crb_acc_ad_values:
            if crb_acc.get('quarantine_action') == 'skip':
                skipped += 1
                continue
            ad_ldap_acc_values = mappers.format_ldap_acc_data(
                df.get_ad_ldap_acc_values(client, crb_acc['username']),
                acc_attrs
            )
            if crb_acc['username'] not in ad_ldap_acc_values:
                not_in_ad.append(crb_acc['account_id'])
                continue
            if not equal(crb_acc,
                         ad_ldap_acc_values[crb_acc['username']],
                         acc_attrs,
                         show_diff=show_diff,
                         entity_id=crb_acc['account_id'],
                         entity_type='account'):
                desynced.append(crb_acc['account_id'])
        for acc in desynced:
            events.append(build_event_dict(acc, 'account', 'modify'))

        for acc in not_in_ad:
            events.append(build_event_dict(acc, 'account', 'add'))
        generate_stats(logger, 'accounts', len(desynced), len(not_in_ad),
                       skipped=skipped)
    else:
        for crb_acc in crb_acc_ad_values:
            events.append(build_event_dict(crb_acc['account_id'],
                                           'account',
                                           'modify',
                                           attrs=['password']))
    return events
