#!/usr/bin/env python2
# encoding: utf-8
#
# Copyright 2015 University of Oslo, Norway
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
u""" This is an auth module for use with bofhd_consent_cmds. """

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import auth
from Cerebrum.modules.bofhd.errors import PermissionDenied


class BofhdAuth(auth.BofhdAuth):
    u""" Methods to control command access. """

    def _get_operator_account(self, operator):
        u""" Get the operator account.

        :param int operator: The operator entity_id.

        :return Cerebrum.Account: The operator account.

        """
        account = Factory.get('Account')(self._db)
        account.find(operator)
        return account

    def is_entity(self, operator, entity):
        u""" Checks if operator is entity.

        :param int operator: The operator entity_id
        :param Cerebrum.Entity entity: The entity to check.

        :return bool:
            True if operator has the same entity_id as entity.

        """
        op_acc = self._get_operator_account(operator)
        return op_acc.entity_id == getattr(entity, 'entity_id', None)

    def is_entity_owner(self, operator, entity):
        u""" Checks if operator is the owner of entity.

        :param int operator: The operator entity_id
        :param Cerebrum.Entity entity: The entity to check.

        :return bool:
            True if operator is the owner_id of entity.

        """
        op_acc = self._get_operator_account(operator)
        return op_acc.entity_id == getattr(entity, 'owner_id', None)

    def is_owned_by_entity(self, operator, entity):
        u""" Checks if entity is the owner of operator.

        :param int operator: The operator entity_id
        :param Cerebrum.Entity entity: The entity to check.

        :return bool:
            True if entity is the owner_id of operator.

        """
        op_acc = self._get_operator_account(operator)
        return op_acc.owner_id == getattr(entity, 'entity_id', None)

    def can_set_consent(self, operator, entity=None, query_run_any=False):
        u""" Checks if operator can set consent for entity.

        :param int operator:
            The operator entity_id.
        :param Cerebrum.Entity entity:
            The entity to check.
        :param bool query_run_any:
            If client is fetching list of allowed commands.

        :return bool: True if authorization is granted.

        :raise PermissionDenied: If authorization is denied.

        """
        if query_run_any:
            return True  # Should be available to everyone

        if self.is_entity(operator, entity):
            return True
        if self.is_entity_owner(operator, entity):
            return True
        if self.is_owned_by_entity(operator, entity):
            return True
        raise PermissionDenied(
            "Not allowed to see or change consent on this %s (entity_id=%s)." %
            (self.const.EntityType(entity.entity_type), entity.entity_id))

    def can_unset_consent(self, operator, entity=None, query_run_any=False):
        u""" Checks if operator can remove consent for entity.

        :param int operator:
            The operator entity_id.
        :param Cerebrum.Entity entity:
            The entity to check.
        :param bool query_run_any:
            If client is fetching list of allowed commands.

        :return bool: True if authorization is granted.

        :raise PermissionDenied: If authorization is denied.

        """
        # The same rules should apply to unsetting:
        return self.can_set_consent(operator,
                                    entity=entity,
                                    query_run_any=query_run_any)

    def can_show_consent_info(
            self, operator, entity=None, query_run_any=False):
        u""" Checks if operator can list consents set for entity.

        :param int operator:
            The operator entity_id.
        :param Cerebrum.Entity entity:
            The entity to check.
        :param bool query_run_any:
            If client is fetching list of allowed commands.

        :return bool: True if authorization is granted.

        :raise PermissionDenied: If authorization is denied.

        """
        if self.is_superuser(operator, query_run_any=query_run_any):
            return True
        # The same rules should apply to viewing:
        return self.can_set_consent(operator,
                                    entity=entity,
                                    query_run_any=query_run_any)

    def can_list_consents(self, operator, query_run_any=False):
        u""" Checks if operator can list all consent types. """
        return True

if __name__ == '__main__':
    del cereconf
