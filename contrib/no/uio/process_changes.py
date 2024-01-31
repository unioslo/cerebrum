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
This script processes the changelog, and performs a number of tasks:

- when a user has been created: create users homedir
- when a guest user's home has been archived: make a new home directory
- when a quarantine is modified: schedule quarantine refresh bofhd requests

It should be run regularly.

TBD: There are already other scripts that process the changelog themselves.  We
need to determine wheter it is a good idea to have multiple small scripts doing
this, or if there is an advantage into merging all of them into a bigger
script, perhaps with some plugin-like structure for subscribing to certain
event types.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import getopt
import os
import sys

import six

import cereconf

from Cerebrum import Errors
from Cerebrum.Entity import EntityQuarantine
from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler
from Cerebrum.modules import PosixGroup
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.utils import date_compat
from Cerebrum.utils import json


logger = Factory.get_logger("cronjob")

db = Factory.get('Database')()
db.cl_init(change_program="process_changes")
cl_const = Factory.get('CLConstants')(db)
const = Factory.get('Constants')(db)

debug_hostlist = None

DEBUG = False
SUDO_CMD = "sudo"
SSH_CEREBELLUM = ["/usr/bin/ssh", cereconf.ARCHIVE_USER_SERVER]


class EvtHandler(object):
    """Abstract parent class for event handlers.  Currently it only
    defines the default evt_key to use.

    Subclasses should implement get_triggers and one or more notify
    methods.

    Note: Users should be careful about having multiple classes
    listening for the same event with the same evt_key.  If so, all
    classes must confirm the event before it is removed.  TBD: should
    we even allow it?
    """

    evt_key = 'uio_ch'

    def __init__(self, db):
        self.db = db

    def get_triggers(self):
        """
        Get changelog triggers for this handler.

        This method returns a list of strings representing the events in the
        changelog that we want callbacks for.  The string should be the name of
        a constant in CLConstants, and the corresponding callback method should
        be named notify_<string>
        """
        raise NotImplementedError

    def notify_example(self, evt, params):
        """
        Example callback for a trigger named *example*.

        Callback method called when an event of type CLConstants.example is
        found in the changelog.

        :param evt: a database row from the changelog
        :param params: deserialized change_params from the changelog event

        :returns bool: the method should return True upon success
        """

        raise NotImplementedError


class MakeUser(EvtHandler):

    def __init__(self, db):
        super(MakeUser, self).__init__(db)
        # TODO: change if we decide to allow different homedirs for same user
        self.home_spread = const.spread_uio_nis_user

    def get_triggers(self):
        return ("account_home_added", "homedir_update")

    def notify_account_home_added(self, evt, params):
        if params.get('spread', 0) == int(self.home_spread):
            logger.debug("Creating entity_id=%s", evt.fields.subject_entity)
            try:
                if self._make_user(evt['subject_entity']):
                    status = const.home_status_on_disk
                else:
                    status = const.home_status_create_failed
            except Errors.NotFoundError:
                # A reserved user or similar that don't get a homedir
                return True
            posix_user = Factory.get('PosixUser')(self.db)
            posix_user.find(evt['subject_entity'])
            home = posix_user.get_home(self.home_spread)
            posix_user.set_homedir(current_id=home['homedir_id'],
                                   status=status)
            db.commit()
        return True

    def notify_homedir_update(self, evt, params):
        acc = Factory.get("Account")(db)
        try:
            x, accid, x, x, status = acc.get_homedir(params['homedir_id'])
        except Errors.NotFoundError:
            # Ancient changelog entry?  Skip it.
            logger.debug("Skipping deleted homedir %d for account %d",
                         params['homedir_id'], evt['subject_entity'])
            return True
        if accid != evt['subject_entity']:
            logger.error("Homedir %d doesn't belong to account %d",
                         params['homedir_id'], evt['subject_entity'])
            return True
        acc.find(accid)
        guest_trait = acc.get_trait(const.trait_uio_guest_owner)
        if (guest_trait and status == const.home_status_archived and
                not acc.is_expired()):
            logger.debug("Creating fresh home directory for guest %d", accid)
            if not self._make_user(evt['subject_entity']):
                return False
            logger.debug("Successfully created home %d", params['homedir_id'])
            acc.set_homedir(current_id=params['homedir_id'],
                            status=const.home_status_on_disk)
            db.commit()
        return True

    def _get_make_user_data(self, entity_id):
        posix_user = Factory.get('PosixUser')(self.db)
        posix_user.find(entity_id)

        posix_group = PosixGroup.PosixGroup(self.db)
        posix_group.find(posix_user.gid_id)

        home = posix_user.get_home(self.home_spread)
        homedir = posix_user.get_posix_home(self.home_spread)

        disk = Factory.get('Disk')(self.db)
        disk.find(home['disk_id'])

        host = Factory.get('Host')(self.db)
        host.find(disk.host_id)
        return {
            'uname': posix_user.account_name,
            'uid': six.text_type(posix_user.posix_uid),
            'gid': six.text_type(posix_group.posix_gid),
            'gecos': posix_user.get_gecos(),
            'host': host.name,
            'home': home,
            'homedir': homedir,
        }

    def _make_user(self, entity_id):
        try:
            info = self._get_make_user_data(entity_id)
        except Errors.NotFoundError:
            logger.warn("NotFound error for entity_id %s",
                        entity_id, exc_info=1)
            raise
        if int(info['home']['status']) == const.home_status_on_disk:
            logger.warn("User already on disk? %s", entity_id)
            return
        if info['homedir'] is None:
            logger.warn("No home for %s", entity_id)
            return

        args = [
            SUDO_CMD, cereconf.CREATE_USER_SCRIPT,
            '--username', info['uname'],
            '--homedir', info['homedir'],
            '--uid', info['uid'],
            '--gid', info['gid'],
            '--gecos', '"' + info['gecos'] + '"'
        ]
        if DEBUG:
            args.append('--debug')
        cmd = SSH_CEREBELLUM + [" ".join(args), ]
        logger.debug("Doing: %s", cmd)
        if debug_hostlist is None or info['host'] in debug_hostlist:
            errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
        else:
            errnum = 0
        if not errnum:
            return 1
        logger.error("%s returned %i", cmd, errnum)
        return 0


class Quarantine2Request(EvtHandler):
    """When a quarantine has been added/updated/deleted, we register a
    bofh_quarantine_refresh bofhd_request on the apropriate
    start_date, end_date and disable_until dates.
    """

    def __init__(self, db):
        super(Quarantine2Request, self).__init__(db)
        self.br = BofhdRequests(db, const)
        self.eq = EntityQuarantine(db)

    def get_triggers(self):
        return ("quarantine_add", "quarantine_mod", "quarantine_del")

    def _get_quarantine(self, entity_id, q_type):
        self.eq.clear()
        try:
            self.eq.find(entity_id)
        except Errors.NotFoundError:
            return None
        qdata = self.eq.get_entity_quarantine(q_type)
        if not qdata:
            return None
        return qdata[0]

    def notify_quarantine_add(self, evt, params):
        # Register a bofh_quarantine_refresh on start, end and
        # disable_date
        qdata = self._get_quarantine(evt['subject_entity'], params['q_type'])
        if not qdata:
            return True
        for when_col in ('start_date', 'end_date', 'disable_until'):
            when = date_compat.get_date(qdata[when_col])
            if when is not None:
                self.br.add_request(
                    operator=None,
                    when=when,
                    op_code=const.bofh_quarantine_refresh,
                    entity_id=evt['subject_entity'],
                    destination_id=None,
                    state_data=int(params['q_type']),
                )
            db.commit()
        return True

    def notify_quarantine_mod(self, evt, params):
        # Currently only disable_until is affected by quarantine_mod.
        qdata = self._get_quarantine(evt['subject_entity'], params['q_type'])
        if not qdata:
            return True

        when = date_compat.get_date(qdata['disable_until'])
        if when:
            self.br.add_request(
                operator=None,
                when=when,
                op_code=const.bofh_quarantine_refresh,
                entity_id=evt['subject_entity'],
                destination_id=None,
                state_data=int(params['q_type']),
            )

        self.br.add_request(
            operator=None,
            when=self.br.now,
            op_code=const.bofh_quarantine_refresh,
            entity_id=evt['subject_entity'],
            destination_id=None,
            state_data=int(params['q_type']),
        )
        db.commit()
        return True

    def notify_quarantine_del(self, evt, params):
        # Remove existing requests for this entity_id/quarantine_type
        # combination as they are no longer needed
        for row in self.br.get_requests(
                entity_id=evt['subject_entity'],
                operation=int(const.bofh_quarantine_refresh)):
            if int(row['state_data']) == int(params['q_type']):
                self.br.delete_request(request_id=row['request_id'])
        self.br.add_request(
            operator=None,
            when=self.br.now,
            op_code=const.bofh_quarantine_refresh,
            entity_id=evt['subject_entity'],
            destination_id=None,
            state_data=int(params['q_type']),
        )
        db.commit()
        return True


def process_changelog(evt_key, classes):
    """Process the entries from changelog identifying previous events
    by evt_key, and using events and callback methods in classes
    """

    evt_id2call_back = {}
    for c in classes:
        for t in c.get_triggers():
            evt_id2call_back.setdefault(int(getattr(cl_const, t)), []).append(
                getattr(c, "notify_%s" % t))

    ei = CLHandler.CLHandler(Factory.get('Database')())
    for evt in ei.get_events(evt_key, evt_id2call_back.keys()):
        ok = []
        for call_back in evt_id2call_back[int(evt.fields.change_type_id)]:
            if evt['change_params']:
                params = json.loads(evt['change_params'])
            else:
                params = {}
            logger.debug2("Callback %i -> %s", evt['change_id'], call_back)
            ok.append(call_back(evt, params))
        # Only confirm if all call_backs returned true
        if not filter(lambda t: not t, ok):
            ei.confirm_event(evt)
    ei.commit_confirmations()


def process_changes():
    # TODO: Make db here, rather than globally
    classes = (MakeUser(db), Quarantine2Request(db))
    keys = dict([(c.evt_key, None) for c in classes]).keys()
    for k in keys:
        process_changelog(k, filter(lambda c: c.evt_key == k, classes))


def usage(exitcode=0):
    print("""process_changes.py [options]

    -h | --help
    -i | --insert account_name
    -p | --process-changes
    -d | --debug
        Enable debugging in remote scripts, where avaliable
    --debug-hosts <comma-serparated list>
        limit rsh targets to hosts in host_info
    """)
    sys.exit(exitcode)


def main():
    global debug_hostlist, DEBUG
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            'hdi:p',
            ['help',
             'debug',
             'insert=',
             'process-changes',
             'debug-hosts='])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)
    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-d', '--debug'):
            DEBUG = True
        elif opt in ('-i', '--insert'):
            # insert_account_in_cl doesn't exist?
            raise NotImplementedError("gone")
            # insert_account_in_cl(val)
        elif opt in ('-p', '--process-changes'):
            process_changes()
        elif opt == '--debug-hosts':
            debug_hostlist = val.split(",")
            print(debug_hostlist)


if __name__ == '__main__':
    main()
