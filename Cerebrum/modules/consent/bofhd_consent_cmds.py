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
This module implements basic commands for interacting with consents.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import six

from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    Id,
    Parameter,
    get_format_suggestion_table,
)
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.help import merge_help_strings

from .Consent import EntityConsentMixin
from .bofhd_consent_auth import BofhdConsentAuth


class ConsentType(Parameter):
    """ Consent type parameter. """
    _type = 'consent_type'
    _help_ref = 'consent-type'


def _format_dt(field):
    """ Date format for FormatSuggestion. """
    fmt = "yyyy-MM-dd HH:mm"  # 16 characters wide
    return ":".join((field, "date", fmt))


class BofhdExtension(BofhdCommonMethods):
    """ Commands for getting, setting and unsetting consent. """

    hidden_commands = {}  # Not accessible through bofh
    all_commands = {}
    parent_commands = False
    authz = BofhdConsentAuth

    def __init__(self, *args, **kwargs):
        super(BofhdExtension, self).__init__(*args, **kwargs)
        # POST:
        for attr in ('ConsentType', 'EntityConsent'):
            if not hasattr(self.const, attr):
                raise RuntimeError('consent: Missing consent constant types')

    @classmethod
    def get_help_strings(cls):
        """ Help strings for consent commands. """
        group, cmd, args = {}, {}, {}

        group['consent'] = 'Commands for handling consents'
        cmd['consent'] = {
            'consent_set': cls.consent_set.__doc__,
            'consent_unset': cls.consent_unset.__doc__,
            'consent_info': cls.consent_info.__doc__,
            'consent_list': cls.consent_list.__doc__,
        }
        args.update({
            'consent-type': [
                'consent-type',
                'Enter consent type',
                "'consent list' lists defined consents",
            ],
        })

        return merge_help_strings(
            get_help_strings(),
            (group, cmd, args),
        )

    def check_consent_support(self, entity):
        """ Assert that entity has EntityConsentMixin.

        :param Cerebrum.Entity entity: The entity to check.

        :raise CerebrumError: If entity lacks consent support.
        """
        entity_type = self.const.EntityType(entity.entity_type)
        if not isinstance(entity, EntityConsentMixin):
            raise CerebrumError(
                "Entity type '%s' does not support consent."
                % six.text_type(entity_type))

    def _get_consent(self, consent_ident):
        """ Get consent constant from constant strval or intval.

        :type consent_ident: int, str, Cerebrum.Constant.ConstantCode
        :param consent_ident: Something to lookup a consent constant by

        :return tuple:
            A tuple consisting of a EntityConsent constant and its ConsentType
            constant.

        :raise Cerebrum.Error.NotFoundError: If the constant cannot be found.

        """
        # TODO: Replace with self.const.get_constant()
        consent = self.const.human2constant(
            consent_ident, const_type=self.const.EntityConsent)
        if not consent:
            raise CerebrumError("No consent %r" % consent_ident)
        consent_type = self.const.ConsentType(consent.consent_type)
        return (consent, consent_type)

    #
    # consent set <ident> <consent_type>
    #
    all_commands['consent_set'] = Command(
        ('consent', 'set'),
        Id(help_ref="id:target:account"),
        ConsentType(),
        fs=FormatSuggestion(
            "OK: Set consent '%s' (%s) for %s '%s' (entity_id=%s)",
            ('consent_name', 'consent_type', 'entity_type', 'entity_name',
             'entity_id')),
        perm_filter='can_set_consent',
    )

    def consent_set(self, operator, entity_ident, consent_ident):
        """ Set a consent for an entity. """
        entity = self.util.get_target(entity_ident, restrict_to=[])
        self.ba.can_set_consent(operator.get_entity_id(), entity)
        self.check_consent_support(entity)
        consent, consent_type = self._get_consent(consent_ident)
        entity_name = self._get_entity_name(entity.entity_id,
                                            entity.entity_type)
        entity.set_consent(consent)
        entity.write_db()
        return {
            'consent_name': six.text_type(consent),
            'consent_type': six.text_type(consent_type),
            'entity_id': entity.entity_id,
            'entity_type': six.text_type(
                self.const.EntityType(entity.entity_type)),
            'entity_name': entity_name,
        }

    #
    # consent unset <ident> <consent_type>
    #
    all_commands['consent_unset'] = Command(
        ('consent', 'unset'),
        Id(help_ref="id:target:account"),
        ConsentType(),
        fs=FormatSuggestion(
            "OK: Removed consent '%s' (%s) for %s '%s' (entity_id=%s)",
            ('consent_name', 'consent_type', 'entity_type', 'entity_name',
             'entity_id')),
        perm_filter='can_unset_consent',
    )

    def consent_unset(self, operator, entity_ident, consent_ident):
        """ Remove a previously set consent. """
        entity = self.util.get_target(entity_ident, restrict_to=[])
        self.ba.can_unset_consent(operator.get_entity_id(), entity)
        self.check_consent_support(entity)
        consent, consent_type = self._get_consent(consent_ident)
        entity_name = self._get_entity_name(entity.entity_id,
                                            entity.entity_type)
        entity.remove_consent(consent)
        entity.write_db()
        return {
            'consent_name': six.text_type(consent),
            'consent_type': six.text_type(consent_type),
            'entity_id': entity.entity_id,
            'entity_type': six.text_type(
                self.const.EntityType(entity.entity_type)),
            'entity_name': entity_name,
        }

    #
    # consent info <ident>
    #
    all_commands['consent_info'] = Command(
        ('consent', 'info'),
        Id(help_ref="id:target:account"),
        fs=get_format_suggestion_table(
            ('consent_name', 'Name', 15, 's', True),
            ('consent_type', 'Type', 8, 's', True),
            (_format_dt('consent_time_set'), 'Set at', 17, 's', True),
            (_format_dt('consent_time_expire'), 'Expires at', 17, 's', True),
            ('consent_description', 'Description', 30, 's', True),
        ),
        perm_filter='can_show_consent_info',
    )

    def consent_info(self, operator, ident):
        """ View all set consents for a given entity. """
        entity = self.util.get_target(ident, restrict_to=[])
        self.check_consent_support(entity)
        self.ba.can_show_consent_info(operator.get_entity_id(), entity)

        consents = []
        for row in entity.list_consents(entity_id=entity.entity_id):
            consent, consent_type = self._get_consent(int(row['consent_code']))
            consents.append({
                'consent_name': six.text_type(consent),
                'consent_type': six.text_type(consent_type),
                'consent_time_set': row['set_at'],
                # note: expire is no longer supported in consents
                'consent_time_expire': None,
                'consent_description': row['description'],
            })
        if not consents:
            name = self._get_entity_name(entity.entity_id, entity.entity_type)
            raise CerebrumError(
                "'%s' (entity_type=%s, entity_id=%s) has no consents set"
                % (
                    name,
                    six.text_type(self.const.EntityType(entity.entity_type)),
                    entity.entity_id,
                ))
        return consents

    #
    # consent list
    #
    all_commands['consent_list'] = Command(
        ('consent', 'list'),
        fs=get_format_suggestion_table(
            ('consent_name', 'Name', 15, 's', True),
            ('consent_type', 'Type', 8, 's', True),
            ('consent_description', 'Description', 30, 's', True),
        ),
        perm_filter='can_list_consents',
    )

    def consent_list(self, operator):
        """ List all consent types. """
        self.ba.can_list_consents(operator.get_entity_id())
        consents = []
        for consent in self.const.fetch_constants(self.const.EntityConsent):
            consent, consent_type = self._get_consent(int(consent))
            consents.append({
                'consent_name': six.text_type(consent),
                'consent_type': six.text_type(consent_type),
                'consent_description': consent.description,
            })
        if not consents:
            raise CerebrumError("No consent types defined yet")
        return consents
