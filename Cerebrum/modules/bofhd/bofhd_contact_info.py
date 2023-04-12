# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway
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
""" This module contains contact_info related commands in bofhd.

NOTE: The classes in this module should probably not be used directly. Make
subclasses of the classes here, and mix in the proper auth classes.

E.g. given a ``FooAuth`` class that implements or overrides the core
``BofhdAuth`` authorization checks, you should create:
::

    class FooContactAuth(FooAuth, BofhdContactAuth):
        pass


    class FooContactCommands(BofhdContactCommands):
        authz = FooContactAuth

Then list the FooContactCommands in your bofhd configuration file. This way,
any override done in FooAuth (e.g. is_superuser) will also take effect in these
classes.

"""
from __future__ import unicode_literals

import logging
import re
import textwrap

import six

from Cerebrum.Constants import (
    _AuthoritativeSystemCode,
    _ContactInfoCode,
    _EntityTypeCode,
)
from Cerebrum.Entity import EntityContactInfo
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.bofhd_utils import format_time
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    SimpleString,
    SourceSystem,
    get_format_suggestion_table,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd.utils import BofhdUtils
from Cerebrum.utils import date_compat
from Cerebrum.utils.email import legacy_validate_lp, legacy_validate_domain


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


def _get_contact_type(const, value, user_input=False, optional=False):
    """ Get a contact type constant.  """
    return _get_constant(const, _ContactInfoCode, value,
                         "contact type" if user_input else None, optional)


def _get_source_system(const, value, user_input=False, optional=False):
    """ Get a source system constant. """
    return _get_constant(const, _AuthoritativeSystemCode, value,
                         "source system" if user_input else None, optional)


def _get_entity_type(const, value, user_input=False, optional=False):
    """ Get an entity type constant. """
    return _get_constant(const, _EntityTypeCode, value,
                         "entity type" if user_input else None, optional)


class BofhdContactAuth(BofhdAuth):
    """ Auth for entity contactinfo_* commands. """

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

    def can_get_contact_info(self, operator,
                             entity=None,
                             contact_type=None,
                             query_run_any=False):
        """ Check if an operator is allowed to see contact info.

        :param int operator: entity_id of the authenticated user
        :param entity: A cerebrum entity object (e.g. person, account)
        :param contact_type: A ContactInfo constant
        """
        if self.is_superuser(operator):
            return True

        if query_run_any:
            return True

        if self._is_owned_by_operator(operator, entity):
            return True

        entity_type = _get_entity_type(self.const, entity.entity_type)
        contact_type = _get_contact_type(self.const, contact_type)

        # check for permission through opset
        op_attr = six.text_type(contact_type)
        if (self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_view_contactinfo,
                target_type=self.const.auth_target_type_host,
                target_id=entity.entity_id,
                victim_id=entity.entity_id,
                operation_attr=op_attr)
            or self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_view_contactinfo,
                target_type=self.const.auth_target_type_disk,
                target_id=entity.entity_id,
                victim_id=entity.entity_id,
                operation_attr=op_attr)
            or self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_view_contactinfo,
                target_type=self.const.auth_target_type_ou,
                target_id=entity.entity_id,
                victim_id=entity.entity_id,
                operation_attr=op_attr)):
            return True

        raise PermissionDenied(
            "Not allowed to see contact info %s for entity type=%s, id=%d"
            % (op_attr, entity_type, entity.entity_id))

    def can_add_contact_info(self, operator,
                             entity=None,
                             contact_type=None,
                             source_system=None,
                             query_run_any=False):
        """ Check if an operator is allowed to add manual contact info.

        :param int operator: entity_id of the authenticated user
        :param entity: A cerebrum entity object (e.g. person, account)
        :type contact_type: _ContactInfoCode
        :type source_system: _AuthoritativeSystemCode
        """
        # Superusers can see and run command
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_add_contactinfo)

        entity_type = _get_entity_type(self.const, entity.entity_type)
        source_system = _get_source_system(self.const, source_system)
        contact_type = _get_contact_type(self.const, contact_type)

        # check for permission through opset
        op_attr = six.text_type(contact_type)
        # TODO: should refactor op-attrs and check for:
        #   - <source-system>:<contact-type>
        #   - <source-system>:*
        #   - *:<contact-type>
        if (self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_add_contactinfo,
                target_type=self.const.auth_target_type_host,
                target_id=entity.entity_id,
                victim_id=entity.entity_id,
                operation_attr=op_attr)
            or self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_add_contactinfo,
                target_type=self.const.auth_target_type_disk,
                target_id=entity.entity_id,
                victim_id=entity.entity_id,
                operation_attr=op_attr)
            or self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_add_contactinfo,
                target_type=self.const.auth_target_type_ou,
                target_id=entity.entity_id,
                victim_id=entity.entity_id,
                operation_attr=op_attr)):
            return True
        raise PermissionDenied(
            "Not allowed to add contact info %s for entity type=%s, id=%d"
            % (op_attr, entity_type, entity.entity_id))

    def can_remove_contact_info(self, operator,
                                entity=None,
                                contact_type=None,
                                source_system=None,
                                query_run_any=False):
        """ Check if an operator is allowed to remove contact info.

        :param int operator: entity_id of the authenticated user
        :param entity: A cerebrum entity object (e.g. person, account)
        :param contact_type: A ContactInfo constant
        :param source_system: An AuthoritativeSystem constant
        """
        # Superusers can see and run command
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_remove_contactinfo)

        entity_type = _get_entity_type(self.const, entity.entity_type)
        source_system = _get_source_system(self.const, source_system)
        contact_type = _get_contact_type(self.const, contact_type)

        # check for permission through opset
        op_attr = six.text_type(contact_type)
        # TODO: should refactor op-attrs and check for:
        #   - <source-system>:<contact-type>
        #   - <source-system>:*
        #   - *:<contact-type>
        if (self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_remove_contactinfo,
                target_type=self.const.auth_target_type_host,
                target_id=entity.entity_id,
                victim_id=entity.entity_id,
                operation_attr=op_attr)
            or self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_remove_contactinfo,
                target_type=self.const.auth_target_type_disk,
                target_id=entity.entity_id,
                victim_id=entity.entity_id,
                operation_attr=op_attr)
            or self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_remove_contactinfo,
                target_type=self.const.auth_target_type_ou,
                target_id=entity.entity_id,
                victim_id=entity.entity_id,
                operation_attr=op_attr)):
            return True
        raise PermissionDenied(
            "Not allowed to remove contact info %s for entity type=%s, id=%d"
            % (op_attr, entity_type, entity.entity_id))

    def can_search_contact_info(self, operator,
                                contact_type=None,
                                query_run_any=False):
        """ Check if an operator is allowed to search for contact info.

        :param int operator: entity_id of the authenticated user
        :param contact_type: A ContactInfo constant
        """
        if self.is_superuser(operator):
            return True

        if query_run_any:
            return False

        if contact_type:
            contact_type = _get_contact_type(self.const, contact_type)
            op_attr = six.text_type(contact_type)
            raise PermissionDenied(
                "Not allowed to search for contact info %s"
                % (op_attr,))
        else:
            raise PermissionDenied(
                "Not allowed to search for all contact info")


CMD_HELP = {
    'entity': {
        'entity_contactinfo_show':
            'show registered contact info',
        'entity_contactinfo_add':
            'add contact information to an entity',
        'entity_contactinfo_remove':
            'remove contact information from an entity',
        'entity_contactinfo_search':
            'find entities with a given contact info value',
    },
}

CMD_ARGS = {
    'entity-contact-source': [
        "entity-contact-source",
        "Enter source system",
        textwrap.dedent(
            """
            Name of a source system for the contact info type.

            An empty value can be given to mean "no source system" if this
            value is optional.

            Source systems:

            """
        ).lstrip(),
    ],
    'entity-contact-type': [
        "entity-contact-type",
        "Enter contact type",
        textwrap.dedent(
            """
            The name of a contact info type.

            Contact info types:

            """
        ).lstrip(),
    ],
    'entity-contact-value': [
        "entity-contact-value",
        "Enter contact info value",
        "A valid contact info value.",
    ],
}


class BofhdContactCommands(BofhdCommandBase):

    all_commands = {}
    authz = BofhdContactAuth
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
        cinfo_sources = sorted(co.fetch_constants(_AuthoritativeSystemCode),
                               key=six.text_type)
        cinfo_types = sorted(co.fetch_constants(_ContactInfoCode),
                             key=six.text_type)

        # Enrich cmd_args with actual constants.
        cmd_args = {}
        for k, v in CMD_ARGS.items():
            cmd_args[k] = v[:]
            if k == 'entity-contact-source':
                cmd_args[k][2] += "\n".join(
                    " - " + six.text_type(c) for c in cinfo_sources)
            if k == 'entity-contact-type':
                cmd_args[k][2] += "\n".join(
                    " - " + six.text_type(c) for c in cinfo_types)
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

    def _check_cinfo_modify_support(self, entity, search_string):
        """ helper - check if a given entity can get any cinfo modified. """
        if not isinstance(entity, EntityContactInfo):
            raise CerebrumError(
                "No support for contact info in %s"
                % self._format_match(entity, search_string))

    #
    # entity contactinfo_add <entity> <contact type> <contact value>
    #
    all_commands['entity_contactinfo_add'] = Command(
        ('entity', 'contactinfo_add'),
        SimpleString(help_ref='id:target:entity'),
        SimpleString(help_ref='entity-contact-type'),
        SimpleString(help_ref='entity-contact-value'),
        fs=FormatSuggestion(
            "Added contact info %s:%s '%s' to '%s' with id=%d",
            ('source_system', 'contact_type', 'contact_value', 'entity_type',
             'entity_id')
        ),
        perm_filter='can_add_contact_info',
    )

    def _normalize_cinfo(self, contact_type, contact_value,
                         contact_source=None):
        """
        Validate and normalize a new contact info value.

        :type contact_type: Cerebrum.Constants._ContactInfoCode
        :type contact_value: str
        :type contact_source: Cerebrum.Constants._AuthoritativeSystemCode

        :throws CerebrumError:
            Throws a bofhd client error if the given external id is not valid.
        """
        # validate email
        if contact_type == self.const.contact_email:
            # validate localpart and extract domain
            if contact_value.count('@') != 1:
                raise CerebrumError(
                    "Email address (%s) must be on form <localpart>@<domain>"
                    % repr(contact_value))
            localpart, domain = contact_value.split('@')
            # normalize domain-part:
            domain = domain.lower()
            try:
                legacy_validate_lp(localpart)
                legacy_validate_domain(domain)
                return localpart + "@" + domain
            except ValueError as e:
                raise CerebrumError(e)

        # validate phone numbers
        if contact_type in (self.const.contact_phone,
                            self.const.contact_phone_private,
                            self.const.contact_mobile_phone,
                            self.const.contact_private_mobile):
            # allows digits and a prefixed '+'
            # TODO: Proper nomalized numbers (Cerebrum.utils.phone)
            if not re.match(r"^\+?\d+$", contact_value):
                raise CerebrumError(
                    "Phone number (%s) can only contain digits, optionally "
                    "with a '+' prefix"
                    % repr(contact_value))
            return contact_value

        # TODO: Normalize other types?
        return contact_value

    def entity_contactinfo_add(self, operator,
                               entity_target, contact_type, contact_value):
        """ Manually add contact info to an entity. """
        # default values
        contact_pref = 50
        # TODO: We should probably have a source_system argument - it could be
        # useful to allow superusers to fix non-manual values
        source_system = self.const.system_manual

        # Look up and validate user input
        entity = self.util.get_target(entity_target, restrict_to=[])
        entity_type = self.const.EntityType(int(entity.entity_type))
        contact_type = _get_contact_type(self.const, contact_type,
                                         user_input=True)
        contact_value = self._normalize_cinfo(contact_type, contact_value,
                                              source_system)

        # check for support, permission
        self._check_cinfo_modify_support(entity, entity_target)
        self.ba.can_add_contact_info(operator.get_entity_id(),
                                     entity=entity,
                                     contact_type=contact_type,
                                     source_system=source_system)

        # get existing contact info for this entity and contact type
        contacts = entity.get_contact_info(source=source_system,
                                           type=contact_type)

        # TODO: Replace all this with contact-info-sync?
        existing_prefs = [int(row["contact_pref"]) for row in contacts]

        for row in contacts:
            # if the same value already exists, don't add it
            # case-insensitive check for existing email address
            if contact_value.lower() == row["contact_value"].lower():
                raise CerebrumError(
                    "Can't set contact type %s for %s: already exists"
                    % (contact_type,
                       self._format_match(entity, entity_target)))
            # if the value is different, add it with a lower (=greater number)
            # preference for the new value
            if contact_pref == row["contact_pref"]:
                contact_pref = max(existing_prefs) + 1
                logger.debug(
                    'Incremented preference, new value = %d' % contact_pref)

        logger.debug('Adding contact info: %r, %r, %r, %r',
                     entity.entity_id,
                     six.text_type(contact_type),
                     contact_value,
                     contact_pref)

        entity.add_contact_info(source=source_system,
                                type=contact_type,
                                value=contact_value,
                                pref=int(contact_pref),
                                description=None,
                                alias=None)

        return {
            'source_system': six.text_type(source_system),
            'contact_type': six.text_type(contact_type),
            'contact_value': six.text_type(contact_value),
            'entity_type': six.text_type(entity_type),
            'entity_id': int(entity.entity_id),
        }

    #
    # entity contactinfo_remove <entity> <source system> <contact type>
    #
    all_commands['entity_contactinfo_remove'] = Command(
        ("entity", "contactinfo_remove"),
        SimpleString(help_ref='id:target:entity'),
        SourceSystem(help_ref='entity-contact-source'),
        SimpleString(help_ref='entity-contact-type'),
        fs=FormatSuggestion([
            ("Removed contact info %s:%s from %s with id=%d",
             ('source_system', 'contact_type', 'entity_type', 'entity_id',)),
            ("Old value: '%s'",
             ('contact_value', )),
            ('Warning: %s', ('warning',)),
        ]),
        perm_filter='can_remove_contact_info')

    def entity_contactinfo_remove(self, operator, entity_target, source_system,
                                  contact_type):
        """
        Deleting an entity's contact info from a given source system. Useful in
        cases where the entity has old contact information from a source system
        he no longer is exported from, i.e. no affiliations.
        """
        # Look up and validate user input
        entity = self.util.get_target(entity_target, restrict_to=[])
        entity_type = self.const.EntityType(int(entity.entity_type))
        source_system = _get_source_system(self.const, source_system,
                                           user_input=True)
        contact_type = _get_contact_type(self.const, contact_type,
                                         user_input=True)

        # check for support, permission
        self._check_cinfo_modify_support(entity, entity_target)
        self.ba.can_remove_contact_info(operator.get_entity_id(),
                                        entity=entity,
                                        contact_type=contact_type,
                                        source_system=source_system)

        warning = None
        if (entity_type == self.const.entity_person
                and source_system != self.const.system_manual):
            if int(source_system) in set(int(a['source_system'])
                                         for a in entity.get_affiliations()):
                # person is still affiliated with the given source system
                warning = (
                    'person has affiliation from source_system %s' %
                    (source_system,))

        # check if given contact info type exists for this entity
        contact_info = entity.get_contact_info(source=source_system,
                                               type=contact_type)
        if not contact_info:
            raise CerebrumError("No contact info of type %s:%s for: %s"
                                % (six.text_type(source_system),
                                   six.text_type(contact_type),
                                   self._format_match(entity, entity_target)))
        else:
            contact_info = contact_info.pop(0)

        logger.debug('Removing contact info: %r, %r, %r',
                     entity.entity_id,
                     six.text_type(source_system),
                     six.text_type(contact_type))
        try:
            entity.delete_contact_info(source=source_system,
                                       contact_type=contact_type)
            entity.write_db()
        except Exception:
            raise CerebrumError(
                "Could not remove contact info of type %s:%s for: %s"
                % (six.text_type(source_system),
                   six.text_type(contact_type),
                   self._format_match(entity, entity_target)))

        result = {
            'source_system': six.text_type(source_system),
            'contact_type': six.text_type(contact_type),
            'entity_type': six.text_type(entity_type),
            'entity_id': int(entity.entity_id),
        }

        try:
            self.ba.can_get_contact_info(operator.get_entity_id(),
                                         entity=entity,
                                         contact_type=contact_type)
            result['contact_value'] = six.text_type(
                contact_info['contact_value'])
        except PermissionDenied:
            pass

        if warning:
            result['warning'] = warning

        return result

    def _search_cinfo(self, entity_id=None, entity_type=None,
                      cinfo_source=None, cinfo_type=None, cinfo_value=None,
                      limit=search_limit):
        """ Get formatted and limited results from list_contact_info. """
        cinfo_db = EntityContactInfo(self.db)
        # TODO: Consider making a contact info search method, for dealing with
        # patterns?
        for count, row in enumerate(
                cinfo_db.list_contact_info(entity_id=entity_id,
                                           entity_type=entity_type,
                                           source_system=cinfo_source,
                                           contact_type=cinfo_type,
                                           contact_value=cinfo_value,
                                           # TODO: in a search, we don't want
                                           # fetchall...
                                           # fetchall=False,
                                           ), 1):
            result = {
                'entity_id': int(row['entity_id']),
                # TODO: ideally, we want to include entity type in results, but
                # list_contact_info doesn't support this...
                #   'entity_type': six.text_type(
                #       _get_entity_type(self.const, row['entity_type'])),
                'contact_type': six.text_type(
                    _get_contact_type(self.const, row['contact_type'])),
                'source_system': six.text_type(
                    _get_source_system(self.const, row['source_system'])),
                'modified': date_compat.get_datetime_tz(
                    row['last_modified']),
                'contact_value': row['contact_value'],
                'contact_alias': row['contact_alias'],
                # Not sure why contact_pref is text ...
                'contact_pref': six.text_type(row['contact_pref']),
                'description': row['description'],
            }

            yield result
            if count < limit:
                continue
            yield {'limit': int(limit)}
            break

    #
    # entity contactinfo_show <entity>
    #
    all_commands['entity_contactinfo_show'] = Command(
        ("entity", "contactinfo_show"),
        SimpleString(help_ref='id:target:entity'),
        fs=get_format_suggestion_table(
            ('source_system', 'Source', 15, 's', True),
            ('contact_type', 'Type', 15, 's', True),
            ('contact_pref', 'Weight', 8, 's', False),
            (format_time('modified'), 'Modified', 16, 's', False),
            ('contact_value', 'Value', 24, 's', False),
            limit_key='limit',
        ),
        perm_filter='can_get_contact_info')

    def entity_contactinfo_show(self, operator, entity_target):
        """ Show contact info of an entity. """

        entity = self.util.get_target(entity_target, restrict_to=[])

        # This is oddly restrictive
        def get_allowed_types():
            for contact_type in self.const.fetch_constants(_ContactInfoCode):
                try:
                    self.ba.can_get_contact_info(operator.get_entity_id(),
                                                 entity=entity,
                                                 contact_type=contact_type)
                    yield contact_type
                except PermissionDenied:
                    continue

        contact_types = list(get_allowed_types())
        if not contact_types:
            raise PermissionDenied("Not allowed to see any contact info for %s"
                                   % self._format_match(entity, entity_target))

        # Note that contact types that aren't listed won't be shown in the
        # results *at all*.
        #
        # We should include all *types* but *censor* the values that the
        # operator aren't permitted to get?
        #
        # We should re-work the permissions a bit here, maybe
        contact_info = list(self._search_cinfo(entity_id=int(entity.entity_id),
                                               cinfo_type=contact_types))

        if not contact_info:
            raise CerebrumError("No contact info for %s"
                                % self._format_match(entity, entity_target))

        return contact_info

    #
    # entity contactinfo_search <contact-tyupe> <contact-value>
    #
    # Note: Currently not a proper search, as list_contact_info doesn't support
    # wildcards.
    #
    all_commands['entity_contactinfo_search'] = Command(
        ("entity", "contactinfo_search"),
        SimpleString(help_ref='entity-contact-value'),
        SimpleString(help_ref='entity-contact-type', optional=True),
        fs=get_format_suggestion_table(
            ('entity_id', 'Entity Id', 15, 's', True),
            ('source_system', 'Source', 15, 's', True),
            ('contact_type', 'Type', 15, 's', True),
            ('contact_value', 'Value', 24, 's', False),
            limit_key='limit',
        ),
        perm_filter='can_search_contact_info')

    def entity_contactinfo_search(self, operator, contact_value, _c_type=None):
        """ Show contact info of an entity. """
        contact_type = _get_contact_type(self.const, _c_type,
                                         user_input=True, optional=True)

        self.ba.can_search_contact_info(operator.get_entity_id(),
                                        contact_type=contact_type)

        # Since we can't actually search yet, let's inlcude the normalized
        # value too, if it's different...
        values = set((contact_value,))
        try:
            values.add(self._normalize_cinfo(contact_type, contact_value))
        except Exception:
            pass

        contact_info = list(self._search_cinfo(cinfo_type=contact_type,
                                               cinfo_value=values))
        #
        # Should we check for permissions to *get* a given value too?
        #
        if not contact_info:
            raise CerebrumError("No contact info of type %s matching %s"
                                % (contact_type,
                                   ", ".join(repr(v) for v in values)))

        return contact_info
