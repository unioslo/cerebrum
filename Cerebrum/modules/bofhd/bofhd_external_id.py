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

TODO
----
This module can replace a lot of older commands in other BofhdCommand modules.
We should probably consider doing this in order to clean up legacy code, and
get rid of duplicated functionality.

Remove related functionality
    We should replace any `get_id`/`set_id`/`clear_id` commands from other
    command groups with this bofhd module.

    `person_info` lists external id types, we might want to replace this e.g.
    with a hint to use `entity extid_list id:<entity-id>`?

    `person_find` allows searching for various mapped external id types.  This
    command has virtually no access restrictions...

Bofhd op-codes
     We should implement bofhd op-codes for setting/clearing external ids, so
     that this access can be delegated through op-sets.  See comments in
     :meth:`.BofhdExtidAuth.can_set_extid` for details on how to implement
     this.

     Maybe consider an op-code for searching for external-ids as well?  Or
     should this always be linked to getting/viewing external ids?

Refactor view_external_id op-code
    The `auth_view_external_id` op-attrs were previously expected to be
    formatted as <source-system>:<id-type>.  It makes little sense to restrict
    external-ids by source system, so we've chosen *not* to do that in the
    :meth:`.BofhdExtidAuth.can_get_extid` check.  This expects only <id-type>
    op-attrs.  op-attrs of both formats *should* be able to co-exist, as:

    - any <source-sys>:<id-type> op-attr for
      `BofhdAuth._can_get_person_external_id` won't match op-attrs for this
      method

    - any <id-type> op-attr for this method won't match op-attrs for
      `_can_get_person_external_id`

    - any op-set without op-attrs will match all <source-system>/<id-type>
      pairs anyway

    We should clean this up later by:

    - removing `person get_id`, `_can_get_person_external_id`,
      `can_get_external_id`

    - refactor `person_info` to either list all external id types, or not
      list external id types at all?

    - remove <source-system>:<id-type> op-attrs from this op-code in
      op-sets

Normalize external ids
    We should probably validate and normalize all external ids set by the
    `entity extid_set` command.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import textwrap

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
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    SimpleString,
    get_format_suggestion_table,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd.utils import BofhdUtils


logger = logging.getLogger(__name__)


def _get_constant(const, ctype, value, user_input_hint, optional):
    """ Helper to assert that a given value is a valid constant.  """
    if optional and not value and value != 0:
        return None
    try:
        return const.get_constant(ctype, value)
    except LookupError:
        if user_input_hint:
            raise CerebrumError("Invalid %s: %s" %
                                (user_input_hint, repr(value)))
        raise


def _get_id_type(const, value, user_input=False, optional=False):
    """ Get an external id type constant.  """
    return _get_constant(const, _EntityExternalIdCode, value,
                         "id type" if user_input else None, optional)


def _get_source_system(const, value, user_input=False, optional=False):
    """ Get a source system constant. """
    return _get_constant(const, _AuthoritativeSystemCode, value,
                         "source system" if user_input else None, optional)


def _get_entity_type(const, value, user_input=False, optional=False):
    """ Get an entity type constant. """
    return _get_constant(const, _EntityTypeCode, value,
                         "entity type" if user_input else None, optional)


class BofhdExtidAuth(BofhdAuth):
    """ Auth for entity extid_* commands.  """

    @property
    def visible_external_ids(self):
        """
        A set of external ids that *anyone* can view.

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

        :type operator: int
        :type entity: Cerebrum.Entity.EntityExternalId
        :type id_type: Cerebrum.Constants._EntityExternalIdCode
        """
        if query_run_any:
            return True

        if self.is_superuser(operator):
            return True

        id_const = _get_id_type(self.const, id_type)
        entity_type = _get_entity_type(self.const, entity.entity_type)

        # check if id_type is visible to all operators
        if id_const in self.visible_external_ids:
            return True

        # All orgunit ids are visible to all operators, regarless of listing in
        # visible_external_ids
        if entity_type == self.const.entity_ou:
            return True

        if entity_type == self.const.entity_person:
            # Operator can view all external ids from the operator account
            # owner object (as long as it's a personal account)
            account_ids = self._get_accounts_owned_by(entity.entity_id)
            if operator in account_ids:
                return True

        if entity_type == self.const.entity_account:
            # Operator can view all external ids for the operator account
            if operator == entity.entity_id:
                return True

            # If operator account is a personal account, then operator can view
            # all external ids for other accounts owned by the operator.
            if entity.owner_type == self.const.entity_person:
                account_ids = self._get_accounts_owned_by(entity.owner_id)
                if operator in account_ids:
                    return True

        # Check if operator has access to view *all* external ids of this type
        # through an op-set.
        #
        op_attr = six.text_type(id_const)
        if self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_view_external_id,
                target_type=self.const.auth_target_type_global_person,
                target_id=None,
                victim_id=None,
                operation_attr=op_attr):
            return True

        raise PermissionDenied(
            "No permission to view id type %s for entity type=%s, id=%d"
            % (op_attr, entity_type, entity.entity_id))

    def can_set_extid(self, operator,
                      entity=None, id_type=None, source_system=None,
                      query_run_any=False):
        """
        Check if an operator is allowed to set external id.

        :type operator: int
        :type entity: Cerebrum.Entity.EntityExternalId
        :type id_type: Cerebrum.Constants._EntityExternalIdCode
        :type source_system: Cerebrum.Constants._AuthoritativeSystemCode
        """
        # If we implement an op-code for setting external ids, should probably
        # check for this with:
        #
        #     if query_run_any:
        #         return self._has_operation_perm_somewhere(
        #             operator, self.const.auth_foo)

        if self.is_superuser(operator):
            return True
        elif query_run_any:
            return False

        id_const = _get_id_type(self.const, id_type)
        sys_const = _get_source_system(self.const, source_system)
        entity_type = _get_entity_type(self.const, entity.entity_type)
        op_attr = "{}:{}".format(six.text_type(sys_const),
                                 six.text_type(id_const))

        error = PermissionDenied(
            "No permission to set id type %s for entity type=%s, id=%d"
            % (op_attr, entity_type, entity.entity_id))

        # Sanity check - if we add an op-code for setting ext-ids, we might
        # want to also ensure operator is allowed to search for the given
        # id-type, as the entity_extid_set command can leak info on which
        # entities has a given (id_type, id_value) pair
        #
        #     try:
        #         self.can_search_extid(id_type=id_type)
        #     except PermissionDenied:
        #         raise error
        #
        # Example: Given an op-code, const.auth_foo, the following code should
        # check if any op-set grants access to the given source-system/id-type
        # pair.  This code also checks for wildcards (*) in op-attrs.  That
        # way we could grant access to:
        #
        #  - All id-types from a given source system (e.g. "GREG:*")
        #  - A given id-type from all source systems (e.g. "*:NO_SKO")
        #
        #     op_attrs = [
        #         "{}:*".format(six.text_type(sys_const)),
        #         "*:{}".format(six.text_type(id_const)),
        #         op_attr,
        #     ]
        #
        #     for attr in op_attrs:
        #         if self._has_target_permissions(
        #                 operator=operator,
        #                 operation=self.const.auth_foo,
        #                 target_type=self.const.auth_target_type_global_person,
        #                 target_id=None,
        #                 victim_id=None,
        #                 operation_attr=attr):
        #             return True
        raise error

    def can_clear_extid(self, operator,
                        entity=None,
                        id_type=None,
                        source_system=None,
                        query_run_any=False):
        """
        Check if an operator is allowed to clear external id.

        :type operator: int
        :type entity: Cerebrum.Entity.EntityExternalId
        :type id_type: Cerebrum.Constants._EntityExternalIdCode
        :type source_system: Cerebrum.Constants._AuthoritativeSystemCode
        """
        if self.is_superuser(operator):
            return True
        elif query_run_any:
            return False

        id_const = _get_id_type(self.const, id_type)
        sys_const = _get_source_system(self.const, source_system)
        entity_type = _get_entity_type(self.const, entity.entity_type)
        op_attr = "{}:{}".format(six.text_type(sys_const),
                                 six.text_type(id_const))

        # See comments in can_set_extid for how we'd want to implement
        # op-set/op-code checks
        raise PermissionDenied(
            "No permission to clear id type %s for entity type=%s, id=%d"
            % (op_attr, entity_type, entity.entity_id))

    def can_list_extid(self, operator, entity=None, query_run_any=False):
        """
        Check if an operator is allowed to list external id types.

        :type operator: int
        :type entity: Cerebrum.Entity.EntityExternalId
        """
        if query_run_any:
            return True

        if self.is_superuser(operator):
            return True

        entity_type = _get_entity_type(self.const, entity.entity_type)
        if entity_type != self.const.entity_person:
            return True

        try:
            # TODO: Re-consider this?  This check is basically *True*
            # everywhere, so we could simplify a lot by de-coupling
            # can_view_person and can_list_extid...
            return self.can_view_person(operator, person=entity,
                                        query_run_any=query_run_any)
        except PermissionDenied:
            pass
        raise PermissionDenied(
            "No permission to list id types for entity type=%s, id=%d"
            % (entity_type, entity.entity_id))

    def can_search_extid(self, operator, id_type=None, query_run_any=False):
        """
        Check if an operator is allowed to search for an external id.

        :type operator: int
        :type id_type: Cerebrum.Constants._EntityExternalIdCode
        """
        # Some external ids (visible_external_ids, org unit ids) are available
        # to everyone, so everyone should *see* this command
        if query_run_any:
            return True

        if self.is_superuser(operator):
            return True

        id_const = _get_id_type(self.const, id_type)

        # All orgunit ids are visible to all operators, regardless of listing
        # in visible_external_ids
        if id_const.entity_type == self.const.entity_ou:
            return True

        # check if id_type is visible to all operators
        if id_const in self.visible_external_ids:
            return True

        # Can view attribute if operator has access to view the given id-type
        # through an op-set.
        #
        # We may want a separate op-code for this, but for now everyone who can
        # *see* a given id-type can also *search* for that id-type.
        op_attr = six.text_type(id_const)
        if self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_view_external_id,
                target_type=self.const.auth_target_type_global_person,
                target_id=None,
                victim_id=None,
                operation_attr=op_attr):
            return True

        raise PermissionDenied("No permission to search for id type %s"
                               % (op_attr,))


CMD_HELP = {
    'entity': {
        'entity_extid_clear': "clear an external id from an entity",
        'entity_extid_get': "show external id for an entity",
        'entity_extid_list': "show external id types for an entity",
        'entity_extid_search': "search for entities with a given external id",
        'entity_extid_set': "set an external id for an entity",
    },
}

CMD_ARGS = {
    'entity-extid-pattern': [
        "entity-extid-pattern",
        "Enter external id search pattern",
        textwrap.dedent(
            """
            Enter an external id value or a glob-like search pattern.

            Glob-like patterns:

             - '?': match exactly one character
             - '*': match zero, one or multiple characters
            """
        ).lstrip(),
    ],
    'entity-extid-source': [
        "entity-extid-source",
        "Enter source system",
        textwrap.dedent(
            """
            Name of a source system for the external id type.

            An empty value can be given to mean "no source system" if this
            value is optional.

            Source systems:

            """
        ).lstrip(),
    ],
    'entity-extid-type': [
        "entity-extid-type",
        "Enter external id type",
        textwrap.dedent(
            """
            The name of an external id type.

            External id types:

            """
        ).lstrip(),
    ],
    'entity-extid-value': [
        "entity-extid-value",
        "Enter external id value",
        "A valid external id value.",
    ],
}


class BofhdExtidCommands(BofhdCommandBase):

    all_commands = {}
    authz = BofhdExtidAuth
    search_limit = 50

    @property
    def util(self):
        try:
            return self.__util
        except AttributeError:
            self.__util = BofhdUtils(self.db)
            return self.__util

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        co = Factory.get('Constants')()
        id_sources = sorted(co.fetch_constants(_AuthoritativeSystemCode),
                            key=six.text_type)
        id_types = sorted(co.fetch_constants(_EntityExternalIdCode),
                          key=six.text_type)

        # Enrich cmd_args with actual constants.
        cmd_args = {}
        for k, v in CMD_ARGS.items():
            cmd_args[k] = v[:]
            if k == 'entity-extid-source':
                cmd_args[k][2] += "\n".join(
                    " - " + six.text_type(c) for c in id_sources)
            if k == 'entity-extid-type':
                cmd_args[k][2] += "\n".join(
                    " - " + six.text_type(c) for c in id_types)
        del co

        return merge_help_strings(
            ({}, {}, cmd_args),  # We want _our_ cmd_args to win!
            get_help_strings(),
            ({}, CMD_HELP, {}))

    def _format_match(self, entity, search_string):
        """ helper - format the matched entity from user input. """
        return ("%s (type=%s, id=%s)"
                % (repr(search_string),
                   _get_entity_type(self.const, entity.entity_type),
                   entity.entity_id))

    def _check_id_type_support(self, entity, _id_type, search_string):
        """ helper - check if a given entity can have a given id_type. """
        id_type = _get_id_type(self.const, _id_type)
        if id_type.entity_type != entity.entity_type:
            raise CerebrumError(
                "Invalid id type %s (type=%s) for %s"
                % (id_type, id_type.entity_type,
                   self._format_match(entity, search_string)))

    def _check_extid_modify_support(self, entity, search_string):
        """ helper - check if a given entity can get any extid set/cleared. """
        if not isinstance(entity, EntityExternalId):
            raise CerebrumError(
                "No support for external id in %s"
                % self._format_match(entity, search_string))

    _list_extid_types_fs = get_format_suggestion_table(
        ("entity_id", "Entity Id", 12, "d", False),
        ("entity_type", "Entity Type", 12, "s", True),
        ("id_source", "Id Source", 12, "s", True),
        ("id_type", "Id Type", 12, "s", True),
        limit_key="limit",
    )

    _list_extid_values_fs = get_format_suggestion_table(
        ("entity_id", "Entity Id", 12, "d", False),
        ("entity_type", "Entity Type", 12, "s", True),
        ("id_source", "Id Source", 12, "s", True),
        ("id_type", "Id Type", 12, "s", True),
        ("id_value", "Id Value", 12, "s", False),
        limit_key="limit",
    )

    def _search_extid(self, entity_id=None, entity_type=None,
                      id_source=None, id_type=None, id_pattern=None,
                      include_value=False, limit=search_limit):
        """ Get formatted and limited results from search_external_ids. """
        id_db = EntityExternalId(self.db)
        for count, row in enumerate(
                id_db.search_external_ids(entity_id=entity_id,
                                          entity_type=entity_type,
                                          source_system=id_source,
                                          id_type=id_type,
                                          external_id=id_pattern,
                                          fetchall=False), 1):
            result = {
                'entity_id': int(row['entity_id']),
                'entity_type': six.text_type(
                    _get_entity_type(self.const, row['entity_type'])),
                'id_type': six.text_type(
                    _get_id_type(self.const, row['id_type'])),
                'id_source': six.text_type(
                    _get_source_system(self.const, row['source_system'])),
            }
            if include_value:
                result['id_value'] = row['external_id']
            yield result
            if count < limit:
                continue
            yield {'limit': int(limit)}
            break

    #
    # entity extid_get <entity> <id-type> [id-source]
    #
    all_commands['entity_extid_get'] = Command(
        ("entity", "extid_get"),
        SimpleString(help_ref='id:target:entity'),
        SimpleString(help_ref='entity-extid-type'),
        SimpleString(help_ref='entity-extid-source', optional=True),
        fs=_list_extid_values_fs,
        perm_filter='can_get_extid',
    )

    def entity_extid_get(self, operator,
                         entity_target, _id_type, _id_source=None):
        """ Show external ids of a given type for an entity. """
        entity = self.util.get_target(entity_target, restrict_to=[])
        id_type = _get_id_type(self.const, _id_type, user_input=True)
        id_source = _get_source_system(self.const, _id_source,
                                       user_input=True, optional=True)

        self._check_id_type_support(entity, id_type, entity_target)

        self.ba.can_get_extid(operator.get_entity_id(),
                              entity=entity, id_type=id_type)
        results = list(self._search_extid(entity_id=int(entity.entity_id),
                                          id_type=id_type,
                                          id_source=id_source,
                                          include_value=True))
        if not results:
            raise CerebrumError("No external id of type %s for: %s"
                                % (id_type, repr(entity_target)))
        return results

    #
    # entity extid_list <entity>
    #
    all_commands['entity_extid_list'] = Command(
        ("entity", "extid_list"),
        SimpleString(help_ref='id:target:entity'),
        fs=_list_extid_types_fs,
        perm_filter='can_list_extid',
    )

    def entity_extid_list(self, operator, entity_target):
        """ List external id types for an entity. """
        entity = self.util.get_target(entity_target, restrict_to=[])
        self.ba.can_list_extid(operator.get_entity_id(), entity=entity)
        results = list(self._search_extid(entity_id=int(entity.entity_id),
                                          include_value=False))
        if not results:
            raise CerebrumError("No external ids for: %s"
                                % repr(entity_target))
        return results

    #
    # entity extid_search <id-type> <pattern> [system]
    #
    all_commands['entity_extid_search'] = Command(
        ("entity", "extid_search"),
        SimpleString(help_ref='entity-extid-type'),
        SimpleString(help_ref='entity-extid-pattern'),
        SimpleString(help_ref='entity-extid-source', optional=True),
        fs=_list_extid_values_fs,
        perm_filter='can_search_extid',
    )

    def entity_extid_search(self, operator,
                            _id_type, id_pattern, _id_source=None):
        """ Search for entities that match a given external id. """
        id_type = _get_id_type(self.const, _id_type, user_input=True)
        id_source = _get_source_system(self.const, _id_source,
                                       user_input=True, optional=True)

        self.ba.can_search_extid(operator.get_entity_id(), id_type=id_type)
        results = list(self._search_extid(id_source=id_source,
                                          id_type=id_type,
                                          id_pattern=id_pattern,
                                          include_value=True))

        if not results:
            raise CerebrumError(
                "No external id matches for %s %s in %s"
                % (id_type, repr(id_pattern), id_source or "any system"))
        return results

    #
    # entity extid_set <entity> <id-type> <id-value> [id-source]
    #
    all_commands['entity_extid_set'] = Command(
        ('entity', 'extid_set'),
        SimpleString(help_ref='id:target:entity'),
        SimpleString(help_ref='entity-extid-source'),
        SimpleString(help_ref='entity-extid-type'),
        SimpleString(help_ref='entity-extid-value'),
        fs=FormatSuggestion(
            "Set external id %s:%s to '%s' for %s with id=%d",
            ('id_source', 'id_type', 'id_value', 'entity_type', 'entity_id')
        ),
        perm_filter='can_set_extid',
    )

    def _normalize_id(self, id_source, id_type, id_value):
        """
        Validate and normalize external id.

        :type id_source: Cerebrum.Constants._AuthoritativeSystemCode
        :type id_type: Cerebrum.Constants._EntityExternalIdCode
        :type id_value: str

        :throws CerebrumError:
            Throws a bofhd client error if the given external id is not valid.
        """
        # If we need to validate new external ids, we could do so here.
        return id_value

    def entity_extid_set(self, operator,
                         entity_target, _id_source, _id_type, _id_value):
        """ Set external id for an entity. """
        # get entity object
        entity = self.util.get_target(entity_target, restrict_to=[])
        entity_id = int(entity.entity_id)
        entity_type = _get_entity_type(self.const, entity.entity_type)
        id_source = _get_source_system(self.const, _id_source, user_input=True)
        id_type = _get_id_type(self.const, _id_type, user_input=True)
        id_value = self._normalize_id(id_source, id_type, _id_value)

        # Check for support
        self._check_extid_modify_support(entity, entity_target)
        self._check_id_type_support(entity, id_type, entity_target)

        # Check permissions
        self.ba.can_set_extid(operator.get_entity_id(),
                              entity=entity, id_type=id_type,
                              source_system=id_source)

        # Check if the given id-type/id-value has been given to another entity.
        # If so, it needs to be cleared from that entity first...
        other_owners = set(
            row['entity_id']
            for row in entity.search_external_ids(id_type=id_type,
                                                  external_id=id_value)
            if row['entity_id'] != entity_id
            and row['external_id'] == id_value)
        if other_owners:
            raise CerebrumError(
                "Can't set id type %s for %s: already assigned to %s"
                % (id_type, self._format_match(entity, entity_target),
                   ", ".join("id:%d" % i for i in sorted(other_owners))))

        # Check if this entity already has the given id-type with another
        # id-value
        other_values = set(
            row['external_id']
            for row in entity.search_external_ids(entity_id=entity_id,
                                                  id_type=id_type)
            if row['external_id'] != id_value)
        if other_values:
            logger.warning("Entity id=%r already has a %s set to another value"
                           % (entity_id, six.text_type(id_type)))

        # Check if this value is already set for this person (i.e. no change)
        is_set = False
        for row in entity.search_external_ids(entity_id=entity_id,
                                              id_type=id_type,
                                              source_system=id_source):
            is_set = True
            if row['external_id'] != id_value:
                continue
            raise CerebrumError(
                "Can't set id type %s for %s: already set to same value"
                % (id_type, self._format_match(entity, entity_target)))

        entity.affect_external_id(id_source, id_type)
        entity.populate_external_id(id_source, id_type, id_value)
        entity.write_db()
        logger.info(
            "%s external id: entity_id=%r, source_system=%r, id_type=%r",
            "Updated" if is_set else "Added",
            entity_id, six.text_type(id_source), six.text_type(id_type))

        return {
            'id_source': six.text_type(id_source),
            'id_type': six.text_type(id_type),
            'id_value': six.text_type(id_value),
            'entity_type': six.text_type(entity_type),
            'entity_id': entity_id,
        }

    #
    # entity extid_clear <entity> <id-type> [id-source]
    #
    all_commands['entity_extid_clear'] = Command(
        ('entity', 'extid_clear'),
        SimpleString(help_ref='id:target:entity'),
        SimpleString(help_ref='entity-extid-source'),
        SimpleString(help_ref='entity-extid-type'),
        fs=FormatSuggestion(
            "Cleared external id %s:%s from %s with id=%d",
            ('id_source', 'id_type', 'entity_type', 'entity_id')
        ),
        perm_filter='can_clear_extid',
    )

    def entity_extid_clear(self, operator,
                           entity_target, _id_source, _id_type):
        """ Clear external id for an entity. """
        # get entity object
        entity = self.util.get_target(entity_target, restrict_to=[])
        entity_id = int(entity.entity_id)
        entity_type = self.const.EntityType(entity.entity_type)
        id_source = _get_source_system(self.const, _id_source, user_input=True)
        id_type = _get_id_type(self.const, _id_type, user_input=True)

        # Check for support
        self._check_extid_modify_support(entity, entity_target)

        # Check permissions
        self.ba.can_clear_extid(operator.get_entity_id(),
                                entity=entity, id_type=id_type,
                                source_system=id_source)

        exists = set(
            row['external_id']
            for row in entity.search_external_ids(
                entity_id=entity_id, id_type=id_type, source_system=id_source))

        if not exists:
            raise CerebrumError("No external id of type %s:%s for: %s"
                                % (six.text_type(id_source),
                                   six.text_type(id_type),
                                   self._format_match(entity, entity_target)))

        entity.affect_external_id(id_source, id_type)
        entity.write_db()
        logger.info(
            "Cleared external id: entity_id=%r, source_system=%r, id_type=%r",
            entity_id, six.text_type(id_source), six.text_type(id_type))

        return {
            'id_source': six.text_type(id_source),
            'id_type': six.text_type(id_type),
            'entity_type': six.text_type(entity_type),
            'entity_id': entity_id,
        }
