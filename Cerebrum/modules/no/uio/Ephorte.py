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

import pickle

from Cerebrum import Constants
from Cerebrum.Constants import ConstantsBase, _CerebrumCode, _SpreadCode
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError

class _EphorteRoleTypeCode(_CerebrumCode):
    "Mappings stored in the contact_info_code table"
    _lookup_table = '[:table schema=cerebrum name=ephorte_role_type_code]'
    pass

class _EphorteArkivdelCode(_CerebrumCode):
    "Mappings stored in the contact_info_code table"
    _lookup_table = '[:table schema=cerebrum name=ephorte_arkivdel_code]'
    pass

class _EphorteJournalenhetCode(_CerebrumCode):
    "Mappings stored in the contact_info_code table"
    _lookup_table = '[:table schema=cerebrum name=ephorte_journalenhet_code]'
    pass

class EphorteConstants(ConstantsBase):
    # Values from the ePhorte table ROLE
    ephorte_role_ar1 = _EphorteRoleTypeCode('AR1', 'Arkivansvarlig')
    ephorte_role_ar2 = _EphorteRoleTypeCode('AR2', 'Arkival')
    ephorte_role_ld = _EphorteRoleTypeCode('LD', 'Leder/saksfordeler')
    ephorte_role_sb = _EphorteRoleTypeCode('SB', 'Saksbehandler')

    # Values from the ePhorte table ARKIVDEL
    ephorte_arkivdel_avtale_uio = _EphorteArkivdelCode(
        'AVTALE UIO', 'Avtalearkiv ved Universitetet i Oslo')
    ephorte_arkivdel_eiend_uio = _EphorteArkivdelCode(
        'EIEND UIO', 'Eiendomsarkiv ved Universitetet i Oslo')
    ephorte_arkivdel_khm_forn = _EphorteArkivdelCode(
        'KHM FORN', 'KHM (Kulturhistorisk museum) - Fornminnneforvaltning')
    ephorte_arkivdel_pers_uio = _EphorteArkivdelCode(
        'PERS UIO', 'Personalarkiv ved Universitetet i Oslo')
    ephorte_arkivdel_persav_uio = _EphorteArkivdelCode(
        'PERSAV UIO', 'Avsluttede personalmapper ved UiO')
    ephorte_arkivdel_sak_nikk = _EphorteArkivdelCode(
        'SAK NIKK', 'Saksarkiv ved NIKK')
    ephorte_arkivdel_sak_so = _EphorteArkivdelCode(
        'SAK SO', 'Saksarkiv ved Samordna Opptak')
    ephorte_arkivdel_sak_uio = _EphorteArkivdelCode(
        'SAK UIO', 'Saksarkiv ved Universitetet i Oslo')
    ephorte_arkivdel_stud_uio = _EphorteArkivdelCode(
        'STUD UIO', 'Studentarkiv ved Universitetet i Oslo')
    ephorte_arkivdel_studav_uio = _EphorteArkivdelCode(
        'STUDAV UIO', 'Avsluttede studentmapper ved UiO')

    # Values from the ePhorte table JOURNENHET
    ephorte_journenhet_uio = _EphorteJournalenhetCode(
        'J-UIO', 'Journalenhet for UiO - Universitetet i Oslo')
    ephorte_journenhet_so = _EphorteJournalenhetCode(
        'J-SO', 'Journalenhet for SO - Samordna Opptak')
    ephorte_journenhet_nikk = _EphorteJournalenhetCode(
        'J-NIKK', 'Journalenhet for NIKK - Nordisk institutt for kvinne- og kjønnsforskn')

    spread_ephorte_person = _SpreadCode('ePhorte_person', Constants.Constants.entity_person,
                                         'Person included in ePhorte exprot')

    EphorteRole = _EphorteRoleTypeCode
    EphorteArkivdel = _EphorteArkivdelCode
    EphorteJournalenhet = _EphorteJournalenhetCode

class EphorteRole(DatabaseAccessor):
    def __init__(self, database):
        super(EphorteRole, self).__init__(database)
        self.co = Factory.get('Constants')(database)

    def add_role(self, person_id, role, sko, arkivdel, journalenhet,
                 rolletittel='', stilling=''):
        # TODO: Skrive noe om start_date/end_date
        # TODO: Bruke account_id for brukerens primærbruker
        binds = {
            'person_id': person_id,
            'role_type': role,
            'standard_role': 'F',  # TODO: verdi?
            'adm_enhet': sko,
            'arkivdel': arkivdel,
            'journalenhet': journalenhet,
            'rolletittel': rolletittel,
            'stilling': stilling
            }
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=ephorte_role]
          (%s) VALUES (%s)""" % (", ".join(binds.keys()),
                                 ", ".join([":%s" % k for k in binds.keys()])),
                                 binds)
    
    def remove_role(self, person_id, role, sko, arkivdel, journalenhet):
        binds = {
            'person_id': person_id,
            'role_type': role,
            'adm_enhet': sko,
            'arkivdel': arkivdel,
            'journalenhet': journalenhet
            }
        # TODO: Takler ikke NULL for arkivdel/journalenhet
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=ephorte_role]
        WHERE %s""" % " AND ".join(["%s=:%s" % (x, x) for x in binds.keys()]),
                     binds)
    
    def list_roles(self, person_id=None):
        if person_id:
            where = "WHERE person_id=:person_id"
        else:
            where = ""
        return self.query("""
        SELECT person_id, role_type, standard_role, adm_enhet,
               arkivdel, journalenhet, rolletittel, stilling,
               start_date, end_date
        FROM [:table schema=cerebrum name=ephorte_role] %s""" % where, {
            'person_id': person_id})

