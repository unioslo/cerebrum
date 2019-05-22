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
from __future__ import unicode_literals

import argparse
import json
import logging
import time

import cereconf
import Cerebrum.logutils

from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler


logger = logging.getLogger(__name__)

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
clco = Factory.get('CLConstants')(db)
entity = Entity.Entity(db)
entityname = Entity.EntityName(db)
account = Factory.get('Account')(db)
cl = CLHandler.CLHandler(db)


def pwd_wipe(changes, age_threshold, commit):
    global cl

    now = time.time()

    for chg in changes:
        changed = False
        age = now - chg['tstamp'].ticks()
        if age > age_threshold:
            logger.debug('Password will be wiped: %s', str(chg['change_id']))
            change_params = json.loads(chg['change_params'])
            if wipe_pw(chg['change_id'], change_params, commit):
                changed = True
        else:
            logger.debug('Password will not be wiped (too recent): %s' + str(
                chg['change_id']))

        if changed:
            cl.confirm_event(chg)
    if commit:
        logger.info('Committing changes')
        cl.commit_confirmations()
    else:
        logger.info('Changes not committed (dryrun)')


def wipe_pw(change_id, pw_params, commit):
    global cl

    if pw_params.has_key('password'):
        del (pw_params['password'])
        if commit:
            db.update_log_event(change_id, pw_params)
            logger.debug("Wiped password for change_id=%i" % change_id)
            return True
        else:
            return False
    else:
        return True


def main():

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
        dest='max_changes',
        default=cereconf.PWD_MAX_WIPES,
        help='Maximum number of passwords to wipe. Default is {0}'.format(
            cereconf.PWD_MAX_WIPES))
    parser.add_argument(
        '-a',
        '-age_threshold',
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
        logger.error("Empty changelog tracker! This would go through the "
                     "entire change-log. No way! Quitting!")
        return

    changes = cl.get_events(args.changelog_tracker, (clco.account_password,))
    num_changes = len(changes)

    if num_changes == 0:
        logger.info("No passwords to wipe!")
        return
    elif num_changes > args.max_changes:
        logger.error("Too many changes (%s)! Check if changelog tracker "
                     "(%s) is correct, or override limit in command-line "
                     "or cereconf", num_changes, args.changelog_tracker)
        return

    logger.info("Starting to wipe %s password changes since last wipe",
                num_changes)
    pwd_wipe(changes, args.age_threshold, args.commit)
    logger.info("Finished wiping passwords")


if __name__ == '__main__':
    main()
