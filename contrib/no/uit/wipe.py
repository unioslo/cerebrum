#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2023 University of Oslo, Norway
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
Wipe passwords from the changelog
"""

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import json
import logging

import cereconf
import Cerebrum.logutils

from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import date_compat


logger = logging.getLogger(__name__)


def pwd_wipe(db, cl, changes, age_threshold, commit):
    """Remove password older than a threshold from the changelog."""
    # Cutoff datetime: Only process changes older than this
    threshold = date_utils.now() - date_compat.get_timedelta(age_threshold)

    for chg in changes:
        tstamp = date_compat.get_datetime_tz(chg['tstamp'])
        changed = False
        if tstamp < threshold:
            logger.debug('Password will be wiped: %s', chg['change_id'])
            change_params = json.loads(chg['change_params'])
            if wipe_pw(db, chg['change_id'], change_params, commit):
                changed = True
        else:
            logger.debug('Password will not be wiped (too recent): %s',
                         chg['change_id'])

        if changed:
            cl.confirm_event(chg)
    if commit:
        logger.info('Committing changes')
        cl.commit_confirmations()
    else:
        logger.info('Changes not committed (dryrun)')


def wipe_pw(db, change_id, pw_params, commit):
    """Remove password from a changelog item."""
    if 'password' in pw_params:
        del (pw_params['password'])
        if commit:
            db.update_log_event(change_id, pw_params)
            logger.debug("Wiped password for change_id=%i", change_id)
            return True
        else:
            return False
    else:
        return True


def main():
    db = Factory.get('Database')()
    clco = Factory.get('CLConstants')(db)
    cl = CLHandler.CLHandler(db)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-t',
        '--changelog_tracker',
        dest='changelog_tracker',
        default=cereconf.PWD_WIPE_EVENT_HANDLER_KEY,
        help='Event handler key to monitor for changes. Default is {0}'.format(
            cereconf.PWD_WIPE_EVENT_HANDLER_KEY))
    parser.add_argument(
        '-m',
        '--max_changes',
        type=int,
        dest='max_changes',
        default=cereconf.PWD_MAX_WIPES,
        help='Maximum number of passwords to wipe. Default is {0}'.format(
            cereconf.PWD_MAX_WIPES))
    parser.add_argument(
        '-a',
        '-age_threshold',
        type=int,
        dest='age_threshold',
        default=cereconf.PWD_AGE_THRESHOLD,
        help='how old passwords need to be before they are wiped. ' +
             'Default is {0}'.format(cereconf.PWD_AGE_THRESHOLD))
    parser.add_argument(
        '-c',
        '--commit',
        dest='commit',
        action='store_true',
        help='Write changes to database')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    if not args.changelog_tracker:
        # TODO: We should *not* exit with a success code here!  This is (most
        # likely) an invalid input argument - replace with parser.error() +
        # message to stderr
        logger.error("Empty changelog tracker! This would go through the "
                     "entire change-log. No way! Quitting!")
        return

    changes = cl.get_events(args.changelog_tracker, (clco.account_password,))
    num_changes = len(changes)

    if num_changes == 0:
        logger.info("No passwords to wipe!")
        return
    elif num_changes > args.max_changes:
        # TODO: We should *not* exit with a success code here!  Replace with
        # an unhandled exception.
        logger.error("Too many changes (%s)! Check if changelog tracker "
                     "(%s) is correct, or override limit in command-line "
                     "or cereconf", num_changes, args.changelog_tracker)
        return

    logger.info("Starting to wipe %s password changes since last wipe",
                num_changes)
    pwd_wipe(db, cl, changes, args.age_threshold, args.commit)
    logger.info("Finished wiping passwords")


if __name__ == '__main__':
    main()
