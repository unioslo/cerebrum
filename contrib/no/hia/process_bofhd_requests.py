#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2003-2017 University of Oslo, Norway
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

import errno
import fcntl
import getopt
import mx
import os
import pickle
import sys
import time
from contextlib import closing

import cereconf

from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.Utils import Factory, spawn_and_log_output
from Cerebrum.modules.bofhd.utils import BofhdRequests


logger = Factory.get_logger("bofhd_req")
db = Factory.get('Database')()
db.cl_init(change_program='process_bofhd_r')
cl_const = Factory.get('CLConstants')(db)
const = Factory.get('Constants')(db)

max_requests = 999999

EXIT_SUCCESS = 0


class RequestLocked(Exception):
    pass


class RequestLockHandler(object):
    def __init__(self, lockdir=None):
        """lockdir should be a template holding exactly one %d."""
        if lockdir is None:
            lockdir = cereconf.BOFHD_REQUEST_LOCK_DIR
        self.lockdir = lockdir
        self.lockfd = None

    def grab(self, reqid):
        """Release the old lock if one is held, then grab the lock
        corresponding to reqid.  Returns False if it fails.

        """
        if self.lockfd is not None:
            self.close()

        self.reqid = reqid
        try:
            lockfile = file(self.lockdir % reqid, "w")
        except IOError, e:
            logger.error("Checking lock for %d failed: %s", reqid, e)
            return False
        try:
            fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError, e:
            if e.errno == errno.EAGAIN:
                logger.debug("Skipping locked request %d", reqid)
            else:
                logger.error("Locking request %d failed: %s", reqid, e)
            return False
        self.lockfd = lockfile
        return True

    def close(self):
        """Release and clean up lock."""
        if self.lockfd is not None:
            fcntl.flock(self.lockfd, fcntl.LOCK_UN)
            # There's a potential race here (someone else can grab and
            # release this lock before the unlink), but users of this
            # class should remove the request from the todo list
            # before releasing the lock.
            os.unlink(self.lockdir % self.reqid)
            self.lockfd = None


def dependency_pending(dep_id, local_db=db, local_co=const):
    if not dep_id:
        return False
    br = BofhdRequests(local_db, local_co)
    for dr in br.get_requests(request_id=dep_id):
        logger.debug("waiting for request %d" % int(dep_id))
        return True
    return False


def process_requests(types):
    global max_requests

    operations = {
        'sympa':
        [(const.bofh_sympa_create, proc_sympa_create, 2*60),
         (const.bofh_sympa_remove, proc_sympa_remove, 2*60)],
        }
    """Each type (or category) of requests consists of a list of which
    requests to process.  The tuples are operation, processing function,
    and how long to delay the request (in minutes) if the function returns
    False.

    """

    # TODO: There is no variable containing the default log directory
    # in cereconf

    with closing(RequestLockHandler()) as reqlock:
        br = BofhdRequests(db, const)
        for t in types:
            for op, process, delay in operations[t]:
                set_operator()
                start_time = time.time()
                for r in br.get_requests(operation=op, only_runnable=True):
                    reqid = r['request_id']
                    logger.debug("Req: %s %d at %s, state %r",
                                 op, reqid, r['run_at'], r['state_data'])
                    if time.time() - start_time > 30 * 60:
                        break
                    if r['run_at'] > mx.DateTime.now():
                        continue
                    if not is_valid_request(reqid):
                        continue
                    if reqlock.grab(reqid):
                        if max_requests <= 0:
                            break
                        max_requests -= 1
                        if process(r):
                            br.delete_request(request_id=reqid)
                            db.commit()
                        else:
                            db.rollback()
                            if delay:
                                br.delay_request(reqid, minutes=delay)
                                db.commit()


def proc_sympa_create(request):
    """Execute the request for creating a sympa mailing list.

    @type request: ??
    @param request:
      An object describing the sympa list creation request.
    """

    try:
        listname = get_address(request["entity_id"])
    except Errors.NotFoundError:
        logger.warn("Sympa list address %s is deleted! No need to create",
                    listname)
        return True

    try:
        state = pickle.loads(str(request["state_data"]))
    except:
        logger.exception("Corrupt request state for sympa list=%s: %s",
                         listname, request["state_data"])
        return True

    try:
        host = state["runhost"]
        profile = state["profile"]
        description = state["description"]
        admins = state["admins"]
        admins = ",".join(admins)
    except KeyError:
        logger.error("No host/profile/description specified for sympa list %s",
                     listname)
        return True

    # 2008-08-01 IVR FIXME: Safe quote everything fished out from state.
    cmd = [cereconf.SYMPA_SCRIPT, host, 'newlist',
           listname, admins, profile, description]
    return spawn_and_log_output(cmd) == EXIT_SUCCESS
# end proc_sympa_create


def proc_sympa_remove(request):
    """Execute the request for removing a sympa mailing list.

    @type request: ??
    @param request:
      A dict-like object containing all the parameters for sympa list
      removal.
    """

    try:
        state = pickle.loads(str(request["state_data"]))
    except:
        logger.exception("Corrupt request state for sympa request %s: %s",
                         request["request_id"], request["state_data"])
        return True

    try:
        listname = state["listname"]
        host = state["run_host"]
    except KeyError:
        logger.error("No listname/runhost specified for request %s",
                     request["request_id"])
        return True

    cmd = [cereconf.SYMPA_SCRIPT, host, 'rmlist', listname]
    return spawn_and_log_output(cmd) == EXIT_SUCCESS
# end proc_sympa_remove


def get_address(address_id):
    ea = Email.EmailAddress(db)
    ea.find(address_id)
    ed = Email.EmailDomain(db)
    ed.find(ea.email_addr_domain_id)
    return "%s@%s" % (ea.email_addr_local_part,
                      ed.rewrite_special_domains(ed.email_domain_name))


def is_ok_batch_time(now):
    times = cereconf.LEGAL_BATCH_MOVE_TIMES.split('-')
    if times[0] > times[1]:
        #  Like '20:00-08:00'
        if now > times[0] or now < times[1]:
            return True
    else:
        #  Like '08:00-20:00'
        if now > times[0] and now < times[1]:
            return True
    return False


def set_operator(entity_id=None):
    if entity_id:
        db.cl_init(change_by=entity_id)
    else:
        db.cl_init(change_program='process_bofhd_r')


def is_valid_request(req_id, local_db=db, local_co=const):
    # The request may have been canceled very recently
    br = BofhdRequests(local_db, local_co)
    for r in br.get_requests(request_id=req_id):
        return True
    return False


def main():
    global max_requests
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dpt:m:',
                                   ['debug', 'process', 'type=', 'max=', ])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)
    types = []
    for opt, val in opts:
        if opt in ('-d', '--debug'):
            print "debug mode has not been implemented"
            sys.exit(1)
        elif opt in ('-t', '--type',):
            types.append(val)
        elif opt in ('-m', '--max',):
            max_requests = int(val)
        elif opt in ('-p', '--process'):
            if not types:
                types = ['quarantine', 'delete', 'move',
                         'email', 'sympa', ]
            process_requests(types)


def usage(exitcode=0):
    print """Usage: process_bofhd_requests.py
    -d | --debug: turn on debugging
    -p | --process: perform the queued operations
    -t | --type type: performe queued operations of this type.  May be
         repeated, and must precede -p
    -m | --max val: perform up to this number of requests

    Legal values for --type:
      sympa

    """
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
