# -*- coding: iso-8859-1 -*-
# Copyright 2003 University of Oslo, Norway
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

""""""

import random

import re
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd.utils import BofhdRequests


class AccountUiOMixin(Account.Account):
    """Account mixin class providing functionality specific to UiO.

    The methods of the core Account class that are overridden here,
    ensure that any Account objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies of the University of Oslo.

    """

    def add_spread(self, spread):
        #
        # Pre-add checks
        #
        spreads = [int(r['spread']) for r in self.get_spread()]
        # All users in the 'ifi' NIS domain must also exist in the
        # 'uio' NIS domain.
        if spread == self.const.spread_ifi_nis_user \
               and int(self.const.spread_uio_nis_user) not in spreads:
            raise self._db.IntegrityError, \
                  "Can't add ifi spread to an account without uio spread."
        #
        # (Try to) perform the actual spread addition.
        ret = self.__super.add_spread(spread)
        #
        # Additional post-add magic
        #        
        if spread == self.const.spread_uio_imap:
            # Unless this account already has been associated with an
            # Cyrus EmailServerTarget, we need to do so.
            est = Email.EmailServerTarget(self._db)
            old_server = None
            try:
                est.find_by_entity(self.entity_id)
                old_server = est.email_server_id
            except Errors.NotFoundError:
                pass
            est = self._UiO_update_email_server(
                self.const.email_server_type_cyrus)

            if old_server == est.email_server_id:
                return ret
            br = BofhdRequests(self._db, self.const)
            # Register a BofhdRequest to create the mailbox
            reqid = br.add_request(None,        # Requestor
                                   br.now, self.const.bofh_email_create,
                                   self.entity_id, est.email_server_id)
            if old_server:
                # Move user iff we chose a new server.  Add a
                # dependency on the create above.
                br.add_request(None,	# Requestor
                               br.now, self.const.bofh_email_move,
                               self.entity_id, old_server,
                               state_data = reqid)
            # The user's email target is now associated with an email
            # server; try generating email addresses connected to the
            # target.
            self.update_email_addresses()
            # Make sure that Cyrus is told about the quota, the
            # previous call probably didn't change the database value
            # and therefore didn't add a request.
            self.update_email_quota(force=True)

        # add an account_home entry pointing to the same disk as the uio spread
        if spread == self.const.spread_ifi_nis_user:
            tmp = self.get_home(self.const.spread_uio_nis_user)
            self.set_home(spread, disk_id=tmp['disk_id'],
                          home=tmp['home'], status=tmp['status'])
        return ret

    def set_home(self, spread, disk_id=None, home=None, status=None):
        # Assert that user has same home at ifi & uio
        ret = self.__super.set_home(spread, disk_id=disk_id,
                                    home=home, status=status)
        if spread == self.const.spread_ifi_nis_user:
            other_home_spread = self.const.spread_uio_nis_user
        elif spread == self.const.spread_uio_nis_user:
            other_home_spread = self.const.spread_ifi_nis_user
        else:
            raise ValueError, "Unexpected spread %s in set_home" % spread
        ret = self.__super.set_home(other_home_spread, disk_id=disk_id,
                                    home=home, status=status)        

    def _UiO_update_email_server(self, server_type):
        est = Email.EmailServerTarget(self._db)
        es = Email.EmailServer(self._db)
        old_server = None
        is_on_cyrus = False
        try:
            est.find_by_entity(self.entity_id)
            old_server = est.email_server_id
            es.find(est.email_server_id)
            if es.email_server_type == server_type:
                # All is well
                return est
            if es.email_server_type == self.const.email_server_type_cyrus:
                is_on_cyrus = True
        except Errors.NotFoundError:
            pass
        if old_server is None \
           or (server_type == self.const.email_server_type_cyrus
               and not is_on_cyrus):
            email_servs = []
            for svr in es.list_email_server_ext():
                if svr['server_type'] <> server_type:
                    continue
                if (server_type == self.const.email_server_type_cyrus
                    and svr['name'] == 'mail-sg0'):
                    # Reserved for test users.
                    continue
                email_servs.append(svr['server_id'])
            svr_id = random.choice(email_servs)
            if old_server is None:
                try:
                    et = Email.EmailTarget(self._db)
                    et.find_by_email_target_attrs(entity_id = self.entity_id)
                except Errors.NotFoundError:
                    et.clear()
                    et.populate(self.const.email_target_account,
                                self.entity_id,
                                self.const.entity_account)
                    et.write_db()
                est.clear()
                est.populate(svr_id, parent = et)
            else:
                est.populate(svr_id)
            est.write_db()
            return est
        elif is_on_cyrus:
            # Even though this Account's email target already resides
            # on one of the Cyrus servers, something has called this
            # method with a non-Cyrus-servertype arg.
            #
            # The most likely cause for this is the Account not having
            # spread_uio_imap.  Check if this is indeed the case, and
            # report error accordingly.
            spreads = [int(r['spread']) for r in self.get_spread()]
            if int(self.const.spread_uio_imap) not in spreads:
                raise self._db.IntegrityError, \
                      "Database inconsistency; need to add spread IMAP@uio."
            else:
                raise self._db.IntegrityError, \
                      "Can't move email target away from IMAP."

    def illegal_name(self, name):
        # Avoid circular import dependency
        from Cerebrum.modules.PosixUser import PosixUser

        if isinstance(self, PosixUser):
            # TODO: Kill the ARsystem user to limit range og legal characters
            if len(name) > 8:
                return "too long (%s)" % name
            if re.search("^[^A-Za-z]", name):
                return "must start with a character (%s)" % name
            if re.search("[^A-Za-z0-9\-_]", name):
                return "contains illegal characters (%s)" % name
        return False
        
    def delete_spread(self, spread):
        #
        # Pre-remove checks
        #
        spreads = [int(r['spread']) for r in self.get_spread()]
        # All users in the 'ifi' NIS domain must also exist in the
        # 'uio' NIS domain.
        if spread == self.const.spread_uio_nis_user \
               and int(self.const.spread_ifi_nis_user) in spreads:
            raise self._db.IntegrityError, \
                  "Can't remove uio spread to an account with ifi spread."

        # keep account_home in sync
        if spread == self.const.spread_ifi_nis_user:
            self.clear_home(self.const.spread_ifi_nis_user)
        elif spread == self.const.spread_uio_nis_user:
            try:
                self.get_home(spread)
                raise self._db.IntegrityError, \
                      "Must delete user to remove uio_nis spread"
            except Errors.NotFoundError:
                pass

        #
        # (Try to) perform the actual spread removal.
        ret = self.__super.delete_spread(spread)
        return ret


    def update_email_addresses(self):
        # The "cast" into PosixUser causes this function to be called
        # twice in the typical case, so the "pre" code must be idempotent.

        # Make sure the email target of this account is associated
        # with an appropriate email server.  We must do this before
        # super, since without an email server, no target or address
        # will be created.
        if not (self.is_reserved() or self.is_deleted()):
            spreads = [int(r['spread']) for r in self.get_spread()]
            srv_type = self.const.email_server_type_nfsmbox
            if int(self.const.spread_uio_imap) in spreads:
                srv_type = self.const.email_server_type_cyrus
            self._UiO_update_email_server(srv_type)
            self.update_email_quota()

        # Avoid circular import dependency
        from Cerebrum.modules.PosixUser import PosixUser
        if isinstance(self, PosixUser):
            ret = self.__super.update_email_addresses()
        else:
            try:
                # We use the PosixUser object to get access to GECOS.
                # TODO: This ought to be in a mixin class for Account
                # for installations where both the PosixUser and the
                # Email module is in use.  For now we'll just put it
                # in the UiO specific code.
                posixuser = PosixUser(self._db)
                posixuser.find(self.entity_id)
                # Return immediately, any post code will be executed
                # on the second run of this function.
                return posixuser.__super.update_email_addresses()
            except Errors.NotFoundError:
                ret = self.__super.update_email_addresses()
        return ret

    def update_email_quota(self, force=False):
        """Set e-mail quota according to affiliation.  If any change
        is made and user's e-mail is on a Cyrus server, add a request
        to have Cyrus updated accordingly.  If force is true, such a
        request is always made for Cyrus users."""
        change = force
        quota = 100
        if self.is_employee():
            quota = 200
        eq = Email.EmailQuota(self._db)
        try:
            eq.find_by_entity(self.entity_id)
        except Errors.NotFoundError:
            change = True
            eq.populate(90, quota)
            eq.write_db()
        else:
            # We never decrease the quota, to allow for manual overrides
            if quota > eq.email_quota_hard:
                change = True
                eq.email_quota_hard = quota
                eq.write_db()
        if not change:
            return
        est = Email.EmailServerTarget(self._db)
        try:
            est.find_by_entity(self.entity_id)
        except:
            return
        es = Email.EmailServer(self._db)
        es.find(est.email_server_id)
        if es.email_server_type == self.const.email_server_type_cyrus:
            br = BofhdRequests(self._db, self.const)
            # The call graph is too complex when creating new users or
            # migrating old users.  So to avoid problems with this
            # function being called more than once, we just remove any
            # conflicting requests, so that the last request added
            # wins.
            br.delete_request(entity_id=self.entity_id,
                              operation=self.const.bofh_email_hquota)
            br.add_request(None, br.now, self.const.bofh_email_hquota, 
                           self.entity_id, None)

    def is_employee(self):
        for r in self.get_account_types():
            if r['affiliation'] == self.const.affiliation_ansatt:
                return True
        return False
