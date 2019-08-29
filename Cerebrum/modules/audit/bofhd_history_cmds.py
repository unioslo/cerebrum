# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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

from Cerebrum.modules.audit.auditdb import AuditLogAccessor
from Cerebrum.modules.audit.formatter import AuditRecordProcessor
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    Id,
    Integer,
    YesNo,
)
from Cerebrum.modules.bofhd.errors import (CerebrumError, PermissionDenied)
from Cerebrum.modules.bofhd.utils import BofhdUtils


class BofhdHistoryAuth(BofhdAuth):
    """ Auth for history commands. """

    def can_show_history(self, operator, entity=None, query_run_any=False):
        """ Check if an operator is allowed to see history info of an entity

        :param int operator: entity_id of the authenticated user
        :param entity: A cerebrum entity object (e.g. person, account)
        """

        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_view_history)

        # Check if user has been granted an op-set that allows viewing the
        # entity's history in some specific fashion.
        for row in self._list_target_permissions(
                operator, self.const.auth_view_history,
                # TODO Should the auth target type be generalized?
                self.const.auth_target_type_global_group,
                None, get_all_op_attrs=True):
            attr = row.get('operation_attr')

            # Op-set allows viewing history for this entity type
            # We need try/except here as self.const.EntityType will throw
            # exceptions if attr is something else than an entity-type
            # (for example a spread-type).
            try:
                if entity.entity_type == int(self.const.EntityType(attr)):
                    return True
            except Exception:
                pass

            # For groups we use the op-set attribute to specify groups that has
            # specified spreads (for example, postmasters are permitted to view
            # the entity history of groups with the exchange_group spread).
            # try/except is needed here for the same reasons as above.
            if entity.entity_type == self.const.entity_group:
                try:
                    spread_type = int(self.const.Spread(attr))
                    if entity.has_spread(spread_type):
                        return True
                except Exception:
                    pass

        if entity.entity_type == self.const.entity_account:
            if self._no_account_home(operator, entity):
                return True
            return self.has_privileged_access_to_account_or_person(
                operator, self.const.auth_view_history, entity)
        if entity.entity_type == self.const.entity_group:
            return self.has_privileged_access_to_group(
                operator, self.const.auth_view_history, entity)
        raise PermissionDenied("no access for that entity_type")


class BofhdExtension(BofhdCommandBase):
    """BofhdExtension for history related commands and functionality."""

    all_commands = {}
    authz = BofhdHistoryAuth

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

        group_help = {'history': "History related commands.", }

        command_help = {
            'history': {
                'history_show': 'List changes made to an entity'
            }
        }

        argument_help = {
            'limit_number_of_results':
                ['limit', 'Number of changes to list',
                 'Upper limit for how many changes to include, counting '
                 'backwards from the most recent. Default (when left empty) '
                 'is 0, which means no limit'],
            'yes_no_all_changes':
                ['all', 'All involved changes?',
                 'List all changes where the entity is involved (yes), or '
                 'only the ones where the entity itself is changed (no)'],
        }

        return (group_help, command_help, argument_help)

    #
    # history show
    #
    all_commands['history_show'] = Command(
        ('history', 'show'),
        Id(help_ref='id:target:account'),
        YesNo(help_ref='yes_no_all_changes', optional=True, default='yes'),
        Integer(help_ref='limit_number_of_results', optional=True,
                default='0'),
        fs=FormatSuggestion(
            '%s [%s]: %s', ('timestamp', 'change_by', 'message')),
        perm_filter='can_show_history')

    def history_show(self, operator, entity, any_entity,
                     limit_number_of_results):
        ent = self.util.get_target(entity, restrict_to=[])
        self.ba.can_show_history(operator.get_entity_id(), ent)
        ret = []
        try:
            N = int(limit_number_of_results)
        except ValueError:
            raise CerebrumError('Illegal range limit, must be an integer: '
                                '{}'.format(limit_number_of_results))

        record_db = AuditLogAccessor(self.db)
        rows = list(record_db.search(entities=ent.entity_id))
        if self._get_boolean(any_entity):
            rows.extend(list(record_db.search(targets=ent.entity_id)))
        rows = sorted(rows)

        _process = AuditRecordProcessor()
        for r in rows[-N:]:
            processed_row = _process(r)
            ret.append({
                'timestamp': processed_row.timestamp,
                'change_by': processed_row.change_by,
                'message': processed_row.message
            })
        return ret
