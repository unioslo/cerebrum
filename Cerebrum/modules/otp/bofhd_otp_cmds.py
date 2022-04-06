# -*- coding: utf-8 -*-
#
# Copyright 2021-2022 University of Oslo, Norway
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
Bofhd ``person otp_*`` commands for managing shared otp secrets.
"""
from operator import itemgetter

from Cerebrum import Errors
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
from Cerebrum.utils.aggregate import unique

from . import otp_db
from . import otp_utils
from .otp_types import PersonOtpUpdater, get_policy


class OtpSessionCache(object):
    """
    Temporary otp secret storage in the bofhd operator session.

    When we generate or store otp secrets in bofhd, we temporarily store the
    secret in plaintext, so that the operator can retrieve it and pass it on to
    the user.
    """

    state_type = "person_otp_secret"

    def __init__(self, session):
        """
        :type session: Cerebrum.modules.bofhd.session.BofhdSession
        :param session: Operator session (`operator` in bofhd commands)
        """
        self._session = session

    def set(self, person_id, secret):
        """ Add a secret to the session cache. """
        self._session.store_state(
            self.state_type,
            {
                'person_id': int(person_id),
                'secret': secret,
            },
        )

    def clear(self, person_id):
        """ Clear a secret from the session cache. """
        # Session state is a bit bare-bones, and there are no good ways to
        # *remove* a single entry.  We cheat by setting the latest entry to
        # None, and removing blank entries when listing.
        self.set(person_id, None)

    def list(self):
        """ Get most recent secret for each person in the session cache. """
        # Get all relevant rows, ordered by set_time:
        all_entries = [row['state_data']
                       for row in self._session.get_state(self.state_type)]
        # Remove duplicate entries, keeping only the most recent:
        most_recent = list(unique(reversed(all_entries),
                           key=itemgetter('person_id')))
        # Reverse and remove cleared (empty) secrets:
        return [item for item in reversed(most_recent) if item['secret']]

    def clear_all(self):
        """ Clear all secrets in the session cache. """
        self._session.clear_state(state_types=self.state_type)


class OtpAuth(BofhdAuth):
    """
    Auth for person otp_* commands.

    Overview
    --------
    If a person is *protected* from otp changes through bofhd
    (see py:meth:`._is_otp_protected`), then no-one (not even superuser) is
    allowed to alter the otp secrets of this person.

    Otherwise, operators must be superuser, or be granted access through
    op-sets to modify otp secrets.  As with many other bofhd commands, the
    operations are bound to *global host* - i.e any grant to
    *op-set with otp-operation @ global host* will grant access to
    *all persons*.

    Operations
    ----------
    ``person_otp_set[attr="generate"]``
        Allowed to generate a secret, *not* allowed to set a user defined
        secret.

    ``person_otp_set[attr="specify"]``
        Allowed to speficy a user defined secret - only useful if migrating a
        shared secret from elsewhere

    ``person_otp_set[]``
        Allowed to to both generate and speficy a secret

    ``person_otp_clear[]``
        Allowed to to clear an exising secret

    .. note:: Both person_otp_set and person_otp_clear is needed to reset
    """

    def is_otp_operator(self, operator, query_run_any=True):
        """
        Check if operator has _any_ otp-specific permissions.

        .. important::
            Can only be used as perm_filter or in branching.  Never raises
            PermissionDenied.
        """
        if self.is_superuser(operator):
            return True

        for op_type in (self.const.auth_person_otp_set,
                        self.const.auth_person_otp_clear):
            if self._has_operation_perm_somewhere(operator, op_type):
                return True
        return False

    def _is_otp_protected(self, person):
        """
        Check if person is protected from otp changes in bofhd.

        An *otp protected* person cannot have their otp secret modified through
        bofhd - not even by superusers.
        """
        return False

    def can_show_otp_info(self, operator, person=None, query_run_any=False):
        """
        Verify access to show otp state/list otp-types for a given person.

        :param int operator: entity_id of the authenticated user
        :param person: A cerebrum person object
        """
        if self.is_otp_operator(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("No access to otp info")

    def _get_otp_set_perms(self, operator):
        """ Get relevant operator op-attrs for operation 'person_otp_set'. """
        # We collect all relevant op-attrs from list_target_permissions, so
        # that we can separate between access to operation and access to
        # op-attr without having to do multiple queries
        all_attrs = set(("generate", "specify"))
        collected = set()

        for row in self._list_target_permissions(
                operator=operator,
                operation=self.const.auth_person_otp_set,
                target_type=self.const.auth_target_type_global_host,
                target_id=None,
                get_all_op_attrs=True):
            # op has access to at least *one* opset with person_otp_set ...
            op_attr = row.get('operation_attr')
            if not op_attr:
                # ... and that opset has no op-attr limitations - this means
                # that op has access to *all* relevant op-attrs through that
                # opset
                return set(all_attrs)

            if op_attr in all_attrs:
                # ... with a specific op-attr
                collected.add(op_attr)

            if collected == all_attrs:
                # short circuit - op already has all relevant op attrs, no need
                # to check other opsets/op-attrs
                break
        return collected

    def can_set_otp_secret(self, operator, person=None, generate=True,
                           query_run_any=False):
        """
        Verify access to set otp secret for a given person.

        :param int operator: entity_id of the authenticated user
        :param person: A cerebrum person object
        :param generate: If the secret is generated by us, and not given by op
        """
        if query_run_any:
            if self.is_superuser(operator):
                return True
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_person_otp_set)

        if self._is_otp_protected(person):
            raise PermissionDenied('Person is protected from otp changes')

        if self.is_superuser(operator):
            return True

        op_attr = "generate" if generate else "specify"
        perms = self._get_otp_set_perms(operator)
        if op_attr in perms:
            return True

        if perms:
            # Access to person_set_otp, but missing required op-attr
            raise PermissionDenied("Not allowed to %s shared otp secret"
                                   % (op_attr,))
        # No access to person_set_otp at all
        raise PermissionDenied("Not allowed to set shared otp secret")

    def can_clear_otp_secret(self, operator, person=None, query_run_any=False):
        """
        Verify access to clear otp secret for a given person.

        :param int operator: entity_id of the authenticated user
        :param person: A cerebrum person object
        """
        op_type = self.const.auth_person_otp_clear
        if query_run_any:
            if self.is_superuser(operator):
                return True
            return self._has_operation_perm_somewhere(operator, op_type)

        if self._is_otp_protected(person):
            raise PermissionDenied('Person is protected from otp changes')

        if self.is_superuser(operator):
            return True

        if self._has_target_permissions(
                operator=operator,
                operation=op_type,
                target_type=self.const.auth_target_type_global_host,
                target_id=None,
                victim_id=None):
            return True

        raise PermissionDenied("Not allowed to clear shared otp secret")


def _get_person_name(person):
    """ get full name from a person object. """
    try:
        return person.get_name(person.const.system_cached,
                               person.const.name_full)
    except Errors.NotFoundError:
        return None


def _get_primary_account(person):
    """ get primary account object from a person object. """
    account_id = person.get_primary_account()
    if account_id is None:
        return None
    account = Factory.get('Account')(person._db)
    try:
        account.find(account_id)
        return account
    except Errors.NotFoundError:
        return None


class OtpCommands(BofhdCommandBase):
    """BofhdExtension for history related commands and functionality."""

    all_commands = {}
    authz = OtpAuth

    @property
    def otp_policy(self):
        """ default otp policy. """
        try:
            self.__otp_pol
        except AttributeError:
            self.__otp_pol = get_policy()
        return self.__otp_pol

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
        """ Show registered OTP types (targets) for a person. """
        person = self._get_entity(entity_type='person', ident=person_ident)
        self.ba.can_show_otp_info(operator.get_entity_id(), person=person)
        otp_data = otp_db.sql_search(self.db, person_id=person.entity_id)
        if not otp_data:
            raise CerebrumError('No OTP secret set for person %r' %
                                (person_ident,))

        return [{
            'person_id': row['person_id'],
            'otp_type': row['otp_type'],
            'updated_at': row['updated_at'],
        } for row in otp_data]

    #
    # person otp_set <person> [secret]
    #
    all_commands['person_otp_set'] = Command(
        ('person', 'otp_set'),
        PersonId(help_ref="id:target:person"),
        SimpleString(help_ref='otp-secret', optional=True),
        fs=FormatSuggestion(
            "\n".join((
                "OK, stored OTP secret for person_id: %d",
                "(use 'person otp_session_list' to show secrets from"
                " this session)",
            )),
            ('person_id',),
        ),
        perm_filter='can_set_otp_secret',
    )

    def _set_otp_secret(self, session, person_id, secret):
        PersonOtpUpdater(self.db, self.otp_policy).update(person_id, secret)
        OtpSessionCache(session).set(person_id, secret)

    def person_otp_set(self, operator, person_ident, secret=None):
        """ Set or reset OTP secret for a person. """
        person = self._get_entity(entity_type='person', ident=person_ident)
        self.ba.can_set_otp_secret(operator.get_entity_id(),
                                   person=person, generate=not secret)

        for row in otp_db.sql_search(self._db, person_id=person.entity_id):
            # This check is here for *two* reasons:
            #
            # 1. we want operators to explicitly *decide* to clear/reset otp
            #    secrets if already set.
            #
            # 2. operator may not have access to reset otp secrets - this is
            #    checked by person_otp_clear.
            #
            raise CerebrumError(
                "OTP secret already set for id:%d, "
                "must be cleared (person otp_clear)"
                % (person.entity_id, ))

        if not secret:
            secret = otp_utils.generate_secret()

        try:
            otp_utils.validate_secret(secret)
        except ValueError as e:
            raise CerebrumError(e)

        self._set_otp_secret(operator, person.entity_id, secret)
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

    def _clear_otp_secret(self, session, person_id):
        PersonOtpUpdater(self.db, self.otp_policy).clear_all(person_id)
        OtpSessionCache(session).clear(person_id)

    def person_otp_clear(self, operator, person_ident):
        """ Clear all OTP secrets set for a person. """
        person = self._get_entity(entity_type='person', ident=person_ident)
        self.ba.can_clear_otp_secret(operator.get_entity_id(), person=person)

        self._clear_otp_secret(operator, person.entity_id)
        return {
            'person_id': int(person.entity_id),
        }

    #
    # person otp_session_list
    #
    all_commands['person_otp_session_list'] = Command(
        ('person', 'otp_session_list'),
        fs=FormatSuggestion(
            "%-8s  %-10s  %s", ("person_id", "account_name", "uri"),
            hdr="%-8s  %-10s  %s" % ("Id", "Primary",  "Uri")
        ),
        perm_filter='is_otp_operator',
    )

    def _get_otp_session_entry(self, session_data):
        person_id = session_data['person_id']
        secret = session_data['secret']

        entry = {
            'person_id': person_id,
            'person_name': None,
            'secret': secret,
            'uri': otp_utils.format_otp_uri(secret),
            'account_name': None,
            'account_id': None,
        }

        pe = Factory.get('Person')(self.db)
        pe.find(person_id)
        entry['person_name'] = _get_person_name(pe)
        ac = _get_primary_account(pe)
        if ac:
            entry.update({
                'account_name': ac.account_name,
                'account_id': ac.entity_id,
            })
        return entry

    def person_otp_session_list(self, operator):
        """ List otpauth uris for secrets set in current session. """
        # No access check - anyone has access to their own session data
        # perm_filter is only there to hide the command if not relevant
        cached_secrets = OtpSessionCache(operator).list()
        if not cached_secrets:
            raise CerebrumError('No otp secrets set in current session')

        return [self._get_otp_session_entry(item) for item in cached_secrets]

    #
    # person otp_session_clear
    #
    all_commands['person_otp_session_clear'] = Command(
        ('person', 'otp_session_clear'),
        fs=FormatSuggestion(
            'OK, cleared %d entries from session cache', ('count',),
        ),
        perm_filter='is_otp_operator',
    )

    def person_otp_session_clear(self, operator):
        """ Clear otpauth uris for secrets set in current session. """
        # No access check - anyone has access to their own session data
        # perm_filter is only there to hide the command if not relevant
        session_cache = OtpSessionCache(operator)
        session_data = session_cache.list()

        # We want to run `OtpSessionCache.clear_all` even if `session_data` is
        # empty, as session *could* contain cleared otp secrets.
        session_cache.clear_all()
        return {
            'count': len(session_data),
        }


def _from_docstring(func):
    return func.__doc__.strip().split('\n')[0]


COMMAND_HELP = {
    'person': {
        'person_otp_info': _from_docstring(OtpCommands.person_otp_info),
        'person_otp_set': _from_docstring(OtpCommands.person_otp_set),
        'person_otp_clear': _from_docstring(OtpCommands.person_otp_clear),
        'person_otp_session_list':
            _from_docstring(OtpCommands.person_otp_session_list),
        'person_otp_session_clear':
            _from_docstring(OtpCommands.person_otp_session_clear),
    }
}

ARGUMENT_HELP = {
    'otp-secret': [
        'otp-secret',
        'OTP shared secret',
        'An OTP shared secret to use (in base32 representation)',
    ],
}
