# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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


from Cerebrum import Cache
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.no.uio.Ephorte import EphorteRole

class Journalenhet(Parameter):
    _type = 'journalenhet'
    _help_ref = 'journalenhet'

class Arkivdel(Parameter):
    _type = 'arkivdel'
    _help_ref = 'arkivdel'

class Rolle(Parameter):
    _type = 'rolle'
    _help_ref = 'rolle'

class BofhdExtension(object):
    all_commands = {}
    OU_class = Factory.get('OU')

    def __new__(cls, *arg, **karg):
        # A bit hackish.  A better fix is to split bofhd_uio_cmds.py
        # into seperate classes.
        from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as \
             UiOBofhdExtension

        for func in ('get_commands', '_get_ou', 'get_format_suggestion', '_format_ou_name'):
            setattr(cls, func, UiOBofhdExtension.__dict__.get(func))
        x = object.__new__(cls)
        return x

    def __init__(self, server):
        self.server = server
        self.logger = server.logger
        self.db = server.db
        self.util = server.util
        self.const = Factory.get('Constants')(self.db)
        self.ephorte_role = EphorteRole(self.db)
        self.ba = BofhdAuth(self.db)

        self._cached_client_commands = Cache.Cache(mixins=[Cache.cache_mru,
                                                           Cache.cache_slots,
                                                           Cache.cache_timeout],
                                                   size=500,
                                                   timeout=60*60)

    def get_help_strings(self):
        group_help = {
            'eph': "Commands for administrating ePhorte data"
            }
        command_help = {
            'eph': {
            'eph_add_role': 'Add an ePhorte role for a person',
            'eph_remove_role': 'Remove an ePhorte role from a person',
            'eph_list_roles': 'List a persons ePhorte roles'
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
            }

        # liste lovlige arkivdel/journalenhet
        
        return (group_help, command_help, arg_help)

    def _get_role(self, code_str):
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
  

    all_commands['eph_add_role'] = Command(("eph", "add_role"), PersonId(), Rolle(), OU(), Arkivdel(), Journalenhet(), 
        perm_filter='is_superuser')
    def eph_add_role(self, operator, person_id, role, sko, arkivdel, journalenhet):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ou = self._get_ou(stedkode=sko)

        if arkivdel:
            arkivdel = self._get_arkivdel(arkivdel)
        else:
            arkivdel = None
        if journalenhet:
            journalenhet = self._get_journalenhet(journalenhet)
        else:
            journalenhet = None
        self.ephorte_role.add_role(person.entity_id, self._get_role(role), ou.entity_id,
                                   arkivdel, journalenhet)
        return "OK, added %s role for %s" % (role, person_id)

    all_commands['eph_remove_role'] = Command(("eph", "remove_role"), PersonId(), Rolle(), OU(), Arkivdel(), Journalenhet(), 
        perm_filter='is_superuser')
    def eph_remove_role(self, operator, person_id, role, sko, arkivdel, journalenhet):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ou = self._get_ou(stedkode=sko)
        if arkivdel:
            arkivdel = self._get_arkivdel(arkivdel)
        else:
            arkivdel = None
        if journalenhet:
            journalenhet = self._get_journalenhet(journalenhet)
        else:
            journalenhet = None

        self.ephorte_role.remove_role(person.entity_id, self._get_role(role), ou.entity_id,
                                   arkivdel, journalenhet)
                                   
        return "OK, removed %s role for %s" % (role, person_id)

    all_commands['eph_list_roles'] = Command(("eph", "list_roles"), PersonId(), 
        perm_filter='is_superuser', fs=FormatSuggestion(
        "%-5s %-25s %-15s %s", ('role', 'adm_enhet', 'arkivdel', 'journalenhet'),
        hdr="%-5s %-25s %-15s %s" % ("Rolle", "Adm enhet", "Arkivdel", "Journalenhet")))
    def eph_list_roles(self, operator, person_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
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
                'role': str(self._get_role(row['role_type'])),
                'adm_enhet': self._format_ou_name(ou),
                'arkivdel': arkivdel,
                'journalenhet': journalenhet
                }
                )
        return ret
