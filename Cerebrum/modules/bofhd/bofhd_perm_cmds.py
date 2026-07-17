# -*- coding: utf-8 -*-
#
# Copyright 2003-2024 University of Oslo, Norway
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
This module contains the perm command group and commands for bofhd.

.. important::
   These classes should not be used directly.  Always make subclasses of
   BofhdCommandBase classes, and add a proper auth class/mixin to the class
   authz.

The `perm` commands typically interacts directly with the bofhd auth tables.
These commands are closely related to the :mod:`.bofhd_access` command module,
which provides some of the same functionality with more business logic applied.
These two modules should be reviewed and probably merged to one unified command
group.
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

import Cerebrum.Errors
from Cerebrum.modules.bofhd import auth as bofhd_auth
from Cerebrum.modules.bofhd import bofhd_constants
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd.utils import BofhdUtils


logger = logging.getLogger(__name__)


def _list_target_types():
    """ Get a list of the op target types defined in code. """
    tt = set()
    for attr in dir(bofhd_constants.Constants):
        if attr.startswith("auth_target_type"):
            tt.add(getattr(bofhd_constants.Constants, attr))
    return sorted(tt)


class BofhdPermAuth(bofhd_auth.BofhdAuth):
    """ Default authorization for running perm commands. """

    def _can_run_perm_command(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    #
    # Permission checks for perm commands
    #

    def can_list_auth_opsets(self, operator, query_run_any=False):
        """ Check if operator can list roles/opsets. """
        return self._can_run_perm_command(operator=operator,
                                          query_run_any=query_run_any)

    def can_show_auth_opset(self, operator, opset=None, query_run_any=False):
        """ Check if operator can show a role/opset. """
        return self._can_run_perm_command(operator=operator,
                                          query_run_any=query_run_any)

    def can_list_auth_targets(self, operator, target_type=None, target_id=None,
                              entity_id=None, query_run_any=False):
        """ Check if operator can list auth targets. """
        return self._can_run_perm_command(operator=operator,
                                          query_run_any=query_run_any)

    def can_add_auth_target(self, operator, target_type=None, entity=None,
                            attr=None, query_run_any=False):
        """ Check if operator can create an auth target. """
        return self._can_run_perm_command(operator=operator,
                                          query_run_any=query_run_any)

    def can_del_auth_target(self, operator, target=None, query_run_any=False):
        """ Check if operator can delete an auth target. """
        return self._can_run_perm_command(operator=operator,
                                          query_run_any=query_run_any)

    def can_list_auth_roles(self, operator, entity=None, opset=None,
                            target=None, query_run_any=False):
        """
        Check if operator can list roles/opsets.

        Entity, opset, or target can be provided depending on context.
        """
        return self._can_run_perm_command(operator=operator,
                                          query_run_any=query_run_any)

    def can_add_auth_role(self, operator, entity=None, opset=None, target=None,
                          query_run_any=False):
        """ Check if operator can grant a role/opset to an entity. """
        return self._can_run_perm_command(operator=operator,
                                          query_run_any=query_run_any)

    def can_del_auth_role(self, operator, entity=None, opset=None, target=None,
                          query_run_any=False):
        """ Check if operator can revoke a role/opset from an entity. """
        return self._can_run_perm_command(operator=operator,
                                          query_run_any=query_run_any)


class BofhdPermCommands(BofhdCommandBase):
    """ Default implementation of perm commands. """

    all_commands = {}
    authz = BofhdPermAuth

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

        # look up types
        target_types = _list_target_types()

        # Enrich cmd_args with actual constants.
        cmd_args = {}
        for k, v in CMD_ARGS.items():
            cmd_args[k] = v[:]
            if k == 'op-target-type':
                cmd_args[k][2] += (
                    "\nValid target types:\n"
                ) + "\n".join(" - " + tt for tt in target_types)

        return merge_help_strings(
            (CMD_GROUP, CMD_HELP, {}),
            get_help_strings(),
            ({}, {}, cmd_args),  # We want *our* cmd_args to win!
        )

    #
    # Some lookup helpers
    #

    def _list_opsets(self):
        """ List all opset ids and names. """
        aos = bofhd_auth.BofhdAuthOpSet(self.db)
        for row in aos.list():
            yield (int(row['op_set_id']), row['name'])

    def _get_opset(self, value):
        """ Look up BofhdAuthOpSet by name. """
        aos = bofhd_auth.BofhdAuthOpSet(self.db)
        try:
            aos.find_by_name(value)
        except Cerebrum.Errors.NotFoundError:
            raise CerebrumError("No opset with name: " + repr(value))
        return aos

    def _get_op_target(self, value):
        """ Look up BofhdAuthOpTarget by id. """
        aot = bofhd_auth.BofhdAuthOpTarget(self.db)
        try:
            aot.find(int(value))
        except (TypeError, ValueError):
            raise CerebrumError("Invalid auth target id: " + repr(value))
        except Cerebrum.Errors.NotFoundError:
            raise CerebrumError("No auth target with id: " + repr(value))
        return aot

    #
    # perm opset_list
    #
    all_commands['perm_opset_list'] = cmd_param.Command(
        ("perm", "opset_list"),
        fs=cmd_param.get_format_suggestion_table(
            ("opset_id", "Id", 10, "d", False),
            ("opset_name", "Name", 20, "s", True),
        ),
        perm_filter='can_list_auth_opsets',
    )

    def perm_opset_list(self, operator):
        self.ba.can_list_auth_opsets(operator.get_entity_id())

        results = []
        for opset_id, opset_name in self._list_opsets():
            results.append({
                'opset_id': opset_id,
                'opset_name': opset_name,
            })
        results.sort(key=lambda r: (r.get('opset_id'), r.get('opset_name')))
        if not results:
            raise CerebrumError("No opsets defined")
        return results

    #
    # perm opset_show <opset>
    #
    all_commands['perm_opset_show'] = cmd_param.Command(
        ("perm", "opset_show"),
        cmd_param.SimpleString(help_ref="opset-name"),
        fs=cmd_param.get_format_suggestion_table(
            ("op_id", "Id", 10, "d", False),
            ("op_type", "Operation", 20, "s", True),
            ("attrs", "Attributes", 40, "s", True),
        ),
        perm_filter='can_show_auth_opset',
    )

    def perm_opset_show(self, operator, name):
        aos = self._get_opset(name)
        self.ba.can_show_auth_opset(operator.get_entity_id(), opset=aos)

        results = []
        # TODO: Consistent ordering?
        for row in aos.list_operations():
            c = self.const.AuthRoleOp(int(row['op_code']))
            attrs = [r['attr'] for r in aos.list_operation_attrs(row['op_id'])]
            attrs.sort()
            results.append({
                'op_type': six.text_type(c),
                'op_id': row['op_id'],
                'attrs_list': attrs,
                'attrs': ", ".join(six.text_type(a) for a in attrs),
            })
        results.sort(key=lambda r: (r.get('op_type'), r.get('op_id')))
        if not results:
            raise CerebrumError("No operations defined in opset")
        return results

    #
    # perm target_list <target> [id]
    #
    all_commands['perm_target_list'] = cmd_param.Command(
        ("perm", "target_list"),
        cmd_param.SimpleString(help_ref="op-target-type-or-id"),
        cmd_param.Id(help_ref="op-entity-id", optional=True),
        fs=cmd_param.get_format_suggestion_table(
            ("target_id", "Target Id", 9, "d", False),
            ("entity_id", "Entity Id", 9, "s", False),  # s format, may be None
            ("target_type", "Target Type", 15, "s", True),
            ("name", "Name", 18, "s", True),
            ("attrs", "Attributes", 20, "s", True),
            limit_key="limit",
        ),
        perm_filter='can_list_auth_targets',
    )

    _list_auth_op_target_limit = 250

    def perm_target_list(self, operator, id_or_type, entity_id=None):
        # target-id is the unique id of the auth target.  Giving *just* a
        # number as the first argument will try to look up a single target.
        #
        # target-type tells what the target points to.  It can be e.g. account,
        # group, ou, with a entity-id value that points to an entity, *or* it
        # can be e.g. global_account, global_group, global_ou, with no
        # entity-id (meaning it applies to all ids or a subset scoped by an
        # attr
        # TODO: The mixed input arguments are a bit weird here.  This would
        # probably be better implemented as `perm_target_search target-filter+`
        # with a target-filter parser to handle values like
        # `target-type:global_person`
        #
        if id_or_type.isdigit():
            params = {
                'target_id': int(id_or_type),
            }
        else:
            params = {
                'target_type': id_or_type,
                'entity_id': entity_id,
            }
        self.ba.can_list_auth_targets(operator.get_entity_id(), **params)

        aot = bofhd_auth.BofhdAuthOpTarget(self.db)

        def _get_name(row):
            """ get name from `BofhdAuthOpTarget.list` row. """
            try:
                if row['target_type'] == 'group':
                    return self._get_entity_name(row['entity_id'],
                                                 self.const.entity_group)
                if row['target_type'] == 'disk':
                    return self._get_entity_name(row['entity_id'],
                                                 self.const.entity_disk)
                if row['target_type'] == 'host':
                    return self._get_entity_name(row['entity_id'],
                                                 self.const.entity_host)
                if row['target_type'] == 'ou':
                    return self._get_entity_name(row['entity_id'],
                                                 self.const.entity_ou)
            except Exception:
                pass
            return None

        # TODO: Consistent ordering
        results = []
        count = 0
        for r in aot.list(**params):
            count += 1
            if (self._list_auth_op_target_limit
                    and count > self._list_auth_op_target_limit):
                results.append({
                    'limit': self._list_auth_op_target_limit,
                })
                break

            results.append({
                'target_id': r['op_target_id'],
                'entity_id': r['entity_id'],
                'name': _get_name(r),
                'target_type': r['target_type'],
                'attrs': r['attr'] or None,
            })

        if not results:
            raise CerebrumError("No matching targets")

        results.sort(key=lambda r: (r.get('limit', 0), r.get('target_id', 0)))
        return results

    #
    # perm add_target <target-type> <entity-id> [attr]
    #
    all_commands['perm_add_target'] = cmd_param.Command(
        ("perm", "add_target"),
        cmd_param.SimpleString(help_ref="op-target-type"),
        cmd_param.Id(help_ref="op-entity-id"),
        cmd_param.SimpleString(help_ref="op-target-attr", optional=True),
        fs=cmd_param.FormatSuggestion(
            "OK, target id=%d created",
            ('target_id',),
        ),
        perm_filter='can_add_auth_target',
    )

    def perm_add_target(self, operator, target_type, _entity, attr=None):
        #
        # This function does very little to validate input arguments.
        # We probably want to check that the given entity makes sense with the
        # provided target-type.
        #
        # Because we require an entity, providing global_* target-types makes
        # little sense too.
        #
        if target_type not in set(_list_target_types()):
            raise CerebrumError("Invalid target type: " + repr(target_type))
        entity = self.util.get_target(_entity, default_lookup="id")

        self.ba.can_add_auth_target(
            operator.get_entity_id(),
            target_type=target_type,
            entity=entity,
            attr=attr,
        )

        aot = bofhd_auth.BofhdAuthOpTarget(self.db)
        aot.populate(int(entity.entity_id), target_type, attr)
        aot.write_db()

        target_data = {
            'target_id': int(aot.op_target_id),
            'target_attr': aot.attr,
            'target_type': aot.target_type,
            'entity_id': aot.entity_id,
        }
        return target_data

    #
    # perm del_target <op-target-id> ???
    #
    all_commands['perm_del_target'] = cmd_param.Command(
        ("perm", "del_target"),
        cmd_param.Id(help_ref="op-target-id"),
        fs=cmd_param.FormatSuggestion(
            "OK, target id=%d, attr=%s deleted",
            ('target_id', 'target_attr'),
        ),
        perm_filter='can_del_auth_target',
    )

    def perm_del_target(self, operator, _target):
        aot = self._get_op_target(_target)
        self.ba.can_del_auth_target(operator.get_entity_id(), target=aot)

        target_data = {
            'target_id': int(aot.op_target_id),
            'target_attr': aot.attr,
            'target_type': aot.target_type,
            'entity_id': aot.entity_id,
        }

        # TODO: Will fail if there are references (roles) to this aot. Should
        # check and provide a better error message
        aot.delete()
        return target_data

    _list_roles_fs = cmd_param.get_format_suggestion_table(
        ("entity_id", "Entity Id", 10, "d", False),
        ("entity_name", "Entity Name", 24, "s", True),
        ("opset_name", "Opset", 20, "s", True),
        ("target_id", "Target Id", 10, "d", False),
    )

    def _rows_to_roles(self, rows):
        """ Convert rows from auth_role to client response. """
        opsets = dict(self._list_opsets())
        results = []
        for r in rows:
            results.append({
                'entity_id': int(r['entity_id']),
                'entity_name': self._get_entity_name(r['entity_id']),
                'opset_id': int(r['op_set_id']),
                'opset_name': opsets[int(r['op_set_id'])],
                'target_id': r['op_target_id'],
            })

        results.sort(key=lambda r: (r.get('entity_id', 0),
                                    r.get('opset_name', ''),
                                    r.get('opset_id', 0)))
        return results

    #
    # perm list <entity>
    #
    all_commands['perm_list'] = cmd_param.Command(
        ("perm", "list"),
        cmd_param.Id(help_ref="op-entity-id"),
        fs=cmd_param.get_format_suggestion_table(
            ("entity_id", "Entity Id", 10, "d", False),
            ("entity_name", "Entity Name", 24, "s", True),
            ("opset_name", "Opset", 20, "s", True),
            ("target_id", "Target Id", 10, "d", False),
        ),
        perm_filter='can_list_auth_roles',
    )

    def perm_list(self, operator, _entity):
        # Lists all roles granted to a given entity
        entity = self.util.get_target(_entity, default_lookup="id")
        self.ba.can_list_auth_roles(operator.get_entity_id(), entity=entity)

        entity_ids = [int(entity.entity_id)]

        # include account memberships if account
        if entity.entity_type == self.const.entity_account:
            group = self.Group_class(self.db)
            for row in group.search(member_id=int(entity.entity_id),
                                    indirect_members=False):
                entity_ids.append(row['group_id'])

        bar = bofhd_auth.BofhdAuthRole(self.db)
        results = self._rows_to_roles(
            bar.list(entity_ids=set(entity_ids)))

        if not results:
            entity_type = six.text_type(
                self.const.EntityType(entity.entity_type))
            raise CerebrumError("No roles granted to %s with id=%d"
                                % (entity_type, entity.entity_id))
        return results

    #
    # perm grant <entity> <opset> <op-target-id>
    #
    all_commands['perm_grant'] = cmd_param.Command(
        ("perm", "grant"),
        cmd_param.Id(help_ref="op-entity-id"),
        cmd_param.SimpleString(help_ref="opset-name"),
        cmd_param.Id(help_ref="op-target-id"),
        fs=cmd_param.FormatSuggestion(
            "OK, granted %s@%d to %s id=%d",
            ("opset_name", "target_id", "entity_type", "entity_id"),
        ),
        perm_filter='can_add_auth_role',
    )

    def perm_grant(self, operator, _entity, _opset, _target):
        # grant access for a given entity to an opset and op-target
        entity = self.util.get_target(_entity, default_lookup="id")
        aos = self._get_opset(_opset)
        aot = self._get_op_target(_target)

        self.ba.can_add_auth_role(
            operator.get_entity_id(),
            entity=entity,
            opset=aos,
            target=aot,
        )

        role = {
            'entity_id': int(entity.entity_id),
            'entity_type': six.text_type(
                self.const.EntityType(entity.entity_type)
            ),
            'opset_id': int(aos.op_set_id),
            'opset_name': aos.name,
            'target_id': int(aot.op_target_id),
            'target_type': aot.target_type,
        }

        bar = bofhd_auth.BofhdAuthRole(self.db)

        if list(bar.list(entity_ids=role['entity_id'],
                         op_set_id=role['opset_id'],
                         op_target_id=role['target_id'])):
            raise CerebrumError("Role %s@%d for %s id=%d already exists"
                                % (role['opset_name'], role['target_id'],
                                   role['entity_type'], role['entity_id']))

        bar.grant_auth(role['entity_id'], role['opset_id'], role['target_id'])
        return role

    #
    # perm revoke <entity> <opset> <op-target-id>
    #
    all_commands['perm_revoke'] = cmd_param.Command(
        ("perm", "revoke"),
        cmd_param.Id(help_ref="op-entity-id"),
        cmd_param.SimpleString(help_ref="opset-name"),
        cmd_param.Id(help_ref="op-target-id"),
        fs=cmd_param.FormatSuggestion(
            "OK, revoked %s@%d from %s id=%d",
            ("opset_name", "target_id", "entity_type", "entity_id"),
        ),
        perm_filter='can_del_auth_role',
    )

    def perm_revoke(self, operator, _entity, _opset, _target):
        entity = self.util.get_target(_entity, default_lookup="id")
        aos = self._get_opset(_opset)
        aot = self._get_op_target(_target)

        self.ba.can_del_auth_role(
            operator.get_entity_id(),
            entity=entity,
            opset=aos,
            target=aot,
        )

        role = {
            'entity_id': int(entity.entity_id),
            'entity_type': six.text_type(
                self.const.EntityType(entity.entity_type)
            ),
            'opset_id': int(aos.op_set_id),
            'opset_name': aos.name,
            'target_id': int(aot.op_target_id),
            'target_type': aot.target_type,
        }

        bar = bofhd_auth.BofhdAuthRole(self.db)

        if not list(bar.list(entity_ids=role['entity_id'],
                             op_set_id=role['opset_id'],
                             op_target_id=role['target_id'])):
            raise CerebrumError("Role %s@%d for %s id=%d doesn't exist"
                                % (role['opset_name'], role['target_id'],
                                   role['entity_type'], role['entity_id']))

        bar.revoke_auth(role['entity_id'], role['opset_id'], role['target_id'])

        # TODO: should we remove the 'target_id' as well if this was the last
        # reference to it?

        return role

    #
    # perm who_has_perm <opset>
    #
    all_commands['perm_who_has_perm'] = cmd_param.Command(
        ("perm", "who_has_perm"),
        cmd_param.SimpleString(help_ref="opset-name"),
        fs=_list_roles_fs,
        perm_filter='can_list_auth_roles',
    )

    def perm_who_has_perm(self, operator, _opset):
        aos = self._get_opset(_opset)
        self.ba.can_list_auth_roles(operator.get_entity_id(), opset=aos)

        bar = bofhd_auth.BofhdAuthRole(self.db)
        results = self._rows_to_roles(
            bar.list(op_set_id=int(aos.op_set_id)))
        if not results:
            raise CerebrumError("No roles granted for opset: "
                                + repr(aos.name))
        return results

    #
    # perm who_owns
    #
    all_commands['perm_who_owns'] = cmd_param.Command(
        ("perm", "who_owns"),
        cmd_param.Id(help_ref="op-entity-or-target-id"),
        fs=_list_roles_fs,
        perm_filter='can_list_auth_roles',
    )

    def _find_target_ids(self, entity):
        """ Find all targets that cause "ownership" of entity. """
        aot = bofhd_auth.BofhdAuthOpTarget(self.db)
        return set(r['op_target_id']
                   for r in aot.list(entity_id=int(entity.entity_id)))

    def perm_who_owns(self, operator, _entity):
        if _entity.startswith("target-id:"):
            try:
                target_id = int(_entity[len("target-id:"):])
            except (ValueError, IndexError):
                raise CerebrumError("Invalid target-id: " + repr(_entity))
            aot = self._get_op_target(target_id)
            entity = None
            target_ids = set([int(aot.op_target_id)])
        else:
            aot = None
            entity = self.util.get_target(_entity, default_lookup="id")
            target_ids = set(self._find_target_ids(entity))

        self.ba.can_list_auth_roles(
            operator.get_entity_id(),
            target=aot,
            entity=entity,
        )

        bar = bofhd_auth.BofhdAuthRole(self.db)
        results = self._rows_to_roles(bar.list_owners(target_ids))

        if not results:
            entity_type = six.text_type(
                self.const.EntityType(entity.entity_type))
            raise CerebrumError(
                "No roles grants explicit access to %s with id=%d"
                % (entity_type, entity.entity_id))

        return results


CMD_GROUP = {
    'perm': 'Control of Privileges in Cerebrum',
}


CMD_HELP = {
    'perm': {
        'perm_opset_list': "List defined opsets",
        'perm_opset_show': "List operations in a given opset",
        'perm_target_list': "List auth targets of the given type",
        'perm_add_target': "Define a new auth target",
        'perm_del_target': "Remove an existing auth target",
        'perm_list': "List roles granted to an entity",
        'perm_grant': "Add a role to a given entity",
        'perm_revoke': "Remove a role from a given entity",
        'perm_who_has_perm': "List entities with a given opset",
        'perm_who_owns': "Show owners of an entity or auth target",
    },
}

CMD_ARGS = {
    'opset-name': [
        "opset-name",
        "Enter opset name",
        textwrap.dedent(
            """
            Enter the name of a known opset.

            Use `perm list_opsets` to list known opsets.
            """
        ).lstrip(),
    ],
    'op-target-id': [
        "op-target-id",
        "Enter target id",
        textwrap.dedent(
            """
            Enter the id of an auth target.
            """
        ).lstrip(),
    ],
    'op-target-type': [
        "op-target-type",
        "Enter a target type",
        textwrap.dedent(
            """
            Enter a target type.
            """
        ).lstrip(),
    ],
    'op-target-attr': [
        "op-target-attr",
        "Enter a target attribute",
        textwrap.dedent(
            """
            Enter a target attribute.

            A target attribute is typically used to restrict target selection
            for a given auth target.  An example could be e.g. setting a given
            affiliation on an 'ou' target, to restrict access to persons on
            that OU, or setting an attribute for a global target, to make a
            more restrictive global access.
            """
        ).lstrip(),
    ],
    'op-entity-id': [
        # This is for `BofhdUtils.get_target(..., default_lookup="id")`
        "op-entity-id",
        "Enter an existing entity",
        textwrap.dedent(
            """
            Enter <entity-id> or <type>:<ident>, e.g.: 'account:bob'

            Valid types are
              - 'account' (name of user => Account)
              - 'person' (name of user => Person)
              - 'group' (name of group => Group)
              - 'host' (name of host => Host)
              - 'id' (entity ID => any)
              - 'stedkode' (stedkode => OU)
            """
        ).strip(),
    ],
    'op-entity-or-target-id': [
        # this weird help text is just for the mixed lookup value of
        # `perm_who_owns`
        "op-entity-or-target-id",
        "Enter an existing entity",
        textwrap.dedent(
            """
            Enter <entity-id> or <type>:<ident>, e.g.: 'account:bob'

            Also allows for explicit listing of 'target-id:<target-id>'.
            Otherwise accepts the same arguments as `help arg_help
            `op-entity-id`.
            """
        ).strip(),
    ],
    'op-target-type-or-id': [
        # this weird help text is just for the mixed first argument of
        # perm_target_list
        "op-target-type-or-id",
        "Enter target id or target type",
        textwrap.dedent(
            """
            Enter a <target-id> or a <target-type>.

            If a <target-type> is given, then a target <entity-id> can be
            given at the next argument.  If a <target-id> is given, then adding
            an <entity-id> as the next argument has no effect.

            See `help arg_help op-target-type` and `help arg_help op-target-id`
            for details.
            """
        ).strip(),
    ],
}
