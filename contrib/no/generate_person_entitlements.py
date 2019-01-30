#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2018 University of Oslo, Norway
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

"""
Generate a JSON file that contains entitlement traits per each active
primary user account. The entitlement traits per account is a list that is
composed from 'entitlement' group traits collected from every group
the given primary user account is a member of.
"""

from __future__ import unicode_literals

import argparse
import json
from collections import defaultdict
from six import text_type

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import AtomicFileWriter

logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
ac = Factory.get('Account')(db)
gr = Factory.get('Group')(db)
co = Factory.get('Constants')(db)


def get_groups_with_entitlement():
    groups_with_entitlement = {}
    for group in gr.list_traits(co.trait_group_entitlement):
        groups_with_entitlement[group['entity_id']] = group['strval']
    return groups_with_entitlement


def map_entitlements_to_persons(groups_entitlement):
    """
    The function gets all primary user accounts that are the members of
    the groups with 'entitlement' trait, determines which persons accounts
    belong to and composes a dictionary of entitlements per person.
    """
    mapped_entitlements = defaultdict(list)
    primary_accounts_dict = {}
    for account in ac.list_accounts_by_type(primary_only=True):
        primary_accounts_dict[account['account_id']] = account['person_id']
    for group_id, group_entitlement in groups_entitlement.iteritems():
        group_members = gr.search_members(group_id=group_id,
                                          member_type=co.entity_account,
                                          member_filter_expired=True,
                                          indirect_members=True)
        for member in group_members:
            # Non-primary accounts are excluded
            if not member['member_id'] in primary_accounts_dict:
                continue
            # There is only one primary account per person
            person_id = primary_accounts_dict[member['member_id']]
            if (person_id not in mapped_entitlements) or (
                    group_entitlement not in mapped_entitlements[person_id]):
                mapped_entitlements[person_id].append(group_entitlement)
    return mapped_entitlements


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output',
        type=text_type,
        default=cereconf.LDAP_PERSON.get('entitlements_file', ''),
        dest='output',
        help='output file')
    args = parser.parse_args()

    if not args.output:
        parser.exit('No output file specified')

    logger.info('Start')
    logger.info('Fetching groups...')
    groups = get_groups_with_entitlement()
    logger.info('Mapping entitlements to person...')
    entitlements_per_person = map_entitlements_to_persons(groups)
    logger.info('Writing to %s', args.output)
    data = json.dumps(entitlements_per_person, ensure_ascii=False)
    with AtomicFileWriter(args.output, 'w') as fd:
        fd.write(data)
    logger.info('Done')


if __name__ == '__main__':
    main()
