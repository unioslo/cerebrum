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
    system_migrate = _AuthoritativeSystemCode('MIGRATE', 'Migrate from files')
    system_sap = _AuthoritativeSystemCode('SAP', 'SAP')

    perspective_fs = _OUPerspectiveCode('FS', 'FS')

    account_test = _AccountCode('testbruker', 'Testkonto')
    account_kurs = _AccountCode('kursbruker','Kurskonto')

# ANSATTE

    affiliation_ansatt = _PersonAffiliationCode('ANSATT','Ansatt ved HiA')
    affiliation_status_ansatt_manuell = _PersonAffStatusCode(
        affiliation_ansatt, 'manuell', 'Ansatt, manuell import')
    affiliation_status_ansatt_vitenskapelig = _PersonAffStatusCode(
        affiliation_ansatt, 'vitenskapelig', 'Ansatt, vitenskapelige ansatte')
    affiliation_status_ansatt_tekadm = _PersonAffStatusCode(
        affiliation_ansatt, 'tekadm', 'Tekniske/administrative ansatte')
    affiliation_status_ansatt_primaer = _PersonAffStatusCode(
        affiliation_ansatt, 'primær', 'Primærtilknytning for SAP ansatte')
    
# STUDENTER
    affiliation_student = _PersonAffiliationCode(
        'STUDENT', 'Student ved HiA (i følge FS)')
    affiliation_status_student_manuell = _PersonAffStatusCode(
	affiliation_student, 'student', 'Student, manuell import')

    # We override the default settings for shells, thus this file
    # should be before PosixUser in cereconf.CLASS_CONSTANTS

# DEFINISJON AV SHELL 
    posix_shell_bash = _PosixShellCode('bash', '/local/gnu/bin/bash')

# SPREAD DEFINISJONER
    spread_hia_novell_user = _SpreadCode('NOVELL_user@hia', Constants.Constants.entity_account,
					 'User in Novell domain "hia"')
    spread_hia_novell_group = _SpreadCode('NOVELL_group@hia', Constants.Constants.entity_group,
					 'Group in Novell domain "hia"')
    spread_stud_nis_user = _SpreadCode('NIS_user@stud', Constants.Constants.entity_account,
					 'User in NIS domain "stud"')
    spread_ans_nis_user = _SpreadCode('NIS_user@ans', Constants.Constants.entity_account,
					 'User in NIS domain "ans"')
    spread_stud_nis_fg = _SpreadCode('NIS_fg@stud', Constants.Constants.entity_group,
                                    'File group in NIS domain "stud"')
    spread_stud_nis_ng = _SpreadCode('NIS_ng@stud', Constants.Constants.entity_group,
                                    'Net group in NIS domain "stud"')
    spread_ans_nis_fg = _SpreadCode('NIS_fg@ans', Constants.Constants.entity_group,
                                    'File group in NIS domain "ans"')
    spread_ans_nis_ng = _SpreadCode('NIS_ng@ans', Constants.Constants.entity_group,
                                    'Net group in NIS domain "ans"')
    spread_hia_adgang = _SpreadCode('Adgang@hia', Constants.Constants.entity_person,
				    'Person exported to Adgang system')
    spread_hia_email = _SpreadCode('EMAIL@hia', Constants.Constants.entity_account,
				   'Email user at HiA')
    spread_hia_bibsys = _SpreadCode('BIBSYS@hia', Constants.Constants.entity_person,
				    'Person exported to BIBSYS')
    spread_hia_tele = _SpreadCode('TELE@hia', Constants.Constants.entity_person,
				  'Person exported to phone system')
    spread_hia_ldap_person = _SpreadCode('LDAP_person', Constants.Constants.entity_person, 
					 'Person included in LDAP directory')
    spread_hia_ldap_ou = _SpreadCode('LDAP_OU', Constants.Constants.entity_ou,
                                     'OU included in LDAP directory')
    spread_hia_helpdesk = _SpreadCode('HELPDESK@uio', Constants.Constants.entity_account, 
				      'Account exported to helpdesk system')
    spread_hia_ad_account = _SpreadCode('AD_account', Constants.Constants.entity_account,
					'Account included in Active Directory')
    spread_hia_ad_group = _SpreadCode('AD_group', Constants.Constants.entity_group,
				      'group included in Active Directory')   

    spread_hia_fronter = _SpreadCode('CF@hia', Constants.Constants.entity_group,
				     '''Group representing a course \
				     that should be exported to the ClassFronter.\
				     Should only be given to groups that have been \
				     automatically generated from FS.''')  

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






