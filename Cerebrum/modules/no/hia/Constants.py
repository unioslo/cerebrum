# -*- coding: iso-8859-1 -*-

# Copyright 2002, 2003, 2004 University of Oslo, Norway
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

from Cerebrum.Constants import Constants, \
     _AuthoritativeSystemCode, _OUPerspectiveCode, _SpreadCode, \
     _QuarantineCode, _PersonExternalIdCode, _PersonAffiliationCode, \
     _PersonAffStatusCode, _AccountCode, _PersonNameCode, \
     _ContactInfoCode, _CountryCode
from Cerebrum.modules.PosixUser import _PosixShellCode

central_Constants = Constants

class Constants(central_Constants):

    externalid_fodselsnr = _PersonExternalIdCode('NO_BIRTHNO',
                                                 'Norwegian birth number')
    externalid_studentnr = _PersonExternalIdCode('NO_STUDNO',
                                                 'Norwegian student number')
    externalid_sap_ansattnr = _PersonExternalIdCode('HiA_SAP_EMP#',
                                                    'HiA SAP employee number')

    system_fs = _AuthoritativeSystemCode('FS', 'FS')
    system_fs_derived = _AuthoritativeSystemCode('FS-auto',
                                                 'Utledet av FS data')
    system_migrate = _AuthoritativeSystemCode('MIGRATE', 'Migrate from files')
    system_sap = _AuthoritativeSystemCode('SAP', 'SAP')
    system_pbx = _AuthoritativeSystemCode('PBX', 'PBX')
    system_manual =  _AuthoritativeSystemCode('MANUELL',
                                              'Manually added information')

    perspective_fs = _OUPerspectiveCode('FS', 'FS')

    account_test = _AccountCode('testbruker', 'Testkonto')
    account_kurs = _AccountCode('kursbruker', 'Kurskonto')
    account_studorg = _AccountCode('studorgbruker','Studentorganisasjonsbruker')
    account_felles  = _AccountCode('fellesbruker','Fellesbruker')
    account_system  = _AccountCode('systembruker', 'Systembruker') 

## AFFILIATIONS FOR ANSATTE
    affiliation_ansatt = _PersonAffiliationCode('ANSATT', 'Ansatt ved HiA')
    affiliation_status_ansatt_manuell = _PersonAffStatusCode(
        affiliation_ansatt, 'ans_manuell', 'Ansatt, manuell import')
    affiliation_status_ansatt_vitenskapelig = _PersonAffStatusCode(
        affiliation_ansatt, 'vitenskapelig', 'Ansatt, vitenskapelige ansatte')
    affiliation_status_ansatt_tekadm = _PersonAffStatusCode(
        affiliation_ansatt, 'tekadm', 'Tekniske/administrative ansatte')
    affiliation_status_ansatt_primaer = _PersonAffStatusCode(
        affiliation_ansatt, 'primær', 'Primærtilknytning for SAP ansatte')
    
## AFFILIATIONS FOR STUDENTER
    affiliation_student = _PersonAffiliationCode('STUDENT', 'Student ved HiA')
    affiliation_status_student_manuell = _PersonAffStatusCode(
        affiliation_student, 'stud_manuell', 'Student, manuell import')
    affiliation_status_student_evu = _PersonAffStatusCode(
        affiliation_student, 'evu', 'Student, etter og videre utdanning')
    affiliation_status_student_aktiv = _PersonAffStatusCode(
        affiliation_student, 'aktiv', 'Student, aktiv')
    affiliation_status_student_tilbud = _PersonAffStatusCode(
        affiliation_student, 'tilbud', 'Student, tilbud')
    affiliation_status_student_privatist = _PersonAffStatusCode(
        affiliation_student, 'privatist', 'Student, privatist')
## We are not going to use this affiliation for the time being
##     affiliation_status_student_opptak = _PersonAffStatusCode(
##         affiliation_student, 'opptak', 'Student, opptak')

## AFFILIATIONS FOR ANDRE
    affiliation_manuell = _PersonAffiliationCode(
        'MANUELL',
        ('Tilknyttet HiA uten å være registrert i et av de'
         ' autoritative kildesystemene'))
    affiliation_status_manuell_ekstern = _PersonAffStatusCode(
        affiliation_manuell, 'ekstern',
        'Eksternt tilknyttet person, når spesifikke kategorier ikke passer')
    affiliation_status_manuell_sia = _PersonAffStatusCode(
        affiliation_manuell, 'sia',
        'Person tilknyttet Studentsamskipnaden i Agder')
    affiliation_status_manuell_sta = _PersonAffStatusCode(
        affiliation_manuell, 'sta',
        'Person tilknyttet Studentorganisasjonen Agder')
    affiliation_status_manuell_filonova = _PersonAffStatusCode(
        affiliation_manuell, 'filonova',
        'Person tilknyttet Filonova kursstiftelse')
    affiliation_status_manuell_agderforskning = _PersonAffStatusCode(
        affiliation_manuell, 'agderforskning',
        'Person tilknyttet Agderforskning')
    affiliation_status_manuell_statsbygg = _PersonAffStatusCode(
        affiliation_manuell, 'statsbygg',
        'Person tilknyttet Statsbygg ved HiA')
    affiliation_status_manuell_pensjonist = _PersonAffStatusCode(
        affiliation_manuell, 'pensjonist',
        'Pensjonist ved HiA, ikke registrert i SAP')
    affiliation_status_manuell_gjest = _PersonAffStatusCode(
        affiliation_manuell, 'gjest', 'Gjesteopphold ved HiA')
    affiliation_status_manuell_ans_uten_sap = _PersonAffStatusCode(
        affiliation_manuell, 'ans_uten_sap',
        'Ansatt som ikke er lagt inn i SAP. En midlertidig status for folk')
    affiliation_status_manuell_gjest_ikke_epost = _PersonAffStatusCode(
        affiliation_manuell, 'gjest_no_epost', 
	'Gjesteopphold som ansatt ved HiA. Skal ikke ha epost')
    affiliation_status_manuell_gjest_student = _PersonAffStatusCode(
        affiliation_manuell, 'gjest_student', 
	'Gjesteopphold for student ved HiA. Epost skal tildeles')
    affiliation_status_manuell_gjest_student_ikke_epost = _PersonAffStatusCode(
	affiliation_manuell, 'gj_st_no_epost', 
	'Gjesteopphold for student ved HiA. Epost skal ikke tildeles')

    affiliation_upersonlig = _PersonAffiliationCode(
        'UPERSONLIG', 'Fellesbrukere, samt andre brukere uten eier')
    affiliation_upersonlig_felles = _PersonAffStatusCode(
        affiliation_upersonlig, 'felles', 'Felleskonti')
    affiliation_upersonlig_kurs = _PersonAffStatusCode(
        affiliation_upersonlig, 'kurs', 'Kurskonti')
    affiliation_upersonlig_pvare = _PersonAffStatusCode(
        affiliation_upersonlig, 'pvare', 'Programvarekonti')
    affiliation_upersonlig_studentforening = _PersonAffStatusCode(       
	affiliation_upersonlig, 'studorg', 
	'Studentforening eller -aktivitet ved HiA')

## DEFINISJON AV SHELL 
    # We override the default Cerebrum paths for shells, thus this
    # file should appear before PosixUser in cereconf.CLASS_CONSTANTS
    posix_shell_bash = _PosixShellCode('bash', '/bin/bash')
    posix_shell_tcsh = _PosixShellCode('tcsh', '/bin/tcsh')
    posix_shell_csh = _PosixShellCode('csh', '/bin/csh')
    posix_shell_sh = _PosixShellCode('sh', '/bin/sh')

## DEFINISJON AV SPREAD
    spread_hia_novell_user = _SpreadCode(
        'account@edir', central_Constants.entity_account,
        'User in Novell domain "hia"')
    spread_hia_novell_empl = _SpreadCode(
        'employee@edir', central_Constants.entity_account,
        'Employee in Novell domain "hia"')
    spread_hia_novell_labuser = _SpreadCode(
        'account@edirlab', central_Constants.entity_account,
        'User in Novell domain "hia", employee lab-users only')
    spread_hia_novell_group = _SpreadCode(
        'group@edir', central_Constants.entity_group,
        'Group in Novell domain "hia"')
    spread_nis_user = _SpreadCode(
        'account@nis', central_Constants.entity_account,
        'User in NIS domain "stud"')
    spread_ans_nis_user = _SpreadCode(
        'account@nisans', central_Constants.entity_account,
        'User in NIS domain "ans"')
    spread_nis_fg = _SpreadCode(
        'group@nis', central_Constants.entity_group,
        'File group in NIS domain "stud"')
    spread_nis_ng = _SpreadCode(
        'netgroup@nis', central_Constants.entity_group,
        'Net group in NIS domain "stud"')
    spread_ans_nis_fg = _SpreadCode(
        'group@nisans', central_Constants.entity_group,
        'File group in NIS domain "ans"')
    spread_ans_nis_ng = _SpreadCode(
        'netgroup@nisans', central_Constants.entity_group,
        'Net group in NIS domain "ans"')
    spread_hia_adgang = _SpreadCode(
        'account@adgang', central_Constants.entity_person,
        'Person exported to Adgang system')
    spread_hia_email = _SpreadCode(
        'account@imap', central_Constants.entity_account,
        'Email user at HiA')
    spread_hia_bibsys = _SpreadCode(
        'account@bibsys', central_Constants.entity_person,
        'Person exported to BIBSYS')
    spread_hia_tele = _SpreadCode(
        'account@telefon', central_Constants.entity_person,
        'Person exported to phone system')
    spread_hia_ldap_person = _SpreadCode(
        'account@ldap', central_Constants.entity_person, 
        'Person included in LDAP directory')
    spread_hia_ldap_ou = _SpreadCode(
        'ou@ldap', central_Constants.entity_ou,
        'OU included in LDAP directory')
    spread_hia_helpdesk = _SpreadCode(
        'account@helpdesk', central_Constants.entity_account, 
        'Account exported to helpdesk system')
    spread_hia_ad_account = _SpreadCode(
        'account@ad', central_Constants.entity_account,
        'Account included in Active Directory')
    spread_hia_ad_group = _SpreadCode(
        'group@ad', central_Constants.entity_group,
        'group included in Active Directory')   

    spread_hia_fronter = _SpreadCode(
        'group@fronter', central_Constants.entity_group,
        ('Group representing a course that should be exported to'
         ' the ClassFronter.  Should only be given to groups that'
         ' have been automatically generated from FS.'))

## Kommenteres ut foreløpig, er usikkert om vi skal ha dem 

##     spread_hia_fs = _SpreadCode(
##         'FS@hia', central_Constants.entity_account,
##         'Account exported to FS')
##     spread_hia_sap = _SpreadCode(
##         'SAP@hia', central_Constants.entity_account,
##         'Account exported to SAP')

## KARANTENEGRUPPER
    quarantine_generell = _QuarantineCode('generell', 'Generell splatt')
    quarantine_teppe = _QuarantineCode('teppe',
                                       'Kalt inn på teppet til drift')
    quarantine_auto_inaktiv = _QuarantineCode('auto_inaktiv', 'Ikke aktiv student, utestengt')
    quarantine_auto_emailonly = _QuarantineCode('auto_emailonly',
                                                'Ikke ordinær student, tilgang til bare e-post')
    quarantine_slutta = _QuarantineCode('slutta', 'Personen har slutta')
    quarantine_system = _QuarantineCode('system',
                                        'Systembrukar som ikke skal logge inn')
    quarantine_permisjon = _QuarantineCode('permisjon',
                                           'Brukeren har permisjon')
    quarantine_svakt_passord = _QuarantineCode('svakt_passord',
                                               'For dårlig passord')
    quarantine_autopassord = _QuarantineCode(
        'autopassord', 'Passord ikke skiftet trass pålegg')
    quarantine_autostud = _QuarantineCode('autostud', 'Ikke aktiv student')
    quarantine_autoekstern = _QuarantineCode('autoekstern',
                                             'Ekstern konto gått ut på dato')
    quarantine_ou_notvalid = _QuarantineCode(
        'ou_notvalid', 'OU not valid from external source')    
    quarantine_ou_remove = _QuarantineCode('ou_remove',
                                           'OU is clean and may be removed')

## SAP-spesifikke navnekonstanter
    name_middle = _PersonNameCode('MIDDLE', 'Middle name')
    name_initials = _PersonNameCode('INITIALS', 'Initials')

## SAP-spesifikke kommtypekonstater
    contact_phone_cellular = _ContactInfoCode("CELLPHONE",
                                              "Person's cellular phone")
    contact_phone_cellular_private = _ContactInfoCode(
                                       "PRIVCELLPHONE",
                                       "Person's private cellular phone")

## Landkonstanter for SAP
    country_no = _CountryCode("NO", "Norway", "47", "Norway")
    country_gb = _CountryCode("GB", "Great Britain", "44", "Great Britain")
    country_fi = _CountryCode("FI", "Finland", "358", "Finland")
    country_se = _CountryCode("SE", "Sweden", "46", "Sweden")
    country_us = _CountryCode("US", "USA", "1", "United states of America")
    country_nl = _CountryCode("NL", "The Netherlands", "31", "The Netherlands")
    country_de = _CountryCode("DE", "Germany", "49", "Germany")
    country_au = _CountryCode("AU", "Australia", "61", "Australia")
    country_dk = _CountryCode("DK", "Denmark", "45", "Denmark")
    country_it = _CountryCode("IT", "Italia", "39", "Denmark")

## Landkoder som forekommer i SAP-dumpen uten å være
## definert i Cerebrum
## BE
## CH
## CS
## EE
## FR
## GR
## ID
## IE
## IS
## LV
## SG
## SI
## TN

# end Constants

# arch-tag: 7cf93c78-fe00-41f3-8fee-1289c86b7086
