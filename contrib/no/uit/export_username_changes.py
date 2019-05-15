#!/usr/bin/python
# -*- coding: iso8859-1 -*-
#
# Copyright 2004 University of Oslo, Norway
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
This script is a UiT specific export script for keeping track of changes in usernames
"""

import getopt
import os.path
import sys
import time

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.legacy_users import LegacyUsers

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
pe = Factory.get('Person')(db)
logger_name = cereconf.DEFAULT_LOGGER_TARGET
lu = LegacyUsers(db)

date = time.localtime()
date_today = "%02d%02d%02d" % (date[0], date[1], date[2])
default_export_file = os.path.join(cereconf.DUMPDIR, 'username_changes',
                                   'username_changes_%s' % date_today)


def usage():
    print """This program exports BAS username changes to an file

    Usage: [options]
    -f | --file : export file
    -l | --logger-name : name of logger target
    -h | --help : this text """
    sys.exit(1)


def main():
    global logger, logger_name

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'l:f:h',
                                   ['file=', 'logger-name', 'help'])
    except getopt.GetoptError:
        usage()

    export_file = default_export_file

    help = 0
    for opt, val in opts:
        if opt in ('-f', '--file'):
            export_file = val
        if opt in ('-l', '--logger-name'):
            logger_name = val
        if opt in ('-h', '--help'):
            usage()

    logger = Factory.get_logger(logger_name)

    # Get all legacy info
    legacy = lu.search()

    export = []
    fnr2leg = {}
    for row in legacy:

        old = None
        new = None
        date = ""

        user_name = row.get('user_name')
        comment = row.get('comment')
        ssn = row.get('ssn')

        # comment = 'YYYYMMDD - Duplicate of NEW'
        if comment is not None and " - Duplicate of " in comment:
            comment_parts = comment.split()
            old = user_name
            new = comment_parts[4]
            date = comment_parts[0]

        # comment = 'YYYYMMDD - Renamed from OLD to NEW.'
        elif comment is not None and " - Renamed from " in comment:
            comment_parts = comment.split()
            old = user_name
            new = comment_parts[6].strip(".")
            date = comment_parts[0]

        # comment = 'Renamed from OLD to NEW.'
        elif comment is not None and comment.startswith("Renamed from "):
            comment_parts = comment.split()
            old = user_name
            new = comment_parts[4].strip(".")

        # comment = 'This username is reserved. It is a duplicate of '
        elif comment is not None and "This username is reserved. It is a duplicate of " in comment:
            comment_parts = comment.split()
            old = user_name
            new = comment_parts[9].split(",")[0]

        # comment = 'Duplicate of NEW' (manuelt inntastet)
        elif comment is not None and comment.upper().startswith(
                "DUPLICATE OF "):
            comment_parts = comment.split()
            old = user_name
            new = comment_parts[2].strip(".,")

        # comment = 'duplikat av NEW' (manuelt inntastet)
        elif comment is not None and comment.upper().startswith(
                "DUPLIKAT AV "):
            comment_parts = comment.split()
            old = user_name
            new = comment_parts[2].strip(",.")

        # comment = 'duplikat ac ' (feiltasting)
        elif comment is not None and comment.startswith('duplikat ac '):
            comment_parts = comment.split()
            old = user_name
            new = comment_parts[2]

        # Accumulating FNRs to see if I can sort them out later
        elif ssn is not None and user_name[3:5] != '99':

            old = user_name

            ssn_list = fnr2leg.get(ssn)
            if ssn_list is None:
                ssn_list = []
            ssn_list.append(old)
            fnr2leg[ssn] = ssn_list


        else:
            logger.warn("Legacy info not processed: %s" % (row))
            continue

        if old is not None and new is not None and old[3:5] != '99' and new[
                                                                        3:5] != '99':
            export.append("%s;%s;%s\n" % (old, new, date))

    # Going through accumulated FNRs to see if I can do some more mapping
    const_fnr = co.externalid_fodselsnr

    # Get all accounts
    owner2acc = {}
    for row in ac.search(expire_start='19000101'):
        owner2acc[row['owner_id']] = row['name']

    # Map FNR 2 account
    fnr2acc = {}
    for row in pe.list_external_ids(id_type=const_fnr):
        try:
            fnr2acc[row['external_id']] = owner2acc[row['entity_id']]
        except:
            logger.warn("Person has no account: %s" % row['entity_id'])
            pass

    for fnr in fnr2leg.keys():
        fnr = fnr.strip()
        if fnr in fnr2acc:
            for acc in fnr2leg[fnr]:
                if acc != fnr2acc[fnr] and '999' not in fnr2acc[fnr]:
                    export.append("%s;%s;\n" % (acc, fnr2acc[fnr]))

    fh = open(export_file, 'w')
    fh.writelines(export)
    fh.close()


if __name__ == '__main__':
    main()
