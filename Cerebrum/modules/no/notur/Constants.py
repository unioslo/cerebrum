# -*- coding: iso-8859-1 -*-
# Copyright 2005-2006 University of Oslo, Norway
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
     _SpreadCode, _QuarantineCode, _EntityExternalIdCode, \
     _PersonAffiliationCode, _PersonAffStatusCode, _AccountCode,_AuthenticationCode
from Cerebrum.modules.PosixUser import _PosixShellCode
from Cerebrum.modules.Hpc import _CpuArchCode, _OperatingSystemCode, \
     _InterConnectCode, _ScienceCode, _AllocationAuthorityCode

class Constants(Constants.Constants):

    science_chemistry = _ScienceCode('Chemistry', 'Chemistry')

    operatingsystem_irix = _OperatingSystemCode('IRIX', "SGI's UNIX")

    interconnect_numa = _InterConnectCode('numa', 'NUMAlink')

    cpuarch_i386 = _CpuArchCode('i386', 'Intel IA32');

    allocationauthority_notur = _AllocationAuthorityCode('notur',
        'forskningsrådet, fordelingsutvalget')

    externalid_fodselsnr = _EntityExternalIdCode('NO_BIRTHNO',
        Constants.Constants.entity_person,
        'Norwegian birth number')

    externalid_feideid = _EntityExternalIdCode('FEIDEID',
        Constants.Constants.entity_person,
        'Feide name')

    system_feide = _AuthoritativeSystemCode('Feide', 'Feide')
    perspective_feide = _OUPerspectiveCode('Feide', 'Feide')

    account_test = _AccountCode('testbruker', 'Testkonto')
    account_kurs = _AccountCode('kursbruker','Kurskonto')

    affiliation_ansatt = _PersonAffiliationCode('ANSATT',
                                                'Ansatt ved primærinstitusjonen')
    affiliation_status_ansatt_vit = _PersonAffStatusCode(
        affiliation_ansatt, 'vitenskapelig', 'Vitenskapelig ansatt')
    affiliation_status_ansatt_tekadm = _PersonAffStatusCode(
        affiliation_ansatt, 'tekadm', 'Teknisk/administrativt ansatt')

    affiliation_student = _PersonAffiliationCode(
        'STUDENT', 'Student')
    affiliation_status_student_aktiv = _PersonAffStatusCode(
        affiliation_student, 'aktiv', 'Aktiv student')
    affiliation_status_student_drgrad = _PersonAffStatusCode(
        affiliation_student, 'drgrad', 'Registrert student på doktorgrad')

    affiliation_tilknyttet = _PersonAffiliationCode(
        'TILKNYTTET', 'Tilknyttet primærinstitusjonen uten å være ansatt eller student')

    affiliation_manuell = _PersonAffiliationCode(
        'MANUELL', 'Andre tilknytninger')
    affiliation_manuell_annen = _PersonAffStatusCode(
        affiliation_manuell, 'annen', 'Annen tilknytning (Husk kommentar)')

    affiliation_upersonlig = _PersonAffiliationCode(
        'UPERSONLIG', 'Fellesbrukere, samt andre brukere uten eier')
    affiliation_upersonlig_felles = _PersonAffStatusCode(
        affiliation_upersonlig, 'felles', 'Felleskonti')
    affiliation_upersonlig_kurs = _PersonAffStatusCode(
        affiliation_upersonlig, 'kurs', 'Kurskonti')
    affiliation_upersonlig_pvare = _PersonAffStatusCode(
        affiliation_upersonlig, 'pvare', 'Programvarekonti')

    # We override the default settings for shells, thus this file
    # should be before PosixUser in cereconf.CLASS_CONSTANTS

    posix_shell_bash = _PosixShellCode('bash', '/bin/bash')
    posix_shell_tcsh = _PosixShellCode('tcsh', '/bin/tcsh')

    #Old BDB-stuff goes here
    posix_shell_false = _PosixShellCode('true', '/bin/true')
    posix_shell_false = _PosixShellCode('false', '/bin/false')
    posix_shell_sperret = _PosixShellCode('sperret', '/bin/sperret')
    posix_shell_sperret = _PosixShellCode('badpw', '/bin/badpw')


    spread_gridur_nis_user = _SpreadCode('NIS_user@gridur', Constants.Constants.entity_account,
                                         'User on system "gridur"')
    spread_gridur_nis_fg = _SpreadCode('NIS_fg@gridur', Constants.Constants.entity_account,
                                         'File group on system "gridur"')
    spread_tre_nis_user = _SpreadCode('NIS_user@tre', Constants.Constants.entity_account,
                                         'User on system "tre"')
    spread_tre_nis_fg = _SpreadCode('NIS_fg@tre', Constants.Constants.entity_account,
                                         'File group on system "tre"')
    spread_magnum_nis_user = _SpreadCode('NIS_user@magnum', Constants.Constants.entity_account,
                                         'User on system "magnum"')
    spread_magnum_nis_fg = _SpreadCode('NIS_fg@magnum', Constants.Constants.entity_account,
                                         'File group on system "magnum"')
    

    quarantine_generell = _QuarantineCode('generell', 'Generell splatt')
    quarantine_teppe = _QuarantineCode('teppe', 'Kallt inn på teppet til drift')
    quarantine_slutta = _QuarantineCode('slutta', 'Personen har slutta')
    quarantine_system = _QuarantineCode('system', 'Systembrukar som ikke skal logge inn')
    quarantine_permisjon = _QuarantineCode('permisjon', 'Brukeren har permisjon')
    quarantine_svakt_passord = _QuarantineCode('svakt_passord', 'For dårlig passord')

# arch-tag: 672f7902-9d38-11da-886a-76f0d5251865
