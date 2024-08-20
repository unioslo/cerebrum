# -*- coding: utf-8 -*-
#
# Copyright 2014-2024 University of Oslo, Norway
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
This module implenents access control for personal guest commands.

.. important::
   Remember to implement a new command class with a subclassed auth-class for
   actual use.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import six

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import auth
from Cerebrum.modules.bofhd.errors import PermissionDenied

logger = logging.getLogger(__name__)


def _get_guest_owner_id(account):
    """ Get the owner_id (sponsor) of a personal guest account. """
    const = account.const
    return int(account.get_trait(const.trait_guest_owner)['target_id'])


def _get_guest_name(account):
    """ Get name of the guest from a personal guest account. """
    const = account.const
    return account.get_trait(const.trait_guest_name)['strval']


def _is_guest_account(account):
    """ Check if an account object is a personal guest account. """
    const = account.const

    if account.np_type != const.account_guest:
        return False

    try:
        _get_guest_owner_id(account)
        _get_guest_name(account)
    except Exception:
        logger.warning(
            "Account %s (%d) has np_type=%s, but missing guest traits",
            account.account_name, account.entity_id,
            six.text_type(const.account_guest),
        )
        return False

    return True


class BofhdGuestAuth(auth.BofhdAuth):
    """ Methods to control command access. """

    def _is_employee(self, operator_id):
        """ Check if operator is an employee. """
        pe = Factory.get('Person')(self._db)
        for row in pe.list_affiliations(
                person_id=int(operator_id),
                affiliation=int(self.const.affiliation_ansatt)):
            return True
        return False

    def _is_personal_guest_owner(self, operator_id, guest):
        """ Check if operator is the owner of guest. """
        if not _is_guest_account(guest):
            return False
        if operator_id == guest.entity_id:
            return True
        if not self._is_employee(operator_id):
            return False
        try:
            return operator_id == _get_guest_owner_id(guest)
        except Exception:
            return False

    def can_view_personal_guest(self, operator_id,
                                guest=None, query_run_any=False):
        """ Check if *operator_id* has access to see info about *guest*. """
        if self.is_superuser(operator_id):
            return True
        if query_run_any:
            # Employees should have access to the command
            if self._is_employee(operator_id):
                return True
            # The guest should have access to the command
            ac = Factory.get('Account')(self._db)
            ac.find(operator_id)
            if _is_guest_account(ac):
                return True
            return False

        if self._is_personal_guest_owner(operator_id, guest):
            return True
        raise PermissionDenied("No permission to show guest account %s"
                               % (guest.account_name,))

    def can_create_personal_guest(self, operator_id, query_run_any=False):
        """ Check if *operator_id* can create new personal guest accounts. """
        if self.is_superuser(operator_id):
            return True
        if self._is_employee(operator_id):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("No permission to create guest accounts")

    def can_reset_guest_password(self, operator_id,
                                 guest=None, query_run_any=False):
        """ Check if *operator_id* has access to reset password for *guest*."""
        if self.is_superuser(operator_id):
            return True
        if query_run_any:
            return self._is_employee(operator_id)

        if not _is_guest_account(guest):
            raise PermissionDenied("Account %s is not a guest account"
                                   % (guest.account_name,))

        if self._is_personal_guest_owner(operator_id, guest):
            return True

        raise PermissionDenied(
            "No permission to reset password for guest account %s"
            % (guest.account_name))

    def can_remove_personal_guest(self, operator_id, guest=None,
                                  query_run_any=False):
        """ Check if *operator_id* has access to remove *guest*. """
        if self.is_superuser(operator_id):
            return True
        if query_run_any:
            return self._is_employee(operator_id)

        # The account _must_ be a guest, regardless of op
        if not _is_guest_account(guest):
            raise PermissionDenied("Account %s is not a guest account"
                                   % (guest.account_name,))

        if (self._is_employee(operator_id)
                and self._is_personal_guest_owner(operator_id, guest)):
            return True

        raise PermissionDenied("No permission to remove guest account %s"
                               % (guest.account_name,))
