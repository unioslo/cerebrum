# -*- coding: utf-8 -*-
#
# Copyright 2004-2026 University of Oslo, Norway
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
Script to move student user accounts to an appropriate homedir.

*move student* is a request to *calculate* an appropriate target disk according
to the *studconf.xml* config file, and current FS student data.

This script is really a ``process_bofhd_requets.py`` pre-processor script.  It
only translates *move student* bofhd requests into regular *move* requests.

The only reason this uses bofhd-requests and has its own script, is to
encapsulate all the complex logic required to calculate a disk for student
accounts, as this requires a series of up-to-date cache files from FS.

Configuration
==============
*studconf.xml*
    Student profile configuration file.  Used along with the *FS import files*
    to select a target disk for *move student* requests.

``cereconf.AUTOSTUD_PENDING_DISK``
    Sets the default disk to use for requests where the account owner does not
    appear to be a student according to *studconf.xml* and FS import files.

TODO
====
This script has a lot of weird, legacy behaviour.  A lot of it is probably
bugs, but those bugs might be considered features now, given their age.

Possible improvements:

1. Don't actually process requests in the AutoStud callbacks - just build a
   cache of disk(s) to use, and maybe requests to ignore.  I.e.:

   - A mapping of (account_id -> [(disk, spread), ...]).  Any move student
     request for an account in this set, with an actual list, should be moved
     to the given disk(s).

   - A set of account ids to *ignore*.  These would be accounts that are
     already *on* a student disk, and shouln't be moved

2. Remove the multi-homedir support.  We don't actually use or support it
   anyway, so just accept *one* disk from the user/student profile, the one
   using *default spread*.

History
========
This used to be implemented in ``contrib/no/uio/process_bofhd_requests.py``.

The main functionality was gathered in a MoveStudentProcessor class, and moved
to :mod:`Cerebrum.modules.bofhd_requests` in a major bofhd-requests refactor.

In an attempt to completely isolate the special *move student* request
requirements and complexities, it was moved out of the ``bofhd_requests``
module and back into this script.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.modules.disk_quota import DiskQuota
from Cerebrum.modules.no.uio import AutoStud
from Cerebrum.modules.no.uio.AutoStud.Util import AutostudError
from Cerebrum.utils import argutils


logger = logging.getLogger(__name__)


class _NextAccount(Exception):
    pass


def _get_account_by_id(db, account_id):
    ac = Factory.get("Account")(db)
    ac.find(int(account_id))
    return ac


def _get_owner_fnr(account):
    if account.owner_type != account.const.entity_person:
        return None
    pe = Factory.get("Person")(account._db)
    pe.find(int(account.owner_id))
    fnr_results = list(
        row['external_id']
        for row in pe.get_external_id(
            id_type=int(pe.const.externalid_fodselsnr),
            source_system=int(pe.const.system_fs)
        )
    )
    if not fnr_results:
        return None
    return fnr_results[0]


class MoveStudentProcessor(object):

    def __init__(self, db, co, autostud, default_spread=None):
        """
        Process move student requests.

        :param db:
        :param co:
        :param autostud: A configured AutoStud.AutoStud object
        :param default_spread: default homedir/disk spread
        :param bool dryrun:
        """
        self.db = db
        self.co = co
        self.gr = Factory.get("Group")(db)
        self.br = BofhdRequests(db, co)
        self.autostud = autostud
        self.default_spread = default_spread

    def _list_requests(self):
        """ list all move student requests """
        return list(self.br.get_requests(operation=self.co.bofh_move_student))

    def _delete_request(self, request_id):
        """ remove request by id """
        self.br.delete_request(request_id=int(request_id))
        logger.info("Removed request id=%s", repr(request_id))

    def _add_request(self, operator, account_id, disk_id, disk_spread):
        """ add a new move request """
        req_id = self.br.add_request(
            operator=int(operator),
            when=self.br.batch_time,
            op_code=int(self.co.bofh_move_user),
            entity_id=int(account_id),
            destination_id=int(disk_id),
            state_data=int(disk_spread),
        )
        logger.info("Added move request id=%d for account id=%s",
                    req_id, repr(account_id))

    def _get_memberships(self, account):
        """ get group ids of all account memberships. """
        return set(
            int(row["group_id"])
            for row in self.gr.search(member_id=int(account.entity_id),
                                      indirect_members=False)
        )

    def _build_queue(self, rows):
        """ Group move student reqeusts by student fnr. """
        mapping = {}

        for row in rows:
            try:
                account = _get_account_by_id(self.db, row['entity_id'])
            except Errors.NotFoundError:
                logger.warning("no account id=%r", repr(row['entity_id']))
                self._delete_request(row['request_id'])
                continue

            fnr = _get_owner_fnr(account)
            if not fnr:
                # TODO: Move awau from using fnr as a *primary key* when
                # processing students
                logger.warning("No fnr (primary key) for account id=%d",
                               account.entity_id)
                self._delete_request(row['request_id'])
                continue

            mapping.setdefault(fnr, []).append((
                int(account.entity_id),
                int(row['request_id']),
                int(row['requestee_id']),
            ))
        return mapping

    def process_requests(self, person_file):
        """
        Process move student requests.

        :param str person_file:
            A file with all current persons from FS (e.g. merged_persons.xml)
        """
        requests = self._list_requests()
        logger.debug("Found %d requests", len(requests))

        if not requests:
            logger.info("No pending move student requests")
            return

        self.fnr2move_student = self._build_queue(requests)
        logger.info("Found move student requests for %d persons",
                    len(self.fnr2move_student))

        logger.debug("Processing requests for current students")
        self.autostud.start_student_callbacks(
            person_file,
            self.move_student_callback,
        )

        self.move_remaining_users()

    def move_student_callback(self, person_info):
        """
        Move student callback for AutoStud.

        This callback runs for every active student according to the given
        input file, and processes any current *move student* request that
        exists for this person.

        Currently we only operate on the disk whose spread is *default_spread*.

        :param dict person_info: person/student data from AutoStud
        """
        fnr = "%06d%05d" % (int(person_info['fodselsdato']),
                            int(person_info['personnr']))

        if fnr not in self.fnr2move_student:
            # nothing to do here
            return

        def _clear_fnr(fnr):
            # remove all requests for the given fnr from our processing queue
            #
            # TODO: Shouldn't we really only remove the specific request_id
            # from the list of reqeusts?  Some of the odd flow control in this
            # script stems from the fact that we de-queue *all* requests for a
            # given person here.
            if fnr in self.fnr2move_student:
                del self.fnr2move_student[fnr]

        for account_id, request_id, operator in self.fnr2move_student[fnr]:
            logger.debug("Processing request id=%d for account id=%d",
                         request_id, account_id)
            account = _get_account_by_id(self.db, account_id)
            memberships = self._get_memberships(account)
            try:
                profile = self.autostud.get_profile(person_info,
                                                    member_groups=memberships)
                self.autostud._logger.debug(profile.matcher.debug_dump())
            except AutostudError as msg:
                logger.warning("No profile for account id=%d (%s)",
                               account_id, msg)
                continue

            try:
                disks = self.determine_disks(account, request_id, profile, fnr)
            except _NextAccount:
                # determine_disks decided that this move shouldn't happen - the
                # homedir is already on the correct disk.
                _clear_fnr(fnr)
                self._delete_request(request_id)
                continue

            if not disks:
                logger.info("No appropriate disks for account id=%d",
                            account_id)
                continue

            # We have to delete the *move-student* request before adding a
            # *move* request - as they are considered to be conflicing.
            _clear_fnr(fnr)
            self._delete_request(request_id)

            # TODO: Don't think this will *actually* work if we expand
            # `determine_disks()` to return multiple (disk_id, disk_spread)
            # tuples.  `BofhdRequests` only allows *one* request of a given
            # op-type for a given entity.
            for disk_id, disk_spread in disks:
                self._add_request(
                    operator=operator,
                    account_id=account_id,
                    disk_id=disk_id,
                    disk_spread=disk_spread,
                )
                logger.info("Moving account id=%d to disk id=%d (spread=%d)",
                            account_id, disk_id, disk_spread)

    def _update_quota(self, profile, new_disk, homedir_id):
        """ Update homedir quota according profile. """
        if not self.autostud.disk_tool.using_disk_kvote:
            return
        if homedir_id is None:
            return
        disk_quota_obj = DiskQuota(self.db)
        try:
            cur_quota = disk_quota_obj.get_quota(homedir_id)
        except Errors.NotFoundError:
            cur_quota = None
        quota = profile.get_disk_kvote(new_disk)
        if (cur_quota is None or
                cur_quota['quota'] != int(quota)):
            disk_quota_obj.set_quota(homedir_id, quota=int(quota))

    def determine_disks(self, account, request_id, profile, fnr):
        """ Find homedir disks for a given account and profile. """
        disks = []
        spreads = [int(s) for s in profile.get_spreads()]

        for d_spread in profile.get_disk_spreads():
            if d_spread not in spreads:
                logger.debug(
                    "ignoring disk spread %s (not in profile spreads)",
                    repr(d_spread),
                )
                continue
            if d_spread != self.default_spread:
                logger.debug(
                    "ignoring unsupported disk spread %s (not default spread)",
                    repr(d_spread),
                )
                continue
            try:
                ah = account.get_home(d_spread)
                homedir_id = ah['homedir_id']
                current_disk_id = ah['disk_id']
            except Errors.NotFoundError:
                homedir_id, current_disk_id = None, None

            if (current_disk_id and
                    self.autostud.disk_tool.get_diskdef_by_diskid(
                        int(current_disk_id))):
                # TODO: Couldn't it be a _different_ student disk pool?
                logger.warning("Account id=%d already on a student disk",
                               account.entity_id)
                raise _NextAccount

            try:
                new_disk = profile.get_disk(d_spread,
                                            current_disk_id,
                                            do_check_move_ok=False)
                if new_disk == current_disk_id:
                    # Don't think this actually *can* happen, as the
                    # *current_disk_id* would have to be a student disk...
                    # TODO: If it *does* happen, shouldn't it be a _NextAccount
                    # exception, to prevent moving this user to the default
                    # disk?
                    continue
                disks.append((new_disk, d_spread))
                self._update_quota(profile, new_disk, homedir_id)
            except AutostudError as msg:
                logger.warning("Unable to find disk for account id=%d (%s)",
                               account.entity_id, msg)
                break
        return disks

    def move_remaining_users(self):
        """
        Move remaining requests.

        Adds *move* requests for remaining *move student* requests.  This will
        be requests to move to a *default student disk*, using a *default
        homedir spread*.

        This includes all requests for non-students, as well as reqeusts for
        students that doesn't have an appropriate disk set in *studconfig.xml*.
        """
        disk = Factory.get('Disk')(self.db)
        disk.find_by_path(cereconf.AUTOSTUD_PENDING_DISK)
        remaining_requests = list(self.fnr2move_student.values())
        logger.debug("Processing %d remaining requests",
                     len(remaining_requests))
        for move_requests in remaining_requests:
            for account_id, request_id, requestee_id in move_requests:
                self._delete_request(request_id)
                self._add_request(
                    operator=requestee_id,
                    account_id=account_id,
                    disk_id=disk.entity_id,
                    disk_spread=self.default_spread,
                )
                logger.info("Moving account id=%d to pending disk", account_id)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Translate *move student* to regular *move* requests",
    )
    parser.add_argument(
        "--perspective",
        dest="perspective",
        # Why FS?  Seems wrong for uio?
        default="FS",
        help="Use ou perspective %(metavar)s (default: %(default)s)",
        metavar="P",
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        default=False,
        help="Enable autostud debug logging",
    )
    required = parser.add_argument_group("Required files")
    required.add_argument(
        "-c", "--config",
        dest="config_file",
        required=True,
        help="Use student import config from %(metavar)s (e.g. studconf.xml)",
        metavar="FILE",
    )
    required.add_argument(
        "--subjects",
        dest="fs_subjects_file",
        required=True,
        help="Use subjects from %(metavar)s (e.g. emner.xml)",
        metavar="FILE",
    )
    required.add_argument(
        "--programs",
        dest="fs_programs_file",
        default=None,
        required=True,
        help="Use study programs from %(metavar)s (e.g. studieprogs.xml)",
        metavar="FILE",
    )
    required.add_argument(
        "--students",
        dest="fs_persons_file",
        default=None,
        required=True,
        help="Process students from %(metavar)s (e.g. merged_persons.xml)",
        metavar="FILE",
    )

    argutils.add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()

    Cerebrum.logutils.autoconf("daily", args)

    logger.info("start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    db = Factory.get("Database")()
    db.cl_init(change_program=parser.prog)
    const = Factory.get("Constants")(db)

    # defaults
    default_spread = const.spread_uio_nis_user

    # args
    perspective = argutils.get_constant(
        db, parser, const.OUPerspective, args.perspective)

    logger.debug("Configuring AutoStud")
    debug_log = logger.getChild("autostud")
    if not args.debug:
        # filter out debug log messages
        debug_log.setLevel(logging.INFO)
    autostud = AutoStud.AutoStud(
        db, debug_log,
        debug=False,
        cfg_file=args.config_file,
        studieprogs_file=args.fs_programs_file,
        emne_info_file=args.fs_subjects_file,
        ou_perspective=perspective,
    )

    logger.debug("Processing move student requests")
    msp = MoveStudentProcessor(
        db, const, autostud,
        default_spread=default_spread,
    )
    msp.process_requests(args.fs_persons_file)

    if args.commit:
        logger.info("Commiting changes")
        db.commit()
    else:
        logger.info("Rolling back changes (dryrun)")
        db.rollback()

    logger.info("done %s", parser.prog)


if __name__ == '__main__':
    main()
