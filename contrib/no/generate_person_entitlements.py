#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2024 University of Oslo, Norway
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
Generate a JSON cache of entitlements granted by group membership.

The cache contains a list of entitlements for each entity.  Only non-expired
members are included.  The result is a JSON file with the following structure:
::

    {
      <member-id>: [<entitlement-uri>, ...],
      ...
    }

The cache is used to populate the multivalued ldap attribute
*eduPersonEntitlement* by
:class:`Cerebrum.modules.no.OrgLdif.OrgLdifEntitlementsMixin`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import argparse
import json
import logging
from collections import defaultdict

import six

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import AtomicStreamRecoder

logger = logging.getLogger(__name__)


def get_entitlement_groups(db):
    """ Get entitlement group mapping.

    :rtype: generator
    :returns:
        An iterable with (<group-id>, <entitlement-uri>) pairs.
    """
    co = Factory.get('Constants')(db)
    gr = Factory.get('Group')(db)
    for group in gr.list_traits(co.trait_group_entitlement):
        yield (group['entity_id'], group['strval'])


def map_entitlements(db):
    """ Get entitlements mapping.

    This function gets all entitlement group members, and maps them to their
    entitlement.  The return value is basically the whole entitlement cache
    that this script generates.

    :returns:
        A mapping from entity_id to entitlement uri list:

        {321: ["urn:mace:example.org:foo:bar", ...], ...}
    """
    co = Factory.get('Constants')(db)
    gr = Factory.get('Group')(db)

    logger.info('fetching entitlement groups...')
    entitlement_groups = dict(get_entitlement_groups(db))

    logger.info('fetching group memberships...')
    entitlement_map = defaultdict(set)
    for group_id, uri in entitlement_groups.items():
        group_members = gr.search_members(group_id=group_id,
                                          member_type=(co.entity_account,
                                                       co.entity_person),
                                          member_filter_expired=True,
                                          indirect_members=True)
        for member in group_members:
            member_id = int(member['member_id'])
            entitlement_map[member_id].add(uri)

    # sort entitlement uri lists
    pretty_map = {}
    for entity_id in entitlement_map:
        pretty_map[entity_id] = sorted(entitlement_map[entity_id])
    return pretty_map


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Generate a JSON cache of entitlements",
    )
    parser.add_argument(
        '-o', '--output',
        type=six.text_type,
        default=cereconf.LDAP_PERSON.get('entitlements_file', ''),
        dest='output',
        help='output file (default: %(default)s)',
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %s', repr(args))

    if not args.output:
        parser.exit('No output file specified')

    db = Factory.get('Database')()

    logger.info('Caching entitlements...')
    entity_to_entitlements = map_entitlements(db)

    logger.info('Writing to %s', args.output)
    data = json.dumps(
        entity_to_entitlements,
        ensure_ascii=True,
        # sort + pretty print to compare runs with diff:
        indent=2,
        sort_keys=True,
    )
    # PY2/PY3 workaround:
    # `json.dumps(obj, ensure_ascii=True)` will always return:
    #   - ascii bytestring in PY2
    #   - ascii-encodable str/unicode object in PY3
    #
    # `AtomicFileWriter` by default only handles unicode objects, so we use
    # `AtomicStreamRecoder(encoding='ascii') which will both decode any
    # bytestring input using 'ascii', and encode string/unicode data using
    # 'ascii'
    #
    # When on PY3 we can revert to using `AtomicFileWriter(args.output,
    # mode='w')` and `json.dumps(ensure_ascii=False)` - if we want.
    with AtomicStreamRecoder(args.output, mode='w', encoding='ascii') as fd:
        fd.write(data)

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
