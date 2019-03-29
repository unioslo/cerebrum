# -*- coding: utf-8 -*-
#
# Copyright 2003-2019 University of Oslo, Norway
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

import random

import re
import cereconf
from mx import DateTime
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.modules import EmailConstants
from Cerebrum.modules.disk_quota import DiskQuota
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
        if (spread == self.const.spread_ifi_nis_user and
                int(self.const.spread_uio_nis_user) not in spreads):
            raise self._db.IntegrityError(
                "Can't add ifi spread to an account without uio spread.")

        # Gather information on present state, to be used later.  Note
        # that this information gathering must be done before we pass
        # control to our superclass(es), as the superclass methods
        # might change the state.
        #
        # exchange-relatert-jazz
        # this code (up to and including 'pass') may be removed
        # after Exchange roll-out, as it has been decided that all
        # new mail-boxes will be created in Exchange and any old
        # mailboxes restored to Exchange
        # Jazz (2013-11)
        state = {}
        if spread == self.const.spread_uio_imap:
            # exchange-relatert-jazz
            # no account should have both IMAP and Exchange spread at the
            # same time, as this will create a double mailbox
            if self.has_spread(self.const.spread_exchange_account):
                raise self._db.IntegrityError("Can't add IMAP-spread to an "
                                              "account with Exchange-spread.")
            # Is this account already associated with an Cyrus
            # EmailTarget?
            et = Email.EmailTarget(self._db)
            try:
                et.find_by_target_entity(self.entity_id)
                if et.email_server_id:
                    state['email_server_id'] = et.email_server_id
            except Errors.NotFoundError:
                pass

        if spread == self.const.spread_exchange_account:
            # no account should have both IMAP and Exchange spread at the
            # same time, as this will create a double mailbox
            if self.has_spread(self.const.spread_uio_imap):
                raise self._db.IntegrityError("Can't add Exchange-spread to "
                                              "an account with IMAP-spread.")
            # Check if there is an existing email-target for this account
            # (entity) before we actually add the spread.
            is_new_target = not self._has_email_target()

        # (Try to) perform the actual spread addition.
        # An exception will be thrown if the same type of spread exists for
        # this account (entity-id)
        ret = self.__super.add_spread(spread)
        #
        # Additional post-add magic
        #
        # exchange-relatert-jazz
        if spread == self.const.spread_exchange_account:
            # exchange-relatert-jazz
            es = Email.EmailServer(self._db)
            es.clear()
            # we could probably define a cereconf var to hold this
            # default (dummy) server value, but I hope that, since it
            # is not actually used in Exchange, the whole
            # server-reference may de removed from EmailTarget after
            # migration to Exchange is completed (it should be done,
            # no matter if Baardj says differently :-)). Jazz (2013-11)
            es.find_by_name('mail')
            # Check if the account already is associated with an
            # EmailTarget. If so, we are most likely looking at an
            # account restore (or else an anomaly in the cerebrum-db)
            # We should keep the EmailTarget, but make sure that
            # target_type is refreshed to "account" and target_server
            # is refreshed to dummy-exchange server. We are, at this
            # point, not interessted in any target-data.
            et = Email.EmailTarget(self._db)
            try:
                et.find_by_target_entity(self.entity_id)
                et.email_server_id = es.entity_id
                et.email_target_type = self.const.email_target_account
            except Errors.NotFoundError:
                # No EmailTarget found for account, creating one
                # after the migration to Exchange is completed this
                # part may be done by update_email_addresses,
                # but since we need to support both exchange and
                # imap for a while, it's easiest to create the
                # target manually
                et.populate(self.const.email_target_account,
                            self.entity_id,
                            self.const.entity_account,
                            server_id=es.entity_id)
            et.write_db()
            self.update_email_quota()
            # register default spam and filter settings
            self._UiO_default_spam_settings(et)
            if is_new_target:
                self._UiO_default_filter_settings(et)
            # The user's email target is now associated with an email
            # server, try generating email addresses connected to the
            # target.
            self.update_email_addresses()
        # exchange-relatert-jazz
        # this code (up to and including 'update_email_addresse')
        # may be removed after Exchange roll-out, as it has been
        # decided that all new mail-boxes will be created in Exchange
        # and any old mailboxes restored to Exchange
        # Jazz (2013-11)
        if spread == self.const.spread_uio_imap:
            # Unless this account already has been associated with an
            # Cyrus EmailTarget, we need to do so.
            et = self._UiO_update_email_server(
                self.const.email_server_type_cyrus)
            self.update_email_quota()
            # register default spam and filter settings
            self._UiO_default_spam_settings(et)
            self._UiO_default_filter_settings(et)
            # The user's email target is now associated with an email
            # server; try generating email addresses connected to the
            # target.
            self.update_email_addresses()
        elif spread == self.const.spread_ifi_nis_user:
            # Add an account_home entry pointing to the same disk as
            # the uio spread
            try:
                tmp = self.get_home(self.const.spread_uio_nis_user)
                self.set_home(spread, tmp['homedir_id'])
            except Errors.NotFoundError:
                pass  # User has no homedir for this spread yet
        return ret

    # exchange-related-jazz
    def delete_spread(self, spread):
        #
        # Pre-remove checks
        #
        spreads = [int(r['spread']) for r in self.get_spread()]
        if spread not in spreads:  # user doesn't have this spread
            return
        # All users in the 'ifi' NIS domain must also exist in the
        # 'uio' NIS domain.
        if (spread == self.const.spread_uio_nis_user and
                int(self.const.spread_ifi_nis_user) in spreads):
            raise self._db.IntegrityError, \
                  "Can't remove uio spread to an account with ifi spread."

        if (spread == self.const.spread_ifi_nis_user or
                spread == self.const.spread_uio_nis_user):
            self.clear_home(spread)

        # Remove IMAP user
        # TBD: It is currently a bit uncertain who and when we should
        # allow this.  Currently it should only be used when deleting
        # a user.
        # exchange-related-jazz
        # this code, up to and including the TBD should be removed
        # when migration to Exchange is completed as it wil no longer
        # be needed. Jazz (2013-11)
        #
        if (spread == self.const.spread_uio_imap and
                int(self.const.spread_uio_imap) in spreads):
            et = Email.EmailTarget(self._db)
            et.find_by_target_entity(self.entity_id)
            self._UiO_order_cyrus_action(self.const.bofh_email_delete,
                                         et.email_server_id)
            # TBD: should we also perform a "cascade delete" from EmailTarget?
        # exchange-relatert-jazz
        # Due to the way Exchange is updated we no longer need to
        # register a delete request in Cerebrum. Setting target_type
        # to deleted should generate an appropriate event which then
        # may be used to remove the mailbox from Exchange in the
        # agreed maner (export to .pst-file, then remove-mailbox). A
        # clean-up job should probably be implemented to remove
        # email_targets that have had status deleted for a period of
        # time. This will however remove the e-mailaddresses assigned
        # to the target and make their re-use possible. Jazz (2013-11)
        #
        if spread == self.const.spread_exchange_account:
            et = Email.EmailTarget(self._db)
            et.find_by_target_entity(self.entity_id)
            et.email_target_type = self.const.email_target_deleted
            et.write_db()
        # (Try to) perform the actual spread removal.
        ret = self.__super.delete_spread(spread)
        return ret

    def set_home(self, spread, homedir_id):
        self.__super.set_home(spread, homedir_id)
        spreads = [int(r['spread']) for r in self.get_spread()]
        if spread == self.const.spread_uio_nis_user \
           and int(self.const.spread_ifi_nis_user) in spreads:
            self.__super.set_home(self.const.spread_ifi_nis_user, homedir_id)

    # exchange-realatert-jazz
    # this method should not have to be changes after Exchange roll-out
    # or at migration completion. Jazz (2013-11)
    def _UiO_default_filter_settings(self, email_target):
        t_id = email_target.entity_id
        tt_str = str(Email._EmailTargetCode(email_target.email_target_type))
        # Set default filters if none found on this target
        etf = Email.EmailTargetFilter(self._db)
        if tt_str in cereconf.EMAIL_DEFAULT_FILTERS:
            for f in cereconf.EMAIL_DEFAULT_FILTERS[tt_str]:
                f_id = int(EmailConstants._EmailTargetFilterCode(f))
                try:
                    etf.clear()
                    etf.find(t_id, f_id)
                except Errors.NotFoundError:
                    etf.clear()
                    etf.populate(f_id, parent=email_target)
                    etf.write_db()

    # exchange-realatert-jazz
    # this method should not have to be changes after Exchange roll-out
    # or at migration completion. Jazz (2013-11)
    def _UiO_default_spam_settings(self, email_target):
        t_id = email_target.entity_id
        tt_str = str(Email._EmailTargetCode(email_target.email_target_type))
        # Set default spam settings if none found on this target
        esf = Email.EmailSpamFilter(self._db)
        if tt_str in cereconf.EMAIL_DEFAULT_SPAM_SETTINGS:
            if not len(cereconf.EMAIL_DEFAULT_SPAM_SETTINGS[tt_str]) == 2:
                raise Errors.CerebrumError(
                    "Error in cereconf.EMAIL_DEFAULT_SPAM_SETTINGS. "
                    "Expected 'key': ('val', 'val')")
            l, a = cereconf.EMAIL_DEFAULT_SPAM_SETTINGS[tt_str]
            lvl = int(Email._EmailSpamLevelCode(l))
            act = int(Email._EmailSpamActionCode(a))
            try:
                esf.find(t_id)
            except Errors.NotFoundError:
                esf.clear()
                esf.populate(lvl, act, parent=email_target)
                esf.write_db()

    # exchange-relatert-jazz
    # after Exchange migration is completed this method should be
    # removed as it will no longer be necessary due to the Exchange
    # updates being event based. It may even be possible to remove the
    # method after Exchange roll-out and before migration is completed
    # if we are sure that no imap-accounts will be moved between
    # servers after roll-out. Jazz (2013-11)
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
        br.add_request(requestor, br.now, action, self.entity_id, destination,
                       state_data=state_data)

    # exchange-relatert-jazz
    # added a check for reservation from electronic listing
    def owner_has_e_reservation(self):
        # this method may be applied to any Cerebrum-instances that
        # use trait_public_reservation
        person = Factory.get('Person')(self._db)
        try:
            person.find(self.owner_id)
        except Errors.NotFoundError:
            # no reservation may exist unless account is owned by a
            # person-object
            return False
        return person.has_e_reservation()

    def populate(self, name, owner_type, owner_id, np_type, creator_id,
                 expire_date, description=None, parent=None):
        """Override to check that the account name is not already taken by a
        group.
        """
        gr = Factory.get('Group')(self._db)
        try:
            gr.find_by_name(name)
        except Errors.NotFoundError:
            pass
        else:
            raise self._db.IntegrityError('Account name taken by group: %s' %
                                          name)
        return self.__super.populate(name, owner_type, owner_id, np_type,
                                     creator_id, expire_date,
                                     description=description, parent=parent)

    # exchange-relatert-jazz
    # after Exchange roll-out this method should be removed as it will
    # no longer be necessary due to the server-data not being kept in
    # Cerebrum for Exchange mailboxes. This method must not be used at
    # restore of mailboxes after Exchange roll-out or at creation of
    # Exchange mailboxes. The method is made void by 'add_spread
    # override here. Jazz (2013-11)
    #
    def _UiO_update_email_server(self, server_type):
        """Due to diverse legacy stuff and changes in server types as
           well as requirements for assigning e-mail accounts this
           process is getting rather complicated. The email servers are
           now assigned as follows:

            - create on new server, update target_type = CNS
            - create on old server, update target_type = COS
            - move to new server   = MNS

       t_type/srv_type| none| cyrus, active| cyrus,non-active| non-cyrus
       ------------------------------------------------------------------
       target_deleted | CNS | COS          | CNS             | CNS
       ------------------------------------------------------------------
       target_account | MNS | PASS         | MNS             | MNS
       ------------------------------------------------------------------
        """

        et = Email.EmailTarget(self._db)
        es = Email.EmailServer(self._db)
        new_server = None
        old_server = None
        srv_is_cyrus = False
        email_server_in_use = False
        target_type = self.const.email_target_account
        # Find the account's EmailTarget
        try:
            et.find_by_target_entity(self.entity_id)
            if et.email_target_type == self.const.email_target_deleted:
                target_type = self.const.email_target_deleted
        except Errors.NotFoundError:
            # No EmailTarget found for account, creating one
            et.populate(self.const.email_target_account,
                        self.entity_id,
                        self.const.entity_account)
            et.write_db()
        # Find old server id and type
        try:
            old_server = et.email_server_id
            es.find(old_server)
            if es.email_server_type == self.const.email_server_type_cyrus:
                srv_is_cyrus = True
            email_server_in_use = es.get_trait(
                self.const.trait_email_server_weight)
        except Errors.NotFoundError:
            pass
        # Different actions for target_type deleted and account
        if target_type == self.const.email_target_account:
            if srv_is_cyrus and email_server_in_use:
                # both target and server type er ok, do nothing
                pass
            elif old_server is None:
                # EmailTarget with no registered server
                new_server = self._pick_email_server()
                et.email_server_id = new_server
                et.write_db()
                self._UiO_order_cyrus_action(self.const.bofh_email_create,
                                             new_server)
            else:
                # cyrus_nonactive or non_cyrus
                new_server = self._pick_email_server()
                et.email_server_id = new_server
                et.write_db()
        elif target_type == self.const.email_target_deleted:
            if srv_is_cyrus and email_server_in_use:
                # Create cyrus account on active server
                self._UiO_order_cyrus_action(self.const.bofh_email_create,
                                             old_server)
            else:
                # Pick new server and create cyrus account
                new_server = self._pick_email_server()
                et.email_server_id = new_server
                et.write_db()
                self._UiO_order_cyrus_action(self.const.bofh_email_create,
                                             new_server)
        return et

    # exchange-relatert-jazz
    # after Exchange roll-out this method should be removed as it will
    # no longer be necessary due to the server-data not being kept in
    # Cerebrum for Exchange mailboxes. See also
    # _UiO_update_email_server() Jazz (2013-11)
    #
    def _pick_email_server(self):
            # We try to spread the usage across servers, but want a
            # random component to the choice of server.  The choice is
            # weighted, although the determination of weights happens
            # externally to Cerebrum since it is a relatively
            # expensive operation (can take several seconds).
            # Typically the weight will vary with the amount of users
            # already assigned, the disk space available or similar
            # criteria.
            #
            # Servers MUST have a weight trait to be considered for
            # allocation.
        es = Email.EmailServer(self._db)
        user_weight = {}
        total_weight = 0
        for row in es.list_traits(self.const.trait_email_server_weight):
            total_weight += row['numval']
            user_weight[row['entity_id']] = row['numval']

        pick = random.randint(0, total_weight - 1)
        for svr_id in user_weight:
            pick -= user_weight[svr_id]
            if pick <= 0:
                break
        return svr_id

    def illegal_name(self, name):
        # Avoid circular import dependency
        from Cerebrum.modules.PosixUser import PosixUser

        if any(x.isupper() for x in name):
            return 'contains upper case letter(s) ({})'.format(name)

        if isinstance(self, PosixUser):
            # TODO: Kill the ARsystem user to limit range og legal characters
            if len(name) > 16:
                return "is too long (%s)" % name
            if re.search("^[^A-Za-z]", name):
                return "must start with a character (%s)" % name
            if re.search("[^A-Za-z0-9\-_]", name):
                return "contains illegal characters (%s)" % name
        return super(AccountUiOMixin, self).illegal_name(name)

    def validate_new_uname(self, domain, uname):
        """Check that the requested username is legal and free"""
        # TBD: will domain ever be anything else?
        if domain == self.const.account_namespace:
            ea = Email.EmailAddress(self._db)
            for row in ea.search(local_part=uname, filter_expired=False):
                return False
        return self.__super.validate_new_uname(domain, uname)

    # exchange-relatert-jazz
    # For Exchange mailboxes the use of GECOS is void and should be
    # dropped. After Exchange migration is completed, this override
    # may be dropped as using super will be sufficient. Jazz (2013-11)
    #
    def update_email_addresses(self):
        """Update an accounts email addresses and quotas."""
        spreads = [r['spread'] for r in self.get_spread()]
        if self.const.spread_uio_imap in spreads:
            # Make sure the email target of this account is associated
            # with an appropriate email server.  We must do this before
            # super, since without an email server, no target or address
            # will be created.
            self._UiO_update_email_server(self.const.email_server_type_cyrus)
            self.update_email_quota()
            return self.__super.update_email_addresses()
        elif self.const.spread_exchange_account in spreads:
            self.__super.update_email_addresses()
            # Append the default domain for exchange accounts! This should
            # probably be done elsewhere, but the code is so complex, that
            # we'll have to live with this solution, until we redesign the
            # email-module, or force the postmasters to write their own
            # address-management system.
            et = Factory.get('EmailTarget')(self._db)
            ea = Email.EmailAddress(self._db)
            ed = Email.EmailDomain(self._db)
            try:
                ed.find_by_domain(
                    cereconf.EXCHANGE_DEFAULT_ADDRESS_PLACEHOLDER)
                et.find_by_target_entity(self.entity_id)
            except Errors.NotFoundError:
                return
            else:
                try:
                    ea.find_by_local_part_and_domain(self.account_name,
                                                     ed.entity_id)
                except Errors.NotFoundError:
                    ea.populate(self.account_name, ed.entity_id, et.entity_id,
                                expire=None)
                    ea.write_db()
            return self.update_email_quota()

    def is_employee(self):
        for r in self.get_account_types():
            if r['affiliation'] == self.const.affiliation_ansatt:
                return True
        return False

    def wants_auth_type(self, method):
        if method == self.const.Authentication("PGP-guest_acc"):
            # only store this type for guest accounts
            return self.get_trait(self.const.trait_uio_guest_owner) is not None
        return self.__super.wants_auth_type(method)

    def clear_home(self, spread):
        """Remove disk quota before clearing home."""
        try:
            homeinfo = self.get_home(spread)
        except Errors.NotFoundError:
            pass
        else:
            dq = DiskQuota(self._db)
            dq.clear(homeinfo['homedir_id'])
        return self.__super.clear_home(spread)

    def _clear_homedir(self, homedir_id):
        # Since disk_quota has a FK to homedir, we need this override
        dq = DiskQuota(self._db)
        dq.clear(homedir_id)
        return self.__super._clear_homedir(homedir_id)

    def set_homedir(self, *args, **kw):
        """Remove quota information when the user is moved to a disk
        without quotas or where the default quota is larger than his
        existing explicit quota."""

        ret = self.__super.set_homedir(*args, **kw)
        if kw.get('current_id') and kw.get('disk_id'):
            disk = Factory.get("Disk")(self._db)
            disk.find(kw['disk_id'])
            has_quota = disk.has_quota()
            def_quota = disk.get_default_quota()
            dq = DiskQuota(self._db)
            try:
                info = dq.get_quota(kw['current_id'])
            except Errors.NotFoundError:
                pass
            else:
                if not has_quota:
                    # No quota on new disk, so remove the quota information.
                    dq.clear(kw['current_id'])
                elif def_quota is None:
                    # No default quota, so keep the quota information.
                    pass
                else:
                    if (info['override_expiration'] and
                            DateTime.now() < info['override_expiration']):
                        old_quota = info['override_quota']
                    else:
                        old_quota = info['quota']
                    if old_quota <= def_quota:
                        dq.clear(kw['current_id'])
        return ret

    def list_sysadm_accounts(self):
        """
        Return a list of account id for accounts the trait_sysadm_account trait
        """
        accounts = list()
        for row in self.list_traits(self.const.trait_sysadm_account):
            accounts.append(row['entity_id'])
        return accounts

    def _has_email_target(self):
        """
        Returns True if there is an EmailTarget for this account,
        False otherwise.
        """
        et = Email.EmailTarget(self._db)
        try:
            et.find_by_target_entity(self.entity_id)
        except Errors.NotFoundError:
            return False
        return True

    def is_passphrase(self, password):
        return ' ' in password

    def set_password(self, password):
        super(AccountUiOMixin, self).set_password(password)
        if self.is_passphrase(password):
            self.populate_trait(self.const.trait_has_passphrase,
                                self.entity_id)
        elif self.const.trait_has_passphrase in self.get_traits():
            self.delete_trait(self.const.trait_has_passphrase)
