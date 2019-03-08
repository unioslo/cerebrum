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


class _EphorteRoleTypeCode(_CerebrumCode):
    """Mappings stored in the contact_info_code table"""
    _lookup_table = '[:table schema=cerebrum name=ephorte_role_type_code]'
    pass


class _EphortePermTypeCode(_CerebrumCode):
    """Mappings stored for 'tilgangskoder' i UiOs Ephorte"""
    _lookup_table = ' [:table schema=cerebrum name=ephorte_perm_type_code]'
    pass


class _EphorteArkivdelCode(_CerebrumCode):
    """Mappings stored in the contact_info_code table"""
    _lookup_table = '[:table schema=cerebrum name=ephorte_arkivdel_code]'
    pass


class _EphorteJournalenhetCode(_CerebrumCode):
    """Mappings stored in the contact_info_code table"""
    _lookup_table = '[:table schema=cerebrum name=ephorte_journalenhet_code]'
    pass


class EphorteConstants(ConstantsBase):
    # Values from the ePhorte table ROLE
    ephorte_role_ar1 = _EphorteRoleTypeCode('AR1', 'Arkivansvarlig')
    ephorte_role_ar2 = _EphorteRoleTypeCode('AR2', 'Arkivar')
    ephorte_role_ar3 = _EphorteRoleTypeCode('AR3', 'Arkivledelsen')
    ephorte_role_ld = _EphorteRoleTypeCode('LD', 'Leder/saksfordeler')
    ephorte_role_ld_les = _EphorteRoleTypeCode('LD LES', 'Leserolle - leder')
    ephorte_role_sb = _EphorteRoleTypeCode('SB', 'Saksbehandler')
    ephorte_role_sb2 = _EphorteRoleTypeCode('SB2', 'Consultant')
    ephorte_role_sy = _EphorteRoleTypeCode('SY', 'Systemansvarlig')
    ephorte_role_mal = _EphorteRoleTypeCode('MAL', 'Mal-ansvarlige')
    ephorte_role_sub = _EphorteRoleTypeCode('SUB', 'Superbruker')

    # Values from the ePhorte table tilgang_type_code
    ephorte_perm_us = _EphortePermTypeCode(
        'US', 'Unntatt etter offentlighetsloven ved SO')
    ephorte_perm_un = _EphortePermTypeCode(
        'UN', 'Unntatt etter offentlighetsloven ved NIKK')
    ephorte_perm_ua = _EphortePermTypeCode('UA', 'Under arbeid')
    ephorte_perm_uo = _EphortePermTypeCode(
        'UO', 'Unntatt etter offentlighetsloven')
    ephorte_perm_p = _EphortePermTypeCode('P', 'Personalsaker')
    ephorte_perm_p2 = _EphortePermTypeCode(
        'P2', 'Personers økonomiske forhold')
    ephorte_perm_p3 = _EphortePermTypeCode('P3', 'Disiplinærsaker personal')
    ephorte_perm_p4 = _EphortePermTypeCode('P4', 'Rettssaker')
    ephorte_perm_s = _EphortePermTypeCode('S', 'Studentsaker')
    ephorte_perm_s2 = _EphortePermTypeCode('S2', 'Disiplinærsaker studenter')
    ephorte_perm_b = _EphortePermTypeCode(
        'B', 'Begrenset etter sikkerhetsloven')
    ephorte_perm_f = _EphortePermTypeCode(
        'F', 'Fortrolig etter beskyttelsesinstruksen')
    ephorte_perm_k = _EphortePermTypeCode(
        'K', 'Kontrakter og avtaler')
    ephorte_perm_of = _EphortePermTypeCode(
        'OF', 'Unntatt etter offentlighetsloven')
    ephorte_perm_pv = _EphortePermTypeCode('PV', 'Personalsaker')
    ephorte_perm_po = _EphortePermTypeCode(
        'PO', 'Personers økonomiske forhold')
    ephorte_perm_pd = _EphortePermTypeCode('PD', 'Disiplinærsaker personal')
    ephorte_perm_pr = _EphortePermTypeCode('PR', 'Rettssaker')
    ephorte_perm_sv = _EphortePermTypeCode('SV', 'Studentsaker')
    ephorte_perm_sd = _EphortePermTypeCode('SD', 'Disiplinærsaker studenter')
    ephorte_perm_ar = _EphortePermTypeCode('AR', 'Under arbeid')
    ephorte_perm_pa = _EphortePermTypeCode('PA', 'Personalsaker AKAN')
    ephorte_perm_fo = _EphortePermTypeCode('FO', 'Forskningssaker')
    ephorte_perm_st = _EphortePermTypeCode('ST', 'Studenttilrettelegging')
    ephorte_perm_va = _EphortePermTypeCode('VA', 'Varsling ansatte')
    ephorte_perm_vs = _EphortePermTypeCode('VS', 'Varsling studenter')
    ephorte_perm_pb = _EphortePermTypeCode('PB', 'Personalsaker bilagslønn')
    ephorte_perm_os = _EphortePermTypeCode('OS', 'Studentombud')
    ephorte_perm_ai = _EphortePermTypeCode('AI', 'Anskaffelse Innkjøp')
    ephorte_perm_af = _EphortePermTypeCode('AF', 'Forskningsavvik')

    # Values from the ePhorte table ARKIVDEL
    ephorte_arkivdel_avtale_uio = _EphorteArkivdelCode(
        'AVTALE UIO', 'Avtalearkiv ved Universitetet i Oslo')
    ephorte_arkivdel_cristin = _EphorteArkivdelCode(
        'CRISTIN', 'Current Research Information System in Norway')
    ephorte_arkivdel_fs = _EphorteArkivdelCode(
        'FS', 'FS - Felles studentsystem')
    ephorte_arkivdel_eiend_uio = _EphorteArkivdelCode(
        'EIEND UIO', 'Eiendomsarkiv ved Universitetet i Oslo')
    ephorte_arkivdel_khm_forn = _EphorteArkivdelCode(
        'KHM FORN', 'KHM (Kulturhistorisk museum) - Fornminnneforvaltning')
    ephorte_arkivdel_pers_uio = _EphorteArkivdelCode(
        'PERS UIO', 'Personalarkiv ved Universitetet i Oslo')
    ephorte_arkivdel_persav_uio = _EphorteArkivdelCode(
        'PERSAV UIO', 'Avsluttede personalmapper ved UiO')
    ephorte_arkivdel_sak_romani = _EphorteArkivdelCode(
        'ROMANI', 'Romani og taterutvalget')
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
    ephorte_arkivdel_sak_fsat = _EphorteArkivdelCode(
        'SAK FSAT', 'Saksarkiv ved Felles studieadministrativt tjenestesenter')
    ephorte_arkivdel_sak_kdto = _EphorteArkivdelCode(
        'SAK KDTO', 'Saksarkiv ved KDTO - KDs tjenesteorgan')
    ephorte_arkivdel_pers_kdto = _EphorteArkivdelCode(
        'PERS KDTO', 'Personalarkiv ved KDTO - KDs tjenesteorgan')
    ephorte_arkivdel_nasjonklag_kdto = _EphorteArkivdelCode(
        'NASJONKLAG KDTO', 'Nasjonal klagenemnd')
    ephorte_arkivdel_nasjonfag_kdto = _EphorteArkivdelCode(
        'NASJONFAG KDTO', 'Nasjonal klagenemnd for fagskoleutdanning')
    ephorte_arkivdel_fellesklag_kdto = _EphorteArkivdelCode(
        'FELLESKLAG KDTO', 'Felles klagenemnd')

    # Values from the ePhorte table JOURNENHET
    ephorte_journenhet_uio = _EphorteJournalenhetCode(
        'J-UIO', 'Journalenhet for UiO - Universitetet i Oslo')
    ephorte_journenhet_so = _EphorteJournalenhetCode(
        'J-SO', 'Journalenhet for SO - Samordna Opptak')
    ephorte_journenhet_nikk = _EphorteJournalenhetCode(
        'J-NIKK', 'Journalenhet for NIKK - Nordisk institutt for kvinne- og kjønnsforskn')
    ephorte_journenhet_romani = _EphorteJournalenhetCode(
        'J-ROMANI', 'Journalenhet for ROMANI - prosjektet')
    ephorte_journenhet_fsat = _EphorteJournalenhetCode(
        'J-FSAT',
        'Journalenhet for FSAT - Felles studieadministrativt tjenestesenter')
    ephorte_journenhet_kdto = _EphorteJournalenhetCode(
        'J-KDTO', 'Journalenhet for KDTO - KDs tjenesteorgan')

    # Spreads relevant for ephorte
    spread_ephorte_person = _SpreadCode('ePhorte_person',
                                        Constants.Constants.entity_person,
                                        'Person included in ePhorte export')
    spread_ephorte_ou = _SpreadCode('ePhorte_ou',
                                    Constants.Constants.entity_ou,
                                    'OU included in ePhorte export')

    EphorteRole = _EphorteRoleTypeCode
    EphorteArkivdel = _EphorteArkivdelCode
    EphorteJournalenhet = _EphorteJournalenhetCode
    EphortePermission = _EphortePermTypeCode


class CLConstants(Constants.CLConstants):
    ephorte_role_add = Constants._ChangeTypeCode(
        'ephorte', 'role_add', 'add ephorte role @ %(dest)s',
        ('type=%(rolle_type:rolle_type)s',))

    ephorte_role_upd = Constants._ChangeTypeCode(
        'ephorte', 'role_upd', 'update ephorte role @ %(dest)s')

    ephorte_role_rem = Constants._ChangeTypeCode(
        'ephorte', 'role_rem', 'remove ephorte role @ %(dest)s',
        ('type=%(rolle_type:rolle_type)s',))

    ephorte_perm_add = Constants._ChangeTypeCode(
        'ephorte', 'perm_add', 'add ephorte perm @ %(dest)s',
        ('type=%(perm_type:perm_type)s',))

    ephorte_perm_rem = Constants._ChangeTypeCode(
        'ephorte', 'perm_rem', 'remove ephorte perm @ %(dest)s',
        ('type=%(perm_type:perm_type)s',))
