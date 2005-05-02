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
import cereconf
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.modules import PasswordHistory
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.Utils import pgp_encrypt, Factory

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
        # Gather information on present state, to be used later.  Note
        # that this information gathering must be done before we pass
        # control to our superclass(es), as the superclass methods
        # might change the state.
        state = {}
        if spread == self.const.spread_uio_imap:
            # Is this account already associated with an Cyrus
            # EmailServerTarget?
            est = Email.EmailServerTarget(self._db)
            try:
                est.find_by_entity(self.entity_id)
                state['email_server_id'] = est.email_server_id
            except Errors.NotFoundError:
                pass
        #
        # (Try to) perform the actual spread addition.
        ret = self.__super.add_spread(spread)
        #
        # Additional post-add magic
        #
        if spread == self.const.spread_uio_imap:
            # Unless this account already has been associated with an
            # Cyrus EmailServerTarget, we need to do so.
            est = self._UiO_update_email_server(
                self.const.email_server_type_cyrus)

            self._UiO_order_cyrus_action(self.const.bofh_email_create,
                                         est.email_server_id)
            # The user's email target is now associated with an email
            # server; try generating email addresses connected to the
            # target.
            self.update_email_addresses()
            # Make sure that Cyrus is told about the quota, the
            # previous call probably didn't change the database value
            # and therefore didn't add a request.
            self.update_email_quota(force=True, request=True)
        elif spread == self.const.spread_ifi_nis_user:
            # Add an account_home entry pointing to the same disk as
            # the uio spread
            tmp = self.get_home(self.const.spread_uio_nis_user)
            self.set_home(spread, tmp['homedir_id'])
        return ret

    def _UiO_order_cyrus_action(self, action, destination, state_data=None):
        br = BofhdRequests(self._db, self.const)
        # If there are any registered BofhdRequests for this account
        # that would conflict with 'action', remove them.
        for anti_action in br.get_conflicts(action):
            for r in br.get_requests(entity_id=self.entity_id,
                                     operation=anti_action):
                self.logger.info("Removing BofhdRequest #%d: %r",
                                 r['request_id'], r)
                br.delete_request(request_id=r['request_id'])
        # If the ChangeLog module knows who the user requesting this
        # change is, use that knowledge.  Otherwise, set requestor to
        # None; it's the best we can do.
        requestor = getattr(self._db, 'change_by', None)
        # Register a BofhdRequest to create the mailbox.
        reqid = br.add_request(requestor,
                               br.now, action, self.entity_id, destination,
                               state_data=state_data)

    def set_password(self, plaintext):
        # Override Account.set_password so that we get a copy of the
        # plaintext password
        self.__plaintext_password = plaintext
        self.__super.set_password(plaintext)

    def write_db(self):
        try:
            plain = self.__plaintext_password
        except AttributeError:
            plain = None
        ret = self.__super.write_db()
        if plain is not None:
            ph = PasswordHistory.PasswordHistory(self._db)
            ph.add_history(self, plain)
        return ret

    def _UiO_update_email_server(self, server_type):
        est = Email.EmailServerTarget(self._db)
        es = Email.EmailServer(self._db)
        old_server = None
        is_on_cyrus = False
        try:
            est.find_by_entity(self.entity_id)
            old_server = est.email_server_id
            es.find(old_server)
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
                if server_type == self.const.email_server_type_cyrus:
                    if svr['name'].startswith("mail-sg"):
                        # Old (VA) cluster; no longer in use.
                        continue
                    elif (svr['name'].startswith('cyrus')
                          and svr['name'][5:].isdigit()):
                        pkgnum = int(svr['name'][5:])
                        if pkgnum < 1 or pkgnum > 12:
                            # Only the first 12 ServiceGuard packages
                            # of our Cyrus cluster are currently in
                            # use.
                            continue
                # Unless explicitly skipped over by one of the if
                # tests above, add this email server to our list of
                # alternatives.
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
        if not spread in spreads:  # user doesn't have this spread
            return
        # All users in the 'ifi' NIS domain must also exist in the
        # 'uio' NIS domain.
        if spread == self.const.spread_uio_nis_user \
               and int(self.const.spread_ifi_nis_user) in spreads:
            raise self._db.IntegrityError, \
                  "Can't remove uio spread to an account with ifi spread."

        # keep ifi-part of account_home in sync.  We do not do this
        # for uio-spread as that would result in the removal of the
        # homedir uppon user-deletion making it hard to know where the
        # user used to live.
        if spread == self.const.spread_ifi_nis_user:
            self.clear_home(self.const.spread_ifi_nis_user)

        # Remove IMAP user
        # TBD: It is currently a bit uncertain who and when we should
        # allow this.  Currently it should only be used when deleting
        # a user.
        if (spread == self.const.spread_uio_imap and
            int(self.const.spread_uio_imap) in spreads):
            est = Email.EmailServerTarget(self._db)
            est.find_by_entity(self.entity_id)
            self._UiO_order_cyrus_action(self.const.bofh_email_delete, None,
                                         state_data=est.email_server_id)
            # TBD: should we also perform a "cascade delete" from EmailTarget?

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
            est = Email.EmailServerTarget(self._db)
            es = Email.EmailServer(self._db)
            srv_type = self.const.email_server_type_nfsmbox
            try:
                est.find_by_entity(self.entity_id)
            except Errors.NotFoundError:
                pass
            else:
                # This account's email target is already associated
                # with an email server.
                #
                # If the server is of type Cyrus, we want the target
                # to stay on that server; set srv_type to Cyrus.
                # Otherwise, determine srv_type from what spreads the
                # account has.
                #
                # Without this special rule for targets already
                # residing in Cyrus, the call to
                # ._UiO_update_email_server() further down would cause
                # problems when doing removal of all the account's
                # spreads at the start of account deletion.
                es.find(est.email_server_id)
                if es.email_server_type == self.const.email_server_type_cyrus:
                    srv_type = self.const.email_server_type_cyrus
            spreads = [int(r['spread']) for r in self.get_spread()]
            if int(self.const.spread_uio_imap) in spreads:
                srv_type = self.const.email_server_type_cyrus
            self._UiO_update_email_server(srv_type)
            self.update_email_quota()

        # Avoid circular import dependency
        from Cerebrum.modules.PosixUser import PosixUser

        # Try getting the PosixUser-promoted version of self.  Failing
        # that, use self unpromoted.
        userobj = self
        if not isinstance(self, PosixUser):
            try:
                # We use the PosixUser object to get access to GECOS.
                # TODO: This ought to be in a mixin class for Account
                # for installations where both the PosixUser and the
                # Email module is in use.  For now we'll just put it
                # in the UiO specific code.
                tmp = PosixUser(self._db)
                tmp.find(self.entity_id)
                userobj = tmp
            except Errors.NotFoundError:
                # This Account hasn't been promoted to PosixUser yet.
                pass

        return userobj.__super.update_email_addresses()

    def is_employee(self):
        for r in self.get_account_types():
            if r['affiliation'] == self.const.affiliation_ansatt:
                return True
        return False

    def enc_auth_type_pgp_crypt(self, plaintext, salt=None):
        return pgp_encrypt(plaintext, cereconf.PGPID)
    
    def enc_auth_type_md4_nt(self,plaintext,salt=None):
        import smbpasswd
        return smbpasswd.nthash(plaintext)

# arch-tag: 7bc3f7a8-183f-45c7-8a8f-f2ffff5029c5
