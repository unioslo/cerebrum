# -*- coding: utf-8 -*-
#
# Copyright 2002-2024 University of Oslo, Norway
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
This module contains the quarantine command group and commands for bofhd.

.. important::
   These classes should not be used directly.  Always make subclasses of
   BofhdCommandBase classes, and add a proper auth class/mixin to the class
   authz.

Configuration
-------------
The following ``cereconf`` settings are used from this module:

``QUARANTINE_STRICTLY_AUTOMATIC``
    A list of quarantines that cannot be modified through these commands.
    No-one, including superuser, can set, clear, or disable these quarantine
    types.

``QUARANTINE_AUTOMATIC``
    A list of quarantines that can *only* be set or cleared by superusers
    through these commands.  Automatic quarantines can be disabled in the same
    way as all other quarantines.

``QUARANTINE_RULES``
    Shell and lock values from the QuarantineHandler rules are included when
    listing quarantine types.

    See :mod:`Cerebrum.QuarantineHandler` for more info.

``BOFHD_QUARANTINE_DISABLE_LIMIT``
    Max number of days that a quarantine can be disabled by *quarantine
    disable*.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import logging
import textwrap

import six

import cereconf
from Cerebrum.Constants import (
    _EntityTypeCode,
    _QuarantineCode,
)
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd import parsers
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.bofhd_utils import format_time, default_format_day
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.trait.constants import _EntityTraitCode


logger = logging.getLogger(__name__)

format_day = default_format_day  # 10 characters wide


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


def _get_quarantine_type(const, value, user_input=False, optional=False):
    """ Get an entity type constant. """
    return _get_constant(const, _QuarantineCode, value,
                         "quarantine type" if user_input else None, optional)


class BofhdQuarantineAuth(BofhdAuth):
    """ Auth for quarantine commands. """

    # Personal traits that indicates that this object is a guest.
    GUEST_OWNER_TRAITS = ()

    RESTRICTED_QUARANTINES = ()

    def _entity_is_guestuser(self, entity):
        """
        Helper - check if entity is considered a guest user of some sort.
        """
        for trait_value in self.GUEST_OWNER_TRAITS:
            trait_code = self.const.get_constant(_EntityTraitCode, trait_value)
            if entity.get_trait(trait_code):
                return True
        return False

    #
    # Partial permission check helpers
    #

    def _check_strictly_automatic_quarantine(self, quarantine):
        """ Raise PermissionDenied if quarantine is strictly automatic. """
        # TODO: We should reverse this check, to ensure that the cereconf
        # values are also valid quarantine values.
        quarantine_value = six.text_type(quarantine)
        if quarantine_value in cereconf.QUARANTINE_STRICTLY_AUTOMATIC:
            raise PermissionDenied(
                "Not allowed to modify quarantine %s (strictly automatic)"
                % (quarantine_value,))

    def _check_automatic_quarantine(self, quarantine):
        """ Raise PermissionDenied if quarantine is automatic. """
        # TODO: We should reverse this check, to ensure that the cereconf
        # values are also valid quarantine values.
        quarantine_value = six.text_type(quarantine)
        if quarantine_value in cereconf.QUARANTINE_AUTOMATIC:
            raise PermissionDenied(
                "Not allowed to modify quarantine %s (automatic)"
                % (quarantine_value,))

    def _check_quarantine_target_is_account(self, entity):
        """ Raise PermissionDenied if entity is not an account. """
        # Can only grant access to accounts through opsets
        if entity.entity_type != self.const.entity_account:
            entity_type = self.const.get_constant(_EntityTypeCode,
                                                  entity.entity_type)
            raise PermissionDenied("No access to quarantines for entity type: "
                                   + six.text_type(entity_type))

    def _check_quarantine_access(self, operator, operation, entity,
                                 quarantine):
        """
        Check for opset access to a given op and quarantine on a given entity.

        :raises PermissionDenied: no access is granted
        """
        quarantine_text = six.text_type(quarantine)

        # Can only grant access to accounts through opsets
        self._check_quarantine_target_is_account(entity)

        # Does operator have access to an opset that grants access to all
        # entities with the given quarantine type?
        for row in self._list_target_permissions(
                operator=operator,
                operation=operation,
                target_type=self.const.auth_target_type_global_host,
                target_id=None,
                get_all_op_attrs=True):
            attr = row['operation_attr']

            # If no operation attributes are given in the opset, then all
            # quarantines are allowed.
            if not attr:
                return True

            # The given quarantine name is listed in the matching opset.
            if attr == quarantine_text:
                return True

        # Does operator have access to an opset that grants access to this
        # specific entity (by e.g. being a local admin at a given org unit
        # where the entity belongs)?
        if quarantine_text not in self.RESTRICTED_QUARANTINES:
            try:
                return self.has_privileged_access_to_account_or_person(
                    operator=operator,
                    operation=operation,
                    entity=entity,
                    operation_attr=quarantine_text,
                )
            except PermissionDenied:
                # We want to formulate our own PermissionDenied error message
                pass

        raise PermissionDenied(
            "No access to modify quarantine %s for this account"
            % (quarantine_text,))

    #
    # Permission checks for quarantine commands
    #

    def can_disable_quarantine(self, operator,
                               entity=None, qtype=None, query_run_any=False):
        """
        Check if operator can disable a given quarantine for a given entity.
        """
        operation = self.const.auth_quarantine_disable

        if query_run_any:
            if self.is_superuser(operator):
                return True
            return self._has_operation_perm_somewhere(operator, operation)

        self._check_strictly_automatic_quarantine(qtype)

        if self.is_superuser(operator):
            return True

        # Note: Other automatic quarantines can generally be disabled - so we
        # don't run _check_automatic_quarantine.

        if self._entity_is_guestuser(entity):
            # Guest user - only superuser and scripts can touch these
            raise PermissionDenied("No access to quarantines on guest users")

        return self._check_quarantine_access(operator, operation, entity,
                                             qtype)

    def can_remove_quarantine(self, operator,
                              entity=None, qtype=None, query_run_any=False):
        """
        Check if operator can remove a given quarantine from a given entity.
        """
        operation = self.const.auth_quarantine_remove

        if query_run_any:
            if self.is_superuser(operator):
                return True
            return self._has_operation_perm_somewhere(operator, operation)

        self._check_strictly_automatic_quarantine(qtype)

        if self.is_superuser(operator):
            return True

        self._check_automatic_quarantine(qtype)

        # Special rule for guestusers. Only superuser are allowed to
        # alter quarantines for these users.
        if self._entity_is_guestuser(entity):
            raise PermissionDenied("No access to quarantines on guest users")

        # this is a hack
        if (entity.entity_type == self.const.entity_account
                and self._no_account_home(operator, entity)):
            return True

        return self._check_quarantine_access(operator, operation, entity,
                                             qtype)

    def can_set_quarantine(self, operator,
                           entity=None, qtype=None, query_run_any=False):
        """
        Check if operator can add a given quarantine to a given entity.
        """
        operation = self.const.auth_quarantine_set

        if query_run_any:
            if self.is_superuser(operator):
                return True
            return self._has_operation_perm_somewhere(operator, operation)

        self._check_strictly_automatic_quarantine(qtype)

        if self.is_superuser(operator):
            return True

        self._check_automatic_quarantine(qtype)

        # Note: No guest user check for setting quarantines.  Adding a
        # quarantine is generally more permissive than removing them, but this
        # does create an inbalance where an operator can accidentally set a
        # quarantine, and not have access to fix this.

        # TODO 2003-07-04: Bård is going to comment this
        #      2024-04-11: ... but he never did?
        if (entity.entity_type == self.const.entity_account
                and self._no_account_home(operator, entity)):
            return True

        return self._check_quarantine_access(operator, operation, entity,
                                             qtype)

    def can_show_quarantines(self, operator,
                             entity=None, query_run_any=False):
        """
        Check if an operator is allowed to list quarantines for an entity.
        """
        if query_run_any:
            return True

        if self.is_superuser(operator):
            return True

        self._check_quarantine_target_is_account(entity)

        # this is a hack
        if self._no_account_home(operator, entity):
            return True

        if self.is_owner_of_account(operator, entity):
            return True

        return self.has_privileged_access_to_account_or_person(
            operator,
            self.const.auth_quarantine_show,
            entity,
        )


class BofhdQuarantineCommands(BofhdCommandBase):

    all_commands = {}
    authz = BofhdQuarantineAuth

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""

        # get config
        disable_limit_days = getattr(
            cereconf, 'BOFHD_QUARANTINE_DISABLE_LIMIT', None)

        # look up types
        co = Factory.get('Constants')()
        quarantine_types = sorted(co.fetch_constants(_QuarantineCode),
                                  key=six.text_type)

        # Enrich cmd_args with actual constants.
        cmd_args = {}
        for k, v in CMD_ARGS.items():
            cmd_args[k] = v[:]
            if k == 'quarantine-disable-date' and disable_limit_days:
                cmd_args[k][2] += (
                    "Quarantines can only be lifted for up to %d days"
                    % (disable_limit_days,)
                )
            if k == 'quarantine-type':
                cmd_args[k][2] += (
                    "Quarantine types:\n"
                    + "\n".join(
                        ("  - " + six.text_type(q)) for q in quarantine_types
                    )
                )

        return merge_help_strings(
            (CMD_GROUP, CMD_HELP, {}),
            get_help_strings(),
            ({}, {}, cmd_args),  # We want *our* cmd_args to win!
        )

    #
    # quarantine remove <entity-type> <entity-id> <quarantine> [date]
    #
    all_commands['quarantine_disable'] = cmd_param.Command(
        ("quarantine", "disable"),
        cmd_param.EntityType(default="account"),
        cmd_param.Id(),
        cmd_param.QuarantineType(help_ref="quarantine-type"),
        # TODO: Wouldn't it be better to ask for number of days to postpone
        # quarantine?
        cmd_param.Date(help_ref="quarantine-disable-date"),
        perm_filter='can_disable_quarantine',
    )

    def quarantine_disable(self, operator, _id_type, _id_value, _quar, _date):
        entity = self._get_entity(_id_type, _id_value)
        # Note: Giving an *empty* date resets disable_until, i.e. re-enables a
        # previously disabled quarantine.
        quarantine = _get_quarantine_type(self.const, _quar, user_input=True)
        date = parsers.parse_date(_date, optional=True)

        self.ba.can_disable_quarantine(operator.get_entity_id(), entity,
                                       quarantine)

        if not entity.get_entity_quarantine(qtype=quarantine):
            raise CerebrumError("%s does not have a quarantine of type %s"
                                % (self._get_name_from_object(entity),
                                   six.text_type(quarantine)))

        limit_days = getattr(cereconf, 'BOFHD_QUARANTINE_DISABLE_LIMIT', None)
        if date and limit_days:
            limit = datetime.timedelta(days=int(limit_days))
            if date > datetime.date.today() + limit:
                raise CerebrumError(
                    "Quarantines can only be disabled for up to %d days"
                    % (limit.days,))

        if date and date < datetime.date.today():
            raise CerebrumError(
                "End date for quarantine disable cannot be in the past")

        entity.disable_entity_quarantine(quarantine, date)

        # TODO: This should be replaced by structured output and a
        #       FormatSuggestion
        if not date:
            return (
                "OK, reactivated quarantine %s for %s"
                % (six.text_type(quarantine),
                   self._get_name_from_object(entity))
            )
        return (
            "OK, disabled quarantine %s for %s"
            % (six.text_type(quarantine), self._get_name_from_object(entity))
        )

    #
    # quarantine list
    #
    all_commands['quarantine_list'] = cmd_param.Command(
        ("quarantine", "list"),
        fs=cmd_param.FormatSuggestion(
            "%-16s  %1s  %-17s %s",
            ('name', 'lock', 'shell', 'desc'),
            hdr=(
                "%-15s %-4s %-17s %s"
                % ('Name', 'Lock', 'Shell', 'Description')
            ),
        ),
    )

    def quarantine_list(self, operator):
        quarantine_types = sorted(self.const.fetch_constants(_QuarantineCode),
                                  key=six.text_type)

        ret = []
        for c in quarantine_types:
            rule = cereconf.QUARANTINE_RULES.get(six.text_type(c), {})

            # TODO: rule could be a list here, or be limited to a given spread,
            # both of which would give us false results for the lock/shell
            # values.
            # Luckily no-one actually has any rules like this. See
            # QuarantineHandler for details.

            lock = "Y" if 'lock' in rule else "N"
            shell = "-"
            if 'shell' in rule:
                shell = rule['shell'].split("/")[-1]
            ret.append({
                'name': six.text_type(c),
                'lock': lock,
                'shell': shell,
                'desc': c.description,
            })
        return ret

    #
    # quarantine remove <entity-type> <entity-id> <quarantine>
    #
    all_commands['quarantine_remove'] = cmd_param.Command(
        ("quarantine", "remove"),
        cmd_param.EntityType(default="account"),
        cmd_param.Id(),
        cmd_param.QuarantineType(help_ref="quarantine-type"),
        perm_filter='can_remove_quarantine',
    )

    def quarantine_remove(self, operator, _id_type, _id_value, _quar):
        entity = self._get_entity(_id_type, _id_value)
        quarantine = _get_quarantine_type(self.const, _quar, user_input=True)
        self.ba.can_remove_quarantine(operator.get_entity_id(), entity,
                                      quarantine)

        if not entity.get_entity_quarantine(qtype=quarantine):
            raise CerebrumError("%s does not have a quarantine of type %s"
                                % (self._get_name_from_object(entity),
                                   six.text_type(quarantine)))

        entity.delete_entity_quarantine(quarantine)

        # TODO: This should be replaced by structured output and a
        #       FormatSuggestion
        return (
            "OK, removed quarantine %s for %s"
            % (six.text_type(quarantine), self._get_name_from_object(entity))
        )

    #
    # quarantine set <entity-type> <entity-id> <quarantine> <why> [start]
    #
    all_commands['quarantine_set'] = cmd_param.Command(
        ("quarantine", "set"),
        cmd_param.EntityType(default="account"),
        # TODO: *repeat* doesn't actually work as implemented
        cmd_param.Id(repeat=True),
        cmd_param.QuarantineType(help_ref="quarantine-type"),
        cmd_param.SimpleString(help_ref="quarantine-reason"),
        cmd_param.Date(help_ref="quarantine-start-date", default="today",
                       optional=True),
        perm_filter='can_set_quarantine',
    )

    def quarantine_set(self, operator, _id_type, _id_value, _quar, reason,
                       _start_date=None):
        entity = self._get_entity(_id_type, _id_value)
        quarantine = _get_quarantine_type(self.const, _quar, user_input=True)
        start_date = (parsers.parse_date(_start_date, optional=True)
                      or datetime.date.today())

        self.ba.can_set_quarantine(operator.get_entity_id(), entity,
                                   quarantine)

        rows = entity.get_entity_quarantine(qtype=quarantine)
        if rows:
            raise CerebrumError(
                "%s already has a quarantine of type %s"
                % (self._get_name_from_object(entity),
                   six.text_type(quarantine)))

        try:
            entity.add_entity_quarantine(quarantine, operator.get_entity_id(),
                                         reason, start_date)
        except AttributeError:
            entity_type = self.const.get_constant(_EntityTypeCode,
                                                  entity.entity_type)
            raise CerebrumError("Quarantines cannot be set on "
                                + six.text_type(entity_type))

        # TODO: This should be replaced by structured output and a
        #       FormatSuggestion
        return (
            "OK, set quarantine %s for %s"
            % (six.text_type(quarantine), self._get_name_from_object(entity))
        )

    #
    # quarantine show <entity-type> <entity-id>
    #
    all_commands['quarantine_show'] = cmd_param.Command(
        ("quarantine", "show"),
        cmd_param.EntityType(default="account"),
        cmd_param.Id(),
        fs=cmd_param.FormatSuggestion(
            "%-14s %-16s %-16s %-14s %-8s %s",
            (
                'type',
                format_time('start'),
                format_time('end'),
                format_day('disable_until'),
                'who',
                'why',
            ),
            hdr="%-14s %-16s %-16s %-14s %-8s %s" %
            ('Type', 'Start', 'End', 'Disable until', 'Who', 'Why')
        ),
        perm_filter='can_show_quarantines',
    )

    def quarantine_show(self, operator, _id_type, _id_value):
        entity = self._get_entity(_id_type, _id_value)
        self.ba.can_show_quarantines(operator.get_entity_id(), entity)

        ret = []
        for r in entity.get_entity_quarantine():
            acc = self._get_account(r['creator_id'], idtype='id')
            ret.append({
                'type': six.text_type(
                    _get_quarantine_type(self.const, r['quarantine_type'])
                ),
                'start': r['start_date'],
                'end': r['end_date'],
                'disable_until': r['disable_until'],
                'who': acc.account_name,
                'why': r['description'],
            })
        return ret


CMD_GROUP = {
    'quarantine': "Quarantine related commands",
}


CMD_HELP = {
    'quarantine': {
        'quarantine_disable': (
            "Temporarily remove a quarantine"
        ),
        'quarantine_list': (
            "List defined quarantine types"
        ),
        'quarantine_remove': (
            "Remove a quarantine from a Cerebrum entity"
        ),
        'quarantine_set': (
            "Quarantine a given entity"
        ),
        'quarantine_show': (
            "View active quarantines for a given entity"
        ),
    },
}

CMD_ARGS = {
    'quarantine-disable-date': [
        'quarantine-disable-date',
        "Enter end date (YYYY-MM-DD)",
        textwrap.dedent(
            """
            Disable the quarantine until the specified date.

            Valid date values and formats:

            {hint}
            """
        ).lstrip().format(hint=parsers.parse_date_help_blurb),
    ],
    'quarantine-reason': [
        'quarantine-reason',
        "Why?",
        textwrap.dedent(
            """
            Enter a short explanation for why this quarantine is added.
            """
        ).strip(),
    ],
    'quarantine-start-date': [
        'quarantine-start-date',
        "Enter start date (YYYY-MM-DD)",
        textwrap.dedent(
            """
            A start date for the quarantine.

            Valid date values and formats:

            {hint}
            """
        ).lstrip().format(hint=parsers.parse_date_help_blurb),
    ],
    'quarantine-type': [
        'quarantine-type',
        "Enter a valid quarantine type",
        textwrap.dedent(
            """
            Enter a valid quarantine type.

            Note that some quarantine types are considered strictly automatic,
            and cannot be set or cleared through these commands.

            Use `quarantine list` to get more info on the available quarantine
            types.
            """
        ).lstrip(),
    ],
}
