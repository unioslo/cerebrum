# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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

"""Access to Cerebrum code values.

The Constants class defines a set of methods that should be used to
get the actual database code/code_str representing a given Entity,
Address, Gender etc. type."""

from Cerebrum import Constants
from Cerebrum.Constants import _AuthoritativeSystemCode, \
                               _SpreadCode, \
                               _QuarantineCode,\
                               _PersonAffiliationCode, \
                               _PersonAffStatusCode, \
                               _AccountCode, \
                               _PersonNameCode, \
                               _ContactInfoCode, \
                               _CountryCode

class Constants(Constants.Constants):
## AFFILIATIONS FOR ANSATTE
    affiliation_ansatt = _PersonAffiliationCode('ANSATT', 'Ansatt ved NMH')
    affiliation_status_ansatt_ovlaerer = _PersonAffStatusCode(
        affiliation_ansatt, 'ans_ovlaerer', 'Ansatt ved NMH, øvingslærer.')
    affiliation_status_ansatt_vitenskapelig = _PersonAffStatusCode(
        affiliation_ansatt, 'vitenskapelig', 'Vitenskapelig ansatt ved NMH')
    affiliation_status_ansatt_tekadm = _PersonAffStatusCode(
        affiliation_ansatt, 'tekadm', 'Tekniske/administrative ansatte')
    
## AFFILIATIONS FOR STUDENTER
    affiliation_student = _PersonAffiliationCode('STUDENT', 'Student ved NMH')
    affiliation_status_student_evu = _PersonAffStatusCode(
        affiliation_student, 'evu', 'Student, etter og videre utdanning')
    affiliation_status_student_aktiv = _PersonAffStatusCode(
        affiliation_student, 'aktiv', 'Student, aktiv')

## AFFILIATIONS FOR ASSOSIERTE PERSONER
    affiliation_tilknyttet = _PersonAffiliationCode(
        'TILKNYTTET',
        ('Personer tilknyttet NMH og registrert i SAP med utvalgte stillingskoder'))
    ## Fram til SAP er i produksjon hos NMH er fagpersoner å regne
    ## som ansatte og skal behandles deretter (ved f.eks. eksport til LDAP)
    affiliation_status_tilknyttet_fagperson = _PersonAffStatusCode(
        affiliation_tilknyttet, 'fagperson',
        'Personer registrert i FS som fagpersoner')
    affiliation_status_tilknyttet_pensjonist = _PersonAffStatusCode(
        affiliation_tilknyttet, 'pensjonist',
        'Personer registrert i SAP som pensjonister')
    affiliation_status_tilknyttet_bilag = _PersonAffStatusCode(
        affiliation_tilknyttet, 'bilag',
        'Personer registrert i SAP som bilagslønnet')
    affiliation_status_tilknyttet_gjest = _PersonAffStatusCode(
        affiliation_tilknyttet, 'gjest',
        'Personer registrert i SAP som gjest')
    affiliation_status_tilknyttet_gjestefors = _PersonAffStatusCode(
        affiliation_tilknyttet, 'gjesteforsker',
        'Personer registrert i SAP som gjesteforskere')    

## AFFILIATIONS FOR ANDRE
    affiliation_manuell = _PersonAffiliationCode(
        'MANUELL',
        ('Tilknyttet NMH uten å være registrert i et av de'
         ' autoritative kildesystemene'))
    affiliation_status_manuell_inaktiv = _PersonAffStatusCode(
        affiliation_manuell, 'inaktiv',
        'Person uten ekte tilknytning til NMH. Bruk med forsiktighet!')

## DEFINISJON AV SPREAD
    ## Brukerrelaterte spread
    spread_ad_account = _SpreadCode(
        'account@ad', Constants.Constants.entity_account,
        'Brukeren kjent i AD ved NMH')
    spread_exchange_account = _SpreadCode(
        'account@exchange', Constants.Constants.entity_account,
        'Brukeren kjent i AD ved NMH')
    spread_ldap_account = _SpreadCode(
        'account@ldap', Constants.Constants.entity_account,
        'Brukeren kjent i LDAP ved NMH')
    spread_lms_account = _SpreadCode(
        'account@lms', Constants.Constants.entity_account,
        'Brukeren kjent i LMSen til NMH')    

    ## Grupperelaterte spread
    spread_ad_group = _SpreadCode(
        'group@ad', Constants.Constants.entity_group,
        'Gruppe kjent i AD ved NMH')
    spread_lms_group = _SpreadCode(
        'group@lms', Constants.Constants.entity_group,
        'Gruppe kjent i LMSen til NMH')    

    ## Personrelaterte spread
    spread_ldap_person = _SpreadCode(
        'person@ldap', Constants.Constants.entity_person,
        'Person kjent i organisasjonstreet til NMH (FEIDE-person)')
    spread_adgang_person = _SpreadCode(
        'person@adgang', Constants.Constants.entity_person,
        'Person kjent i adgangssystemet til NMH')
    spread_lms_person = _SpreadCode(
        'person@lms', Constants.Constants.entity_person,
        'Person kjent i LMSen til NMH')

## KARANTENETYPER
    quarantine_generell = _QuarantineCode('generell',
                                          'Generell splatt')
    quarantine_teppe = _QuarantineCode('teppe',
                                       'Kalt inn på teppe')
    quarantine_kunepost = _QuarantineCode('kunepost',
                                           'Tilgang kun til e-post')
    quarantine_svaktpassord = _QuarantineCode('svaktpassord',
                                               'For dårlig passord')
    quarantine_system = _QuarantineCode('system',
                                        'Systembrukar som ikke skal logge inn')
    ## Cerebruminternt, skal kun brukes automatisk
    quarantine_auto_passord = _QuarantineCode('auto_passord',
                                             'Passord ikke skiftet trass pålegg')
    quarantine_auto_inaktiv = _QuarantineCode('auto_inaktiv',
                                              'Ikke aktiv student, utestengt')
    quarantine_auto_kunepost = _QuarantineCode('auto_kunepost',
                                               'Privatist, kun tilgang til e-post')
    quarantine_ou_notvalid = _QuarantineCode('ou_notvalid',
                                             'Sted ugyldig i autoritativ kildesystem')    
    quarantine_ou_remove = _QuarantineCode('ou_remove',
                                           'Sted fjernet fra autoritativ kildesystem')
