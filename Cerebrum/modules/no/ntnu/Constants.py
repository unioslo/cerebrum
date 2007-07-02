# -*- coding: iso-8859-1 -*-
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
     _SpreadCode, _QuarantineCode, _EntityExternalIdCode, \
     _PersonAffiliationCode, _PersonAffStatusCode, _AccountCode, \
     _AuthenticationCode, _PersonNameCode
from Cerebrum.modules.PosixUser import _PosixShellCode
from Cerebrum.modules.Email import \
     _EmailSpamLevelCode, _EmailSpamActionCode, _EmailDomainCategoryCode
from Cerebrum.modules.EntityTrait import \
     _EntityTraitCode

class Constants(Constants.Constants):

    name_display = _PersonNameCode('DISPLAY', 'Display name')

    trait_guest_owner = _EntityTraitCode(
        'guest_owner', Constants.Constants.entity_account,
        "When a guest account is requested a group must be set as "
        "owner for the account for the given time.")

    trait_group_owner = _EntityTraitCode(
        'group_owner', Constants.Constants.entity_group,
        "Owner of an user administered group")

    trait_reserve_publish = _EntityTraitCode(
        'reserve_publish', Constants.Constants.entity_person,
        "Persons reserved from anonymous lookups")

    trait_host_owner = _EntityTraitCode(
        'host_owner', Constants.Constants.entity_host,
        "Owner of a host")
        
    externalid_fodselsnr = _EntityExternalIdCode('NO_BIRTHNO',
        Constants.Constants.entity_person,
        'Norwegian birth number')

    externalid_bdb_person = _EntityExternalIdCode('BDB_PERSON_ID',
        Constants.Constants.entity_person,
        'BDBs internal ID for the person')

    externalid_bdb_group = _EntityExternalIdCode('BDB_GROUP_ID',
        Constants.Constants.entity_group,
        'BDBs internal ID for the group')

    externalid_bdb_account = _EntityExternalIdCode('BDB_ACCOUNT_ID',
        Constants.Constants.entity_account,
        'BDBs internal ID for the account')

    externalid_bdb_institute = _EntityExternalIdCode('BDB_INSTITUTE_ID',
        Constants.Constants.entity_ou,
        'BDBs internal ID for the institute')

    externalid_bdb_faculty = _EntityExternalIdCode('BDB_FACULTY_ID',
        Constants.Constants.entity_ou,
        'BDBs internal ID for the faculty')

    system_lt = _AuthoritativeSystemCode('Kjernen', 'Kjernen')
    system_kjernen = _AuthoritativeSystemCode('Kjernen', 'Kjernen')
    perspective_kjernen = _OUPerspectiveCode('Kjernen', 'Kjernen')
    system_fs = _AuthoritativeSystemCode('FS', 'FS')
    perspective_fs = _OUPerspectiveCode('FS', 'FS')
    system_bdb = _AuthoritativeSystemCode('BDB', 'NTNUs old user database')
    perspective_bdb = _OUPerspectiveCode('BDB', 'NTNUs old user database')
    perspective_slp4 = _OUPerspectiveCode('SLP4', 'SLP4')

    account_test = _AccountCode('testbruker', 'Testkonto')
    account_kurs = _AccountCode('kursbruker','Kurskonto')

    auth_type_md4_nt =  _AuthenticationCode('MD4-NT',
        "MD4-derived password hash with Microsoft-added security.")
    auth_type_pgp_offline =  _AuthenticationCode('PGP-offline',
        "PGP encrypted password for offline use") # XXX use PGP-crypt?
    auth_type_pgp_win_ntnu_no =  _AuthenticationCode('PGP-win_ntnu_no',
        "PGP encrypted password for the system win_ntnu_no")
    auth_type_blowfish =  _AuthenticationCode('Blowfish',
        "Blowfish-encrypted password")
    auth_type_ssha = _AuthenticationCode('SSHA', "A salted SHA1-encrypted password. More info in RFC 2307 and at <URL:http://www.openldap.org/faq/data/cache/347.html>")
    

    affiliation_ansatt = _PersonAffiliationCode(
        'ANSATT', 'Ansatt ved NTNU (i følge Kjernen)')
    affiliation_status_ansatt_ansatt = _PersonAffStatusCode(
        affiliation_ansatt, 'ansatt', 'Ansatt, type ukjent')
    affiliation_status_ansatt_vit = _PersonAffStatusCode(
        affiliation_ansatt, 'vitenskapelig', 'Vitenskapelig ansatt')
    affiliation_status_ansatt_tekadm = _PersonAffStatusCode(
        affiliation_ansatt, 'tekadm', 'Teknisk/administrativt ansatt')

    affiliation_student = _PersonAffiliationCode(
        'STUDENT', 'Student ved NTNU (i følge FS)')
    affiliation_status_student_student = _PersonAffStatusCode(
        affiliation_student, 'student', 'Aktiv student, ukjent grad')
    affiliation_status_student_bachelor = _PersonAffStatusCode(
        affiliation_student, 'bachelor', 'Aktiv student på lavere grad')
    affiliation_status_student_aktiv = _PersonAffStatusCode(
        affiliation_student, 'master', 'Aktiv student på høyere grad')
    affiliation_status_student_drgrad = _PersonAffStatusCode(
        affiliation_student, 'drgrad', 'Registrert student på doktorgrad')

    affiliation_tilknyttet = _PersonAffiliationCode(
        'TILKNYTTET', 'Tilknyttet NTNU uten å være student eller ansatt')
    affiliation_status_tilknyttet_fagperson = _PersonAffStatusCode(
        affiliation_tilknyttet, 'fagperson', 'Registrert som fagperson i FS')
    affiliation_status_tilknyttet_bilag = _PersonAffStatusCode(
        affiliation_tilknyttet, 'bilag',
        'Registrert i Kjernen med "timelønnet"')
    affiliation_status_tilknyttet_alumni = _PersonAffStatusCode(
        affiliation_tilknyttet, 'alumni', 'Registert alumni')
    affiliation_status_tilknyttet_annen = _PersonAffStatusCode(
        affiliation_tilknyttet, 'annen', 'Annen tilknytning (Husk kommentar)')

    affiliation_alumni = _PersonAffiliationCode(
        'ALUMNI', 'Tidligere student')
    affiliation_status_alumni_aktiv = _PersonAffStatusCode(
        affiliation_alumni, 'aktiv', 'Registert alumni')

    #affiliation_upersonlig = _PersonAffiliationCode(
    #    'UPERSONLIG', 'Fellesbrukere, samt andre brukere uten eier')
    #affiliation_upersonlig_felles = _PersonAffStatusCode(
    #    affiliation_upersonlig, 'felles', 'Felleskonti')
    #affiliation_upersonlig_kurs = _PersonAffStatusCode(
    #    affiliation_upersonlig, 'kurs', 'Kurskonti')
    #affiliation_upersonlig_pvare = _PersonAffStatusCode(
    #    affiliation_upersonlig, 'pvare', 'Programvarekonti')
    #affiliation_upersonlig_term_maskin = _PersonAffStatusCode(
    #    affiliation_upersonlig, 'bib_felles', 'Bibliotek felles')

    # We override the default settings for shells, thus this file
    # should be before PosixUser in cereconf.CLASS_CONSTANTS

    posix_shell_bash = _PosixShellCode('bash', '/bin/bash')
    posix_shell_tcsh = _PosixShellCode('tcsh', '/bin/tcsh')
    posix_shell_csh = _PosixShellCode('csh', '/bin/csh')
    posix_shell_ksh = _PosixShellCode('ksh', '/bin/ksh')
    posix_shell_zsh = _PosixShellCode('zsh', '/bin/zsh')
    posix_shell_sh = _PosixShellCode('sh', '/bin/sh')

    #Old BDB-stuff goes here
    posix_shell_false = _PosixShellCode('true', '/bin/true')
    posix_shell_false = _PosixShellCode('false', '/bin/false')
    posix_shell_sperret = _PosixShellCode('sperret', '/bin/sperret')
    posix_shell_sperret = _PosixShellCode('badpw', '/bin/badpw')



    # All BDB "systems" with local home-disks goes here
    spread_ntnu_ansatt_user = _SpreadCode('user@ansatt', Constants.Constants.entity_account,
                                          'User on system "ansatt"')
    spread_ntnu_chembio_user = _SpreadCode('user@chembio', Constants.Constants.entity_account,
                                           'User on system "chembio"')
    spread_ntnu_fender_user = _SpreadCode('user@fender', Constants.Constants.entity_account,
                                           'User on system "fender" (Q2S)')
    spread_ntnu_fysmat_user = _SpreadCode('user@fysmat', Constants.Constants.entity_account,
                                           'User on system "fysmat" (NT)')
    spread_ntnu_hf_user = _SpreadCode('user@hf', Constants.Constants.entity_account,
                                           'User on system "hf"')
    spread_ntnu_idi_user = _SpreadCode('user@idi', Constants.Constants.entity_account,
                                           'User on system "idi"')
    spread_ntnu_ime_user = _SpreadCode('user@ime', Constants.Constants.entity_account,
                                           'User on system "ime"')
    spread_ntnu_iptansatt_user = _SpreadCode('user@iptansatt', Constants.Constants.entity_account,
                                           'User on system "iptansatt" (IVT)')
    spread_ntnu_ivt_user = _SpreadCode('user@ivt', Constants.Constants.entity_account,
                                           'User on system "ivt"')
    spread_ntnu_kybernetikk_user = _SpreadCode('user@kybernetikk', Constants.Constants.entity_account,
                                           'User on system "kybernetikk" (IME)')
    spread_ntnu_math_user = _SpreadCode('user@math', Constants.Constants.entity_account,
                                           'User on system "math" (IME)')
    spread_ntnu_norgrid_user = _SpreadCode('user@norgrid', Constants.Constants.entity_account,
                                           'User on system "norgrid" (ITEA)')
    spread_ntnu_ntnu_ad_user = _SpreadCode('user@ntnu_ad', Constants.Constants.entity_account,
                                           'User on system "ntnu_ad"')
    spread_ntnu_odin_user = _SpreadCode('user@odin', Constants.Constants.entity_account,
                                           'User on system "odin" (IVT)')
    spread_ntnu_petra_user = _SpreadCode('user@petra', Constants.Constants.entity_account,
                                           'User on system "petra"')
    spread_ntnu_q2s_user = _SpreadCode('user@q2s', Constants.Constants.entity_account,
                                           'User on system "q2s"')
    spread_ntnu_samson_user = _SpreadCode('user@samson', Constants.Constants.entity_account,
                                           'User on system "samson" (IME)')
    spread_ntnu_sol_user = _SpreadCode('user@sol', Constants.Constants.entity_account,
                                           'User on system "sol" (SVT)')
    spread_ntnu_stud_user = _SpreadCode('user@stud', Constants.Constants.entity_account,
                                           'User on system "stud"')
    spread_ntnu_studmath_user = _SpreadCode('user@studmath', Constants.Constants.entity_account,
                                           'User on system "studmath" (IME)')
    spread_ntnu_ubit_user = _SpreadCode('user@ubit', Constants.Constants.entity_account,
                                           'User on system "ubit"')
    spread_ntnu_ansoppr_user = _SpreadCode('user@ansoppr' , Constants.Constants.entity_account,
                                            'User on system "ansoppr"')
    spread_ntnu_oppringt_user = _SpreadCode('user@oppringt' , Constants.Constants.entity_account,
                                            'User on system "oppringt"')
    spread_ntnu_cyrus_imap_user = _SpreadCode('user@cyrus_imap' , Constants.Constants.entity_account,
                                            'User on system "cyrus_imap"')
    spread_ntnu_test1_user = _SpreadCode('user@test1' , Constants.Constants.entity_account,
                                            'User on system "test1"')
    spread_ntnu_test2_user = _SpreadCode('user@test2' , Constants.Constants.entity_account,
                                            'User on system "test2"')
    spread_ntnu_nav_user = _SpreadCode('user@nav' , Constants.Constants.entity_account,
                                            'User on system "nav"')
    spread_ntnu_itil_cm_user = _SpreadCode('user@itil_cm' , Constants.Constants.entity_account,
                                            'User on system "itil_cm"')
    spread_ntnu_lisens_user = _SpreadCode('user@lisens' , Constants.Constants.entity_account,
                                            'User on system "lisens"')
    spread_ntnu_kalender_user = _SpreadCode('user@kalender' , Constants.Constants.entity_account,
                                            'User on system "kalender"')
    spread_ntnu_vm_user = _SpreadCode('user@vm' , Constants.Constants.entity_account,
                                            'User on system "vm"')
    spread_ntnu_itea_user = _SpreadCode('user@itea' , Constants.Constants.entity_account,
                                            'User on system "itea"')
    spread_ntnu_pride_user = _SpreadCode('user@pride' , Constants.Constants.entity_account,
                                            'User on system "pride"')
    spread_ntnu_hflinux_user = _SpreadCode('user@hflinux' , Constants.Constants.entity_account,
                                            'User on system "hflinux"')
    spread_ntnu_ipt_soil_user = _SpreadCode('user@ipt_soil' , Constants.Constants.entity_account,
                                            'User on system "ipt_soil"')
    spread_ntnu_kerberos_user = _SpreadCode('user@kerberos' , Constants.Constants.entity_account,
                                            'User on system "kerberos"')

    spread_ntnu_group = _SpreadCode('group@ntnu', Constants.Constants.entity_group,
                                    'File group at NTNU')
    spread_ntnu_netgroup = _SpreadCode('netgroup@ntnu', Constants.Constants.entity_group,
                                    'Netgroup at NTNU')



    quarantine_generell = _QuarantineCode('generell', 'Generell splatt')
    quarantine_remote = _QuarantineCode('remote', 'Oppringt og VPN')
    quarantine_teppe = _QuarantineCode('teppe', 'Kallt inn på teppet til drift')
    quarantine_slutta = _QuarantineCode('slutta', 'Personen har slutta')
    quarantine_system = _QuarantineCode('system', 'Systembrukar som ikke skal logge inn')
    quarantine_permisjon = _QuarantineCode('permisjon', 'Brukeren har permisjon')
    quarantine_svakt_passord = _QuarantineCode('svakt_passord', 'For dårlig passord')

    quarantine_bdb = _QuarantineCode('BDB', 'Gammel BDB-karantene /bin/sperret+/bin/true+/bin/false')
    #quarantine_badpw = _QuarantineCode('BDB_badpw', 'Gammel BDB karantene /bin/badpw')

    email_spam_level_none = _EmailSpamLevelCode(
        'ingen', 9999, "No email will be filtered as spam")
    email_spam_level_medium = _EmailSpamLevelCode(
        'medium', 12, "Only filter email that obviously is spam")
    email_spam_level_heightened = _EmailSpamLevelCode(
        'strengt', 8, "Filter most emails that look like spam ")
    email_spam_level_aggressive = _EmailSpamLevelCode(
        'veldig strengt', 5, "Filter everything that resembles spam")

    #email_spam_action_none = _EmailSpamActionCode(
    #    'noaction', "Deliver spam just like legitimate email")
    #email_spam_action_folder = _EmailSpamActionCode(
    #    'spamfolder', "Deliver spam to a separate IMAP folder")
    email_spam_action_delete = _EmailSpamActionCode(
        'dropspam', "Messages classified as spam won't be delivered at all")

# arch-tag: e25e35ae-30f6-11da-9180-bcf822108a14
