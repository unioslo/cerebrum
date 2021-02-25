#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2014 University of Oslo, Norway
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

"""Populate memberships in «employee»-ish groups depending on affiliation."""

from __future__ import unicode_literals

import sys

import six
import logging
import argparse

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum import Errors


logger = logging.getLogger(__name__)


def populate_group_memberships(db, gname, affiliations):
    """Add and remove accounts from the group."""
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    gr = Factory.get('Group')(db)

    logger.info('Populating memberships in %s with %s as criteria',
                gname, six.text_type(affiliations))

    # Verify group existence
    try:
        gr.find_by_name(gname)
    except Errors.NotFoundError:
        logger.error('Group %s does noe exist! Aborting…', gname)
        sys.exit(1)

    members = set()
    # Look up affiliations
    for aff in affiliations:
        ss = None
        # Parse affiliations and source system
        if ':' in aff:
            ss, aff = aff.split(':')
            tmp_ss = co.human2constant(ss)
            if not tmp_ss:
                logger.error('Source system %s is unknown! Aborting…', ss)
                sys.exit(3)
            else:
                ss = tmp_ss

        # Verify that affiliation exists
        tmp_aff = co.human2constant(aff)
        if not tmp_aff:
            logger.error('Affiliation %s is unknown! Aborting…', aff)
            sys.exit(4)
        else:
            aff = tmp_aff

        # Define common arguments
        args = {'source_system': ss,
                'ret_primary_acc': True}

        # Verify correct affiliation type and store appropriatly in arguments.
        if isinstance(aff, co.PersonAffiliation):
            args['affiliation'] = aff
        elif isinstance(aff, co.PersonAffStatus):
            args['status'] = aff
        else:
            logger.error('Wrong affiliation type for %s! Aborting…', str(aff))

        # Fetch the members that should be in the group
        logger.info('Collecting candidates for %s:%s', str(ss), str(aff))
        for person in pe.list_affiliations(**args):
            # The person_id here, is acctually the account_id :S
            members.add(person['person_id'])

    # Fetch exisiting members
    existing_members = set([x['member_id'] for x in
                            gr.search_members(group_id=gr.entity_id)])

    # Calculate whom to remove
    to_remove = existing_members - members

    # calculate whom to add
    to_add = (existing_members & members) ^ members

    logger.info('Removing %d from %s', len(to_remove), gname)
    for x in to_remove:
        gr.remove_member(x)

    logger.info('Adding %d to %s', len(to_add), gname)
    for x in to_add:
        gr.add_member(x)

    logger.info('Finished populating %s', gname)


description ="""
Populate memberships in «employee»-ish groups depending on affiliation.
"""

epilog = """
See cereconf.COLLECTION_GROUPS in default_config for configuration
guidelines and more info.

The following is copy-pasta from default_config. Might be out of date,
so check default_config!

Groups who has memberships populated by contrib/populate-collection-groups.py
E.g. [('uio-tilk', ['system_sap:affiliation_tilknyttet',
                    'system_fs:affiliation_student',
                    'affiliation_tilknyttet_bilag'])]
Will result in the group 'uio-tilk' beeing filled with primary accounts who
have TILKNYTTET affiliations from SAP, STUDENT-affiliations from FS and
TILKNYTTET/bilag from all source systems.

The groups you specify in this configuration, must be created BEFORE
populate-collection-groups.py is run!!!
"""

def main(inargs=None):
    """Arg parsing and handling."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=description,
        epilog=epilog)

    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    """Setting up logger and db."""
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get("Database")()
    db.cl_init(change_program=sys.argv[0].split('/')[-1])

    logger.info('Starting to populate collection groups')

    for gname, affs in cereconf.COLLECTION_GROUPS:
        populate_group_memberships(db, gname, affs)

    if args.commit:
        db.commit()
        logger.info("Committed all changes")
    else:
        db.rollback()
        logger.info("Rolled back all changes")

if __name__ == "__main__":
    main()
