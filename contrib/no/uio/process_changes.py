#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2026 University of Oslo, Norway
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
This script periodically handles new changes in the changelog.

For known change types, we perform a number of tasks:

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
import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Entity import EntityQuarantine
from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler
from Cerebrum.modules import PosixGroup
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.utils import date_compat
from Cerebrum.utils import json
from Cerebrum.utils import reprutils
from Cerebrum.utils.descriptors import lazy_property
from Cerebrum.modules.no.uio import reguser


logger = logging.getLogger(__name__)


class EvtHandler(reprutils.ReprFieldMixin):
    """
    Abstract parent class for event handlers.

    Subclasses should set triggers, and implement a handler method for each
    trigger.

    Note: Users should be careful about having multiple classes
    listening for the same event with the same evt_key.  If so, all
    classes must confirm the event before it is removed.  TBD: should
    we even allow it?
    """
    repr_id = False
    repr_module = False

    evt_key = "uio_ch"
    triggers = ("example",)

    def __init__(self, db, dryrun):
        self.db = db
        self.const = Factory.get('Constants')(db)
        self.dryrun = dryrun

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
    """
    Create user home directories.

    Creates missing user homedirs on disk, using *reguser*.  If successful, the
    current home status in Cerebrum is then updated to *on disk*.
    """

    triggers = ("account_home_added", "homedir_update")

    def __init__(self, *args, **kwargs):
        self.debug = kwargs.pop("debug", False)
        super(MakeUser, self).__init__(*args, **kwargs)

    @lazy_property
    def home_spread(self):
        return self.const.spread_uio_nis_user

    @property
    def reguser(self):
        return reguser.ReguserCommands(
            dryrun=self.dryrun,
            remote_dryrun=False,
            remote_debug=self.debug,
        )

    def notify_account_home_added(self, evt, params):
        """
        on account_home:add - create new homedirs

        Creates new homedirs for new or recently promoted (posix) accounts.
        """
        if params.get('spread') == int(self.home_spread):
            logger.debug("Creating homedir for entity_id=%s",
                         evt['subject_entity'])
            try:
                if self._make_user(int(evt['subject_entity'])):
                    status = self.const.home_status_on_disk
                else:
                    status = self.const.home_status_create_failed
            except Errors.NotFoundError:
                # A reserved user or similar that don't get a homedir
                return True
            posix_user = Factory.get('PosixUser')(self.db)
            posix_user.find(evt['subject_entity'])
            home = posix_user.get_home(self.home_spread)
            posix_user.set_homedir(current_id=home['homedir_id'],
                                   status=status)
            if not self.dryrun:
                self.db.commit()
        return True

    def notify_homedir_update(self, evt, params):
        """
        on homedir:modify - create new homedir if re-usable *guest* account

        Creates fresh homedirs for recently archived guest accounts in the
        guest account pool (gjest-NNN and guest-NNN accounts).
        """
        acc = Factory.get("Account")(self.db)
        try:
            _, accid, _, _, status = acc.get_homedir(params['homedir_id'])
        except Errors.NotFoundError:
            # Ancient changelog entry?  Skip it.
            logger.debug(
                "Ignoring subject id=%r, homedir=%r - homedir deleted",
                evt['subject_entity'], params['homedir_id'])
            return True
        if accid != evt['subject_entity']:
            logger.error(
                "Ignoring subject id=%r, homedir=%r - owner mismatch!",
                evt['subject_entity'], params['homedir_id'])
            return True
        acc.find(accid)
        guest_trait = acc.get_trait(self.const.trait_uio_guest_owner)
        if (guest_trait
                and status == self.const.home_status_archived
                and not acc.is_expired()):
            logger.debug("Creating fresh home directory for guest %d", accid)
            if not self._make_user(int(evt['subject_entity'])):
                return False
            logger.debug("Successfully created home %d", params['homedir_id'])
            acc.set_homedir(current_id=params['homedir_id'],
                            status=self.const.home_status_on_disk)
            if not self.dryrun:
                self.db.commit()
        return True

    def _make_user(self, entity_id):
        try:
            posix_user = Factory.get('PosixUser')(self.db)
            posix_user.find(entity_id)
            username = posix_user.account_name
            uid = int(posix_user.posix_uid)
            gecos = posix_user.get_gecos()
        except Errors.NotFoundError as e:
            logger.warning("No posix account for id=%d: %s", entity_id, e)
            raise

        try:
            posix_group = PosixGroup.PosixGroup(self.db)
            posix_group.find(posix_user.gid_id)
            gid = int(posix_group.posix_gid)
        except Errors.NotFoundError as e:
            logger.warning("Missing file group for %s (%d): %s",
                           username, entity_id, e)
            raise

        try:
            home = posix_user.get_home(self.home_spread)
            homedir = posix_user.get_posix_home(self.home_spread)
            if homedir is None:
                raise Errors.NotFoundError("no home")
        except Errors.NotFoundError as e:
            logger.warning("Missing homedir for %s (%d): %s",
                           username, entity_id, e)
            raise

        if int(home['status']) == self.const.home_status_on_disk:
            logger.warning("User %s (%d) already on disk?",
                           username, entity_id)
            # TODO: False seems wrong here, as it will update the status to
            # *create failed* and/or not confirm the change event.  This is
            # odd, given that the home directory actually *exist*, and
            # everything is probably OK?
            return False

        return self.reguser.create_user(username, homedir, uid, gid, gecos)


class Quarantine2Request(EvtHandler):
    """
    Refresh quarantines.

    When a quarantine is added/updated/deleted, we register a
    ``bofh_quarantine_refresh`` bofhd request on the apropriate start-,
    end-, and *disable until* dates.

    This will make sure that the proper events are (re-)dispatched at those
    dates, and that event based integrations can react to delayed quarantine
    events.
    """
    triggers = ("quarantine_add", "quarantine_mod", "quarantine_del")

    @lazy_property
    def br(self):
        return BofhdRequests(self.db, self.const)

    def _get_quarantine(self, entity_id, q_type):
        eq = EntityQuarantine(self.db)
        try:
            eq.find(int(entity_id))
        except Errors.NotFoundError:
            return None
        qdata = eq.get_entity_quarantine(qtype=int(q_type))
        if not qdata:
            return None
        return qdata[0]

    def _add_refresh(self, entity_id, q_type, at=None):
        if not at:
            at = self.br.now
        when = at or self.br.now
        logger.debug("Add quarantine refresh for id=%d, type=%d, at=%s",
                     entity_id, q_type, when)
        self.br.add_request(
            operator=None,
            when=when,
            op_code=self.const.bofh_quarantine_refresh,
            entity_id=entity_id,
            destination_id=None,
            state_data=int(q_type),
        )

    def _clear_refresh(self, entity_id, q_type):
        for row in self.br.get_requests(
                entity_id=entity_id,
                operation=int(self.const.bofh_quarantine_refresh)):
            if int(row['state_data']) == int(q_type):
                logger.debug("Remove quarantine refresh for id=%d, "
                             "type=%d, request id=%s",
                             entity_id, q_type, row['request_id'])
                self.br.delete_request(request_id=row['request_id'])

    def notify_quarantine_add(self, evt, params):
        """
        on quarantine:add - create quarantine refresh events

        Registers ``bofh_quarantine_refresh`` bofhd requests on each of the
        following dates, if set:

        - start_date
        - end_date
        - disable_until
        """
        qdata = self._get_quarantine(evt['subject_entity'], params['q_type'])
        if not qdata:
            return True
        for when_col in ('start_date', 'end_date', 'disable_until'):
            when = date_compat.get_date(qdata[when_col])
            if when is not None:
                self._add_refresh(evt['subject_entity'], params['q_type'],
                                  when)
            if not self.dryrun:
                self.db.commit()
        return True

    def notify_quarantine_mod(self, evt, params):
        """
        on quarantine:mod - create quarantine refresh events

        Registers a ``bofh_quarantine_refresh`` bofhd request for immediate
        processing, and an additional request for the ``disable_until`` date,
        if set.
        """
        qdata = self._get_quarantine(evt['subject_entity'], params['q_type'])
        if not qdata:
            return True

        when = date_compat.get_date(qdata['disable_until'])
        if when:
            # Add future request @ disable_until
            self._add_refresh(evt['subject_entity'], params['q_type'], when)

        # Add immediate request
        self._add_refresh(evt['subject_entity'], params['q_type'], None)
        if not self.dryrun:
            self.db.commit()
        return True

    def notify_quarantine_del(self, evt, params):
        """
        on quarantine:del - update quarantine refresh events

        Removes existing ``bofh_quarantine_refresh`` bofhd requests, and adds a
        single, new request for immediate processing.
        """
        # Remove existing bofhd requests
        self._clear_refresh(evt['subject_entity'], params['q_type'])

        # Add a new request for immediate processing
        self._add_refresh(evt['subject_entity'], params['q_type'], None)
        if not self.dryrun:
            self.db.commit()
        return True


def process_changelog(db, evt_key, classes):
    """Process the entries from changelog identifying previous events
    by evt_key, and using events and callback methods in classes
    """
    clconst = Factory.get('CLConstants')(db)
    commit_changes = all(not c.dryrun for c in classes)

    callbacks = {}
    for c in [c for c in classes if c.evt_key == evt_key]:
        for trigger in c.triggers:
            change_type = getattr(clconst, trigger)
            callback_name = "notify_{}".format(trigger)
            callback = getattr(c, callback_name)
            if not callable(callback):
                raise ValueError("invalid callback %s for %s"
                                 % (callback_name, repr(c)))
            callbacks.setdefault(int(change_type), []).append(callback)

    # TODO: Do we really need a separate transaction here for the change
    # handler?  Unsure, it might actually be a good idea, but the
    # implementation is very wrong.
    #
    # This script commits changes for each handled event, but *confirms* events
    # after completing all changes for the given evt_key.  This means we could
    # end up in a state where *some* events have completed (and changes
    # commited), but not been acked (because we roll back before running
    # commit_confirmations) if any of the successive events in queue fails!
    ei = CLHandler.CLHandler(Factory.get('Database')())
    for evt in ei.get_events(evt_key, set(callbacks)):
        logger.info("Change id=%r, subject id=%r",
                    evt['change_id'], evt['subject_entity'])
        ok = []
        for callback in callbacks[int(evt['change_type_id'])]:
            if evt['change_params']:
                params = json.loads(evt['change_params'])
            else:
                params = {}
            logger.debug("Running callback %s", callback)
            ok.append(callback(evt, params))
        # Only confirm if all callbacks returned true
        if all(ok):
            ei.confirm_event(evt)
    if commit_changes:
        ei.commit_confirmations()


def process_changes(db, dryrun, debug):
    classes = (
        MakeUser(db, dryrun, debug=debug),
        Quarantine2Request(db, dryrun),
    )
    for change_key in sorted(set(c.evt_key for c in classes)):
        logger.info("Processing changes for key=%s", repr(change_key))
        process_changelog(db, change_key, classes)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Process changelog events",
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Enable debugging in remote scripts, where avaliable",
    )
    commit_mutex = parser.add_mutually_exclusive_group()
    commit_mutex.add_argument(
        "-p", "--process-changes", "--commit",
        action="store_true",
        dest="commit",
        help="Run remote scripts and commit changes",
    )
    commit_mutex.add_argument(
        "--dryrun",
        action="store_false",
        dest="commit",
        help="Don't run scripts or commit changes (default)",
    )
    commit_mutex.set_defaults(commit=False)
    # TODO: For proper debugging and testing, We may want separate --dryrun
    # override flags for the callbacks, the clhandler, and the reguser commands
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf("cronjob", args)
    logger.info("start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    dryrun = not args.commit
    logger.info("dryrun: %s", dryrun)

    db = Factory.get('Database')()
    db.cl_init(change_program="process_changes")
    process_changes(db, dryrun, args.debug)

    logger.info("done %s", parser.prog)


if __name__ == '__main__':
    main()
