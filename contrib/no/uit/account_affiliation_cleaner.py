#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2019 University of Oslo, Norway
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
This script will clean out all account affiliations (account types) that
have no root in reality*.

*) The account owner has no corresponding person affiliation
"""
from __future__ import unicode_literals

import argparse
import logging

from Cerebrum import logutils
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args


logger = logging.getLogger(__name__)


def clean_acc_affs(db):
    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)

    # List over all active person affiliations
    logger.info("Building list over person affiliations...")
    per_affs = pe.list_affiliations()
    affs = []
    for per_aff in per_affs:
        affs.append(
            (per_aff['person_id'], per_aff['ou_id'], per_aff['affiliation']))

    # List all accounts (also closed ones!)
    logger.info(
        "Deleting account affiliations with no corresponding person "
        "affiliation...")
    ac_list = ac.list(filter_expired=False)
    for a in ac_list:
        ac.clear()
        ac.find(a['account_id'])

        # Get account affiliations
        acc_affs = ac.get_account_types(filter_expired=False)
        num_acc_affs = len(acc_affs)

        # Cycle affiliations
        num_deleted = 0
        for acc_aff in acc_affs:

            aux = (
                acc_aff['person_id'], acc_aff['ou_id'],
                acc_aff['affiliation'])

            # If affiliation not in person affiliations at all - DELETE!
            # Do not delete the last account_type. process_students is unable
            # to reactivate accounts that doesnt have a single account_type
            #
            if aux not in affs:
                if num_deleted + 1 == num_acc_affs:
                    pass

                else:
                    num_deleted += 1
                    logger.info(
                        'Deleting affiliation %s on ou %s for account %s',
                        acc_aff['affiliation'], acc_aff['ou_id'],
                        a['account_id'])
                    ac.del_account_type(acc_aff['ou_id'],
                                        acc_aff['affiliation'])

    logger.info("Done verifying account affiliations.")


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser = add_commit_args(parser, default=False)

    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()
    db.cl_init(change_program='account_affiliation_cleaner')

    clean_acc_affs(db)

    if args.commit:
        db.commit()
        logger.info("Committed all changes")
    else:
        db.rollback()
        logger.info("Dryrun, rolled back changes")


if __name__ == '__main__':
    main()
