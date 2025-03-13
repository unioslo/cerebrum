# -*- coding: utf-8 -*-
#
# Copyright 2003-2018 University of Oslo, Norway
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
from six import text_type

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_utils import copy_func
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.no.uio.Elements import ElementsPermission
from Cerebrum.modules.no.uio.Elements import ElementsRole
from Cerebrum.modules.no.uio.bofhd_ephorte_cmds import UiOEphorteAuth, Journalenhet, Arkivdel, Rolle, Tilgang
from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as cl_base
from Cerebrum.utils.date_compat import get_date


@copy_func(
    cl_base,
    methods=[
        '_format_changelog_entry',
        '_format_from_cl',
    ])
class BofhdExtension(BofhdCommonMethods):
    """ Extends bofhd with an 'elements' command group. """

    all_commands = {}
    parent_commands = False
    authz = UiOEphorteAuth

    @property
    def elements_role(self):
        try:
            return self.__elements_role_util
        except AttributeError:
            self.__elements_role_util = ElementsRole(self.db)
            return self.__elements_role_util

    @property
    def elements_perm(self):
        try:
            return self.__elements_perm_util
        except AttributeError:
            self.__elements_perm_util = ElementsPermission(self.db)
            return self.__elements_perm_util

    @classmethod
    def get_help_strings(cls):
        const = Factory.get('Constants')()
        group_help = {
            'elements': "Commands for administrating Elements data"
        }
        command_help = {
            'elements': {
                'elements_add_role':
                    'Add an elements role for a person',
                'elements_history':
                    'Show the Elements related history for a person',
                'elements_remove_role':
                    'Remove an Elements role from a person',
                'elements_list_roles':
                    'List a persons Elements roles',
                'elements_set_standard_role':
                    'Set given role as standard role',
                'elements_add_perm':
                    'Add an Elements permission for a person',
                'elements_remove_perm':
                    'Remove an Elements permission from a person',
                'elements_list_perm':
                    'List a persons Elements permissions'
            }
        }
        arg_help = {
            'journalenhet': [
                'journalenhet', 'Enter journalenhet',
                'Legal values are: \n%s' % "\n".join([
                    "  %-8s : %s" % (text_type(c), c.description)
                    for c in const.fetch_constants(const.ElementsJournalenhet)
                ])
            ],
            'arkivdel': [
                'arkivdel', 'Enter arkivdel',
                'Legal values are: \n%s' % "\n".join([
                    "  %-8s : %s" % (text_type(c), c.description)
                    for c in const.fetch_constants(const.ElementsArkivdel)
                ])
            ],
            'rolle': [
                'rolle', 'Enter rolle',
                'Legal values are: \n%s' % "\n".join([
                    "  %-8s : %s" % (text_type(c), c.description)
                    for c in const.fetch_constants(const.ElementsRole)
                ])
            ],
            'tilgang': [
                'tilgang', 'Enter perm ("tilgang")',
                'Legal values are: \n%s' % "\n".join([
                    "  %-8s : %s" % (text_type(c), c.description)
                    for c in const.fetch_constants(const.ElementsPermission)
                ])
            ],
        }

        # liste lovlige arkivdel/journalenhet
        return (group_help, command_help, arg_help)

    def _get_role_type(self, code_str):
        try:
            c = self.const.ElementsRole(code_str)
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown role")

    def _get_arkivdel(self, code_str):
        try:
            c = self.const.ElementsArkivdel(code_str)
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown arkivdel")

    def _get_journalenhet(self, code_str):
        try:
            c = self.const.ElementsJournalenhet(code_str)
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown journalenhet")

    def _get_tilgang(self, code_str):
        try:
            c = self.const.ElementsPermission(code_str)
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown Elements auth. permission"
                                " (tilgangskode)")

    #
    # Add, remove or list Elements-roles
    #
    all_commands['elements_add_role'] = cmd_param.Command(
        ("elements", "add_role"),
        cmd_param.PersonId(),
        Rolle(),
        cmd_param.OU(),
        Arkivdel(),
        Journalenhet(),
        perm_filter='can_add_ephorte_role')

    def elements_add_role(self, operator,
                         person_id, role, sko, arkivdel, journalenhet):
        not_elements_ou = False
        if not self.ba.can_add_ephorte_role(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to elements admins")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ou = self._get_ou(stedkode=sko)
        if not ou.has_spread(self.const.spread_elements_ou):
            not_elements_ou = True
        extra_msg = ""
        if not person.has_spread(self.const.spread_elements_person):
            person.add_spread(self.const.spread_elements_person)
            extra_msg = " (implicitly added elements-spread)"

        arkivdel = self._get_arkivdel(arkivdel)
        journalenhet = self._get_journalenhet(journalenhet)
        role = self._get_role_type(role)
        self.elements_role.add_role(person.entity_id, role,
                                   ou.entity_id, arkivdel, journalenhet,
                                   auto_role='F')
        if not_elements_ou:
            return ("Warning: Added %s role for %s%s to a"
                    " non-archive OU %r") % (text_type(role), person_id,
                                             extra_msg, sko)
        return "OK, added %s role for %s%s" % (text_type(role), person_id,
                                               extra_msg)

    #
    # elements remove_role
    #
    all_commands['elements_remove_role'] = cmd_param.Command(
        ("elements", "remove_role"),
        cmd_param.PersonId(),
        Rolle(),
        cmd_param.OU(),
        Arkivdel(),
        Journalenhet(),
        perm_filter='can_remove_ephorte_role')

    def elements_remove_role(self, operator,
                            person_id, role, sko, arkivdel, journalenhet):
        if not self.ba.can_remove_ephorte_role(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to elements admins")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ou = self._get_ou(stedkode=sko)
        arkivdel = self._get_arkivdel(arkivdel)
        journalenhet = self._get_journalenhet(journalenhet)
        role = self._get_role_type(role)
        # Check that the person has the given role.
        if not self.elements_role.get_role(
                person.entity_id,
                role,
                ou.entity_id,
                arkivdel,
                journalenhet):
            raise CerebrumError("Person has no such role")
        # Check if role is a standard role
        _list_roles = self.elements_role.list_roles
        if (self.elements_role.is_standard_role(person.entity_id,
                                               role,
                                               ou.entity_id,
                                               arkivdel,
                                               journalenhet)
                and len(_list_roles(person_id=person.entity_id)) > 1):
            raise CerebrumError("Cannot delete standard role.")
        self.elements_role.remove_role(person.entity_id,
                                      role,
                                      ou.entity_id,
                                      arkivdel,
                                      journalenhet)
        return "OK, removed %s role for %s" % (text_type(role), person_id)

    #
    # elements list_roles
    #
    all_commands['elements_list_roles'] = cmd_param.Command(
        ("elements", "list_roles"),
        cmd_param.PersonId(),
        perm_filter='can_list_ephorte_roles',
        fs=cmd_param.FormatSuggestion(
            "%-5s %-30s %-15s %-13s %s",
            ('role', 'adm_enhet', 'arkivdel', 'journalenhet', 'std_role'),
            hdr="%-5s %-30s %-15s %-13s %s" % (
                "Rolle", "Adm enhet", "Arkivdel", "Journalenhet",
                "Standardrolle")
        ))

    def elements_list_roles(self, operator, person_id):
        if not self.ba.can_list_ephorte_roles(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to elements admins")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ret = []

        def to_text(getter, value):
            if not value:
                return ''
            return text_type(getter(value))

        for row in self.elements_role.list_roles(person_id=person.entity_id):
            ou = self._get_ou(ou_id=row['adm_enhet'])
            ret.append({
                'role': to_text(self._get_role_type, row['role_type']),
                'adm_enhet': self._format_ou_name(ou),
                'arkivdel': to_text(self._get_arkivdel, row['arkivdel']),
                'journalenhet': to_text(self._get_journalenhet,
                                        row['journalenhet']),
                'std_role': row['standard_role'] or '',
            })
        return ret

    #
    # elements set_standard_role
    #
    all_commands['elements_set_standard_role'] = cmd_param.Command(
        ("elements", "set_standard_role"),
        cmd_param.PersonId(),
        Rolle(),
        cmd_param.OU(),
        Arkivdel(),
        Journalenhet(),
        perm_filter='can_add_ephorte_role')

    def elements_set_standard_role(self, operator, person_id, role, sko,
                                  arkivdel, journalenhet):
        """
        Set given role as standard role.

        There can be only one standard role, thus if another role is
        marked as standard role, it will no longer be the persons
        standard role.
        """
        # Check operators permissions
        if not self.ba.can_add_ephorte_role(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to elements admins")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ou = self._get_ou(stedkode=sko)
        # Check that the person has the given role.
        tmp = self.elements_role.get_role(person.entity_id,
                                         self._get_role_type(role),
                                         ou.entity_id,
                                         self._get_arkivdel(arkivdel),
                                         self._get_journalenhet(journalenhet))
        # Some sanity checks
        if not tmp:
            raise CerebrumError("Person has no such role")
        elif len(tmp) > 1:
            raise Errors.TooManyRowsError("Unexpectedly found more than one"
                                          " role")
        new_std_role = tmp[0]
        if new_std_role['standard_role'] == 'T':
            return "Role is already standard role"
        # There can be only one standard role
        for row in self.elements_role.list_roles(person_id=person.entity_id):
            if row['standard_role'] == 'T':
                self.logger.debug("Unset role %s at %s as standard_role" % (
                    row['role_type'], row['adm_enhet']))
                self.elements_role.set_standard_role_val(person.entity_id,
                                                        row['role_type'],
                                                        row['adm_enhet'],
                                                        row['arkivdel'],
                                                        row['journalenhet'],
                                                        'F')
        # Finally set the new standard role
        self.elements_role.set_standard_role_val(
            person.entity_id,
            self._get_role_type(role),
            ou.entity_id,
            self._get_arkivdel(arkivdel),
            self._get_journalenhet(journalenhet),
            'T')
        return "OK, set new standard role"

    #
    # Add, remove or list auth. permissions ("tilgangskoder") for Elements
    # TBD: we should consider supporting permissions starting in the future
    #
    all_commands['elements_add_perm'] = cmd_param.Command(
        ("elements", "add_perm"),
        cmd_param.PersonId(),
        Tilgang(),
        cmd_param.OU(repeat=True),
        perm_filter='can_add_ephorte_perm')

    def elements_add_perm(self, operator, person_id, tilgang, sko):
        if not self.ba.can_add_ephorte_perm(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to elements admins")
        operator_id = operator.get_entity_id()
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        if not person.has_spread(self.const.spread_elements_person):
            raise CerebrumError("Person has no elements roles")
        ou = self._get_ou(stedkode=sko)
        ## Comment out this momentarily while we wait for clarification on
        ## OU use for own cases in Elements vs. historical ePhorte base:
        #if not (sko == cereconf.EPHORTE_EGNE_SAKER_SKO or
        #        ou.has_spread(self.const.spread_ephorte_ou)):
        if not (ou.has_spread(self.const.spread_elements_ou)):
            raise CerebrumError("Cannot assign permission to a non-elements OU")

        if self.elements_perm.has_permission(person.entity_id,
                                            self._get_tilgang(tilgang),
                                            ou.entity_id):
            raise CerebrumError("Person %r already has perm %r"
                                " (remove first)" % (person_id, tilgang))

        tilgang = self._get_tilgang(tilgang)
        # Add new permission
        self.elements_perm.add_permission(person.entity_id,
                                         tilgang,
                                         ou.entity_id,
                                         operator_id)
        return "OK, added 'tilgang' %s for %s." % (text_type(tilgang),
                                                   person_id)

    #
    # elements remove_perm
    #
    all_commands['elements_remove_perm'] = cmd_param.Command(
        ("elements", "remove_perm"),
        cmd_param.PersonId(),
        Tilgang(),
        cmd_param.OU(repeat=True),
        perm_filter='can_remove_ephorte_perm')

    def elements_remove_perm(self, operator, person_id, tilgang, sko):
        if not self.ba.can_remove_ephorte_perm(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to elements admins")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ou = self._get_ou(stedkode=sko)
        tilgang = self._get_tilgang(tilgang)

        # Remove new permission
        self.elements_perm.remove_permission(person.entity_id,
                                            tilgang,
                                            ou.entity_id)
        return "OK, removed 'tilgang' %s for %s." % (text_type(tilgang),
                                                     person_id)

    #
    # elements list_perm
    #
    all_commands['elements_list_perm'] = cmd_param.Command(
        ("elements", "list_perm"),
        cmd_param.PersonId(),
        perm_filter='can_list_ephorte_perm',
        fs=cmd_param.FormatSuggestion(
            "%-10s %-34s %-18s %-10s",
            ('tilgang', 'adm_enhet', 'requestee', 'end_date'),
            hdr="%-10s %-34s %-18s %-10s" % (
                "Tilgang", "Adm.enhet", "Tildelt av", "Sluttdato")
        ))

    def elements_list_perm(self, operator, person_id):
        if not self.ba.can_list_ephorte_perm(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to elements admins")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ret = []
        for row in self.elements_perm.list_permission(
                person_id=person.entity_id):
            ou = self._get_ou(ou_id=row['adm_enhet'])
            requestee = self.util.get_target(int(row['requestee_id']))
            if row['end_date']:
                end_date = get_date(row['end_date']).strftime('%Y-%m-%d')
            else:
                end_date = ''
            ret.append({
                'tilgang': text_type(self._get_tilgang(row['perm_type'])),
                'adm_enhet': self._format_ou_name(ou),
                'requestee': requestee.get_names()[0][0],
                'end_date': end_date,
            })
        return ret

    #
    # elements history
    #
    all_commands['elements_history'] = cmd_param.Command(
        ("elements", "history"),
        cmd_param.PersonId(),
        cmd_param.Integer(optional=True, help_ref="limit_number_of_results"),
        fs=cmd_param.FormatSuggestion(
            "%s [%s]: %s", ("timestamp", "change_by", "message")),
        # perm_filter='can_add_ephorte_perm')
        # Only available for superusers for now.
        perm_filter='is_superuser')

    def elements_history(self, operator, person_id, limit=100):
        if not self.ba.can_list_ephorte_perm(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to elements admins")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")

        try:
            limit = int(limit)
        except ValueError:
            raise CerebrumError("Limit must be a number")

        # Only certain tyeps of changes are relevant for elements history
        types = ["elements_role_add", "elements_role_upd", "elements_role_rem",
                 "elements_perm_add", "elements_perm_rem", "person_aff_add",
                 "person_aff_del", "person_aff_mod", "person_aff_src_add",
                 "person_aff_src_del", "person_aff_src_mod", "person_create"]
        ret = []

        rows = list(self.db.get_log_events(0,
                                           subject_entity=person.entity_id,
                                           types=[getattr(self.clconst, t)
                                                  for t in types]))
        for r in rows[-limit:]:
            ret.append(self._format_changelog_entry(r))
        return ret
