#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2004-2019 University of Oslo, Norway
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

# kbj005 2015.02.24: Copied from Leetah.

"""
This program exports BAS username changes to an file.

This script is a UiT specific export script for keeping track of changes in
usernames.
"""

from __future__ import unicode_literals

import argparse
import datetime
import logging
import os.path

import cereconf
import Cerebrum.logutils

from Cerebrum.Utils import Factory
from Cerebrum.modules.legacy_users import LegacyUsers


logger = logging.getLogger(__name__)


def find_username_changes(db):
    """Find changed usernames."""
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)
    lu = LegacyUsers(db)

    # Get all legacy info
    legacy = lu.search()

    export = []
    fnr2leg = {}
    for row in legacy:
        user_name = row['user_name']
        comment = row['comment']
        ssn = row['ssn']

        old = user_name
        new = None
        date = ""

        comment_parts = None
        if comment:
            comment_parts = comment.split()

        # comment = 'YYYYMMDD - Duplicate of NEW'
        if comment and " - Duplicate of " in comment:
            new = comment_parts[4]
            date = comment_parts[0]

        # comment = 'YYYYMMDD - Renamed from OLD to NEW.'
        elif comment and " - Renamed from " in comment:
            new = comment_parts[6].strip(".")
            date = comment_parts[0]

        # comment = 'Renamed from OLD to NEW.'
        elif comment and comment.startswith("Renamed from "):
            new = comment_parts[4].strip(".")

        # comment = 'This username is reserved. It is a duplicate of '
        elif (comment and "This username is reserved. It is a duplicate of " in
              comment):
            new = comment_parts[9].split(",")[0]

        # comment = 'Duplicate of NEW' (manuelt inntastet)
        elif comment and comment.upper().startswith(
                "DUPLICATE OF "):
            new = comment_parts[2].strip(".,")

        # comment = 'duplikat av NEW' (manuelt inntastet)
        elif comment and comment.upper().startswith(
                "DUPLIKAT AV "):
            new = comment_parts[2].strip(",.")

        # comment = 'duplikat ac ' (feiltasting)
        elif comment and comment.startswith('duplikat ac '):
            new = comment_parts[2]

        # Accumulating FNRs to see if I can sort them out later
        elif ssn and user_name[3:5] != '99':
            ssn_list = fnr2leg.get(ssn)
            if ssn_list is None:
                ssn_list = []
            ssn_list.append(old)
            fnr2leg[ssn] = ssn_list
        else:
            logger.warn("Legacy info not processed: %s", row)
            continue

        if old and new and old[3:5] != '99' and new[3:5] != '99':
            export.append("{0};{1};{2}\n".format(old, new, date))

    # Going through accumulated FNRs to see if I can do some more mapping
    const_fnr = co.externalid_fodselsnr

    # Get all accounts
    owner2acc = {}
    for row in ac.search(expire_start='19000101'):
        owner2acc[row['owner_id']] = row['name']

    # Map FNR 2 account
    fnr2acc = {}
    for row in pe.search_external_ids(id_type=const_fnr):
        try:
            fnr2acc[row['external_id']] = owner2acc[row['entity_id']]
        except KeyError:
            logger.warn("Person has no account: %s", row['entity_id'])
            pass

    for fnr in fnr2leg.keys():
        fnr = fnr.strip()
        if fnr in fnr2acc:
            for acc in fnr2leg[fnr]:
                if acc != fnr2acc[fnr] and '999' not in fnr2acc[fnr]:
                    export.append("{0};{1};\n".format(acc, fnr2acc[fnr]))

    return export


def generate_export(export, file_name):
    """Write the export file to disk."""
    with open(file_name, 'w') as fp:
        fp.writelines(export)


def main():
    date = datetime.datetime.today()
    date_today = date.strftime("%Y%m%d")
    default_export_file = os.path.join(cereconf.DUMPDIR,
                                       'username_changes',
                                       'username_changes_{0}'.format(
                                           date_today))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-f',
                        '--file',
                        dest='export_file',
                        default=default_export_file,
                        help='export file')
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of username changes export')
    db = Factory.get('Database')()
    export = find_username_changes(db)
    generate_export(export, args.export_file)
    logger.info('End of username changes export')


if __name__ == '__main__':
    main()
