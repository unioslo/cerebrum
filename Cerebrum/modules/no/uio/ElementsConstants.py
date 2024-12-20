# -*- coding: utf-8 -*-
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

from Cerebrum import Constants
from Cerebrum.Constants import (ConstantsBase, _CerebrumCode, _SpreadCode)


class _ElementsRoleTypeCode(_CerebrumCode):
    """Mappings stored in the contact_info_code table"""
    _lookup_table = '[:table schema=cerebrum name=elements_role_type_code]'
    pass


class _ElementsPermTypeCode(_CerebrumCode):
    """Mappings stored for 'tilgangskoder' i UiOs Elements"""
    _lookup_table = ' [:table schema=cerebrum name=elements_perm_type_code]'
    pass


class _ElementsArkivdelCode(_CerebrumCode):
    """Mappings stored in the contact_info_code table"""
    _lookup_table = '[:table schema=cerebrum name=elements_arkivdel_code]'
    pass


class _ElementsJournalenhetCode(_CerebrumCode):
    """Mappings stored in the contact_info_code table"""
    _lookup_table = '[:table schema=cerebrum name=elements_journalenhet_code]'
    pass


class ElementsConstants(ConstantsBase):
    # Values from the elements table ROLE
    elements_role_ar1 = _ElementsRoleTypeCode('AR1', 'Arkivansvarlig')
    elements_role_ar2 = _ElementsRoleTypeCode('AR2', 'Arkivar')
    elements_role_ar3 = _ElementsRoleTypeCode('AR3', 'Arkivledelsen')
    elements_role_ld = _ElementsRoleTypeCode('LD', 'Leder/saksfordeler')
    elements_role_ld_les = _ElementsRoleTypeCode('LD LES', 'Leserolle - leder')
    elements_role_sb = _ElementsRoleTypeCode('SB', 'Saksbehandler')
    elements_role_sb2 = _ElementsRoleTypeCode('SB2', 'Consultant')
    elements_role_sy = _ElementsRoleTypeCode('SY', 'Systemansvarlig')
    elements_role_mal = _ElementsRoleTypeCode('MAL', 'Mal-ansvarlige')
    elements_role_sub = _ElementsRoleTypeCode('SUB', 'Superbruker')

    # Values from the elements table tilgang_type_code
    elements_perm_b = _ElementsPermTypeCode(
        'B', 'Begrenset etter sikkerhetsloven')
    elements_perm_f = _ElementsPermTypeCode(
        'F', 'Fortrolig etter beskyttelsesinstruksen')
    elements_perm_k = _ElementsPermTypeCode(
        'K', 'Kontrakter og avtaler')
    elements_perm_of = _ElementsPermTypeCode(
        'OF', 'Unntatt etter offentlighetsloven')
    elements_perm_pv = _ElementsPermTypeCode('PV', 'Personalsaker')
    elements_perm_po = _ElementsPermTypeCode(
        'PO', 'Personers økonomiske forhold')
    elements_perm_pd = _ElementsPermTypeCode('PD', 'Disiplinærsaker personal')
    elements_perm_pr = _ElementsPermTypeCode('PR', 'Rettssaker')
    elements_perm_sv = _ElementsPermTypeCode('SV', 'Studentsaker')
    elements_perm_sd = _ElementsPermTypeCode('SD', 'Disiplinærsaker studenter')
    elements_perm_ar = _ElementsPermTypeCode('AR', 'Under arbeid')
    elements_perm_pa = _ElementsPermTypeCode('PA', 'Personalsaker AKAN')
    elements_perm_fo = _ElementsPermTypeCode('FO', 'Forskningssaker')
    elements_perm_st = _ElementsPermTypeCode('ST', 'Studenttilrettelegging')
    elements_perm_va = _ElementsPermTypeCode('VA', 'Varsling ansatte')
    elements_perm_vs = _ElementsPermTypeCode('VS', 'Varsling studenter')
    elements_perm_pb = _ElementsPermTypeCode('PB', 'Personalsaker bilagslønn')
    elements_perm_os = _ElementsPermTypeCode('OS', 'Studentombud')
    elements_perm_ai = _ElementsPermTypeCode('AI', 'Anskaffelse Innkjøp')
    elements_perm_af = _ElementsPermTypeCode('AF', 'Forskningsavvik')
    elements_perm_am = _ElementsPermTypeCode('AM', 'Arbeidsmiljøundersøkelser')

    # Values from the elements table ARKIVDEL
    elements_arkivdel_avtale_uio = _ElementsArkivdelCode(
        'AVTALE UIO', 'Avtalearkiv ved Universitetet i Oslo')
    elements_arkivdel_cristin = _ElementsArkivdelCode(
        'CRISTIN', 'Current Research Information System in Norway')
    elements_arkivdel_fs = _ElementsArkivdelCode(
        'FS', 'FS - Felles studentsystem')
    elements_arkivdel_eiend_uio = _ElementsArkivdelCode(
        'EIEND UIO', 'Eiendomsarkiv ved Universitetet i Oslo')
    elements_arkivdel_khm_forn = _ElementsArkivdelCode(
        'KHM-FORN', 'KHM (Kulturhistorisk museum) - Fornminnneforvaltning')
    elements_arkivdel_khm_objekt = _ElementsArkivdelCode(
        'KHM-OBJEKT', 'KHM (Kulturhistorisk museum) - Objektforvaltning')
    elements_arkivdel_pers_uio = _ElementsArkivdelCode(
        'PERS', 'Personalarkiv ved Universitetet i Oslo')
    elements_arkivdel_persav_uio = _ElementsArkivdelCode(
        'PERSAV UIO', 'Avsluttede personalmapper ved UiO')
    elements_arkivdel_sak_romani = _ElementsArkivdelCode(
        'ROMANI', 'Romani og taterutvalget')
    elements_arkivdel_sak = _ElementsArkivdelCode(
        'SAK', 'Saksarkiv ved Universitetet i Oslo')
    elements_arkivdel_stud = _ElementsArkivdelCode(
        'STUD', 'Studentarkiv ved Universitetet i Oslo')
    elements_arkivdel_studav_uio = _ElementsArkivdelCode(
        'STUDAV UIO', 'Avsluttede studentmapper ved UiO')

    # Values from the elements table JOURNENHET
    elements_journenhet_sp = _ElementsJournalenhetCode(
        'SP', 'Journalenhet for UiO - Universitetet i Oslo')
    elements_journenhet_fsat = _ElementsJournalenhetCode(
        'J-FSAT',
        'Journalenhet for FSAT - Felles studieadministrativt tjenestesenter')
    elements_journenhet_kdto = _ElementsJournalenhetCode(
        'J-KDTO', 'Journalenhet for KDTO - KDs tjenesteorgan')

    # Spreads relevant for elements
    spread_elements_person = _SpreadCode('elements_person',
                                        Constants.Constants.entity_person,
                                        'Person included in elements export')
    spread_elements_ou = _SpreadCode('elements_ou',
                                    Constants.Constants.entity_ou,
                                    'OU included in elements export')

    ElementsRole = _ElementsRoleTypeCode
    ElementsArkivdel = _ElementsArkivdelCode
    ElementsJournalenhet = _ElementsJournalenhetCode
    ElementsPermission = _ElementsPermTypeCode


class CLConstants(Constants.CLConstants):
    elements_role_add = Constants._ChangeTypeCode(
        'elements_role', 'add', 'add elements role @ %(dest)s',
        ('type=%(rolle_type:rolle_type)s',))

    elements_role_upd = Constants._ChangeTypeCode(
        'elements_role', 'modify', 'update elements role @ %(dest)s')

    elements_role_rem = Constants._ChangeTypeCode(
        'elements_role', 'remove', 'remove elements role @ %(dest)s',
        ('type=%(rolle_type:rolle_type)s',))

    elements_perm_add = Constants._ChangeTypeCode(
        'elements_perm', 'add', 'add elements perm @ %(dest)s',
        ('type=%(perm_type:perm_type)s',))

    elements_perm_rem = Constants._ChangeTypeCode(
        'elements_perm', 'remove', 'remove elements perm @ %(dest)s',
        ('type=%(perm_type:perm_type)s',))
