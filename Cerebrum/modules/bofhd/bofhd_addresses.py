# -*- coding: utf-8 -*-
#
# Copyright 2025-2026 University of Oslo, Norway
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
This module implements entity address related commands in bofhd.

.. important::
    Remember to subclass commands to mixin local authz classes.

TODO
=====
This is a simple, initial module, and the commands here are work-in-progress.
It mainly exists for debugging by superusers.  For a more general purpose
module, we should add more fine-grained authz, as well as commands like:

- entity address_show <entity> <addr-type> -- show address of a given type

- entity address_search <search-params> -- search for entities with given
  address data.  We need to implement new queries to allow for this.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging
import json
import textwrap

import six

from Cerebrum.Constants import (
    _AddressCode,
    _AuthoritativeSystemCode,
    _EntityTypeCode,
)
from Cerebrum.Entity import EntityAddress
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    # FormatSuggestion,
    SimpleString,
    get_format_suggestion_table,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd.utils import BofhdUtils


logger = logging.getLogger(__name__)


def _get_constant(constants_base, constant_type, value, user_input_hint,
                  optional):
    if optional and not value and value != 0:
        return None
    try:
        return constants_base.get_constant(constant_type, value)
    except LookupError:
        if user_input_hint:
            raise CerebrumError("Invalid %s: %s" %
                                (user_input_hint, repr(value)))
        raise


def _get_address_type(const, value, user_input=False, optional=False):
    """ Get an address type constant.  """
    return _get_constant(const, _AddressCode, value,
                         "address type" if user_input else None, optional)


def _get_source_system(const, value, user_input=False, optional=False):
    """ Get a source system constant. """
    return _get_constant(const, _AuthoritativeSystemCode, value,
                         "source system" if user_input else None, optional)


def _get_entity_type(const, value, user_input=False, optional=False):
    """ Get an entity type constant. """
    return _get_constant(const, _EntityTypeCode, value,
                         "entity type" if user_input else None, optional)


class BofhdAddressAuth(BofhdAuth):
    """ Auth for entity address_* commands. """

    def _get_personal_accounts(self, entity):
        if (entity.entity_type == self.const.entity_account
                and entity.owner_type == self.const.entity_person):
            owner_id = entity.owner_id
        elif entity.entity_type == self.const.entity_person:
            owner_id = entity.entity_id
        else:
            return set()

        account = Factory.get('Account')(self._db)
        return set(
            int(r['account_id'])
            for r in account.list_accounts_by_owner_id(int(owner_id)))

    def _is_owned_by_operator(self, operator_id, entity):
        if entity.entity_type == self.const.entity_account:
            if operator_id == entity.entity_id:
                return True

        if operator_id in self._get_personal_accounts(entity):
            return True

        return False

    def can_list_addresses(self, operator,
                           entity=None,
                           query_run_any=False):
        """
        Check if an operator is allowed to list address types.

        :param int operator: entity_id of the authenticated user
        :param entity: A cerebrum entity object (e.g. person, ou)
        """
        if self.is_superuser(operator):
            return True

        # Only superusers, for now
        if query_run_any:
            return False
            # return True

        # if entity.entity_type == self.const.entity_ou:
        #     return True

        # if self._is_owned_by_operator(operator, entity):
        #     return True

        entity_type = _get_entity_type(self.const, entity.entity_type)

        raise PermissionDenied(
            "Not allowed to see addresses for entity type=%s, id=%d"
            % (entity_type, entity.entity_id))

    def can_get_address(self, operator,
                        entity=None,
                        address_type=None,
                        query_run_any=False):
        """
        Check if an operator is allowed to show address data.

        :param int operator: entity_id of the authenticated user
        :param entity: A cerebrum entity object (e.g. person, ou)
        :param address_type: An Address constant
        """
        try:
            return self.can_list_addresses(operator, entity=entity,
                                           query_run_any=query_run_any)
        except PermissionDenied:
            pass

        entity_type = _get_entity_type(self.const, entity.entity_type)
        address_type = _get_address_type(self.const, address_type)
        raise PermissionDenied(
            "Not allowed to see address type %s for entity type=%s, id=%d"
            % (address_type, entity_type, entity.entity_id))

    def get_allowed_address_types(self, operator_id, entity):
        """
        Helper to list allowed address types for a given entity.
        """
        for address_type in self.const.fetch_constants(_AddressCode):
            try:
                self.can_get_address(operator_id, entity=entity,
                                     address_type=address_type)
                yield address_type
            except PermissionDenied:
                continue


CMD_HELP = {
    'entity': {
        'entity_address_list': (
            "list all address types and source for a given entity",
        ),
        'entity_address_data': (
            "show raw address data for a given entity"
        ),
    },
}

CMD_ARGS = {
    'address-source': [
        "address-source",
        "Enter source system",
        textwrap.dedent(
            """
            Name of a source system for an address.

            An empty value can be given to mean "no source system" if this
            value is optional.

            Source systems:

            """
        ).lstrip(),
    ],
    'address-type': [
        "address-type",
        "Enter address type",
        textwrap.dedent(
            """
            The name of an address type.

            An empty value can be given to mean "no source system" if this
            value is optional.

            Address types:

            """
        ).lstrip(),
    ],
}


class BofhdAddressCommands(BofhdCommandBase):

    all_commands = {}
    authz = BofhdAddressAuth
    search_limit = 50

    @property
    def util(self):
        # TODO: Or should we inherit from BofhdCommonMethods?
        #       We're not really interested in user_delete, etc...
        try:
            return self.__util
        except AttributeError:
            self.__util = BofhdUtils(self.db)
            return self.__util

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        # look up types
        co = Factory.get('Constants')()
        addr_types = sorted(
            six.text_type(c)
            for c in co.fetch_constants(_AddressCode))
        source_systems = sorted(
            six.text_type(c)
            for c in co.fetch_constants(_AuthoritativeSystemCode))

        # Enrich cmd_args with actual constants.
        cmd_args = {}
        for k, v in CMD_ARGS.items():
            cmd_args[k] = v[:]
            if k == 'address-type':
                cmd_args[k][2] += "\n".join(
                    " - " + c for c in addr_types)
            elif k == 'address-source':
                cmd_args[k][2] += "\n".join(
                    " - " + c for c in source_systems)

        return merge_help_strings(
            get_help_strings(),
            ({}, CMD_HELP, cmd_args),
        )

    def _format_match(self, entity, search_string):
        """ helper - format the matched entity from user input. """
        return ("%s (type=%s, id=%s)"
                % (repr(search_string),
                   _get_entity_type(self.const, entity.entity_type),
                   entity.entity_id))

    def _search_addrs(self, entity_id=None, entity_type=None,
                      address_type=None, source_system=None,
                      limit=search_limit):
        """ Get formatted and limited results from list_entity_addresses. """
        # TODO: Improve on the search parameters:
        #  - address_text pattern search?
        #  - city/postal_code/p_o_box/country filters?
        addr_db = EntityAddress(self.db)
        for count, row in enumerate(
                addr_db.list_entity_addresses(entity_id=entity_id,
                                              entity_type=entity_type,
                                              source_system=source_system,
                                              address_type=address_type), 1):
            result = {
                'entity_id': int(row['entity_id']),
                # TODO: ideally, we want to include entity type in results, but
                # list_entity_addresses doesn't support this...
                #   'entity_type': six.text_type(
                #       _get_entity_type(self.const, row['entity_type'])),
                'source_system': six.text_type(
                    _get_source_system(self.const, row['source_system'])),
                'address_type': six.text_type(
                    _get_address_type(self.const, row['address_type'])),
                'p_o_box': row['p_o_box'],
                'address_text': row['address_text'],
                'postal_number': row['postal_number'],
                'city': row['city'],
                'country': (
                    None if row['country'] is None
                    # Countries are weird - some institutions don't have them
                    # as valid constant attributes, so we must do a permissive
                    # lookup
                    else self.const.Country(row['country']).country
                ),
            }

            yield result
            if count < limit:
                continue
            yield {'limit': int(limit)}
            break

    #
    # entity address_list <entity>
    #
    all_commands['entity_address_list'] = Command(
        ("entity", "address_list"),
        SimpleString(help_ref='id:target:entity'),
        fs=get_format_suggestion_table(
            ('address_type', 'Type', 12, 's', True),
            ('source_system', 'Source', 10, 's', True),
            limit_key='limit',
        ),
        perm_filter='can_list_addresses',
    )

    def entity_address_list(self, operator, entity_target):
        """ List address types registered for a given entity. """
        entity = self.util.get_target(entity_target, restrict_to=[])
        self.ba.can_list_addresses(operator.get_entity_id(), entity=entity)

        # Filter out actual address data in result
        addresses = list(
            {
                'entity_id': a['entity_id'],
                'source_system': a['source_system'],
                'address_type': a['address_type'],
            }
            for a in self._search_addrs(entity_id=int(entity.entity_id)))

        if not addresses:
            raise CerebrumError("No addresses for %s"
                                % self._format_match(entity, entity_target))

        return addresses

    #
    # entity address_data <entity>
    #
    all_commands['entity_address_data'] = Command(
        ("entity", "address_data"),
        SimpleString(help_ref='id:target:entity'),
        fs=get_format_suggestion_table(
            ('address_type', 'Type', 12, 's', True),
            ('source_system', 'Source', 10, 's', True),
            ('json_data', 'JSON', 50, 's', True),
            limit_key='limit',
        ),
        perm_filter='can_list_addresses',
    )

    def entity_address_data(self, operator, entity_target):
        """ Show raw address data registered for a given entity. """
        entity = self.util.get_target(entity_target, restrict_to=[])
        address_types = list(self.ba.get_allowed_address_types(
            operator.get_entity_id(), entity))
        if not address_types:
            raise PermissionDenied("Not allowed to see any addresses for %s"
                                   % self._format_match(entity, entity_target))

        # Note that address types that aren't allowed won't be shown in the
        # results *at all*.
        #
        # TODO: Wouldn't it be better to include a *censored* record of any
        # existing address that the operator doesn't have access to?
        addresses = list(self._search_addrs(entity_id=int(entity.entity_id),
                                            address_type=address_types))
        if not addresses:
            raise CerebrumError("No matching addresses for %s"
                                % self._format_match(entity, entity_target))

        # Add a json-blob of address data
        for addr in addresses:
            addr['json_data'] = json.dumps(
                {k: addr[k]
                 for k in ("address_text", "city", "country", "p_o_box",
                           "postal_number")},
                sort_keys=True,
            )

        return addresses
