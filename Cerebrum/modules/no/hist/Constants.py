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
     _PersonAffiliationCode, _PersonAffStatusCode, _AccountCode
from Cerebrum.modules.PosixUser import _PosixShellCode

class Constants(Constants.Constants):

    externalid_fodselsnr = _PersonExternalIdCode('NO_BIRTHNO',
                                                 'Norwegian birth number')
    externalid_studentnr = _PersonExternalIdCode('NO_STUDNO',
                                                 'Norwegian student number')

    system_fs = _AuthoritativeSystemCode('FS', 'FS')
    system_migrate = _AuthoritativeSystemCode('MIGRATE', 'Migrate from files')

    perspective_fs = _OUPerspectiveCode('FS', 'FS')

# ANSATTE

    affiliation_ansatt = _PersonAffiliationCode('ANSATT','Ansatt ved HiST')
    affiliation_status_ansatt_manuell = _PersonAffStatusCode(
        affiliation_ansatt, 'ansatt', 'Ansatt, manuell import')
    
# STUDENTER
    affiliation_student = _PersonAffiliationCode(
        'STUDENT', 'Student ved HiST (i følge FS)')
    affiliation_status_student_aktiv = _PersonAffStatusCode(
        affiliation_student, 'aktiv', 'Aktiv student')
    affiliation_status_student_valid = _PersonAffStatusCode(
                affiliation_student, 'valid', 'Valid student')
    
# ANDRE
    affiliation_tilknyttet = _PersonAffiliationCode(
        'TILKNYTTET', 'Tilknyttet HiST uten å være student eller ansatt')
    affiliation_status_tilknyttet_AKTIV = _PersonAffStatusCode(
        affiliation_tilknyttet, 'tilknyttet', 'Tilknyttet HiST, men ikke ansatt')

# UPERSONLIGE KONTI
    affiliation_upersonlig = _PersonAffiliationCode(
        'UPERSONLIG', 'Fellesbrukere, samt andre brukere uten eier')
    affiliation_upersonlig_felles = _PersonAffStatusCode(
        affiliation_upersonlig, 'felles', 'Felles konti')
    affiliation_upersonlig_kurs = _PersonAffStatusCode(
        affiliation_upersonlig, 'kurs', 'Kurs konti')
    affiliation_upersonlig_pvare = _PersonAffStatusCode(
        affiliation_upersonlig, 'pvare', 'Programvare konti')
    affiliation_upersonlig_term_maskin = _PersonAffStatusCode(
        affiliation_upersonlig, 'term_maskin', 'Terminalstue maskin')
    affiliation_upersonlig_bib_felles = _PersonAffStatusCode(
        affiliation_upersonlig, 'bib_felles', 'Bibliotek felles')
    affiliation_upersonlig_uio_forening = _PersonAffStatusCode(
        affiliation_upersonlig, 'HiST_forening', 'HiST forening')

    # We override the default settings for shells, thus this file
    # should be before PosixUser in cereconf.CLASS_CONSTANTS

# DEFINISJON AV SHELL 
    posix_shell_bash = _PosixShellCode('bash', '/local/gnu/bin/bash')

# SPREAD DEFINISJONER FRA STUDCONFIG
    spread_HiST_nds_stud_aft= _SpreadCode('nds-stu-aft@hist', Constants.Constants.entity_account, 'Novell system studenter AFT')
    spread_HiST_nds_stud_aft_group= _SpreadCode('nds-s-aft_g@hist', Constants.Constants.entity_group, 'Novell student grupper AFT')
    spread_HiST_nds_stud_aoa= _SpreadCode('nds-stu-aoa@hist', Constants.Constants.entity_account, 'Novell system studenter AØA')
    spread_HiST_nds_stud_aoa_group= _SpreadCode('nds-s-aoa_g@hist', Constants.Constants.entity_group, 'Novell student grupper AØA')
    spread_HiST_AD_stud= _SpreadCode('ad-stud@hist', Constants.Constants.entity_account, 'ActiveDirectory HiST 2003')
    spread_HiST_AD_stud_group= _SpreadCode('ad-s_g@hist', Constants.Constants.entity_group, 'ActiveDirectory student grupper HiST 2003')
    spread_HiST_Hist_epost= _SpreadCode('epost@hist', Constants.Constants.entity_account, 'UNIX epost ansatte')
    spread_HiST_Hist_epost_group= _SpreadCode('epost_g@hist', Constants.Constants.entity_group, 'UNIX epost grupper ansatte')
    spread_HiST_AK_Kalvskinnet = _SpreadCode('AK-Kalvskin@hist', Constants.Constants.entity_person, 'Adgangskontroll AFT/AITeL')
    spread_HiST_AK_Moholt = _SpreadCode('AK-Moholt@hist', Constants.Constants.entity_person, 'Adgangskontroll AØA/HA')
    spread_HiST_AK_Radmann = _SpreadCode('AK-Radmann@hist', Constants.Constants.entity_person, 'Adgangskontroll AHS')
    spread_HiST_AK_Rotvoll = _SpreadCode('AK-Rotvoll@hist', Constants.Constants.entity_person, 'Adgangskontroll ALT')
    



    # LDAP: Brukere, grupper

    # Notes: OU, brukere, ACL-grupper, andre grupper

    # TODO: Kunne begrense tillatte spreads for spesielt priviligerte
    # brukere.

# KARANTENE GRUPPER
    quarantine_generell = _QuarantineCode('generell', 'Generell splatt')
    quarantine_teppe = _QuarantineCode('teppe', 'Kallt inn på teppet til drift')
    quarantine_slutta = _QuarantineCode('slutta', 'Personen har slutta')
    quarantine_system = _QuarantineCode('system', 'Systembrukar som ikke skal logge inn')
    quarantine_permisjon = _QuarantineCode('permisjon', 'Brukeren har permisjon')
    quarantine_svakt_passord = _QuarantineCode('svakt_passord', 'For dårlig passord')
    quarantine_autopassord = _QuarantineCode('autopassord',
                                            'Passord ikke skiftet trass pålegg')
    quarantine_autostud = _QuarantineCode('autostud', 'Ikke aktiv student')
    quarantine_autoekstern = _QuarantineCode('autoekstern',
                                            'Ekstern konto gått ut på dato')
    
    account_test = _AccountCode('T', 'Testkonto')
    
