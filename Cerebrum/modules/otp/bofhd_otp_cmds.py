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
Bofhd *queue* command group for interacting with the event queue log.
"""

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    PersonId,
    SimpleString,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings

from .otp_db import sql_search
from .otp_types import PersonOtpUpdater, get_policy, validate_secret


class OtpAuth(BofhdAuth):
    """ Auth for history commands. """

    def _is_otp_protected(self, person):
        """ check if person is protected from otp changes in bofhd. """
        return False

    def _can_modify_otp_secret(self, operator, person=None,
                               query_run_any=False):
        if query_run_any:
            return self.is_superuser(operator)

        if not self.is_superuser(operator):
            raise PermissionDenied('Only superuser can modify OTP data')

        if self._is_otp_protected(person):
            raise PermissionDenied('Person is protected from OTP changes')

        return True

    def can_show_otp_info(self, operator, person=None, query_run_any=False):
        """ Check if an operator is allowed to show otp info for a given person.

        :param int operator: entity_id of the authenticated user
        :param person: A cerebrum person object
        """
        return self._can_modify_otp_secret(operator, person=person,
                                           query_run_any=query_run_any)

    def can_set_otp_secret(self, operator, person=None, query_run_any=False):
        """ Check if an operator is allowed to set otp secret for a given person.

        :param int operator: entity_id of the authenticated user
        :param person: A cerebrum person object
        """
        return self._can_modify_otp_secret(operator, person=person,
                                           query_run_any=query_run_any)

    def can_clear_otp_secret(self, operator, person=None, query_run_any=False):
        """ Check if an operator is allowed to clear otp secret for a given person.

        :param int operator: entity_id of the authenticated user
        :param person: A cerebrum person object
        """
        return self._can_modify_otp_secret(operator, person=person,
                                           query_run_any=query_run_any)


class OtpCommands(BofhdCommandBase):
    """BofhdExtension for history related commands and functionality."""

    all_commands = {}
    authz = OtpAuth

    @property
    def otp_policy(self):
        try:
            self.__otp_pol
        except AttributeError:
            self.__otp_pol = get_policy()
        return self.__otp_pol

    @property
    def otp_util(self):
        try:
            self.__otp_util
        except AttributeError:
            self.__otp_util = PersonOtpUpdater(self.db, self.otp_policy)
        return self.__otp_util

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        return merge_help_strings(
            get_help_strings(),
            ({}, COMMAND_HELP, ARGUMENT_HELP),
        )

    #
    # person otp_info <person>
    #

    all_commands['person_otp_info'] = Command(
        ('person', 'otp_info'),
        PersonId(help_ref="id:target:person"),
        fs=FormatSuggestion(
            [(" %-9d  %-12s %s", ('person_id', 'otp_type', 'updated_at'))],
            hdr=" %-9s  %-12s %s" % ("person id", "otp type", "updated at"),
        ),
        perm_filter='can_show_otp_info',
    )

    def person_otp_info(self, operator, person_ident):
        person = self._get_entity(entity_type='person', ident=person_ident)
        self.ba.can_show_otp_info(operator.get_entity_id(), person=person)
        otp_data = sql_search(self.db, person_id=person.entity_id)
        if not otp_data:
            raise CerebrumError('No otp_data for person %r' % (person_ident,))
            
        return [{
            'person_id': row['person_id'],
            'otp_type': row['otp_type'],
            'updated_at': row['updated_at'],
        } for row in otp_data]

    #
    # person otp_set <person> <secret>
    #

    all_commands['person_otp_set'] = Command(
        ('person', 'otp_set'),
        PersonId(help_ref="id:target:person"),
        SimpleString(help_ref='otp_shared_secret'),
        fs=FormatSuggestion(
            'OK, stored OTP secret for person_id: %d', ('person_id',),
        ),
        perm_filter='can_set_otp_secret',
    )

    def person_otp_set(self, operator, person_ident, secret):
        person = self._get_entity(entity_type='person', ident=person_ident)
        self.ba.can_set_otp_secret(operator.get_entity_id(), person=person)

        try:
            validate_secret(secret)
        except ValueError as e:
            raise CerebrumError(e)

        self.otp_util.update(person.entity_id, secret)
        return {
            'person_id': int(person.entity_id),
        }

    #
    # person otp_clear <person>
    #

    all_commands['person_otp_clear'] = Command(
        ('person', 'otp_clear'),
        PersonId(help_ref="id:target:person"),
        fs=FormatSuggestion(
            'OK, cleared OTP secret for person_id: %d', ('person_id',),
        ),
        perm_filter='can_clear_otp_secret',
    )

    def person_otp_clear(self, operator, person_ident):
        person = self._get_entity(entity_type='person', ident=person_ident)
        self.ba.can_clear_otp_secret(operator.get_entity_id(), person=person)
        self.otp_util.clear_all(person.entity_id)
        return {
            'person_id': int(person.entity_id),
        }


COMMAND_HELP = {
    'person': {
        'person_otp_info': 'Show registered OTP type (targets) for person',
        'person_otp_set': 'Set a new OTP secret for a person',
        'person_otp_clear': 'Clear all OTP secrets for a person',
    }
}

ARGUMENT_HELP = {
    'otp_shared_secret':
        ['otp-secret', 'OTP shared secret',
         'An OTP shared secret to use (in base32 representation)'],
}
