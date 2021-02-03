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
Create and update ORG-ERA groups from job assignment data.

This script is a proof-of-concept for creating groups based on job assignment
data from our HR system.
"""
from __future__ import unicode_literals

import argparse
import datetime
import logging
import operator

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.Utils import Factory

from Cerebrum.modules.no.orgera import job_groups


logger = logging.getLogger(__name__)


def get_account_by_name(db, username):
    ac = Factory.get('Account')(db)
    ac.find_by_name(username)
    return ac


def _assert_group(db, creator, group_type, visibility, group_name,
                  description, expire_date=None):
    """ TODO: replace with group-tree builder. """
    group = Factory.get('Group')(db)

    try:
        group.find_by_name(group_name)
    except Errors.NotFoundError:
        group.populate(
            name=group_name,
            group_type=group_type,
            visibility=visibility,
            creator_id=creator.entity_id,
            description=description,
            expire_date=expire_date,
        )
        group.write_db()
        logger.info('created group %s (%d)',
                    group.group_name, group.entity_id)
    else:
        if any((
                description != group.description,
                group_type != group.group_type,
                visibility != group.visibility,
                expire_date != group.expire_date,
        )):
            group.description = description
            group.group_type = group_type
            group.visibility = visibility
            group.expire_date = expire_date
            group.write_db()
            logger.info('updated group %s (%d)',
                        group.group_name, group.entity_id)
        else:
            logger.debug('found group %s (%d)',
                         group.group_name, group.entity_id)

    return group


def deactivate_group(db, group_id, expire_date):
    """ Get rid of ORG-ERA assignment group. """
    group = Factory.get('Group')(db)
    group.find(group_id)
    sync_group(db, group, set())
    if group.expire_date and group.expire_date < expire_date:
        # already expired
        return

    group.expire_date = expire_date
    group.write_db()
    logger.info('group %r (%s) disabled', group.group_name, group.entity_id)


def sync_group(db, group, members):
    current = set(r['member_id']
                  for r in group.search_members(group_id=int(group.entity_id)))
    to_remove = set(current) - set(members)
    to_add = set(members) - set(current)

    for member_id in to_remove:
        group.remove_member(member_id)
    for member_id in to_add:
        group.add_member(member_id)

    logger.info('group %r (%s) synced, %d added, %d removed',
                group.group_name, group.entity_id, len(to_add), len(to_remove))


def update_groups(db, templates):
    """ Update all org-era assignment groups. """
    creator = get_account_by_name(db, cereconf.INITIAL_ACCOUNTNAME)

    gr = Factory.get('Group')(db)
    co = Factory.get('Constants')(db)

    visibility = co.group_visibility_all
    group_type = co.group_type_orgera_assignment
    expire_date = datetime.date.today()

    to_remove = {row['group_id']: row['name']
                 for row in gr.search(group_type=group_type)}

    for group_name, template in templates:
        logger.info('processing group %r', group_name)

        group = _assert_group(db, creator, group_type, visibility, group_name,
                              job_groups.format_description(template))

        logger.debug('applying template=%r for group=%r', template, group_name)

        members = job_groups.find_members(db, template)
        logger.debug('found %d members for group=%r',
                     len(members), group.entity_id)

        sync_group(db, group, members)
        to_remove.pop(group.entity_id, None)

    logger.info('Found %d defunct groups', len(to_remove))
    for group_id, group_name in to_remove.items():
        logger.info('clearing group %r (%d)', group_name, group_id)
        deactivate_group(db, group_id, expire_date)


group_templates = {
    # 'org-era-seniors-at-usit': {
    #     # All 1180 @ usit or children
    #     'ou': 'sko:350000',
    #     'sko': (1181, 1182),
    #     'recursion': {
    #         'perspective': 'SAP',
    #         'include': 'children',
    #     },
    # },
    # 'org-era-librarians': {
    #     'styrk': (3493102,),
    # },
    # 'org-era-352100-any-1210128-parents': {
    #     # All 1210128 @ usitint or parents
    #     'ou': 'sko:352100',
    #     'styrk': (1210128,),
    #     'recursion': {
    #         'perspective': 'SAP',
    #         'include': 'parents',
    #     },
    # },
    # 'org-era-150000-1065-any-children': {
    #     'ou': 'sko:150000',
    #     'sko': (1065,),
    #     'recursion': {
    #         'perspective': 'SAP',
    #         'include': 'children',
    #     },
    # },
}


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Sync org-era groups',
    )
    Cerebrum.logutils.options.install_subparser(parser)
    add_commit_args(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    # Validate our templates first:
    templates = sorted(
        [(gn, job_groups.GroupTemplate.from_dict(tpl))
         for gn, tpl in group_templates.items()],
        key=operator.itemgetter(0))

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)

    update_groups(db, templates)

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        logger.info('Rolling back changes (dryrun)')
        db.rollback()

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
