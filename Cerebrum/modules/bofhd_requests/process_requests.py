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
Utils to process requests.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import errno
import fcntl
import logging
import os
import time
from contextlib import closing

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.utils import date_compat
from Cerebrum.utils import reprutils


logger = logging.getLogger(__name__)
default_lockdir = getattr(cereconf, 'BOFHD_REQUEST_LOCK_DIR', None)


def is_ok_batch_time():
    now = time.strftime("%H:%M")
    times = cereconf.LEGAL_BATCH_MOVE_TIMES.split('-')
    if times[0] > times[1]:
        # E.g. '20:00-08:00'
        return now > times[0] or now < times[1]
    else:
        # E.g.'08:00-20:00'
        return times[0] < now < times[1]


def is_valid_request(br, req_id):
    # The request may have been canceled very recently
    for r in br.get_requests(request_id=req_id):
        return True
    return False


class RequestLockHandler(object):
    """
    Create and lock a lockfile.
    """

    def __init__(self, lockdir=default_lockdir):
        """
        :param str lockdir:
            File path of request lock files.

            Should be a template holding exactly one %d (to be replaced with
            the request id). E.g.: "/var/run/br/request-%d.lock"
        """
        self.lockdir = lockdir
        self.lockfd = None

    def grab(self, reqid):
        """
        Grab lock file for a given request-id.

        Release the old lock if one is held, then grab the lock
        corresponding to reqid.  Returns False if it fails.
        """
        if self.lockfd is not None:
            self.close()

        self.reqid = reqid
        try:
            lockfile = open(self.lockdir % reqid, "wb")
        except IOError as e:
            logger.error("Checking lock for %d failed: %s", reqid, e)
            return False
        try:
            fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError as e:
            if e.errno == errno.EAGAIN:
                logger.debug("Skipping locked request %d", reqid)
            else:
                logger.error("Locking request %d failed: %s", reqid, e)
            return False
        self.lockfd = lockfile
        return True

    def close(self):
        """ Release and clean up lock. """
        if self.lockfd is None:
            return
        fcntl.flock(self.lockfd, fcntl.LOCK_UN)
        self.lockfd.close()
        # There's a potential race here (someone else can grab and
        # release this lock before the unlink), but users of this
        # class should remove the request from the todo list
        # before releasing the lock.
        os.unlink(self.lockdir % self.reqid)
        self.lockfd = None


class SimpleRequestProcessor(reprutils.ReprFieldMixin):
    """
    Simple bofhd request processor.

    This request processor handles a single operation type and callback, and
    leaves operation type management to the caller.
    """
    repr_id = False
    repr_module = False
    repr_fields = ("dryrun",)

    def __init__(self, db, dryrun=True):
        self.db = db
        self.co = Factory.get("Constants")(db)
        self.br = BofhdRequests(self.db, self.co)
        self.dryrun = dryrun

    def _on_success(self, request_id, request):
        self.br.delete_request(request_id=request_id)
        if not self.dryrun:
            self.db.commit()

    def _on_failure(self, request_id, request, delay=0):
        if not self.dryrun:
            self.db.rollback()
        if delay:
            self.br.delay_request(request_id, minutes=(delay // 60))
            if not self.dryrun:
                self.db.commit()

    def __call__(self, op_type, callback, delay=0, max_requests=0):
        """
        :param op_type:
            bofhd request operation type to process

        :param callback:
            Callback to run for each request.

            The callback should accept 2 positional arguments, and an arbitrary
            number of keyword arguments:

                callback(database, request_dict, dryrun=None, **kwargs)

        :param int delay:
            an optional delay (in seconds) to postpone failed requests

        :param int limit:
            an optional max_requests limit
        """
        counter = 0
        logger.debug("%s(%s, %s, delay=%d, max_requests=%d)",
                     repr(self), op_type, repr(callback), delay, max_requests)
        for r in self.br.get_requests(operation=op_type, only_runnable=True):
            request_id = r['request_id']
            run_at = date_compat.get_datetime_tz(r['run_at'])
            logger.debug("processing request: id=%d, run_at=%s, state=%s",
                         request_id, run_at, repr(r['state_data']))
            if not is_valid_request(self.br, request_id):
                # In non-dryrun mode, this loop will re-start our
                # transaction again and again, which means our list of
                # requests may be out-of-date
                logger.warning("request id=%d gone", request_id)
                continue

            with closing(RequestLockHandler()) as reqlock:
                if not reqlock.grab(request_id):
                    continue
                logger.debug("request id=%s, type=%s callback=%s start",
                             request_id, op_type, repr(callback))
                counter += 1
                if callback(self.db, dict(r), dryrun=self.dryrun):
                    self._on_success(request_id, r)
                    logger.info("request id=%s, type=%s processed",
                                request_id, op_type)
                else:
                    self._on_failure(request_id, r)
                    logger.warning("request id=%s, type=%s failed",
                                   request_id, op_type)

            if max_requests and counter >= max_requests:
                logger.warning("abort: processed %d requests", counter)
                break
