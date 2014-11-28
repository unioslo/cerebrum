# -*- coding: iso-8859-1 -*-

# Copyright 2003-2010 University of Oslo, Norway
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

import cereconf
from Cerebrum import Errors
from Cerebrum import Cache
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.no.uit.Ephorte import EphorteRole
from Cerebrum.modules.no.uit.Ephorte import EphortePermission


class UiTEphorteAuth(BofhdAuth):
    """Authorisation. UiT ePhorte specific operations."""

    def can_add_ephorte_role(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if self.is_group_member(operator, cereconf.EPHORTE_ADMINS):
            return True
        return False

    can_remove_ephorte_role = can_add_ephorte_role
    can_list_ephorte_roles = can_add_ephorte_role

    can_add_ephorte_perm = can_add_ephorte_role
    can_remove_ephorte_perm = can_add_ephorte_role
    can_list_ephorte_perm = can_add_ephorte_role

class Journalenhet(Parameter):
    _type = 'journalenhet'
    _help_ref = 'journalenhet'

class Arkivdel(Parameter):
    _type = 'arkivdel'
    _help_ref = 'arkivdel'

class Rolle(Parameter):
    _type = 'rolle'
    _help_ref = 'rolle'

class Tilgang(Parameter):
    _type = 'tilgang'
    _help_ref = 'tilgang'
    
class BofhdExtension(BofhdCommonMethods):
    all_commands = {}

    def __new__(cls, *arg, **karg):
        # A bit hackish.  A better fix is to split bofhd_uit_cmds.py
        # into seperate classes.
        from Cerebrum.modules.no.uit.bofhd_uit_cmds import BofhdExtension as \
             UiTBofhdExtension

        for func in ('_format_changelog_entry', '_format_from_cl',
                     '_format_ou_name', '_get_account'):
            setattr(cls, func, UiTBofhdExtension.__dict__.get(func))
        x = object.__new__(cls)
        return x

    def __init__(self, server):
        super(BofhdExtension, self).__init__(server)
        
        self.util = server.util
        self.ephorte_role = EphorteRole(self.db)
        self.ephorte_perm = EphortePermission(self.db)
        self.ba = UiTEphorteAuth(self.db)
    # end __init__


    def get_help_strings(self):
        group_help = {
            'ephorte': "Commands for administrating ePhorte data"
            }
        command_help = {
            'ephorte': {
            'ephorte_add_role': 'Add an ePhorte role for a person',
            'ephorte_history': 'Show the ePhorte related history for a person',
            'ephorte_remove_role': 'Remove an ePhorte role from a person',
            'ephorte_list_roles': 'List a persons ePhorte roles',
            'ephorte_set_standard_role': 'Set given role as standard role',
            'ephorte_add_perm': 'Add an ePhorte permission for a person',
            'ephorte_remove_perm': 'Remove an ePhorte permission from a person',
            'ephorte_list_perm': 'List a persons ePhorte permissions'            
            }
            }
        arg_help = {
            'journalenhet': ['journalenhet', 'Enter journalenhet',
                             'Legal values are: \n%s' % "\n".join(
            ["  %-8s : %s" % (str(c), c.description)
             for c in self.const.fetch_constants(self.const.EphorteJournalenhet)])],
            'arkivdel': ['arkivdel', 'Enter arkivdel',
                         'Legal values are: \n%s' % "\n".join(
            ["  %-8s : %s" % (str(c), c.description)
             for c in self.const.fetch_constants(self.const.EphorteArkivdel)])],
            'rolle': ['rolle', 'Enter rolle',
                         'Legal values are: \n%s' % "\n".join(
            ["  %-8s : %s" % (str(c), c.description)
             for c in self.const.fetch_constants(self.const.EphorteRole)])],
            'tilgang': ['tilgang', 'Enter perm ("tilgang")',
                         'Legal values are: \n%s' % "\n".join(
            ["  %-8s : %s" % (str(c), c.description)
             for c in self.const.fetch_constants(self.const.EphortePermission)])],
            }

        # liste lovlige arkivdel/journalenhet
        
        return (group_help, command_help, arg_help)


    def _get_role_type(self, code_str):
        try:
            c = self.const.EphorteRole(code_str)
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown role")
  
    def _get_arkivdel(self, code_str):
        try:
            c = self.const.EphorteArkivdel(code_str)
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown arkivdel")
  
    def _get_journalenhet(self, code_str):
        try:
            c = self.const.EphorteJournalenhet(code_str)
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown journalenhet")

    def _get_tilgang(self, code_str):
        try:
            c = self.const.EphortePermission(code_str)
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown ePhorte auth. permission (tilgangskode)")

    ##
    ##
    ## Add, remove or list ePhorte-roles
    all_commands['ephorte_add_role'] = Command(("ephorte", "add_role"), PersonId(), Rolle(), OU(), Arkivdel(), Journalenhet(), 
        perm_filter='can_add_ephorte_role')
    def ephorte_add_role(self, operator, person_id, role, sko, arkivdel, journalenhet):
        not_ephorte_ou = False
        if not self.ba.can_add_ephorte_role(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to ephorte admins")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ou = self._get_ou(stedkode=sko)
        if not ou.has_spread(self.const.spread_ephorte_ou):
            not_ephorte_ou = True
        extra_msg = ""
        if not person.has_spread(self.const.spread_ephorte_person):
            person.add_spread(self.const.spread_ephorte_person)
            extra_msg = " (implicitly added ephorte-spread)"

        arkivdel = self._get_arkivdel(arkivdel)
        journalenhet = self._get_journalenhet(journalenhet)
        self.ephorte_role.add_role(person.entity_id, self._get_role_type(role), ou.entity_id,
                                   arkivdel, journalenhet, auto_role='F')
        if not_ephorte_ou:
            return "Warning: Added %s role for %s%s to a non-archive OU %s " % (role, person_id, extra_msg, sko)
        return "OK, added %s role for %s%s" % (role, person_id, extra_msg)


    all_commands['ephorte_remove_role'] = Command(("ephorte", "remove_role"), PersonId(), Rolle(), OU(), Arkivdel(), Journalenhet(), 
        perm_filter='can_remove_ephorte_role')
    def ephorte_remove_role(self, operator, person_id, role, sko, arkivdel, journalenhet):
        if not self.ba.can_remove_ephorte_role(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to ephorte admins")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ou = self._get_ou(stedkode=sko)
        arkivdel = self._get_arkivdel(arkivdel)
        journalenhet = self._get_journalenhet(journalenhet)
        # Check that the person has the given role. 
        if not self.ephorte_role.get_role(person.entity_id,
                                          self._get_role_type(role),
                                          ou.entity_id,
                                          self._get_arkivdel(arkivdel),
                                          self._get_journalenhet(journalenhet)):
            raise CerebrumError("Person has no such role")
        # Check if role is a standard role
        if (self.ephorte_role.is_standard_role(person.entity_id,
                                               self._get_role_type(role),
                                               ou.entity_id,
                                               arkivdel,
                                               journalenhet) and
            len(self.ephorte_role.list_roles(person_id=person.entity_id)) > 1):
            raise CerebrumError("Cannot delete standard role.")
        self.ephorte_role.remove_role(person.entity_id, self._get_role_type(role),
                                      ou.entity_id, arkivdel, journalenhet)
        return "OK, removed %s role for %s" % (role, person_id)

    all_commands['ephorte_list_roles'] = Command(("ephorte", "list_roles"), PersonId(),
        perm_filter='can_list_ephorte_roles', fs=FormatSuggestion(
        "%-5s %-30s %-15s %-13s %s", ('role', 'adm_enhet', 'arkivdel', 'journalenhet', 'std_role'),
        hdr="%-5s %-30s %-15s %-13s %s" % (
        "Rolle", "Adm enhet", "Arkivdel", "Journalenhet", "Standardrolle")))
    def ephorte_list_roles(self, operator, person_id):
        if not self.ba.can_list_ephorte_roles(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to ephorte admins")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ret = []
        for row in self.ephorte_role.list_roles(person_id=person.entity_id):
            ou = self._get_ou(ou_id=row['adm_enhet'])
            if row['arkivdel']:
                arkivdel = str(self._get_arkivdel(row['arkivdel']))
            else:
                arkivdel = ''
            if row['journalenhet']:
                journalenhet = str(self._get_journalenhet(row['journalenhet']))
            else:
                journalenhet = ''
            ret.append({
                'role': str(self._get_role_type(row['role_type'])),
                'adm_enhet': self._format_ou_name(ou),
                'arkivdel': arkivdel,
                'journalenhet': journalenhet,
                'std_role': row['standard_role'] or ''
                }
                )
        return ret

    all_commands['ephorte_set_standard_role'] = Command(
        ("ephorte", "set_standard_role"), PersonId(), Rolle(), OU(), Arkivdel(),
        Journalenhet(), perm_filter='can_add_ephorte_role')
    def ephorte_set_standard_role(self, operator, person_id, role, sko,
                                  arkivdel, journalenhet):
        """
        Set given role as standard role.

        There can be only one standard role, thus if another role is
        marked as standard role, it will no longer be the persons
        standard role.
        """
        # Check operators permissions
        if not self.ba.can_add_ephorte_role(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to ephorte admins")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ou = self._get_ou(stedkode=sko)
        # Check that the person has the given role. 
        tmp = self.ephorte_role.get_role(person.entity_id,
                                         self._get_role_type(role),
                                         ou.entity_id,
                                         self._get_arkivdel(arkivdel),
                                         self._get_journalenhet(journalenhet))
        # Some sanity checks
        if not tmp:
            raise CerebrumError("Person has no such role")
        elif len(tmp) > 1:
            raise Errors.TooManyRowsError("Unexpectedly found more than one role")
        new_std_role = tmp[0]
        if new_std_role['standard_role'] == 'T':
            return "Role is already standard role"
        # There can be only one standard role
        for row in self.ephorte_role.list_roles(person_id=person.entity_id):
            if row['standard_role'] == 'T':
                self.logger.debug("Unset role %s at %s as standard_role" % (
                    row['role_type'], row['adm_enhet']))
                self.ephorte_role.set_standard_role_val(person.entity_id, 
                                                        row['role_type'],
                                                        row['adm_enhet'],
                                                        row['arkivdel'],
                                                        row['journalenhet'],
                                                        'F')
        # Finally set the new standard role
        self.ephorte_role.set_standard_role_val(person.entity_id,
                                                self._get_role_type(role),
                                                ou.entity_id,
                                                self._get_arkivdel(arkivdel),
                                                self._get_journalenhet(journalenhet),
                                                'T')
        return "OK, set new standard role"

    ##
    ## Add, remove or list auth. permissions ("tilgangskoder") for ePhorte
    ## TBD: we should consider supporting permissions starting in the future
    ##
    all_commands['ephorte_add_perm'] = Command(("ephorte", "add_perm"), PersonId(), Tilgang(), OU(repeat=True),
        perm_filter='can_add_ephorte_perm')
    def ephorte_add_perm(self, operator, person_id, tilgang, sko):
        if not self.ba.can_add_ephorte_perm(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to ephorte admins")
        operator_id = operator.get_entity_id()
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        if not person.has_spread(self.const.spread_ephorte_person):
            raise CerebrumError("Person has no ephorte roles")
        ou = self._get_ou(stedkode=sko)
        if not (sko == cereconf.EPHORTE_EGNE_SAKER_SKO or
                ou.has_spread(self.const.spread_ephorte_ou)):
            raise CerebrumError("Cannot assign permission to a non-ephorte OU")
        # This is a hack needed by the archivists.
        # If one of the new permissions, defined in
        # EPHORTE_NEW2OLD_PERMISSIONS.values() is to be added, the old
        # (expired) one must be added to. And vice versa.
        corresponding_perm = cereconf.EPHORTE_NEW2OLD_PERMISSIONS.get(tilgang, None) or \
                             cereconf.EPHORTE_OLD2NEW_PERMISSIONS.get(tilgang, None) 
        if corresponding_perm:
            # Add the corresponding permission
            self.ephorte_perm.add_permission(person.entity_id,
                                             self._get_tilgang(corresponding_perm),
                                             ou.entity_id,
                                             operator_id)
            ret_msg_suffix = " Also added 'tilgang' %s" % corresponding_perm
        else:
            ret_msg_suffix = ""
        # Add new permission
        self.ephorte_perm.add_permission(person.entity_id,
                                         self._get_tilgang(tilgang),
                                         ou.entity_id,
                                         operator_id)
        return "OK, added 'tilgang' %s for %s.%s" % (tilgang, person_id, ret_msg_suffix)
    
    all_commands['ephorte_remove_perm'] = Command(("ephorte", "remove_perm"), PersonId(), Tilgang(), OU(repeat=True), 
        perm_filter='can_remove_ephorte_perm')
    def ephorte_remove_perm(self, operator, person_id, tilgang, sko):
        if not self.ba.can_remove_ephorte_perm(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to ephorte admins")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ou = self._get_ou(stedkode=sko)
        # This is a hack needed by the archivists.
        # If one of the new permissions, defined in
        # EPHORTE_NEW2OLD_PERMISSIONS.values() is to be added, the old
        # (expired) one must be added to. And vice versa.
        corresponding_perm = cereconf.EPHORTE_NEW2OLD_PERMISSIONS.get(tilgang, None) or \
                             cereconf.EPHORTE_OLD2NEW_PERMISSIONS.get(tilgang, None) 
        if corresponding_perm:
            # Remove old permission
            self.ephorte_perm.remove_permission(person.entity_id,
                                                self._get_tilgang(corresponding_perm),
                                                ou.entity_id)
            ret_msg_suffix = " Also removed 'tilgang' %s" % corresponding_perm
        else:
            ret_msg_suffix = ""
        # Remove new permission
        self.ephorte_perm.remove_permission(person.entity_id,
                                            self._get_tilgang(tilgang),
                                            ou.entity_id)
        return "OK, removed 'tilgang' %s for %s.%s" % (tilgang, person_id, ret_msg_suffix)

    all_commands['ephorte_list_perm'] = Command(("ephorte", "list_perm"), PersonId(), 
        perm_filter='can_list_ephorte_perm', fs=FormatSuggestion(
        "%-10s %-34s %-18s %-10s", ('tilgang', 'adm_enhet', 'requestee', 'end_date'),
        hdr="%-10s %-34s %-18s %-10s" % ("Tilgang", "Adm.enhet", "Tildelt av", "Sluttdato")))
    def ephorte_list_perm(self, operator, person_id):
        if not self.ba.can_list_ephorte_perm(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to ephorte admins")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ret = []
        for row in self.ephorte_perm.list_permission(person_id=person.entity_id):
            ou = self._get_ou(ou_id=row['adm_enhet'])
            requestee = self.util.get_target(int(row['requestee_id']))
            if row['end_date']:
                end_date = row['end_date'].date
            else:
                end_date = ''
            ret.append({
                'tilgang': str(self._get_tilgang(row['perm_type'])),
                'adm_enhet': self._format_ou_name(ou),
                'requestee': requestee.get_names()[0][0],
                'end_date': end_date
                }
                )
        return ret

    all_commands['ephorte_history'] = Command(
        ("ephorte", "history"),
        PersonId(),
        Integer(optional=True, help_ref="limit_number_of_results"),
        fs=FormatSuggestion("%s [%s]: %s",
                            ("timestamp", "change_by", "message")),
        #perm_filter='can_add_ephorte_perm')
        # Only available for superusers for now.
        perm_filter='is_superuser')
    def ephorte_history(self, operator, person_id, limit=100):
        if not self.ba.can_list_ephorte_perm(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to ephorte admins")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")

        try:
            limit = int(limit)
        except ValueError:
            raise CerebrumError, "Limit must be a number"
        
        # Only certain tyeps of changes are relevant for ephorte history
        types = ["ephorte_role_add", "ephorte_role_upd", "ephorte_role_rem",
                 "ephorte_perm_add", "ephorte_perm_rem", "person_aff_add",
                 "person_aff_del", "person_aff_mod", "person_aff_src_add",
                 "person_aff_src_del", "person_aff_src_mod", "person_create"]
        ret = []

        rows = list(self.db.get_log_events(0, subject_entity=person.entity_id,
                                           types=[getattr(self.const, t) for t in types]))
        for r in rows[-limit:]:
            ret.append(self._format_changelog_entry(r))
        return ret
