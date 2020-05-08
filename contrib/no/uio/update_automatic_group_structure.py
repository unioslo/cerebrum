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
"""Update automatic groups so that they reflect the OU-structure of an
organization

This script affects two kinds of automatic groups:

1. regular automatic groups:
    The names of these groups are on the form <aff_or_role>-<stedkode>. They
    typically contain persons/accounts with some kind of affiliation or role
    at the organizational unit. This script does NOT do anything to maintain
    the memberships in these groups.

2. meta groups:
    The names of these groups are on the form meta-<aff_or_role>-<stedkode>.
    They should only contain regular automatic groups which are at the unit
    itself or under the organizational unit in the OU-hierarchy.

Here is an example of an OU-structure at an organization and the resulting
group-structure from running this script:

    OU-structure (-> indicates parent-child relationship):

        (stedkode 320000) ----+->(stedkode 325000)+->(stedkode 325100)
                              |
                              +->(stedkode 321000)+->(stedkode 321003)
                                                  |
                                                  +->(stedkode 321001)

    Group-structure (-> indicates group-member relationship):

        (meta-adm-leder-320000)----+->(adm-leder-320000)
                                   |
                                   +->(adm-leder-325000)
                                   |
                                   +->(adm-leder-325100)
                                   |
                                   +->(adm-leder-321000)
                                   |
                                   +->(adm-leder-321003)
                                   |
                                   +->(adm-leder-321001)

        (meta-adm-leder-325000)----+->(adm-leder-325000)
                                   |
                                   +->(adm-leder-325100)

        (meta-adm-leder-321000)----+->(adm-leder-321000)
                                   |
                                   +->(adm-leder-321003)
                                   |
                                   +->(adm-leder-321001)

Note:
    The main difference between this script and 'populate-automatic-groups.py'
    is that this script does not add members to the regular automatic groups.
    This means that it generates generates groups for all non-quarantined
    OUs at run time, whether those OUs have anyone affiliated to them or not.
    'populate-automatic-groups.py' on the other hand does not generate groups
    for OUs where no persons are currently affiliated.
"""
from __future__ import unicode_literals
import logging
import argparse
import six
import datetime

from Cerebrum import logutils
from Cerebrum.Utils import Factory
from Cerebrum.modules.automatic_group.structure import (
    get_automatic_group,
    meta_group_members,
    update_members,
    cache_stedkoder,
    get_current_members,
    get_automatic_group_ids
)
from Cerebrum.utils.argutils import add_commit_args, get_constant

logger = logging.getLogger(__name__)


def process_prefix(db, ou, gr, co, prefix, perspective, ou_id2sko):
    logger.info('Processing prefix: %s', prefix)
    meta_prefix = 'meta-' + prefix
    logger.info('Caching initial groups: %s*', meta_prefix)
    initial_meta_groups = set(get_automatic_group_ids(gr, co, meta_prefix))
    meta_groups = process_meta_groups(db,
                                      ou,
                                      gr,
                                      prefix,
                                      meta_prefix,
                                      perspective,
                                      ou_id2sko)
    logger.info('Expire redundant groups: %s*, %s*', prefix, meta_prefix)
    expire_redundant_groups(gr, meta_groups, initial_meta_groups)
    logger.info('Now got %s %s* groups', len(meta_groups), meta_prefix)


def process_meta_groups(db, ou, gr, prefix, meta_prefix, perspective,
                        ou_id2sko):
    meta_groups = {}
    logger.info('Caching members for %s*', meta_prefix)
    for ou_id, stedkode in six.iteritems(ou_id2sko):
        group = get_automatic_group(db,
                                    stedkode,
                                    meta_prefix)
        logger.info('Processing group: %s', group.group_name)
        meta_groups[group.entity_id] = set(
            meta_group_members(db, ou, ou_id, perspective, prefix, ou_id2sko)
        )

    for group_id, wanted_members in six.iteritems(meta_groups):
        logger.info('Group: %s, needs members: %s', group_id, wanted_members)
        current_members = set(get_current_members(gr, group_id))
        update_members(gr, group_id, current_members, wanted_members)

    return meta_groups


def expire_redundant_groups(gr, meta_groups, initial_meta_groups):
    today = datetime.date.today()
    meta_groups = set(meta_groups)
    for group_id in initial_meta_groups.difference(meta_groups):
        gr.clear()
        gr.find(group_id)
        logger.info('Expire meta group: %s', gr.group_name)
        gr.expire_date = today
        gr.write_db()
        # We deduce that if we deleted meta-<prefix>-<stedkode> we should also
        # delete <prefix>-<stedkode>.
        group_name = gr.group_name[5:]
        gr.clear()
        gr.find_by_name(group_name)
        logger.info('Expire non-meta group: %s', group_name)
        gr.expire_date = today
        gr.write_db()


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--perspective',
        type=six.text_type,
        help='Set the system perspective to fetch the OU structure from, '
             'e.g. SAP or FS.',
        required=True
    )
    parser.add_argument(
        '--prefix',
        type=six.text_type,
        action='append',
        default=[],
        help='Prefix for the automatic groups this script creates',
        required=True
    )
    add_commit_args(parser)

    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)
    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)
    co = Factory.get('Constants')(db)

    perspective = get_constant(db, parser, co.OUPerspective, args.perspective)
    ou = Factory.get('OU')(db)
    gr = Factory.get('Group')(db)

    logger.info('Caching OUs')
    ou_id2sko = cache_stedkoder(ou)
    for prefix in args.prefix:
        process_prefix(db, ou, gr, co, prefix, perspective, ou_id2sko)

    if args.commit:
        logger.info('Committing changes')
        db.commit()
    else:
        logger.info('Rolling back changes')
        db.rollback()
    logger.info('Done with %s', parser.prog)


if __name__ == '__main__':
    main()
