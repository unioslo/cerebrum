#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2005-2024 University of Oslo, Norway
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
""" Export groups. """
import argparse
import os
import sys

from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import AtomicFileWriter


DEFAULT_OUTFILE = os.path.join(
    sys.prefix, 'var', 'cache', 'EZPublish', 'groups.txt')


def make_groups_list(flat, grps):
    """
    :param bool flat:
        Whether to flatten out group memberships.

    :type grps: iterable
    :param grps:
        An iterable of groups to list.

        Each group is a result row from `Group.search()` or compatible
        dict-like object, and must include a 'group_id' and 'name'.

    :return dict:
        A mapping from group names to a string of member names (','-separated).
    """
    entity2name = dict((x["entity_id"], x["entity_name"]) for x in
                       group.list_names(constants.account_namespace))
    entity2name.update((x["entity_id"], x["entity_name"]) for x in
                       group.list_names(constants.group_namespace))
    members = {}
    if flat:
        for i in grps:
            group.clear()
            group.find(i["group_id"])
            tmp = group.search_members(group_id=group.entity_id,
                                       indirect_members=True,
                                       member_type=constants.entity_account)
            tmp = set([int(x["member_id"]) for x in tmp])
            members[i["name"]] = ','.join(entity2name[x]
                                          for x in tmp
                                          if x in entity2name)
    else:
        for i in grps:
            group.clear()
            group.find(i["group_id"])
            # collect the members of group that have names
            member_names = [entity2name.get(int(x["member_id"])) for x in
                            group.search_members(group_id=group.entity_id)
                            if int(x["member_id"]) in entity2name]
            members[i["name"]] = ','.join(member_names)
    return members


def main():
    global group, constants

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-s', '--spread',
        required=True,
        help="choose all groups with given spread")
    parser.add_argument(
        '-o', '--outfile',
        default=DEFAULT_OUTFILE,
        help="override default file name (%(default)s)")
    parser.add_argument(
        '-f', '--flat',
        default=False,
        action='store_true',
        help=("flatten out groups (find all account-members of groups and "
              "their groupmembers)"))
    args = parser.parse_args()

    logger = Factory.get_logger('cronjob')
    db = Factory.get('Database')()
    constants = Factory.get('Constants')(db)
    group = Factory.get("Group")(db)

    spread = int(constants.Spread(args.spread))

    with AtomicFileWriter(args.outfile, 'w') as stream:

        logger.info("Getting groups")
        grps = group.search(spread=spread)

        logger.info("Processing groups")
        groups_and_members = make_groups_list(args.flat, grps)

        logger.info("Writing groups file.")
        for k, v in iter(groups_and_members.items()):
            stream.write(k + ';' + v)
            stream.write(u'\n')
    logger.info("All done.")


if __name__ == '__main__':
    main()
