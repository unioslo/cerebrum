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
    # TODO: unicode_literals,
)
import errno
import fcntl
import logging
import os
import time
from contextlib import closing

import six

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import date_compat
from Cerebrum.utils import mappings
from Cerebrum.utils import reprutils


logger = logging.getLogger(__name__)
default_lockdir = getattr(cereconf, 'BOFHD_REQUEST_LOCK_DIR', None)


def is_ok_batch_time():
    now = time.strftime("%H:%M")
    times = cereconf.LEGAL_BATCH_MOVE_TIMES.split('-')
    if times[0] > times[1]:  # Like '20:00-08:00'
        if now > times[0] or now < times[1]:
            return True
    else:  # Like '08:00-20:00'
        if times[0] < now < times[1]:
            return True
    return False


def is_valid_request(br, req_id):
    # The request may have been canceled very recently
    for r in br.get_requests(request_id=req_id):
        return True
    return False


def set_operator(db, entity_id=None):
    if entity_id:
        db.cl_init(change_by=entity_id)
    else:
        db.cl_init(change_program='process_bofhd_r')


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
        if self.lockfd is not None:
            fcntl.flock(self.lockfd, fcntl.LOCK_UN)
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


class OperationsMap(mappings.SimpleMap):
    """
    A dict for mapping one or more keys to a function and settings

    Example:
    ::

        handlers = OperationsMap()

        @handlers("br_move_user", delay=3)
        def move_user(request):
            # ...
            pass

        @handlers("br_move_user_now", delay=0)
        def move_user_now(request):
            # ...
            pass

        processor = RequestProcessor(...)
        processor.process_requests(handlers, ("move",), ...)
        6)
    """

    def __call__(self, *keys, **settings):
        """
        Registers decorated function with the given keys.

        :param *list keys:
            A list of operations / keys to use the decorated function for.

        :param **dict settings:
            Settings to be used by RequestProcessor.

            See the chosen request processor for valid settings.  Invalid
            settings are usually ignored.

        :return callable:
            Returns a function decorator.
        """
        def register(func):
            value = [func, settings]
            for key in keys:
                self.set(key, value)
            return func
        return register


class RequestProcessor(object):
    """
    Legacy request processor.

    Note: :meth:`.process_requests` calls commit/rollback on the
    database object given to this object!
    """

    def __init__(self, db, co):
        super(RequestProcessor, self).__init__()
        self.db = db
        self.co = co
        self.op_type_map = {
            'quarantine':
                [co.bofh_quarantine_refresh],
            'delete':
                [co.bofh_archive_user,
                 co.bofh_delete_user],
            'move':
                [co.bofh_move_user_now,
                 co.bofh_move_user],
            'email':
                [co.bofh_email_create,
                 co.bofh_email_delete],
            'sympa':
                [co.bofh_sympa_create,
                 co.bofh_sympa_remove],
        }

    def process_requests(self, operations_map, op_types, max_requests):
        max_runtime = date_utils.to_seconds(minutes=30)
        with closing(RequestLockHandler()) as reqlock:
            br = BofhdRequests(self.db, self.co)
            for t in op_types:
                logger.info("Processing operation type %r", t)
                for op in self.op_type_map[t]:
                    op_key = six.text_type(op)
                    logger.info("Processing operation %r (%r)", op_key, op)
                    if op_key not in operations_map:
                        logger.info('Unable to process operation %r (%r)',
                                    op_key, op)
                        continue
                    func, settings = operations_map[op_key]
                    delay = settings.get('delay', 0)
                    set_operator(self.db)
                    start_time = time.time()
                    for r in br.get_requests(operation=op, only_runnable=True):
                        reqid = r['request_id']
                        logger.debug("Req: %s %d at %s, state %r",
                                     op_key, reqid, r['run_at'],
                                     r['state_data'])
                        if (time.time() - start_time) > max_runtime:
                            break
                        run_at = date_compat.get_datetime_tz(r['run_at'])
                        if run_at and run_at > date_utils.now():
                            continue
                        # Moving users only at ok times
                        if (op == self.co.bofh_move_user
                                and not is_ok_batch_time()):
                            break
                        if not is_valid_request(br, reqid):
                            continue
                        if reqlock.grab(reqid):
                            if max_requests <= 0:
                                break
                            max_requests -= 1
                            if func(self.db, r):
                                br.delete_request(request_id=reqid)
                                self.db.commit()
                            else:
                                self.db.rollback()
                                if delay:
                                    br.delay_request(reqid, minutes=delay)
                                    self.db.commit()
