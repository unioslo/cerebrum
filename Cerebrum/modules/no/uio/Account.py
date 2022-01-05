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
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.Utils import Factory


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
        if spread == self.const.spread_ifi_nis_user:
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
            raise self._db.IntegrityError(
                  "Can't remove uio spread to an account with ifi spread.")

        if (spread == self.const.spread_ifi_nis_user or
                spread == self.const.spread_uio_nis_user):
            self.clear_home(spread)

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
        validate_domains = self.get_validate_domains()[1:]
        if not self.is_valid_new_uname(name, domains=validate_domains):
            raise self._db.IntegrityError('Account name not available: %s' %
                                          name)
        return self.__super.populate(name, owner_type, owner_id, np_type,
                                     creator_id, expire_date,
                                     description=description, parent=parent)

    def get_validate_domains(self):
        domains = super(AccountUiOMixin, self).get_validate_domains()
        domains.append(self.const.group_namespace)
        return domains

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

    def is_employee(self):
        for r in self.get_account_types():
            if r['affiliation'] == self.const.affiliation_ansatt:
                return True
        return False

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
