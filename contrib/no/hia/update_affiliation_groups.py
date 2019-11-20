#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2017 University of Oslo, Norway
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

import sys
import getopt

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors

# Initialize logger
logger = Factory.get_logger('cronjob')

# Initialize database connections
db = Factory.get('Database')()
ac = Factory.get('Account')(db)
pe = Factory.get('Person')(db)
gr = Factory.get('Group')(db)

db.cl_init(change_program="update_affiliation_groups.py")


def usage(exitcode=0):
    print """Usage:
    %s [Options]

    Update group memberships for primary accounts based on affiliations.

    Options:
    -l, --list                      List affiliations.
    -d, --dryrun                    Don't commit changes to Cerebrum db.
    -a, --affmap    <aff:group>     Specify mappings between affs and groups.
                                    "ANSATT:ansattgroup STUDENT:studentgroup"
    """ % sys.argv[0]
    sys.exit(exitcode)


def list_affs():
    """
    List person affiliations.
    """
    affiliations = pe.list_person_affiliation_codes()
    for a in affiliations:
        print "%s: %s (%s)" % (str(int(a['code'])),
                               a['code_str'],
                               a['description'])


def update_aff_groups(aff_groups, dryrun):
    # get all affiliations and aff ids
    affs = {}
    for a in pe.list_person_affiliation_codes():
        affs[a['code_str']] = int(a['code'])

    # for each aff:group...
    for affiliation, group in aff_groups.items():

        # valid affiliation?
        if affiliation not in affs:
            logger.error("Affiliation not found (%s)." % affiliation)
            return

        gr.clear()
        try:
            # valid group?
            gr.find_by_name(group)
        except Errors.NotFoundError:
            logger.error("Group not found (%s)." % group)
            return

        # get all persons with this affiliation
        pe.clear()
        persons = pe.list_affiliations(affiliation=affs[affiliation])

        # get each person's primary account
        #####
        # The current solution is classic brute force. An API change would
        # be more elegant, e.g. expanding Person or Account (search or
        # list_affiliations). Account.list_accounts_by_type may serve as an
        # example.
        #####
        primary_accounts = set()
        for person in persons:
            ac.clear()
            account = ac.list_accounts_by_type(person_id=person['person_id'],
                                               primary_only=True)
            if account:
                primary_accounts.add(int(account[0]['account_id']))

        # get all entity_ids in target group
        group_members = set()
        for member in list(gr.search_members(group_id=gr.entity_id)):
            group_members.add(int(member['member_id']))

        # accounts that should be added to the group
        to_be_added = primary_accounts - group_members

        # accounts that should be removed from the group
        to_be_removed = group_members - primary_accounts

        # remove accounts from group
        for account in to_be_removed:
            try:
                gr.remove_member(account)
                gr.write_db()
                logger.debug("Removed %s from %s." % (str(account), group))
            except Errors.DatabaseError, e:
                logger.error("Failed removing %s from %s: %s" %
                             (str(account), group, e))
        if not dryrun:
            try:
                gr.commit()
            except Errors.DatabaseError, e:
                logger.error("Commit of removed group members failed: %s" % e)
        else:
            db.rollback()

        # add accounts to group
        for account in to_be_added:
            try:
                gr.add_member(account)
                gr.write_db()
                logger.debug("Added %s to %s." % (str(account), group))
            except Errors.DatabaseError, e:
                logger.error("Failed adding %s to %s: %s" %
                             (str(account), group, e))
        if not dryrun:
            try:
                gr.commit()
            except Errors.DatabaseError, e:
                logger.error("Commit of added group members failed: %s" % e)
        else:
            db.rollback()


def main():

    dryrun = False
    aff_groups = None

    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'lda:',
                                   ['list', 'dryrun', 'affs='])
    except getopt.GetoptError, e:
        logger.error(e)
        usage(1)

    for opt, val in opts:
        if opt in ('-l', '--list'):
            list_affs()
            sys.exit(0)
        if opt in ('-d', '--dryrun'):
            dryrun = True
        if opt in ('-a', '--affs'):
            aff_groups = {}
            tempaffs = val.split(" ")
            for t in tempaffs:
                a = t.split(":")
                aff_groups[a[0]] = a[1]
            logger.info('Start update of affiliation groups.')
            update_aff_groups(aff_groups, dryrun)
            logger.info('End update of affiliation groups.')

    if aff_groups is None:
        if len(cereconf.AFFILIATION_GROUPS) < 1:
            logger.error("No affiliations/grops defined.")
            usage(1)
        else:
            logger.info('Start update of affiliation groups.')
            update_aff_groups(cereconf.AFFILIATION_GROUPS, dryrun)
            logger.info('End update of affiliation groups.')


if __name__ == '__main__':
    sys.exit(main())
