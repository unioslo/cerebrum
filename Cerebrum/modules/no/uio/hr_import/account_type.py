# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
Update account_types (acccunt affiliations) from person affiliation changes.

The intention is to keep Person affiliations in sync with the persons primary
account account_types.

We can only sync affiliations if:

1. The person only owns *one* account.
2. That account is/was only used for *a similar purpose*.  E.g. we *only*
   update employee account_types if the account is *only* used as an employee
   account (i.e. has account_types of a given affiliation from a given source
   system).

In all other cases, any attempt to automatically assign account_type will
likely end up doing the wrong thing.
"""
import logging

from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)


class _UpdateError(RuntimeError):
    pass


class AccountTypeUpdater(object):
    """
    Account type updater.

    ::

        ansatt = PersonAffiliation('ANSATT')
        tekadm = PersonAffStatus('tekadm')
        sap = AuthoritativeSystem('SAP')
        ac_type_update = AccountTypeUpdater(db, ansatt, sap)

        ac_type_update(person,
                       added=[(ansatt, tekadm, 3)]
                       removed=[(ansatt, tekadm, 4), (ansatt, tekadm, 5)])

    """

    def __init__(self, database, restrict_affiliation, restrict_source):
        """
        :param database:

        :param PersonAffiliation restrict_affiliation:
            Restrict account_types to this affiliation.  We will not touch an
            account if any of the account_types are of another affiliation
            type.

        :param AuthoritativeSystem restrict_source:
            Restrict account_types to affiliations backed by this source
            system.  We will not touch an account if any of the account_types
            are currently maintained from other source systems.
        """
        self.db = database
        self.restrict_affiliation = restrict_affiliation
        self.restrict_source = restrict_source

    @property
    def const(self):
        if not hasattr(self, '_const'):
            self._const = Factory.get('Constants')(self.db)
        return self._const

    def _get_account(self, person):
        """
        Find an appropriate account to target.

        :account to consider for automatic update.
        """
        accounts = person.get_accounts()
        if len(accounts) != 1:
            raise _UpdateError(
                'Person id=%r has %d accounts (expected 1)' %
                (person.entity_id, len(accounts)))
        ac = Factory.get('Account')(self.db)
        ac.find(accounts[0]['account_id'])

        return ac

    def _get_account_types(self, account):
        """
        Get and verify existing account_types for an owner/account.
        """
        account_id = account.entity_id
        account_types = account.get_account_types()

        # Verify that the account doesn't have any incompatible account_types
        for account_type in account_types:
            if account_type['affiliation'] != int(self.restrict_affiliation):
                raise _UpdateError(
                    'account_id=%r has affiliation(s) besides %r' %
                    (account_id, self.restrict_affiliation))

        # Verify that all account_types that *are* backed by a *real*
        # affiliation is from the given source_system.
        pe = Factory.get('Person')(self.db)
        for account_type in account_types:
            try:
                aff_info = pe.list_affiliations(
                    person_id=account_type['person_id'],
                    ou_id=account_type['ou_id'],
                    affiliation=account_type['affiliation'],
                )[0]
            except IndexError:
                # The owner doesn't have this affiliation - we don't really
                # care about the source system if the affiliation is obsolete.
                continue
            if aff_info['source_system'] != int(self.restrict_source):
                raise _UpdateError(
                    'account_id=%r has affiliation(s) from source(s) '
                    'besides %r' % (account_id, self.restrict_sources))

        return account_types

    def _clear_account_type(self, account, account_types, affiliation, ou_id):
        # Verify that the account will remain with at least *one* account type
        if len(account_types) == 1:
            raise _UpdateError(
                'cannot delete last account_type for account_id=%r',
                account.entity_id)

        # Verify that the account_type actually exists
        if not account.list_accounts_by_type(
                ou_id=ou_id,
                affiliation=affiliation,
                account_id=account.entity_id):
            raise _UpdateError(
                'account_id=%r has no account_type %r@%r',
                account.entity_id, affiliation, ou_id)

        logger.info('Clearing account_id=%r type %r@%r',
                    account.entity_id, affiliation, ou_id)
        account.set_account_type(ou_id, affiliation)

    def _set_account_type(self, account, account_types, affiliation, ou_id):
        for at in account_types:
            if at['ou_id'] == ou_id and at['affiliation'] == affiliation:
                raise _UpdateError(
                    'account_id=%r already has type %r@%r',
                    account.entity_id, affiliation, ou_id)

        logger.info('Setting account_id=%r type %r@%r',
                    account.entity_id, affiliation, ou_id)
        account.set_account_type(ou_id, affiliation)

    def sync(self, person, added, removed):

        try:
            account = self._get_account(person)
        except _UpdateError as e:
            logger.info('No accounts to sync for person_id=%r: %s',
                        person.entity_id, e)
            return

        try:
            account_types = self._get_account_types(account)
        except _UpdateError as e:
            logger.info('Incompatible account_types person_id=%r: %s',
                        person.entity_id, e)
            return

        for affiliation, status, ou_id in removed:
            try:
                self._clear_account_type(account, account_types, affiliation,
                                         ou_id)
            except _UpdateError as e:
                logger.info(
                    'Unable to clear account_type for person_id=%r: %s',
                    person.entity_id, e)

        for affiliation, status, ou_id in added:
            try:
                self._set_account_type(account, account_types, affiliation,
                                       ou_id)
            except _UpdateError as e:
                logger.info(
                    'Unable to set account_type for person_id=%r: %s',
                    person.entity_id, e)
