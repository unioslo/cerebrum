# Copyright 2002, 2003 University of Oslo, Norway
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
from Cerebrum.Constants import _AuthoritativeSystemCode,_OUPerspectiveCode, \
     _SpreadCode, _QuarantineCode, _PersonExternalIdCode, \
     _PersonAffiliationCode, _PersonAffStatusCode, _AccountCode, \
     _PersonNameCode, _ContactInfoCode, _CountryCode

from Cerebrum.modules.PosixUser import _PosixShellCode

class Constants(Constants.Constants):

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
    system_manual =  _AuthoritativeSystemCode('MANUELL', 
					      'Manually added information')

    perspective_fs = _OUPerspectiveCode('FS', 'FS')

    account_test = _AccountCode('testbruker', 'Testkonto')
    account_kurs = _AccountCode('kursbruker','Kurskonto')

# ANSATTE

    affiliation_ansatt = _PersonAffiliationCode('ANSATT','Ansatt ved HiA')
    affiliation_status_ansatt_manuell = _PersonAffStatusCode(
        affiliation_ansatt, 'ans_manuell', 'Ansatt, manuell import')
    affiliation_status_ansatt_vitenskapelig = _PersonAffStatusCode(
        affiliation_ansatt, 'vitenskapelig', 'Ansatt, vitenskapelige ansatte')
    affiliation_status_ansatt_tekadm = _PersonAffStatusCode(
        affiliation_ansatt, 'tekadm', 'Tekniske/administrative ansatte')
    affiliation_status_ansatt_primaer = _PersonAffStatusCode(
        affiliation_ansatt, 'primær', 'Primærtilknytning for SAP ansatte')
    
# STUDENTER
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
    
# We are not going to use this affiliation fro the time being
# affiliation_status_student_opptak = _PersonAffStatusCode(
# affiliation_student, 'opptak', 'Student, opptak')

# ANDRE

    affiliation_manuell = _PersonAffiliationCode('MANUELL', 
						 'Tilknyttet HiA uten å være registrert i et av de autoritative kildesystemene')
    affiliation_status_manuell_ekstern = _PersonAffStatusCode(
	affiliation_manuell, 'ekstern', 'Ekstern tilknyttet person')
    affiliation_status_manuell_sia = _PersonAffStatusCode(
	affiliation_manuell, 'sia', 'Person tilknyttet Samskipnaden i Agder')
    affiliation_status_manuell_statsbygg = _PersonAffStatusCode(
	affiliation_manuell, 'statsbygg', 'Person tilknyttet Statsbygg ved Høgskolen i Agder')
    affiliation_status_manuell_filonova = _PersonAffStatusCode(
        affiliation_manuell, 'filonova', 'Person tilknyttet Filonova')
    affiliation_status_manuell_sta = _PersonAffStatusCode(
        affiliation_manuell, 'sta', 'Person tilknyttet STA - Studentforeningen ved Høgskolen i Agder')
    affiliation_status_manuell_agderforskning = _PersonAffStatusCode(
        affiliation_manuell, 'agderforskning', 'Person tilknyttet Agderforskning')

    # We override the default settings for shells, thus this file
    # should be before PosixUser in cereconf.CLASS_CONSTANTS

# DEFINISJON AV SHELL 
    posix_shell_bash = _PosixShellCode('bash', '/bin/bash')
    posix_shell_tcsh = _PosixShellCode('tcsh', '/bin/tcsh')
    posix_shell_csh = _PosixShellCode('csh', '/bin/csh')
    posix_shell_sh = _PosixShellCode('sh', '/bin/sh')

# SPREAD DEFINISJONER
    spread_hia_novell_user = _SpreadCode('account@edir', Constants.Constants.entity_account,
					 'User in Novell domain "hia"')
    spread_hia_novell_labuser = _SpreadCode('account@edirlab', Constants.Constants.entity_account,
					    'User in Novell domain "hia", employee lab-users only')
    spread_hia_novell_group = _SpreadCode('group@edir', Constants.Constants.entity_group,
					 'Group in Novell domain "hia"')
    spread_nis_user = _SpreadCode('account@nis', Constants.Constants.entity_account,
					 'User in NIS domain "stud"')
    spread_ans_nis_user = _SpreadCode('account@nisans', Constants.Constants.entity_account,
				      'User in NIS domain "ans"')
    spread_nis_fg = _SpreadCode('group@nis', Constants.Constants.entity_group,
                                'File group in NIS domain "stud"')
    spread_nis_ng = _SpreadCode('netgroup@nis', Constants.Constants.entity_group,
                                'Net group in NIS domain "stud"')
    spread_ans_nis_fg = _SpreadCode('group@nisans', Constants.Constants.entity_group,
                                    'File group in NIS domain "ans"')
    spread_ans_nis_ng = _SpreadCode('netgroup@nisans', Constants.Constants.entity_group,
                                    'Net group in NIS domain "ans"')
    spread_hia_adgang = _SpreadCode('account@adgang', Constants.Constants.entity_person,
				    'Person exported to Adgang system')
    spread_hia_email = _SpreadCode('account@imap', Constants.Constants.entity_account,
				   'Email user at HiA')
    spread_hia_bibsys = _SpreadCode('account@bibsys', Constants.Constants.entity_person,
				    'Person exported to BIBSYS')
    spread_hia_tele = _SpreadCode('account@telefon', Constants.Constants.entity_person,
				  'Person exported to phone system')
    spread_hia_ldap_person = _SpreadCode('account@ldap', Constants.Constants.entity_person, 
					 'Person included in LDAP directory')
    spread_hia_ldap_ou = _SpreadCode('ou@ldap', Constants.Constants.entity_ou,
                                     'OU included in LDAP directory')
    spread_hia_helpdesk = _SpreadCode('account@helpdesk', Constants.Constants.entity_account, 
				      'Account exported to helpdesk system')
    spread_hia_ad_account = _SpreadCode('account@ad', Constants.Constants.entity_account,
					'Account included in Active Directory')
    spread_hia_ad_group = _SpreadCode('group@ad', Constants.Constants.entity_group,
				      'group included in Active Directory')   

    spread_hia_fronter = _SpreadCode('group@fronter', Constants.Constants.entity_group,
				     '''Group representing a course that should be exported to the ClassFronter.Should only be given to groups that have been automatically generated from FS.''')

#Kommenteres ut foreløpig, er usikkert om vi skal ha dem 

#    spread_hia_fs = _SpreadCode('FS@hia', Constants.Constants.entity_account,
#				'Account exported to FS')
#    spread_hia_sap = _SpreadCode('SAP@hia', Constants.Constants.entity_account,
#				 'Account exported to SAP')

    affiliation_upersonlig = _PersonAffiliationCode('UPERSONLIG', 
						    'Fellesbrukere, samt andre brukere uten eier')
    affiliation_upersonlig_felles = _PersonAffStatusCode(affiliation_upersonlig, 
							 'felles', 'Felleskonti')
    affiliation_upersonlig_kurs = _PersonAffStatusCode(affiliation_upersonlig, 
						       'kurs', 'Kurskonti')
    affiliation_upersonlig_pvare = _PersonAffStatusCode(affiliation_upersonlig, 
							'pvare', 'Programvarekonti')

# KARANTENE GRUPPER
    quarantine_generell = _QuarantineCode('generell', 'Generell splatt')
    quarantine_teppe = _QuarantineCode('teppe', 'Kallt inn på teppet til drift')
    quarantine_slutta = _QuarantineCode('slutta', 'Personen har slutta')
    quarantine_system = _QuarantineCode('system', 'Systembrukar som ikke skal logge inn')
    quarantine_permisjon = _QuarantineCode('permisjon', 'Brukeren har permisjon')
    quarantine_svakt_passord = _QuarantineCode('svakt_passord', 'For dårlig passord')
    quarantine_autopassord = _QuarantineCode('autopassord', 'Passord ikke skiftet trass pålegg')
    quarantine_autostud = _QuarantineCode('autostud', 'Ikke aktiv student')
    quarantine_autoekstern = _QuarantineCode('autoekstern', 'Ekstern konto gått ut på dato')
    quarantine_ou_notvalid = _QuarantineCode('ou_notvalid',
					     'OU not valid from external source')    
    quarantine_ou_remove = _QuarantineCode('ou_remove',
					   'OU is clean and may be removed')

    
    # Navnkonstanter spesifikke for SAP
    name_middle = _PersonNameCode('MIDDLE', 'Middle name')
    name_initials = _PersonNameCode('INITIALS', 'Initials')

    # Kommtypekonstater spesifikke for SAP
    contact_phone_cellular = _ContactInfoCode("CELLPHONE",
                                              "Person's cellular phone")
    contact_phone_cellular_private = _ContactInfoCode(
                                       "PRIVCELLPHONE",
                                       "Person's private cellular phone")

    # Landkonstanter for SAP
    country_no = _CountryCode("NO", "Norway", "47", "Norway")
    country_gb = _CountryCode("GB", "Great Britain", "44", "Great Britain")
    country_fi = _CountryCode("FI", "Finland", "358", "Finland")
    country_se = _CountryCode("SE", "Sweden", "46", "Sweden")
    country_us = _CountryCode("US", "USA", "1", "United states of America")
    country_nl = _CountryCode("NL", "The Netherlands", "31", "The Netherlands")
    country_de = _CountryCode("DE", "Germany", "49", "Germany")
    country_au = _CountryCode("AU", "Australia", "61", "Australia")
    country_dk = _CountryCode("DK", "Denmark", "45", "Denmark")

# end Constants






