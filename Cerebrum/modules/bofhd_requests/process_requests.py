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

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio import AutoStud
from Cerebrum.modules.no.uio.AutoStud.Util import AutostudError
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import date_compat
from Cerebrum.utils import mappings


logger = logging.getLogger(__name__)
default_lockdir = getattr(cereconf, 'BOFHD_REQUEST_LOCK_DIR', None)


class NextAccount(Exception):
    pass


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
    Request processor.

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


class MoveStudentProcessor(object):

    def __init__(self, db, co, ou_perspective, emne_info_file, studconfig_file,
                 studieprogs_file, default_spread=None):
        self.db = db
        self.co = co
        self.br = BofhdRequests(self.db, self.co)
        self.default_spread = default_spread
        logger.debug("Preparing autostud framework")
        self.autostud = AutoStud.AutoStud(self.db, logger.getChild('autostud'),
                                          debug=False,
                                          cfg_file=studconfig_file,
                                          studieprogs_file=studieprogs_file,
                                          emne_info_file=emne_info_file,
                                          ou_perspective=ou_perspective)

    def process_requests(self, student_info_file):
        rows = self.br.get_requests(operation=self.co.bofh_move_student)
        if not rows:
            return

        # Set self.fnr2move_student
        self.set_fnr2move_student(rows)

        logger.debug("Starting callbacks to find: %s",
                     self.fnr2move_student)
        self.autostud.start_student_callbacks(student_info_file,
                                              self.move_student_callback)

        self.move_remaining_users()

    def move_remaining_users(self):
        # Move remaining users to pending disk
        disk = Factory.get('Disk')(self.db)
        disk.find_by_path(cereconf.AUTOSTUD_PENDING_DISK)
        logger.debug("fnr2move_student: %s",
                     str(self.fnr2move_student.values()))
        for tmp_stud in self.fnr2move_student.values():
            for account_id, request_id, requestee_id in tmp_stud:
                logger.debug("Sending %s to pending disk", repr(account_id))
                self.br.delete_request(request_id=request_id)
                self.br.add_request(
                    operator=requestee_id,
                    when=self.br.batch_time,
                    op_code=self.co.bofh_move_user,
                    entity_id=account_id,
                    destination_id=disk.entity_id,
                    state_data=int(self.default_spread),
                )
                self.db.commit()

    def set_fnr2move_student(self, rows):
        # Hent ut personens fodselsnummer + account_id
        self.fnr2move_student = {}
        account = Factory.get('Account')(self.db)
        person = Factory.get('Person')(self.db)
        for r in rows:
            if not is_valid_request(self.br, r['request_id']):
                continue
            account.clear()
            account.find(r['entity_id'])
            person.clear()
            person.find(account.owner_id)
            fnr = person.get_external_id(
                id_type=self.co.externalid_fodselsnr,
                source_system=self.co.system_fs
            )
            if not fnr:
                logger.warn("Not student fnr for: %d", account.entity_id)
                self.br.delete_request(request_id=r['request_id'])
                self.db.commit()
                continue
            fnr = fnr[0]['external_id']
            self.fnr2move_student.setdefault(fnr, []).append(
                (int(account.entity_id),
                 int(r['request_id']),
                 int(r['requestee_id'])))

    def move_student_callback(self, person_info):
        """
        We will only move the student if it has a valid fnr from FS,
        and it is not currently on a student disk.

        If the new homedir cannot be determined, user will be moved to a
        pending disk.  process_students moves users from this disk as soon
        as a proper disk can be determined.

        Currently we only operate on the disk whose spread is
        default_spread
        """
        fnr = "%06d%05d" % (int(person_info['fodselsdato']),
                            int(person_info['personnr']))
        logger.debug("Callback for %s", fnr)
        try:
            fodselsnr.personnr_ok(fnr)
        except Exception:
            logger.error("Unhandled exception in move_student_callback",
                         exc_info=True)
            return
        if fnr not in self.fnr2move_student:
            return
        account = Factory.get('Account')(self.db)
        group = Factory.get('Group')(self.db)
        for account_id, request_id, requestee_id in \
                self.fnr2move_student.get(fnr, []):
            account.clear()
            account.find(account_id)
            groups = list(int(x["group_id"]) for x in
                          group.search(member_id=account_id,
                                       indirect_members=False))
            try:
                profile = self.autostud.get_profile(person_info,
                                                    member_groups=groups)
                logger.debug(profile.matcher.debug_dump())
            except AutostudError as msg:
                logger.debug("Error getting profile, using pending: %s", msg)
                continue

            disks = self.determine_disks(account, request_id, profile, fnr)

            logger.debug("move_student_callback for: %s",
                         str((fnr, account_id, disks)))
            if disks:
                logger.debug("Destination %s", repr(disks))
                del (self.fnr2move_student[fnr])
                for disk, spread in disks:
                    self.br.delete_request(request_id=request_id)
                    self.br.add_request(
                        operator=requestee_id,
                        when=self.br.batch_time,
                        op_code=self.co.bofh_move_user,
                        entity_id=account_id,
                        destination_id=disk,
                        state_data=spread,
                    )
                    self.db.commit()

    def determine_disks(self, account, request_id, profile, fnr):
        disks = []
        spreads = [int(s) for s in profile.get_spreads()]
        try:
            for d_spread in profile.get_disk_spreads():
                if d_spread != self.default_spread:
                    # TBD:  How can all spreads be taken into account?
                    continue
                if d_spread in spreads:
                    try:
                        ah = account.get_home(d_spread)
                        homedir_id = ah['homedir_id']
                        current_disk_id = ah['disk_id']
                    except Errors.NotFoundError:
                        homedir_id, current_disk_id = None, None
                    if self.autostud.disk_tool.get_diskdef_by_diskid(
                            int(current_disk_id)):
                        logger.debug("Already on a student disk")
                        self.br.delete_request(request_id=request_id)
                        self.db.commit()
                        # actually, we remove a bit too much data from
                        # the below dict, but remaining data will be
                        # rebuilt on next run.
                        del (self.fnr2move_student[fnr])
                        raise NextAccount
                    try:
                        new_disk = profile.get_disk(d_spread,
                                                    current_disk_id,
                                                    do_check_move_ok=False)
                        if new_disk == current_disk_id:
                            continue
                        disks.append((new_disk, d_spread))
                        if (self.autostud.disk_tool.using_disk_kvote and
                                homedir_id is not None):
                            from Cerebrum.modules.disk_quota import DiskQuota
                            disk_quota_obj = DiskQuota(self.db)
                            try:
                                cur_quota = disk_quota_obj.get_quota(
                                    homedir_id)
                            except Errors.NotFoundError:
                                cur_quota = None
                            quota = profile.get_disk_kvote(new_disk)
                            if (cur_quota is None or
                                    cur_quota['quota'] != int(quota)):
                                disk_quota_obj.set_quota(homedir_id,
                                                         quota=int(quota))
                    except AutostudError as msg:
                        # Will end up on pending (since we only use one
                        # spread)
                        logger.debug("Error getting disk: %s", msg)
                        break
        except NextAccount:
            pass  # Stupid python don't have labeled breaks
        return disks
