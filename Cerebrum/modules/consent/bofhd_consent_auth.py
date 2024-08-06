# encoding: utf-8
#
# Copyright 2015-2024 University of Oslo, Norway
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
Auth implementation for mod:`.bofhd_consent_cmds`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import auth
from Cerebrum.modules.bofhd.errors import PermissionDenied


def _get_account_by_id(db, account_id):
    account = Factory.get('Account')(db)
    account.find(account_id)
    return account


class BofhdConsentAuth(auth.BofhdAuth):
    """ Methods to control command access. """

    def _can_modify_consent(self, operator_id, entity):
        """ Check if operator can modify consents for entity.  """
        curr_user = _get_account_by_id(self._db, operator_id)

        if curr_user.entity_id == entity.entity_id:
            return True

        if curr_user.entity_id == getattr(entity, "owner_id", None):
            return True

        if curr_user.owner_id == entity.entity_id:
            return True

        raise PermissionDenied(
            "Not allowed to see or change consent on this %s (id=%s)"
            % (self.const.EntityType(entity.entity_type), entity.entity_id))

    def can_set_consent(self, operator, entity=None, query_run_any=False):
        """
        Checks if operator can set consent for entity.

        :param int operator: entity_id of operator
        :param Cerebrum.Entity entity: entity object to check
        :param bool query_run_any: to check if command should be listed

        :return bool: True if authorization is granted
        :raise PermissionDenied: If authorization is denied
        """
        if query_run_any:
            # Command is available to everyone
            return True
        return self._can_modify_consent(operator, entity)

    def can_unset_consent(self, operator, entity=None, query_run_any=False):
        """
        Checks if operator can remove consent for entity.

        :param int operator: entity_id of operator
        :param Cerebrum.Entity entity: entity object to check
        :param bool query_run_any: to check if command should be listed

        :return bool: True if authorization is granted
        :raise PermissionDenied: If authorization is denied
        """
        if query_run_any:
            # Command is available to everyone
            return True
        return self._can_modify_consent(operator, entity)

    def can_show_consent_info(self, operator, entity=None,
                              query_run_any=False):
        """
        Checks if operator can list consents set for entity.

        :param int operator: entity_id of operator
        :param Cerebrum.Entity entity: entity object to check
        :param bool query_run_any: to check if command should be listed

        :return bool: True if authorization is granted
        :raise PermissionDenied: If authorization is denied
        """
        if query_run_any:
            # Command is available to everyone
            return True
        if self.is_superuser(operator, query_run_any=query_run_any):
            return True
        return self._can_modify_consent(operator, entity)

    def can_list_consents(self, operator, query_run_any=False):
        """ Checks if operator can list all consent types. """
        return True
