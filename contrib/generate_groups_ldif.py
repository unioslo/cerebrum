#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
Generate a (supplementary) group tree for LDAP.

This script generates two files:

1. An LDIF-file with basic group info
2. A json or pickle file that maps members (entity_id of persons, accounts) to
groups (dn values present in the LDIF file).

The overall idea is to have membership data in org-ldif that references objects
in this group tree.  By using a membership cache, org-ldif gets a membership
view that is in sync with the current group tree.
"""
from __future__ import unicode_literals

import argparse
import collections
import contextlib
import functools
import json
import logging
import operator
import cPickle as pickle  # noqa: N813
import time

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.modules.LDIFutils import (
    dn_escape_re,
    entry_string,
    get_ldap_config,
    hex_escape_match,
    normalize_string,
)
from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import (AtomicFileWriter, SimilarSizeWriter)


logger = logging.getLogger(__name__)


@contextlib.contextmanager
def timer(what, level=logging.DEBUG):
    """ Log context runtime. """
    start = time.time()
    logger.log(level, 'start %s ...', what)
    yield
    logger.log(level, '... done %s (in %.02f s)',
               what, time.time() - start)


def time_call(fn):
    """ Log function runtime. """
    name = fn.__name__

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with timer('{}()'.format(name)):
            return fn(*args, **kwargs)

    return wrapper


def get_groups(db, spread):
    """
    Fetch groups to export.

    :param db:
    :param spread: Only include groups with the given spread

    :rtype: generator
    :returns:
        Dictionaries with group 'id', 'name', 'description' fields.
    """
    group = Factory.get('Group')(db)
    count = 0
    for count, row in enumerate(group.search(spread=spread), 1):
        yield {
            'id': int(row['group_id']),
            'name': row['name'],
            'description': row['description'],
        }
    logger.info('found %d groups', count)


@time_call
def get_group_memberships(db, groups, spread,
                          map_account_as_person=False,
                          indirect_members=False,
                          ):
    """
    Fetch group memberships.

    :param groups:
        An iterable with group dictionaries (see :func:`.get_groups` and
        :func:`.populate_dn`).

    :param spread:
        Only include memberships of groups with the given spread
        (only for optimization - memberships are also filtered by the given
        groups).

    :param map_account_as_person:
        Include personal account memberships as {owner-id: group-dn} in the
        membership result.

    :param indirect_members:
        Include indirect memberships in the result.

    :rtype: dict
    :returns:
        A dict that maps member entity_ids to a set of group DN values.
    """
    group_dn_map = {g['id']: g['dn'] for g in groups}
    ac = Factory.get('Account')(db)
    gr = Factory.get('Group')(db)
    co = Factory.get('Constants')(db)

    owner_map = {}

    if map_account_as_person:
        with timer('caching account owners'):
            owner_map = {
                r['account_id']: r['owner_id']
                for r in ac.search(expire_start=None,
                                   expire_stop=None,
                                   owner_type=co.entity_person)}

    memberships = collections.defaultdict(set)

    def add_member(group_id, member_id):
        if group_id not in group_dn_map:
            # unknown group
            return

        group_dn = group_dn_map[group_id]
        memberships[member_id].add(group_dn)

        if member_id in owner_map:
            person_id = owner_map[member_id]
            memberships[person_id].add(group_dn)

    if indirect_members:
        # Note: Expensive! Need to run search query on each individual group -
        #       should be fine if there aren't too many groups involved.
        # TODO: This could probably be optimized by implementing a better query
        #       in `Cerebrum.group.memberships`
        with timer('caching recursive memberships'):
            for group_id in group_dn_map:
                for row in gr.search_members(
                        group_id=group_id,
                        indirect_members=True,
                        member_type=(co.entity_account,
                                     co.entity_person)):
                    add_member(group_id, row['member_id'])
    else:
        with timer('caching memberships'):
            for row in gr.search_members(spread=spread,
                                         member_type=(co.entity_account,
                                                      co.entity_person)):
                add_member(row['group_id'], row['member_id'])

    return dict(memberships)


def populate_dn(config, groups):
    """
    Update group dicts with a dn value.

    :param groups:
        An iterable with group dictionaries (see :func:`.get_groups` and
        :func:`.populate_dn`).

    .. note::
        Mutates the given dictionary values.
    """
    base_dn = config.get_dn()

    seen = set()
    for group in groups:
        dn = 'cn={},{}'.format(
            dn_escape_re.sub(hex_escape_match, group['name']),
            base_dn)

        norm_dn = normalize_string(dn)
        if norm_dn in seen:
            logger.warning('Duplicate DN: %s (%s)', dn, norm_dn)
            continue

        group['dn'] = dn
        yield group
        seen.add(norm_dn)


@time_call
def write_ldif(fh, config, groups):
    """
    Write groups to an LDIF file.
    """
    # Write the container object
    fh.write(entry_string(config.get_dn(), config.get_container_entry()))

    group_object_class = tuple(config.get('group_object_class',
                                          ('top', 'uioUntypedObject',)))
    # Write the group objects
    # TODO: Where to get objectClass from?
    for group in groups:
        dn = group['dn']
        entry = {
            'objectClass': group_object_class,
            'description': group['description'],
        }
        fh.write(entry_string(dn, entry))


@time_call
def write_json_cache(fh, members):
    """
    Write group memberships to a json cache file.

    :param file fh:
        An open cache file to write to

    :param dict members:
        A dict that maps members (person_id values) to groups (sets of group dn
        values)
    """
    data = {int(pid): sorted(tuple(dn_set))
            for pid, dn_set in members.items()}
    # Pretty format and sort by keys (person_id) - makes it easier to debug or
    # otherwise compare changes.
    json.dump(data, fh, indent=2, sort_keys=True)


@time_call
def write_pickle_cache(fh, members):
    """
    Write group memberships to a pickle cache file.

    :param file fh:
        An open cache file to write to

    :param dict members:
        A dict that maps members (person_id values) to groups (sets of group dn
        values)
    """
    data = {int(pid): sorted(tuple(dn_set))
            for pid, dn_set in members.items()}
    pickle.dump(data, fh, pickle.HIGHEST_PROTOCOL)


write_map = {
    'json': write_json_cache,
    'pickle': write_pickle_cache,
}


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Generate a basic group LDAP tree",
    )

    ldif_args = parser.add_argument_group(
        title='group ldif file',
        description='Generate an LDAP tree/LDIF file with basic group info',
    )
    ldif_args.add_argument(
        '--ldif-file',
        dest='ldif_file',
        help='Write groups to %(metavar)s',
        metavar='<filename>',
    )
    ldif_args.add_argument(
        '--ldif-max-change',
        dest='ldif_max_change',
        type=int,
        default=100,
        help=(
            'Set change limit to %(metavar)s%% for the ldif file'
            ' (default: %(default)s%%)'),
        metavar='<pct>',
    )

    cache_args = parser.add_argument_group(
        title='membership cache file',
        description='Generate a group membership cache file (for org-ldif)',
    )
    cache_args.add_argument(
        '--cache-file',
        dest='cache_file',
        help='Write group membership cache to %(metavar)s',
        metavar='<filename>',
    )
    cache_args.add_argument(
        '--cache-format',
        dest='cache_format',
        choices=sorted(tuple(write_map.keys())),
        default='json',
        help='use %(metavar)s for the cache file (default: %(default)s)',
        metavar='<format>',
    )
    cache_args.add_argument(
        '--account-to-person',
        dest='account_to_person',
        action='store_true',
        default=False,
        help='cache account memberships as person memberships',
    )
    cache_args.add_argument(
        '--indirect-members',
        dest='indirect_members',
        action='store_true',
        default=False,
        help='include recursive memberships for each group (expensive!)',
    )

    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    if not any((args.ldif_file, args.cache_file)):
        parser.error('Nothing to do (use --ldif-file/--cache-file)')

    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    const = Factory.get('Constants')(db)

    config = get_ldap_config(['LDAP', 'LDAP_GROUP'])
    logger.debug('config: %r', config)

    # We may want to make this value configurable?
    spread = const.spread_ldap_group
    logger.debug('spread: %r', spread)

    with timer('caching groups'):
        groups = sorted(tuple(populate_dn(config, get_groups(db, spread))),
                        key=operator.itemgetter('dn'))

    if args.ldif_file:
        ldif_fh = SimilarSizeWriter(args.ldif_file, 'w')
        ldif_fh.max_pct_change = args.ldif_max_change
        write_ldif(ldif_fh, config, groups)
    else:
        ldif_fh = None

    if args.cache_file:
        write_cache = write_map[args.cache_format]
        members = get_group_memberships(
            db, groups, spread,
            map_account_as_person=args.account_to_person,
            indirect_members=args.indirect_members,
        )
        cache_fh = AtomicFileWriter(args.cache_file, mode='wb')
        write_cache(cache_fh, members)
    else:
        cache_fh = None

    # We wait until the very end to close the files - if anything fails before
    # this point, we want to keep *both* of the originals - as they *should* be
    # 'in sync'.
    #
    # We close the ldif first, as this might fail on a similarsize check:
    if ldif_fh:
        ldif_fh.close()
        logger.info('Wrote LDAP groups to %s', args.ldif_file)

    if cache_fh:
        cache_fh.close()
        logger.info('Wrote %s membership cache to %s',
                    args.cache_format, args.cache_file)

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
