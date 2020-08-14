#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2020 University of Oslo, Norway
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
Generate a group tree for LDAP.

This is a 'helper' script to add groups to an org-ldif script.  The idea is to:

1. Export groups with a given ldap spread to its own dn (typically
   "cn=groups,dc=<org>,dc=no") with basic information.
2. Export a group membership dict to a pickle-file.  This dict maps <person-id>
   to a list of group dn strings.
3. A separate org-ldif mixin (if present) reads the pickle file and adds group
   memberships to each exported person.
"""
from __future__ import unicode_literals

import argparse
import logging
import os
import cPickle as pickle  # noqa: N813

from collections import defaultdict

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import (
    container_entry_string,
    end_ldif_outfile,
    entry_string,
    ldapconf,
    ldif_outfile,
)

logger = logging.getLogger(__name__)


def dump_ldif(db, root_dn, file_handle):
    """
    Generate LDIF and return a dict of group memberships (person -> groups)
    """
    co = Factory.get('Constants')(db)
    group = Factory.get('Group')(db)

    # Generate the LDIF
    logger.debug('Processing groups...')
    group_to_dn = {}
    for row in group.search(spread=co.spread_ldap_group):
        dn = "cn={},{}".format(row['name'], root_dn)
        group_to_dn[row['group_id']] = dn
        file_handle.write(entry_string(
            dn,
            {
                'objectClass': ("top", "uioGroup"),
                'description': (row['description'],)
            }))

    logger.debug('Processing group memberships...')
    member_to_group = defaultdict(list)
    for row in group.search_members(spread=co.spread_ldap_group,
                                    member_type=co.entity_person):
        person_id = int(row['member_id'])
        member_to_group[person_id].append(group_to_dn[row['group_id']])

    return dict(member_to_group)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Generate a group tree for LDAP",
    )
    parser.add_argument(
        '--ldiffile',
        help='Write groups to the ldif-file %(metavar)',
        metavar='file',
    )
    parser.add_argument(
        '--picklefile',
        help='Write group memberships to the pickle-file %(metavar)s',
        metavar='file',
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    if not any((args.ldiffile, args.picklefile)):
        parser.error('Must use --ldiffile or --picklefile')

    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    ldiffile = args.ldiffile
    picklefile = args.picklefile

    db = Factory.get('Database')()
    dn = ldapconf('GROUP', 'dn')

    logger.info('Generating LDIF...')
    destfile = ldif_outfile('GROUP', ldiffile)
    destfile.write(container_entry_string('GROUP'))
    mbr2grp = dump_ldif(db, dn, destfile)
    end_ldif_outfile('GROUP', destfile)
    logger.info('Wrote LDIF to %r', ldiffile)

    logger.info('Generating pickle dump...')
    tmpfname = picklefile + '.tmp'
    pickle.dump(mbr2grp, open(tmpfname, 'wb'), pickle.HIGHEST_PROTOCOL)
    os.rename(tmpfname, picklefile)
    logger.info('Wrote pickle file to %r', picklefile)

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
