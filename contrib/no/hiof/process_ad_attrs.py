#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2006, 2008 University of Oslo, Norway
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


import argparse
import sys
import getopt
import time

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hiof.bofhd_hiof_cmds import HiofBofhdRequests


logger = Factory.get_logger("cronjob")

db = Factory.get('Database')()
const = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
br = HiofBofhdRequests(db, const)
max_requests = 999999
start_time = time.time()


def process_requests(dryrun):
    """
    Process all bofhd requests of type bofh_ad_attrs_remove. Try to
    remove ad attributes given by user and spread. If ad attrs are
    deleted successfully, remove the request.
    """
    op = const.bofh_ad_attrs_remove
    for r in br.get_requests(operation=op, only_runnable=True):
        if not is_valid_request(r['request_id']):
            continue
        if not keep_running():
            break
        logger.debug("Process req: %s %d at %s",
                     op, r['request_id'], r['run_at'])
        set_operator(r['requestee_id'])
        if r['state_data']:
            spread = const.Spread(r['state_data'])
        else:
            spread = None
        if delete_ad_attrs(r['entity_id'], spread):
            br.delete_request(request_id=r['request_id'])

    if dryrun:
        logger.info("Rolling back all changes")
        db.rollback()
    else:
        logger.info("Committing all changes")
        db.commit()


def delete_ad_attrs(entity_id, spread):
    # Find account and delete ad attrs
    ret = False
    ac.clear()
    try:
        ac.find(entity_id)
        ac.delete_ad_attrs(spread)
        ac.write_db()
        ret = True
        logger.info("Deleted ad attrs for %s" % ac.account_name)
    except Errors.NotFoundError:
        logger.error("Unknown account %s" % ac.account_name)
    return ret


def is_valid_request(req_id):
    # The request may have been canceled very recently
    br = HiofBofhdRequests(db, const)
    for r in br.get_requests(request_id=req_id):
        return True
    return False


def keep_running():
    # If we've run for more than half an hour, it's time to go on to
    # the next task.  This check is necessary since job_runner is
    # single-threaded, and so this job will block LDAP updates
    # etc. while it is running.
    global max_requests, start_time
    max_requests -= 1
    if max_requests < 0:
        return False
    return time.time() - start_time < 15 * 60


def set_operator(entity_id=None):
    if entity_id:
        db.cl_init(change_by=entity_id)
    else:
        db.cl_init(change_program='process_ad_attrs')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dryrun",
                        help="Dryrun mode",
                        action='store_true',
                        default=False,
    )
    parser.add_argument("--delete",
                        help="find bofhd requests and delete ad attrs",
                        action='store_true',
                        default=False,
    )
    args = parser.parse_args()

    if args.delete:
        process_requests(args.dryrun)


def usage(exitcode=0):
    print """Usage: process_ad_attrs.py
    --dryrun: dryrun mode
    --delete: find bofhd requests and delete ad attrs
    """
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
