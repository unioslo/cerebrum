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
     _SpreadCode, _QuarantineCode, _PersonExternalIdCode, \
     _PersonAffiliationCode, _PersonAffStatusCode, _AccountCode
from Cerebrum.modules.PosixUser import _PosixShellCode
from Cerebrum.modules.Email import \
     _EmailSpamLevelCode, _EmailSpamActionCode, _EmailDomainCategoryCode

class Constants(Constants.Constants):

    externalid_fodselsnr = _PersonExternalIdCode('NO_BIRTHNO',
                                                 'Norwegian birth number')

    system_lt = _AuthoritativeSystemCode('LT', 'LT')
    system_fs = _AuthoritativeSystemCode('FS', 'FS')
    system_ureg = _AuthoritativeSystemCode('Ureg', 'Imported from ureg')

    perspective_lt = _OUPerspectiveCode('LT', 'LT')
    perspective_fs = _OUPerspectiveCode('FS', 'FS')

    account_test = _AccountCode('testbruker', 'Testkonto')
    account_kurs = _AccountCode('kursbruker','Kurskonto')

    affiliation_ansatt = _PersonAffiliationCode('ANSATT',
                                                'Ansatt ved UiO (i følge LT)')
    affiliation_status_ansatt_vit = _PersonAffStatusCode(
        affiliation_ansatt, 'vitenskapelig', 'Vitenskapelig ansatt')
    affiliation_status_ansatt_bil = _PersonAffStatusCode(
        affiliation_ansatt, 'bilag', 'Bilagslønnet')
    affiliation_status_ansatt_tekadm = _PersonAffStatusCode(
        affiliation_ansatt, 'tekadm', 'Teknisk/administrativt ansatt')
    affiliation_status_ansatt_perm = _PersonAffStatusCode(
        affiliation_ansatt, 'permisjon', 'Ansatt, men med aktiv permisjon')

    affiliation_student = _PersonAffiliationCode(
        'STUDENT', 'Student ved UiO (i følge FS)')
    affiliation_status_student_soker = _PersonAffStatusCode(
        affiliation_student, 'soker', 'Registrert søker i FS')
    affiliation_status_student_tilbud = _PersonAffStatusCode(
        affiliation_student, 'tilbud', 'Har fått tilbud om opptak')
    affiliation_status_student_opptak = _PersonAffStatusCode(
        affiliation_student, 'opptak', 'Har studierett ved studieprogram')
    affiliation_status_student_aktiv = _PersonAffStatusCode(
        affiliation_student, 'aktiv', 'Aktiv student')
    affiliation_status_student_privatist = _PersonAffStatusCode(
        affiliation_student, 'privatist', 'Registrert som privatist i FS')
    affiliation_status_student_evu = _PersonAffStatusCode(
        affiliation_student, 'evu', 'Registrert som EVU-student i FS')
    affiliation_status_student_perm = _PersonAffStatusCode(
        affiliation_student, 'permisjon', 'Har gyldig permisjonstatus i FS')
    affiliation_status_student_alumni = _PersonAffStatusCode(
        affiliation_student, 'alumni', 'Har fullført studieprogram i FS')

    affiliation_tilknyttet = _PersonAffiliationCode(
        'TILKNYTTET', 'Tilknyttet UiO uten å være student eller ansatt')
    affiliation_tilknyttet_fagperson = _PersonAffStatusCode(
        affiliation_tilknyttet, 'fagperson', 'Registrert som fagperson i FS')
    affiliation_tilknyttet_emeritus = _PersonAffStatusCode(
        affiliation_tilknyttet, 'emeritus',
        'Registrert i LT med gjestetypekode EMERITUS')
    affiliation_tilknyttet_ekst_stip = _PersonAffStatusCode(
        affiliation_tilknyttet, 'ekst_stip',
        'Personer registrert i LT med gjestetypekode=EF-STIP')

    affiliation_manuell = _PersonAffiliationCode(
        'MANUELL', 'Tilknyttet enheter/instutusjoner som USIT har avtale med')
    affiliation_manuell_sio = _PersonAffStatusCode(
        affiliation_manuell, 'sio', 'SiO')
    affiliation_manuell_radium = _PersonAffStatusCode(
        affiliation_manuell, 'radium', 'Det norske radiumhospital')
    affiliation_manuell_rikshospital = _PersonAffStatusCode(
        affiliation_manuell, 'rikshospital', 'Rikshospitalet')
    affiliation_manuell_ulleval = _PersonAffStatusCode(
        affiliation_manuell, 'ulleval', 'Ullevål')
    affiliation_manuell_ahus = _PersonAffStatusCode(
        affiliation_manuell, 'ahus', 'Ahus')
    affiliation_manuell_notam2 = _PersonAffStatusCode(
        affiliation_manuell, 'notam2', 'Notam2')
    affiliation_manuell_biotek = _PersonAffStatusCode(
        affiliation_manuell, 'biotek', 'The Biotechnology Centre of Oslo')
    affiliation_manuell_cicero = _PersonAffStatusCode(
        affiliation_manuell, 'cicero', 'Cicero')
    affiliation_manuell_simula = _PersonAffStatusCode(
        affiliation_manuell, 'simula', "Simula Research Laboratory")
    affiliation_manuell_notur = _PersonAffStatusCode(
        affiliation_manuell, 'notur', 'Notur')
    affiliation_manuell_gjest = _PersonAffStatusCode(
        affiliation_manuell, 'gjest', 'Gjest')
    affiliation_manuell_ekst_person = _PersonAffStatusCode(
        affiliation_manuell, 'ekst_person',
        'Ekstern person (under utfasing)')
    affiliation_manuell_spes_avt = _PersonAffStatusCode(
        affiliation_manuell, 'spes_avt',
        'Spesialavtale (under utfasing)')
    affiliation_manuell_gjesteforsker = _PersonAffStatusCode(
        affiliation_manuell, 'gjesteforsker',
        'Gjesteforsker (under utfasing)')
    affiliation_manuell_sivilarb = _PersonAffStatusCode(
        affiliation_manuell, 'sivilarb',
        'Sivilarbeider (under utfasing)')
    affiliation_manuell_kaja_kontrakt = _PersonAffStatusCode(
        affiliation_manuell, 'kaja_kontrakt',
        'Kaja kontrakt (under utfasing)')
    affiliation_manuell_konsulent = _PersonAffStatusCode(
        affiliation_manuell, 'konsulent',
        'Konsulent (under utfasing)')
    affiliation_manuell_inaktiv_student = _PersonAffStatusCode(
        affiliation_manuell, 'inaktiv_student',
        'Ikke-student med studentkonto i Ureg2000 (under utfasing)')
    affiliation_manuell_inaktiv_ansatt = _PersonAffStatusCode(
        affiliation_manuell, 'inaktiv_ansatt',
        'Presumptivt ansatt uten noen registrering i LT')

    affiliation_upersonlig = _PersonAffiliationCode(
        'UPERSONLIG', 'Fellesbrukere, samt andre brukere uten eier')
    affiliation_upersonlig_felles = _PersonAffStatusCode(
        affiliation_upersonlig, 'felles', 'Felleskonti')
    affiliation_upersonlig_kurs = _PersonAffStatusCode(
        affiliation_upersonlig, 'kurs', 'Kurskonti')
    affiliation_upersonlig_pvare = _PersonAffStatusCode(
        affiliation_upersonlig, 'pvare', 'Programvarekonti')
    affiliation_upersonlig_term_maskin = _PersonAffStatusCode(
        affiliation_upersonlig, 'term_maskin', 'Terminalstuemaskin')
    affiliation_upersonlig_bib_felles = _PersonAffStatusCode(
        affiliation_upersonlig, 'bib_felles', 'Bibliotek felles')
    affiliation_upersonlig_uio_forening = _PersonAffStatusCode(
        affiliation_upersonlig, 'uio_forening', 'Forening ved UiO')

    # We override the default settings for shells, thus this file
    # should be before PosixUser in cereconf.CLASS_CONSTANTS

    posix_shell_bash = _PosixShellCode('bash', '/local/gnu/bin/bash')
    posix_shell_csh = _PosixShellCode('csh', '/bin/csh')
    posix_shell_false = _PosixShellCode('false', '/bin/false')
    posix_shell_ksh = _PosixShellCode('ksh', '/bin/ksh')
    posix_shell_ma104 = _PosixShellCode('ma104', '/local/bin/ma104')
    posix_shell_nologin = _PosixShellCode('nologin', '/local/etc/nologin')
    posix_shell_nologin_autostud = _PosixShellCode('nologin.autostud',
                                                   '/local/etc/shells/nologin.autostud')
    posix_shell_nologin_brk = _PosixShellCode('nologin.brk',
                                              '/local/etc/shells/nologin.brk')
    posix_shell_nologin_chpwd = _PosixShellCode('nologin.chpwd',
                                                '/local/etc/shells/nologin.chpwd')
    posix_shell_nologin_ftpuser = _PosixShellCode('nologin.ftpuser',
                                                  '/local/etc/shells/nologin.ftpuser')
    posix_shell_nologin_nystudent = _PosixShellCode('nologin.nystuden',
                                                    '/local/etc/shells/nologin.nystudent')
    posix_shell_nologin_permisjon = _PosixShellCode('nologin.permisjo',
                                                    '/local/etc/shells/nologin.permisjon')
    posix_shell_nologin_pwd = _PosixShellCode('nologin.pwd',
                                              '/local/etc/shells/nologin.pwd')
    posix_shell_nologin_sh = _PosixShellCode('nologin.sh',
                                             '/local/etc/shells/nologin.sh')
    posix_shell_nologin_sluttet = _PosixShellCode('nologin.sluttet',
                                                  '/local/etc/shells/nologin.sluttet')
    posix_shell_nologin_stengt = _PosixShellCode('nologin.stengt',
                                                 '/local/etc/shells/nologin.stengt')
    posix_shell_nologin_teppe = _PosixShellCode('nologin.teppe',
                                                '/local/etc/shells/nologin.teppe')
    posix_shell_puberos = _PosixShellCode('puberos', '/local/bin/puberos')
    posix_shell_pwsh = _PosixShellCode('pwsh', '/etc/pw/sh')
    posix_shell_sftp_server = _PosixShellCode('sftp-server',
                                              '/local/openssh/libexec/sftp-server')
    posix_shell_sh = _PosixShellCode('sh', '/bin/sh')
    posix_shell_simonshell = _PosixShellCode('simonshell',
                                             '/hom/simon/simonshell')
    posix_shell_sync = _PosixShellCode('sync', '/bin/sync')
    posix_shell_tcsh = _PosixShellCode('tcsh', '/local/bin/tcsh')
    posix_shell_true = _PosixShellCode('true', '/bin/true')
    posix_shell_zsh = _PosixShellCode('zsh', '/local/bin/zsh')

    spread_uio_nis_user = _SpreadCode('NIS_user@uio', Constants.Constants.entity_account,
                                      'User in NIS domain "uio"')
    spread_uio_nis_fg = _SpreadCode('NIS_fg@uio', Constants.Constants.entity_group,
                                    'File group in NIS domain "uio"')
    spread_uio_nis_ng = _SpreadCode('NIS_ng@uio', Constants.Constants.entity_group,
                                    'Net group in NIS domain "uio"')
    spread_ifi_nis_user = _SpreadCode('NIS_user@ifi', Constants.Constants.entity_account,
                                      'User in NIS domain "ifi"')
    spread_ifi_nis_fg = _SpreadCode('NIS_fg@ifi', Constants.Constants.entity_group,
                                    'File group in NIS domain "ifi"')
    spread_ifi_nis_ng = _SpreadCode('NIS_ng@ifi', Constants.Constants.entity_group,
                                    'Net group in NIS domain "ifi"')
    spread_uio_ldap_person = _SpreadCode('LDAP_person', Constants.Constants.entity_person,
                                         'Person included in LDAP directory')
    spread_uio_ldap_ou = _SpreadCode('LDAP_OU', Constants.Constants.entity_ou,
                                     'OU included in LDAP directory')
    spread_uio_ad_account = _SpreadCode('AD_account', Constants.Constants.entity_account,'account included in Active Directory')
    spread_uio_ad_group = _SpreadCode('AD_group', Constants.Constants.entity_group,'group included in Active Directory')
    spread_uio_ua = _SpreadCode('UA@uio', Constants.Constants.entity_person,
                                'Person exported to UA')
    spread_uio_imap = _SpreadCode('IMAP@uio', Constants.Constants.entity_account,
                                  'IMAP account')
    spread_uio_notes_account = _SpreadCode('Notes_user', Constants.Constants.entity_account,
                                           'Account exported to Notes')

    # LDAP: Brukere, grupper

    # Notes: OU, brukere, ACL-grupper, andre grupper


    # TODO: Kunne begrense tillatte spreads for spesielt priviligerte
    # brukere.

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
    quarantine_autointsomm = _QuarantineCode('autointsomm',
                                            'Sommerskolen er ferdig for i år')
    quarantine_nologin = _QuarantineCode('nologin', 'Gammel ureg karantene nologin')
    quarantine_nologin_brk = _QuarantineCode('nologin_brk',
                                             'Gammel ureg karantene nologin_brk')
    quarantine_nologin_ftpuser = _QuarantineCode('nologin_ftpuser',
                                                 'Gammel ureg karantene nologin_ftpuser')
    quarantine_nologin_nystudent = _QuarantineCode('nologin_nystuden',
                                                   'Gammel ureg karantene nologin_nystudent')
    quarantine_nologin_sh = _QuarantineCode('nologin_sh',
                                            'Gammel ureg karantene nologin_sh')
    quarantine_nologin_stengt = _QuarantineCode('nologin_stengt',
                                                'Gammel ureg karantene nologin_stengt')

    email_domain_category_uio_globals = _EmailDomainCategoryCode(
        'UIO_GLOBALS',
        "All local_parts defined in domain 'UIO_GLOBALS' are treated"
        " as overrides for all domains posessing this category.")
    email_spam_level_none = _EmailSpamLevelCode(
        'no_filter', 9999, "No email will be filtered as spam")
    email_spam_level_standard = _EmailSpamLevelCode(
        'standard_spam', 20, "Only filter email that obviously is spam")
    email_spam_level_heightened = _EmailSpamLevelCode(
        'most_spam', 12, "Filter most emails that looks like spam ")
    email_spam_level_aggressive = _EmailSpamLevelCode(
        'aggressive_spam', 6, "Filter everything that resembles spam")
    email_spam_action_none = _EmailSpamActionCode(
        'noaction', "Deliver spam just like legitimate email")
    email_spam_action_folder = _EmailSpamActionCode(
        'spamfolder', "Deliver spam to a separate IMAP folder")
    email_spam_action_delete = _EmailSpamActionCode(
        'dropspam', "Messages classified as spam won't be delivered at all")
