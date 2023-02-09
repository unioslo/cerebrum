# -*- coding: utf-8 -*-
#
# Copyright 2023 University of Oslo, Norway
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
This module contains EntityExternalId related commands in bofhd.

.. important::
   These classes should not be used directly.  Always make subclasses of
   BofhdCommandBase classes, and add a proper auth class/mixin to the class
   authz.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import six

import cereconf

from Cerebrum.Constants import (
    _AuthoritativeSystemCode,
    _EntityExternalIdCode,
    _EntityTypeCode,
)
from Cerebrum.Entity import EntityExternalId
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.cmd_param import (Command, FormatSuggestion,
                                              SimpleString)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd.utils import BofhdUtils


logger = logging.getLogger(__name__)


def _get_id_type(const, value):
    return const.get_constant(_EntityExternalIdCode, value)


def _get_id_source(const, value):
    return const.get_constant(_AuthoritativeSystemCode, value)


def _get_entity_type(const, value):
    return const.get_constant(_EntityTypeCode, value)


class BofhdExtidAuth(BofhdAuth):
    """ Auth for entity contactinfo_* commands. """

    @property
    def visible_external_ids(self):
        """
        A set of external-ids that *anyone* can view.

        This is read from the ``cereconf.BOFHD_VISIBLE_EXTERNAL_IDS``, if
        available.
        """
        raw_external_ids = getattr(cereconf, "BOFHD_VISIBLE_EXTERNAL_IDS", ())
        return tuple(_get_id_type(self.const, value)
                     for value in raw_external_ids)

    def _get_accounts_owned_by(self, owner_id):
        account = Factory.get('Account')(self._db)
        return set(
            int(r['account_id'])
            for r in account.list_accounts_by_owner_id(int(owner_id)))

    def can_get_extid(self, operator, entity=None, id_type=None,
                      query_run_any=False):
        """
        Check if an operator is allowed to see external id.

        :param int operator: entity_id of the authenticated user
        :param entity: A cerebrum entity object (e.g. person, account)
        :param id_type: An EntityExternalId constant
        """
        if query_run_any:
            return True

        if self.is_superuser(operator.get_entity_id()):
            return True

        # id_type is visible to all operators
        id_const = _get_id_type(self.const, id_type)
        if id_const in self.visible_external_ids:
            return True

        entity_type = _get_entity_type(self.const, entity.entity_type)
        # All orgunit ids are visible to all operators, regarless of listing in
        # visible_external_ids
        if entity_type == self.const.entity_ou:
            return True

        if entity_type == self.const.entity_person:
            # Operator can view all external ids from the operator account
            # owner object (as long as it's a personal account)
            account_ids = self._get_accounts_owned_by(entity.entity_id)
            if operator.get_entity_id() in account_ids:
                return True

        if entity_type == self.const.entity_account:
            # Operator can view all external ids for the operator account
            if operator.get_entity_id() == entity.entity_id:
                return True

            # If operator account is a personal account, then operator can view
            # all external ids for other accounts owned by the operator.
            if entity.owner_type == self.const.entity_person:
                account_ids = self._get_accounts_owned_by(entity.owner_id)
                if operator.get_entity_id() in account_ids:
                    return True

        # Can view attribute if operator has access view the given id-type
        # through an op-set.
        op_attr = six.text_type(id_const)
        if self._has_target_permissions(
                operator.get_entity_id(),
                self.const.auth_view_external_id,
                self.const.auth_target_type_global_person,
                None, None,
                operation_attr=op_attr):
            return True

        raise PermissionDenied(
            "No permission to view id-type %s for entity type=%s, id=%d"
            % (op_attr, entity_type, entity.entity_id))

    def can_list_extid(self, operator, entity=None, query_run_any=False):
        """
        Check if an operator is allowed to list external id types.

        :param int operator: entity_id of the authenticated user
        :param entity: A cerebrum entity object (e.g. person, account)
        """
        # Allow everyonw access to list which id types are set for a given
        # entity
        return True

        # if query_run_any:
        #     return True

        # if self.is_superuser(operator.get_entity_id()):
        #     return True
        entity_type = _get_entity_type(self.const, entity.entity_type)
        raise PermissionDenied(
            "No permission to list id-types for entity type=%s, id=%d"
            % (entity_type, entity.entity_id))

    def can_set_extid(self, operator,
                      entity=None, id_type=None, source_system=None,
                      query_run_any=False):
        """
        Check if an operator is allowed to set external id.

        :param int operator: entity_id of the authenticated user
        :param entity: A cerebrum entity object (e.g. person, account)
        :param id_type: An EntityExternalId constant
        :param source_system: An AuthoritativeSystem constant
        """
        if query_run_any:
            return True
        # TODO: We probably want something like:
        # if query_run_any:
        #     return self._has_operation_perm_somewhere(
        #         operator, self.const.auth_foo)
        # ... if we ever set up an op-code for setting external-id

        if self.is_superuser(operator.get_entity_id()):
            return True

        id_const = _get_id_type(self.const, id_type)
        sys_const = _get_id_source(self.const, source_system)
        entity_type = _get_entity_type(entity.entity_type)

        op_attr = "{}:{}".format(six.text_type(sys_const),
                                 six.text_type(id_const))
        # Should we check for op-attrs with wildcards?  That way we could e.g.
        # create an op-set "greg-admin", and allow access to all external-ids
        # set from Greg (i.e.: "GREG:*")
        # op_attrs = [
        #     "{}:*".format(six.text_type(sys_const)),
        #     "*:{}".format(six.text_type(id_const)),
        #     op_attr,
        # ]

        # Check for target permissions if we ever get an op-code for it
        # if self._has_target_permissions(
        #         operator.get_entity_id(),
        #         self.const.auth_foo,
        #         self.const.auth_target_type_global_person,
        #         None, None,
        #         operation_attr=op_attr):
        #     return True

        raise PermissionDenied(
            "No permission to set id-type %s for entity type=%s, id=%d"
            % (op_attr, entity_type, entity.entity_id))

    def can_clear_extid(self, operator,
                        entity=None,
                        id_type=None,
                        source_system=None,
                        query_run_any=False):
        """
        Check if an operator is allowed to set external id.

        :param int operator: entity_id of the authenticated user
        :param entity: A cerebrum entity object (e.g. person, account)
        :param id_type: An EntityExternalId constant
        :param source_system: An AuthoritativeSystem constant
        """
        if query_run_any:
            return True

        if self.is_superuser(operator.get_entity_id()):
            return True

        id_const = _get_id_type(self.const, id_type)
        sys_const = _get_id_source(self.const, source_system)
        entity_type = _get_entity_type(entity.entity_type)
        op_attr = "{}:{}".format(six.text_type(sys_const),
                                 six.text_type(id_const))

        # TODO: See can_set_extid for how we'd want to implement op-set/op-code
        # checks

        raise PermissionDenied(
            "No permission to clear id-type %s for entity type=%s, id=%d"
            % (op_attr, entity_type, entity.entity_id))


CMD_HELP = {
    'entity': {
        'entity_extid_get': 'show external id for an entity',
        'entity_extid_set': 'set an external id for an entity',
        'entity_extid_clear': 'clear an external id from an entity',
    },
}

CMD_ARGS = {
    'entity-extid-source': [
        'entity-extid-source',
        'Enter source system',
        'Name of a source system for the external-id type.',
    ],
    'entity-extid-type': [
        'entity-extid-type',
        'Enter external id type',
        'The name of an external-id type.',
    ],
    'entity-extid-value': [
        'entity-extid-value',
        'Enter external-id value',
        'Enter a valid external-id value',
    ],
}


class BofhdExtidCommands(BofhdCommandBase):

    all_commands = {}
    authz = BofhdExtidAuth
    default_source_system = 'Manual'

    @property
    def util(self):
        # TODO: Or should we inherit from BofhdCommonMethods?
        #       We're not really interested in user_delete, etc...
        try:
            return self.__util
        except AttributeError:
            self.__util = BofhdUtils(self.db)
            return self.__util

    def _normalize_id(self, id_source, id_type, id_value):
        """
        Validate and normalize external id.

        :type id_source: _AuthoritativeSystemCode
        :type id_type: _EntityExternalIdCode
        :type id_value: str

        :throws CerebrumError:
            Throws a bofhd client error if the given external id is not valid.
        """
        return id_value

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        # look up types
        co = Factory.get('Constants')()
        source_systems = co.fetch_constants(_AuthoritativeSystemCode)
        id_types = co.fetch_constants(_EntityExternalIdCode)

        # Enrich cmd_args with actual constants.
        # TODO: Find a better way to do this for all similar cmd_args
        cmd_args = {}
        list_sep = '\n - '
        for k, v in CMD_ARGS.items():
            cmd_args[k] = v[:]
            if k == 'entity-extid-source':
                cmd_args[k][2] += '\nSource systems:'
                cmd_args[k][2] += list_sep + list_sep.join(six.text_type(c) for
                                                           c in source_systems)
            if k == 'entity-extid-type':
                cmd_args[k][2] += '\nExternal-id types:'
                cmd_args[k][2] += list_sep + list_sep.join(six.text_type(c) for
                                                           c in id_types)
        del co

        return merge_help_strings(
            ({}, {}, cmd_args),  # We want _our_ cmd_args to win!
            get_help_strings(),
            ({}, CMD_HELP, {}))

    #
    # entity extid_set <entity> <id-type> <id-value> [id-source]
    #
    all_commands['entity_extid_set'] = Command(
        ('entity', 'extid_set'),
        SimpleString(help_ref='id:target:entity'),
        SimpleString(help_ref='entity-extid-type'),
        SimpleString(help_ref='entity-extid-value'),
        SimpleString(help_ref='entity-extid-source', optional=True),
        fs=FormatSuggestion(
            "Set external id %s:%s to '%s' for %s with id=%d",
            ('id_source', 'id_type', 'id_value', 'entity_type', 'entity_id')
        ),
        perm_filter='can_set_extid',
    )

    def entity_extid_set(self, operator, entity_target,
                         _id_type, _id_value,
                         _id_source=default_source_system):
        """ Set external id for an entity. """
        # get entity object
        entity = self.util.get_target(entity_target, restrict_to=[])
        entity_type = _get_entity_type(self.const, entity.entity_type)

        # Check for support
        if not isinstance(entity, EntityExternalId):
            raise CerebrumError("No support for external id in %s entity"
                                % (entity_type,))

        # Normalize/validate user input
        id_source = _get_id_source(self.const, _id_source)
        id_type = _get_id_type(self.const, _id_type)
        id_value = self._normalize_id(id_source, id_type, _id_value)

        if id_type.entity_type != entity_type:
            raise CerebrumError(
                "Can't set id-type %s for entity of type %s (expected %s)"
                % (id_type, entity_type, id_type.entity_type))

        # Check permissions
        self.ba.can_set_extid(operator,
                              entity=entity, id_type=id_type,
                              source_system=id_source)

        # Check if the given id-type/id-value has been given to another entity.
        # If so, it needs to be cleared from that entity first...
        other_owners = set(
            row['entity_id']
            for row in entity.search_external_ids(id_type=id_type,
                                                  external_id=id_value)
            if row['entity_id'] != entity.entity_id)
        if other_owners:
            raise CerebrumError(
                "Can't set id-type %s for entity id %d - assigned to ids: %s"
                % (six.text_type(id_type), entity.entity_id,
                   repr(tuple(sorted(other_owners)))))

        # Check if this entity already has the given id-type with another
        # id-value
        other_values = set(
            row['external_id']
            for row in entity.search_external_ids(
                entity_id=int(entity.entity_id),
                id_type=id_type)
            if row['external_id'] != id_value)
        if other_values:
            logger.warning("Entity id=%r already has a %s set to another value"
                           % (entity.entity_id, six.text_type(id_type)))

        logger.debug("Adding external id: %r, %r, %r, %r",
                     entity.entity_id,
                     six.text_type(id_source),
                     six.text_type(id_type),
                     id_value)

        entity.affect_external_id(id_source, id_type)
        entity.populate_external_id(id_source, id_type, id_value)
        entity.write_db()

        return {
            'id_source': six.text_type(id_source),
            'id_type': six.text_type(id_type),
            'id_value': six.text_type(id_value),
            'entity_type': six.text_type(entity_type),
            'entity_id': int(entity.entity_id),
        }

    #
    # entity extid_clear <entity> <id-type> [id-source]
    #
    all_commands['entity_extid_clear'] = Command(
        ('entity', 'extid_clear'),
        SimpleString(help_ref='id:target:entity'),
        SimpleString(help_ref='entity-extid-type'),
        SimpleString(help_ref='entity-extid-source', optional=True),
        fs=FormatSuggestion(
            "Cleared external id %s:%s from %s with id=%d",
            ('id_source', 'id_type', 'entity_type', 'entity_id')
        ),
        perm_filter='can_clear_extid',
    )

    def entity_extid_clear(self, operator, entity_target,
                           _id_type, _id_source=default_source_system):
        """ Clear external id for an entity. """
        # get entity object
        entity = self.util.get_target(entity_target, restrict_to=[])
        entity_type = self.const.EntityType(int(entity.entity_type))

        # Check for support
        if not isinstance(entity, EntityExternalId):
            raise CerebrumError("No support for external id in %s entity"
                                % six.text_type(entity_type))

        # Normalize/validate user input
        id_source = _get_id_source(self.const, _id_source)
        id_type = _get_id_type(self.const, _id_type)

        if id_type.entity_type != entity_type:
            raise CerebrumError(
                "Can't clear id-type %s for entity of type %s (expected %s)"
                % (id_type, entity_type, id_type.entity_type))

        # Check permissions
        self.ba.can_clear_extid(operator,
                                entity=entity, id_type=id_type,
                                source_system=id_source)

        logger.debug('Removing external id: %r, %r, %r',
                     entity.entity_id,
                     six.text_type(id_source),
                     six.text_type(id_type))

        entity.affect_external_id(id_source, id_type)
        entity.write_db()

        return {
            'id_source': six.text_type(id_source),
            'id_type': six.text_type(id_type),
            'entity_type': six.text_type(entity_type),
            'entity_id': int(entity.entity_id),
        }

    #
    # entity extid_get <entity> <id-type> [id-source]
    #
    all_commands['entity_extid_get'] = Command(
        ("entity", "extid_get"),
        SimpleString(help_ref='id:target:entity'),
        SimpleString(help_ref='entity-extid-type'),
        SimpleString(help_ref='entity-extid-source', optional=True),
        fs=FormatSuggestion(
            "%-15s %-15s %s", ('id_source', 'id_type', 'id_value'),
            hdr="%-15s %-15s %s" % ('Source', 'Type', 'Value'),
        ),
        perm_filter='can_get_extid',
    )

    def entity_extid_get(self, operator, entity_target, _id_type,
                         _id_source=None):
        """ Show external id for an entity. """
        entity = self.util.get_target(entity_target, restrict_to=[])
        entity_type = self.const.EntityType(int(entity.entity_type))
        id_db = EntityExternalId(self.db)

        # Normalize/validate user input
        if _id_source:
            id_source = _get_id_source(self.const, _id_source)
        else:
            id_source = None
        id_type = _get_id_type(self.const, _id_type)

        if id_type.entity_type != entity_type:
            raise CerebrumError(
                "Can't get id-type %s for entity of type %s (expected %s)"
                % (id_type, entity_type, id_type.entity_type))

        self.ba.can_get_extid(operator, entity=entity, id_type=id_type)

        results = []
        for row in id_db.search_external_ids(entity_id=int(entity.entity_id),
                                             id_type=id_type,
                                             source_system=id_source):
            results.append({
                'id_source': six.text_type(
                    _get_id_source(self.const, row['source_system'])),
                'id_type': six.text_type(
                    _get_id_type(self.const, row['id_type'])),
                'id_value': six.text_type(row['external_id']),
                'entity_type': six.text_type(entity_type),
                'entity_id': int(entity.entity_id),
            })

        if not results:
            raise CerebrumError("No external id of type %s for: %s"
                                % (six.text_type(id_type),
                                   repr(entity_target)))

        return results

    #
    # entity extid_list <entity>
    #
    all_commands['entity_extid_list'] = Command(
        ("entity", "extid_list"),
        SimpleString(help_ref='id:target:entity'),
        fs=FormatSuggestion(
            "%-15s %-15s", ('id_source', 'id_type'),
            hdr="%-15s %-15s" % ('Source', 'Type'),
        ),
        perm_filter='can_list_extid',
    )

    def entity_extid_list(self, operator, entity_target):
        """ List external id types for an entity. """
        entity = self.util.get_target(entity_target, restrict_to=[])
        entity_type = self.const.EntityType(int(entity.entity_type))
        id_db = EntityExternalId(self.db)

        # Normalize/validate user input
        self.ba.can_list_extid(operator, entity=entity)

        results = []
        for row in id_db.search_external_ids(entity_id=int(entity.entity_id)):
            results.append({
                'id_source': six.text_type(
                    _get_id_source(self.const, row['source_system'])),
                'id_type': six.text_type(
                    _get_id_type(self.const, row['id_type'])),
                'entity_type': six.text_type(entity_type),
                'entity_id': int(entity.entity_id),
            })

        if not results:
            raise CerebrumError("No external ids for: %s"
                                % repr(entity_target))

        return results
