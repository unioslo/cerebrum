#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2002, 2003 University of Oslo, Norway
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
This program adds accounts to groups. The program can
either read users and their groups from a text file, or from user input.
"""
from __future__ import print_function

import argparse
import logging

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import logutils
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)

group = []
current_group = None


def process_file(filename):
    fh = open(filename, 'r')
    for line in fh:
        line = line.strip()
        process_line(line)
    fh.close()


def process_line(line):
    global current_group
    if (line[0:3].isalpha()) and (line[3:5].isdigit()) and (len(line) == 6):
        add_user(line)
    elif len(line) > 0:
        current_group = line.strip()
        add_group(line)


def add_group(group_name):
    group_info = {'group_name': group_name, 'member': ''}
    group.append(group_info)


def add_user(user):
    for group_info in group:
        if group_info['group_name'] == current_group:
            group_info['member'] = "%s,%s" % (group_info['member'], user)


def print_all():
    for item in group:
        print(
            "group: %s has members:%s" % (item['group_name'], item['member'])
        )


#
# Parse group list. foreach group, add all members.
#
def add_user_to_group(db):
    person = Factory.get('Person')(db)
    account = Factory.get('Account')(db)
    const = Factory.get('Constants')(db)
    cere_group = Factory.get('Group')(db)

    for item in group:
        cere_group.clear()
        print("group is:%s" % item['group_name'].decode('utf-8'))
        cere_group.find_by_name(item['group_name'].decode('utf-8'))

        member_list = item['member'].split(',')
        for member in member_list:
            if len(member) > 0:
                try:
                    logger.info("processing account name:%s" % member)
                    account.clear()
                    account.find_by_name(member)
                    logger.info("\t account found")
                except Exception:
                    logger.error("Account %s not found" % (member,))
                    continue
                try:
                    person.clear()
                    person.find(account.owner_id)
                    logger.info("\t found person_id:%s" % person.entity_id)
                    if person.has_spread(const.spread_uit_ldap_person) == 0:
                        person.add_spread(const.spread_uit_ldap_person)
                except Errors.NotFoundError:
                    logger.error(
                        "\r unable to set person spread LDAP_person for "
                        "person:%s",
                        account.owner_id)
                    continue
                try:
                    retval = cere_group.has_member(account.entity_id)
                    print("retval:%s" % retval)
                    if retval is False:
                        cere_group.add_member(account.entity_id)
                        logger.info("adding account_id:%s to group id:%s",
                                    account.entity_id, cere_group.entity_id)
                    else:
                        logger.info(
                            "account_id:%s is already a member of group id:%s",
                            account.entity_id, cere_group.entity_id)
                except Exception:
                    logger.error(
                        "unable to add account_id:%s to group_id:%s",
                        account.entity_id, cere_group.entity_id)
                    logger.error("is account already a member of this group?")
                    db.rollback()
                    continue


def main(inargs=None):
    # Parse arguments
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-f',
                        '--file',
                        dest='input_file')
    parser.add_argument('-i',
                        '--input',
                        action='store_true')
    # Add args.commit and args.dryrun args
    add_commit_args(parser)

    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)

    # Initialize database and objects
    db = Factory.get('Database')()
    db.cl_init(change_program='groupadd')

    if not args.commit:
        logger.info("Dryrun. no changes to database")
    if not args.input and not args.input_file:
        parser.error(
            "You must specify either -f or -i to add/remove accounts to groups"
        )
    if args.input:
        input()
    if args.input_file:
        process_file(args.input_file)
        print_all()
        add_user_to_group(db)

    if args.commit:
        db.commit()
        logger.info("Committing changes to database")
    else:
        db.rollback()
        logger.info("Dryrun, rollback changes")


if __name__ == '__main__':
    main()
