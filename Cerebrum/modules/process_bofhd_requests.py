#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2003-2016 University of Oslo, Norway
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

import mx
import os
import time
import errno
import fcntl
import logging
from contextlib import closing

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio import AutoStud
from Cerebrum.modules.no.uio.AutoStud.Util import AutostudError


import cereconf

logger = logging.getLogger(__name__)


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
            lockfile = file(self.lockdir % reqid, "wb")
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


class OperationsMap(object):
    def __init__(self):
        self.operations_map = {}

    def __call__(self, *keys, **kwargs):
        """ Registers decorated function with the given keys.

        :param *list keys:
            A list of keys to add the decorated function to.

        :param **dict kwargs:
            A dict of additional information about the operation

        :return callable:
            Returns a function decorator.
        """
        def register(func):
            for key in keys:
                self.operations_map[key] = [func, kwargs]
            return func
        return register


class RequestProcessor(OperationsMap):
    def __init__(self, db, const, default_spread=None):
        super(RequestProcessor, self).__init__()
        self.db = db
        self.const = const
        self.default_spread = default_spread
        self.operations = {
            'quarantine':
                [const.bofh_quarantine_refresh],
            'delete':
                [const.bofh_archive_user,
                 const.bofh_delete_user],
            'move':
                [const.bofh_move_user_now,
                 const.bofh_move_user],
            'email':
                [const.bofh_email_create,
                 const.bofh_email_delete],
            'sympa':
                [const.bofh_sympa_create,
                 const.bofh_sympa_remove],
        }

    def process_requests(self, types, max_requests, *move_students_args):
        if 'move' in types:
            # Convert move_student requests into move_user requests
            self.process_move_student_requests(*move_students_args)
        with closing(RequestLockHandler()) as reqlock:
            br = BofhdRequests(self.db, self.const)
            for t in types:
                for op in self.operations[t]:
                    process = self.operations_map[op][0]
                    delay = self.operations_map[op][1].get('delay', 0)
                    self.set_operator()
                    start_time = time.time()
                    for r in br.get_requests(operation=op, only_runnable=True):
                        reqid = r['request_id']
                        logger.debug("Req: %s %d at %s, state %r",
                                     op, reqid, r['run_at'], r['state_data'])
                        if time.time() - start_time > 30 * 60:
                            break
                        if r['run_at'] > mx.DateTime.now():
                            continue
                        # Moving users only at ok times
                        if (op is self.const.bofh_move_user
                                and not self.is_ok_batch_time()):
                            break
                        if not self.is_valid_request(reqid):
                            continue
                        if reqlock.grab(reqid):
                            if max_requests <= 0:
                                break
                            max_requests -= 1
                            if process(r):
                                br.delete_request(request_id=reqid)
                                self.db.commit()
                            else:
                                self.db.rollback()
                                if delay:
                                    br.delay_request(reqid, minutes=delay)
                                    self.db.commit()

    @staticmethod
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

    def is_valid_request(self, req_id):
        # The request may have been canceled very recently
        br = BofhdRequests(self.db, self.const)
        for r in br.get_requests(request_id=req_id):
            return True
        return False

    def set_operator(self, entity_id=None):
        if entity_id:
            self.db.cl_init(change_by=entity_id)
        else:
            self.db.cl_init(change_program='process_bofhd_r')

    def process_move_student_requests(self, ou_perspective, emne_info_file,
                                      studconfig_file, studieprogs_file,
                                      student_info_file):
        br = BofhdRequests(self.db, self.const)
        rows = br.get_requests(operation=self.const.bofh_move_student)
        if not rows:
            return
        logger.debug("Preparing autostud framework")
        self.autostud = AutoStud.AutoStud(self.db, logger.getChild('autostud'),
                                          debug=False,
                                          cfg_file=studconfig_file,
                                          studieprogs_file=studieprogs_file,
                                          emne_info_file=emne_info_file,
                                          ou_perspective=ou_perspective)

        # Set self.fnr2move_student
        self.set_fnr2move_student(rows, br)

        logger.debug("Starting callbacks to find: %s" %
                     self.fnr2move_student)
        self.autostud.start_student_callbacks(student_info_file,
                                              self.move_student_callback)

        self.move_remaining_users(br)

    def move_remaining_users(self, br):
        # Move remaining users to pending disk
        disk = Factory.get('Disk')(self.db)
        disk.find_by_path(cereconf.AUTOSTUD_PENDING_DISK)
        logger.debug(str(self.fnr2move_student.values()))
        for tmp_stud in self.fnr2move_student.values():
            for account_id, request_id, requestee_id in tmp_stud:
                logger.debug("Sending %s to pending disk" % repr(account_id))
                br.delete_request(request_id=request_id)
                br.add_request(requestee_id, br.batch_time,
                               self.const.bofh_move_user,
                               account_id, disk.entity_id,
                               state_data=int(self.default_spread))
                self.db.commit()

    def set_fnr2move_student(self, rows, br):
        # Hent ut personens fodselsnummer + account_id
        self.fnr2move_student = {}
        account = Factory.get('Account')(self.db)
        person = Factory.get('Person')(self.db)
        for r in rows:
            if not self.is_valid_request(r['request_id']):
                continue
            account.clear()
            account.find(r['entity_id'])
            person.clear()
            person.find(account.owner_id)
            fnr = person.get_external_id(
                id_type=self.const.externalid_fodselsnr,
                source_system=self.const.system_fs
            )
            if not fnr:
                logger.warn("Not student fnr for: %i" % account.entity_id)
                br.delete_request(request_id=r['request_id'])
                self.db.commit()
                continue
            fnr = fnr[0]['external_id']
            self.fnr2move_student.setdefault(fnr, []).append(
                (int(account.entity_id),
                 int(r['request_id']),
                 int(r['requestee_id'])))

    def move_student_callback(self, person_info):
        """We will only move the student if it has a valid fnr from FS,
        and it is not currently on a student disk.

        If the new homedir cannot be determined, user will be moved to a
        pending disk.  process_students moves users from this disk as soon
        as a proper disk can be determined.

        Currently we only operate on the disk whose spread is
        default_spread"""

        fnr = "%06d%05d" % (int(person_info['fodselsdato']),
                            int(person_info['personnr']))
        logger.debug("Callback for %s" % fnr)
        try:
            fodselsnr.personnr_ok(fnr)
        except Exception, e:
            logger.exception(e)
            return
        if fnr not in self.fnr2move_student:
            return
        account = Factory.get('Account')(self.db)
        group = Factory.get('Group')(self.db)
        br = BofhdRequests(self.db, self.const)
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
            except AutostudError, msg:
                logger.debug("Error getting profile, using pending: %s" % msg)
                continue

            # Determine disk
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
                            br.delete_request(request_id=request_id)
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
                                from Cerebrum.modules.no.uio import DiskQuota
                                disk_quota_obj = DiskQuota.DiskQuota(self.db)
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
                        except AutostudError, msg:
                            # Will end up on pending (since we only use one
                            # spread)
                            logger.debug("Error getting disk: %s" % msg)
                            break
            except NextAccount:
                pass  # Stupid python don't have labeled breaks
            logger.debug(str((fnr, account_id, disks)))
            if disks:
                logger.debug("Destination %s" % repr(disks))
                del (self.fnr2move_student[fnr])
                for disk, spread in disks:
                    br.delete_request(request_id=request_id)
                    br.add_request(requestee_id, br.batch_time,
                                   self.const.bofh_move_user,
                                   account_id, disk, state_data=spread)
                    self.db.commit()


class NextAccount(Exception):
    pass



