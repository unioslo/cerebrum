# -*- coding: utf-8 -*-
#
# Copyright 2016-2018 University of Oslo, Norway
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
""" Feide attribute bofhd commands.

This module contains commands for managing Feide services and
multifactor authentication for those services.
"""
import six

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.cmd_param import (Command,
                                              FormatSuggestion,
                                              SimpleString,
                                              Integer,
                                              YesNo)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.feide.service import (FeideService,
                                            FeideServiceAuthnLevelMixin)
from Cerebrum.modules.feide.feide_utils import (is_valid_feide_id_type,
                                                is_keyword_all)


class BofhdFeideAuth(BofhdAuth):
    pass


class BofhdExtension(BofhdCommonMethods):
    """Commands for managing Feide services and multifactor authentication."""

    hidden_commands = {}  # Not accessible through bofh
    all_commands = {}
    parent_commands = False
    authz = BofhdFeideAuth

    def _find_service(self, service_name):
        fse = FeideService(self.db)
        try:
            fse.find_by_name(service_name)
        except Errors.NotFoundError:
            raise CerebrumError('No such Feide service')
        return fse


    @classmethod
    def get_help_strings(cls):
        """ Help strings for Feide commands. """
        return (HELP_FEIDE_GROUP, HELP_FEIDE_CMDS, HELP_FEIDE_ARGS)

    #
    # feide service_add
    #
    all_commands['feide_service_add'] = Command(
        ('feide', 'service_add'),
        Integer(help_ref='feide_service_id'),
        SimpleString(help_ref='feide_service_name'),
        perm_filter='is_superuser')

    def feide_service_add(self, operator, feide_id, service_name):
        """ Add a Feide service

        The Feide service must have an ID, which will either be an integer
        or an UUID. The keyword 'all' is also accepted (capitalization is
        arbitrary). """
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied('Only superusers may add Feide services')
        if not is_valid_feide_id_type(feide_id):
            raise CerebrumError('Feide ID must either be a UUID, an integer, '
                                'a string representation thereof, or the word '
                                '"all" (arbitrary capitalization).')
        fse = FeideService(self.db)
        service_name = service_name.strip()
        name_error = fse.illegal_name(service_name)
        if name_error:
            raise CerebrumError(name_error)
        if not is_keyword_all(feide_id):
            for service in fse.search():
                if feide_id == service['feide_id']:
                    raise CerebrumError(
                        'A Feide service with that ID already exists')
                if service_name == service['name']:
                    raise CerebrumError(
                        'A Feide service with that name already exists')
        fse.populate(feide_id, service_name)
        fse.write_db()
        return "Added Feide service '{}'".format(service_name)

    #
    # feide service_remove
    #
    all_commands['feide_service_remove'] = Command(
        ('feide', 'service_remove'),
        SimpleString(help_ref='feide_service_name'),
        YesNo(help_ref='feide_service_confirm_remove'),
        perm_filter='is_superuser')

    def feide_service_remove(self, operator, service_name, confirm):
        """ Remove a Feide service. """
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied(
                'Only superusers may remove Feide services')
        if not confirm:
            return 'No action taken.'
        service_name = service_name.strip()
        fse = self._find_service(service_name)
        fse.delete()
        fse.write_db()
        return "Removed Feide service '{}'".format(service_name)

    #
    # feide service_list
    #
    all_commands['feide_service_list'] = Command(
        ('feide', 'service_list'),
        fs=FormatSuggestion(
            '%-10i %-37s %s', ('service_id', 'feide_id', 'name'),
            hdr='%-10s %-37s %s' % ('Entity ID', 'Feide ID', 'Name')),
        perm_filter='is_superuser')

    def feide_service_list(self, operator):
        """
        List Feide services.

        :rtype: dict
        :return:
            service_id: <int>
            feide_id: <str>
            name: <str>
        """
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied('Only superusers may list Feide services')
        fse = FeideService(self.db)
        return map(dict, fse.search())

    #
    # feide authn_level_add
    #
    all_commands['feide_authn_level_add'] = Command(
        ('feide', 'authn_level_add'),
        SimpleString(help_ref='feide_service_name'),
        SimpleString(help_ref='feide_authn_entity_target'),
        Integer(help_ref='feide_authn_level'),
        perm_filter='is_superuser')

    def feide_authn_level_add(self, operator, service_name, target, level):
        """ Add an authentication level for a given service and entity. """
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied(
                'Only superusers may add Feide authentication levels')
        if not level.isdigit() or int(level) not in (3, 4):
            raise CerebrumError('Authentication level must be 3 or 4')
        service_name = service_name.strip()
        fse = self._find_service(service_name)
        # Allow authentication levels for persons and groups
        entity = self.util.get_target(target,
                                      default_lookup='person',
                                      restrict_to=['Person', 'Group'])
        if entity.search_authn_level(service_id=fse.entity_id,
                                     entity_id=entity.entity_id,
                                     level=level):
            raise CerebrumError(
                'Authentication level {} for {} for service {} '
                'already enabled'.format(level, target, service_name))
        entity.add_authn_level(service_id=fse.entity_id,
                               level=level)
        return 'Added authentication level {} for {} for {}'.format(
            level, target, service_name)

    #
    # feide authn_level_remove
    #
    all_commands['feide_authn_level_remove'] = Command(
        ('feide', 'authn_level_remove'),
        SimpleString(help_ref='feide_service_name'),
        SimpleString(help_ref='feide_authn_entity_target'),
        Integer(help_ref='feide_authn_level'),
        perm_filter='is_superuser')

    def feide_authn_level_remove(self, operator, service_name, target, level):
        """ Remove an authentication level for a given service and entity. """
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied(
                'Only superusers may remove Feide authentication levels')
        if not level.isdigit() or int(level) not in (3, 4):
            raise CerebrumError('Authentication level must be 3 or 4')
        service_name = service_name.strip()
        fse = self._find_service(service_name)
        # Allow authentication levels for persons and groups
        entity = self.util.get_target(target,
                                      default_lookup='person',
                                      restrict_to=['Person', 'Group'])
        if not entity.search_authn_level(service_id=fse.entity_id,
                                         entity_id=entity.entity_id,
                                         level=level):
            raise CerebrumError(
                'No such authentication level {} for {} for service {}'.format(
                    level, target, service_name))
        entity.remove_authn_level(service_id=fse.entity_id,
                                  level=level)
        return 'Removed authentication level {} for {} for {}'.format(
            level, target, service_name)

    #
    # feide authn_level_search
    #
    all_commands['feide_authn_level_list'] = Command(
        ('feide', 'authn_level_list'),
        SimpleString(help_ref='feide_service_name'),
        fs=FormatSuggestion(
            '%-20s %-6d %s', ('service_name', 'level', 'entity'),
            hdr='%-20s %-6s %s' % ('Service', 'Level', 'Entity')),
        perm_filter='is_superuser')

    def feide_authn_level_list(self, operator, service_name):
        """ List all authentication levels for a service. """
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied(
                'Only superusers may list Feide authentication levels')
        service_name = service_name.strip()
        fse = self._find_service(service_name)
        en = Factory.get('Entity')(self.db)
        fsal = FeideServiceAuthnLevelMixin(self.db)
        result = []
        for x in fsal.search_authn_level(service_id=fse.entity_id):
            try:
                en.clear()
                en.find(x['entity_id'])
                entity_type = six.text_type(
                    self.const.map_const(en.entity_type))
                entity_name = self._get_entity_name(
                    en.entity_id, en.entity_type)
                entity = '{} {} (id:{:d})'.format(
                    entity_type, entity_name, en.entity_id)
            except:
                entity = 'id:{}'.format(x['entity_id'])
            result.append({
                'service_name': service_name,
                'level': x['level'],
                'entity': entity
            })
        return result


HELP_FEIDE_GROUP = {
    'feide': 'Commands for Feide multifactor authentication',
}

HELP_FEIDE_CMDS = {
    'feide': {
        'feide_service_add':
            BofhdExtension.feide_service_add.__doc__,
        'feide_service_remove':
            BofhdExtension.feide_service_remove.__doc__,
        'feide_service_list':
            BofhdExtension.feide_service_list.__doc__,
        'feide_authn_level_add':
            BofhdExtension.feide_authn_level_add.__doc__,
        'feide_authn_level_remove':
            BofhdExtension.feide_authn_level_remove.__doc__,
        'feide_authn_level_list':
            BofhdExtension.feide_authn_level_list.__doc__,
    },
}

HELP_FEIDE_ARGS = {
    'feide_service_name':
        ['service_name', 'Enter Feide service name'],
    'feide_service_id':
        ['feide_id', 'Enter Feide service ID'],
    'feide_service_confirm_remove':
        ['confirm',
         'This will remove any authentication levels associated with '
         'this service. Continue? [y/n]'],
    'feide_authn_level':
        ['level', 'Enter authentication level'],
    'feide_authn_entity_target':
        ['entity', 'Enter an existing entity',
         "Enter the entity as type:name, for example: 'group:admin-users'\n\n"
         "If only a name is entered, it will be assumed to be an"
         " account name.\n\n"
         "Supported types are:\n"
         " - 'person' (name of user => Person)\n"
         " - 'group' (name of group => Group)\n"
         " - 'id' (entity ID => any Person or Group)"],
}
