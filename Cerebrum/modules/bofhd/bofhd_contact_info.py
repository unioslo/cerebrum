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

import six

from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.cmd_param import (Command, FormatSuggestion,
                                              SimpleString, SourceSystem)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd.utils import BofhdUtils


logger = logging.getLogger(__name__)


def format_time(field):
    """ build a FormatSuggestion field for DateTime.

    Note: The client should format a 16 char long datetime string.
    """
    fmt = "yyyy-MM-dd HH:mm"
    return ':'.join((field, "date", fmt))


class BofhdContactAuth(BofhdAuth):
    """ Auth for entity contactinfo_* commands. """

    def can_get_contact_info(self, operator,
                             entity=None,
                             contact_type=None,
                             query_run_any=False):
        """ Check if an operator is allowed to see contact info.

        :param int operator: entity_id of the authenticated user
        :param entity: A cerebrum entity object (e.g. person, account)
        :param contact_type: A ContactInfo constant
        """
        # TODO: Why is this the only permission that takes a person/entity
        # object, and not an entity_id?
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return True
        # check for permission through opset
        if (self._has_target_permissions(operator,
                                         self.const.auth_view_contactinfo,
                                         self.const.auth_target_type_host,
                                         entity.entity_id, entity.entity_id,
                                         six.text_type(contact_type)) or
            self._has_target_permissions(operator,
                                         self.const.auth_view_contactinfo,
                                         self.const.auth_target_type_disk,
                                         entity.entity_id, entity.entity_id,
                                         six.text_type(contact_type))):
            return True
        # The person itself should be able to see it:
        account = Factory.get('Account')(self._db)
        account.find(operator)
        if entity.entity_id == account.owner_id:
            return True
        raise PermissionDenied("Not allowed to see contact info")

    def can_add_contact_info(self, operator,
                             entity=None,
                             contact_type=None,
                             query_run_any=False):
        """ Check if an operator is allowed to add manual contact info.

        :param int operator: entity_id of the authenticated user
        :param entity: A cerebrum entity object (e.g. person, account)
        :param contact_type: A ContactInfo constant
        """
        # Superusers can see and run command
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_add_contactinfo)
        # check for permission through opset
        if (self._has_target_permissions(operator,
                                         self.const.auth_add_contactinfo,
                                         self.const.auth_target_type_host,
                                         entity.entity_id, entity.entity_id,
                                         six.text_type(contact_type)) or
            self._has_target_permissions(operator,
                                         self.const.auth_add_contactinfo,
                                         self.const.auth_target_type_disk,
                                         entity.entity_id, entity.entity_id,
                                         six.text_type(contact_type))):
            return True
        raise PermissionDenied("Not allowed to add contact info")

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
        # check for permission through opset
        if (self._has_target_permissions(operator,
                                         self.const.auth_remove_contactinfo,
                                         self.const.auth_target_type_host,
                                         entity.entity_id, entity.entity_id,
                                         six.text_type(contact_type)) or
            self._has_target_permissions(operator,
                                         self.const.auth_remove_contactinfo,
                                         self.const.auth_target_type_disk,
                                         entity.entity_id, entity.entity_id,
                                         six.text_type(contact_type))):
            return True
        raise PermissionDenied("Not allowed to remove contact info")


CMD_HELP = {
    'entity': {
        'entity_contactinfo_show':
            'show registered contact info',
        'entity_contactinfo_add':
            'add contact information to an entity',
        'entity_contactinfo_remove':
            'remove contact information from an entity',
    },
}

CMD_ARGS = {
    'entity_contact_source_system':
        ['source_system', 'Enter source system',
         'The name of the source system.'],
    'entity_contact_type':
        ['contact_type', 'Enter contact type',
         'The name of the contact type.'],
    'entity_contact_value':
        ['contact_value', 'Enter contact value',
         'Enter the valid contact information.'],
}


class BofhdContactCommands(BofhdCommandBase):

    all_commands = {}
    authz = BofhdContactAuth

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
        source_systems = co.fetch_constants(co.AuthoritativeSystem)
        contact_types = co.fetch_constants(co.ContactInfo)

        # Enrich cmd_args with actual constants.
        # TODO: Find a better way to do this for all similar cmd_args
        cmd_args = {}
        list_sep = '\n - '
        for k, v in CMD_ARGS.items():
            cmd_args[k] = v[:]
            if k == 'entity_contact_source_system':
                cmd_args[k][2] += '\nSource systems:'
                cmd_args[k][2] += list_sep + list_sep.join(six.text_type(c) for
                                                           c in source_systems)
            if k == 'entity_contact_type':
                cmd_args[k][2] += '\nContact types:'
                cmd_args[k][2] += list_sep + list_sep.join(six.text_type(c) for
                                                           c in contact_types)
        del co

        return merge_help_strings(
            ({}, {}, cmd_args),  # We want _our_ cmd_args to win!
            get_help_strings(),
            ({}, CMD_HELP, {}))

    #
    # entity contactinfo_add <entity> <contact type> <contact value>
    #
    all_commands['entity_contactinfo_add'] = Command(
        ('entity', 'contactinfo_add'),
        SimpleString(help_ref='id:target:entity'),
        SimpleString(help_ref='entity_contact_type'),
        SimpleString(help_ref='entity_contact_value'),
        fs=FormatSuggestion(
            "Added contact info %s:%s '%s' to '%s' with id=%d",
            ('source_system', 'contact_type', 'contact_value', 'entity_type',
             'entity_id')
        ),
        perm_filter='can_add_contact_info',
    )

    def entity_contactinfo_add(self, operator,
                               entity_target, contact_type, contact_value):
        """Manually add contact info to an entity."""

        # default values
        contact_pref = 50
        source_system = self.const.system_manual

        # get entity object
        entity = self.util.get_target(entity_target, restrict_to=[])
        entity_type = self.const.EntityType(int(entity.entity_type))

        if not hasattr(entity, 'get_contact_info'):
            raise CerebrumError("No support for contact info in %s entity" %
                                six.text_type(entity_type))

        # validate contact info type
        contact_type = self._get_constant(self.const.ContactInfo, contact_type)

        # check permissions
        self.ba.can_add_contact_info(operator.get_entity_id(),
                                     entity=entity,
                                     contact_type=contact_type)

        # validate email
        if contact_type == self.const.contact_email:
            contact_value = contact_value.lower()

            # validate localpart and extract domain.
            if contact_value.count('@') != 1:
                raise CerebrumError("Email address (%r) must be on form"
                                    "<localpart>@<domain>" % contact_value)
            localpart, domain = contact_value.split('@')
            ea = Email.EmailAddress(self.db)
            ed = Email.EmailDomain(self.db)
            try:
                if not ea.validate_localpart(localpart):
                    raise AttributeError('Invalid local part')
                ed._validate_domain_name(domain)
            except AttributeError as e:
                raise CerebrumError(e)

        # validate phone numbers
        if contact_type in (self.const.contact_phone,
                            self.const.contact_phone_private,
                            self.const.contact_mobile_phone,
                            self.const.contact_private_mobile):
            # allows digits and a prefixed '+'
            if not re.match(r"^\+?\d+$", contact_value):
                raise CerebrumError(
                    "Invalid phone number: %r. "
                    "The number can contain only digits "
                    "with possible '+' for prefix." % contact_value)

        # get existing contact info for this entity and contact type
        contacts = entity.get_contact_info(source=source_system,
                                           type=contact_type)

        existing_prefs = [int(row["contact_pref"]) for row in contacts]

        for row in contacts:
            # if the same value already exists, don't add it
            if contact_value == row["contact_value"]:
                raise CerebrumError("Contact value already exists")
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

        entity.add_contact_info(source_system,
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
        SourceSystem(help_ref='entity_contact_source_system'),
        SimpleString(help_ref='entity_contact_type'),
        fs=FormatSuggestion([
            ("Removed contact info %s:%s from %s with id=%d",
             ('source_system', 'contact_type', 'entity_type', 'entity_id',)),
            ("Old value: '%s'",
             ('contact_value', )),
        ]),
        perm_filter='can_remove_contact_info')

    def entity_contactinfo_remove(self, operator, entity_target, source_system,
                                  contact_type):
        """Deleting an entity's contact info from a given source system. Useful in
        cases where the entity has old contact information from a source system
        he no longer is exported from, i.e. no affiliations."""

        co = self.const

        # get entity object
        entity = self.util.get_target(entity_target, restrict_to=[])
        entity_type = self.const.EntityType(int(entity.entity_type))

        if not hasattr(entity, 'get_contact_info'):
            raise CerebrumError("No support for contact info in %s entity" %
                                six.text_type(entity_type))

        source_system = self._get_constant(self.const.AuthoritativeSystem,
                                           source_system)
        contact_type = self._get_constant(self.const.ContactInfo, contact_type)

        # check permissions
        self.ba.can_remove_contact_info(operator.get_entity_id(),
                                        entity=entity,
                                        contact_type=contact_type,
                                        source_system=source_system)

        # if the entity is a person...
        if entity_type == co.entity_person:
            # check if person is still affiliated with the given source system
            for a in entity.get_affiliations():
                # allow contact info added manually to be removed
                if (co.AuthoritativeSystem(a['source_system']) is
                        co.system_manual):
                    continue
                if (co.AuthoritativeSystem(a['source_system']) is
                        source_system):
                    raise CerebrumError(
                        'Person has an affiliation from source system '
                        '%r, cannot remove' % source_system)

        # check if given contact info type exists for this entity
        contact_info = entity.get_contact_info(source=source_system,
                                               type=contact_type)
        if not contact_info:
            raise CerebrumError(
                "Entity does not have contact info type %s in %s" %
                (six.text_type(contact_type),
                 six.text_type(source_system)))
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
        except:
            raise CerebrumError("Could not remove contact info %s:%s from %r" %
                                (six.text_type(source_system),
                                 six.text_type(contact_type),
                                 entity_target))

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

        return result

    #
    # entity contactinfo_show <entity>
    #
    all_commands['entity_contactinfo_show'] = Command(
        ("entity", "contactinfo_show"),
        SimpleString(help_ref='id:target:entity'),
        # SimpleString(help_ref='entity_contact_type'),
        fs=FormatSuggestion(
            "%-15s %-15s %-8s %-16s  %s",
            ('source_system', 'contact_type', 'contact_pref',
             format_time('modified'), 'contact_value', ),
            hdr="%-15s %-15s %-8s %-16s  %s" % ('Source', 'Type', 'Weight',
                                                'Modified', 'Value')
        ),
        perm_filter='can_get_contact_info')

    def entity_contactinfo_show(self, operator, entity_target):
        """ Show contact info of an entity. """

        entity = self.util.get_target(entity_target, restrict_to=[])
        entity_type = self.const.EntityType(int(entity.entity_type))

        if not hasattr(entity, 'get_contact_info'):
            raise CerebrumError("No support for contact info in %s entity" %
                                six.text_type(entity_type))

        def get_allowed_types():
            for contact_type in self.const.fetch_constants(
                    self.const.ContactInfo):
                try:
                    self.ba.can_get_contact_info(operator.get_entity_id(),
                                                 entity=entity,
                                                 contact_type=contact_type)
                    yield contact_type
                except PermissionDenied:
                    continue

        contact_types = list(get_allowed_types())
        if not contact_types:
            raise PermissionDenied("Not allowed to see any contact info for %r"
                                   % entity_target)

        contact_info = list()
        for row in entity.get_contact_info(type=contact_types):
            contact_info.append({
                'source_system': six.text_type(
                    self.const.AuthoritativeSystem(row['source_system'])),
                'contact_type': six.text_type(
                    self.const.ContactInfo(row['contact_type'])),
                'contact_pref': six.text_type(row['contact_pref']),
                'contact_value': row['contact_value'],
                'description': row['description'],
                'contact_alias': row['contact_alias'],
                'modified': row['last_modified'],
            })

        if not contact_info:
            raise CerebrumError("No contact info for %r" % entity_target)

        return contact_info
