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
     _PersonAffiliationCode, _PersonAffStatusCode, _AccountCode, _PersonNameCode, _ContactInfoCode ,_CerebrumCode, _AddressCode, _AuthenticationCode
from Cerebrum.modules.PosixUser import _PosixShellCode
from Cerebrum.modules.Email import _EmailServerTypeCode



class Constants(Constants.Constants):

    
    contact_workphone = _ContactInfoCode('PHONE_WORK', 'Work Phone') # uit
    contact_homephone = _ContactInfoCode('PHONE_HOME', 'Home Phone') # uit
    contact_mobile = _ContactInfoCode('PHONE_MOBILE','Mobile phone') # uit
    contact_phone = _ContactInfoCode('CONTACT_PHONE','Contact Phone') # uit ?
    name_contact_name = _PersonNameCode('CONTACT_NAME', 'Persons contact name') # uit

    #affiliation_language_norwegian = _language_code('NORSK','Norsk') # uit
    #affiliation_language_english = _language_code('ENGELSK','Engelsk') # uit
    #affiliation_language_sami = _language_code('SAMISK','Samisk') # uit
    #affiliation_language_newnorwegian = _language_code('NY_NORSK','Ny Norsk') # uit

    externalid_fodselsnr = _EntityExternalIdCode('NO_BIRTHNO',
                                                 Constants.Constants.entity_person,
                                                 'Norwegian birth number')
    externalid_student_kort = _EntityExternalIdCode('STUDENT_CARD',
                                                    Constants.Constants.entity_person,
                                                    'Student card number') # uit
    externalid_feide_id = _EntityExternalIdCode('FEIDE_ID',
                                                 Constants.Constants.entity_person,
                                                'Feide identification')        # uit
    externalid_studentnr = _EntityExternalIdCode('STUDENT_NUMBER',
                                                  Constants.Constants.entity_person,
                                                 'Student card number') # uit
    address_post = _AddressCode('POST','Post address') # uit
    system_lt = _AuthoritativeSystemCode('SLP4', 'SLP4') # uit
    system_fs = _AuthoritativeSystemCode('FS', 'FS')
    system_x = _AuthoritativeSystemCode('SYS_X', 'Manuelt personal system')

    system_fs_derived = _AuthoritativeSystemCode('FS-auto','Utledet av FS data')
    #system_lt = _AuthoritativeSystemCode('')
    system_asp = _AuthoritativeSystemCode('ASP', 'ASP') # uit
    system_sut = _AuthoritativeSystemCode('SUT', 'SUT') # uit
    system_Bofh = _AuthoritativeSystemCode('BOFH', 'BOFH') # uit
    #system_ureg = _AuthoritativeSystemCode('Ureg', 'Imported from ureg') # uit
    perspective_foo = _OUPerspectiveCode('FOO','BAR')
    perspective_slp4 = _OUPerspectiveCode('SLP4', 'SLP4') # uit
    perspective_fs = _OUPerspectiveCode('FS', 'FS')

    account_test = _AccountCode('T', 'Testkonto')
    account_felles_drift = _AccountCode('FD','Felles Drift') # uit
    account_felles_intern = _AccountCode('FI','Felles Intern') # uit
    account_kurs = _AccountCode('K','Kurs') # uit
    account_forening = _AccountCode('F','Forening') # uit
    account_maskin = _AccountCode('M','Maskin') # uit
    account_prosess = _AccountCode('P','Prosess') # uit


    #affiliation_fs_friends = _PersonAffiliationCode('FS_friend','Har faatt student konto uten aa vaere student')
    #affiliation_ad_friends = _PersonAffiliationCode('AD_friend','Har faatt AD konto uten aa vaere ansatt')
    affiliation_ansatt = _PersonAffiliationCode('ANSATT',
                                                'Ansatt ved UiT (i følge LT)') # uit
    affiliation_status_ansatt_sys_x = _PersonAffStatusCode(
        affiliation_ansatt, 'sys_x-ansatt','Manuelt gitt tilgang til AD (bør nyanseres)')

    affiliation_status_ansatt_vit = _PersonAffStatusCode(
        affiliation_ansatt, 'vitenskapelig', 'Vitenskapelig ansatt')
    affiliation_status_ansatt_bil = _PersonAffStatusCode(
        affiliation_ansatt, 'bilag', 'Bilagslønnet')
    affiliation_status_ansatt_tekadm = _PersonAffStatusCode(
        affiliation_ansatt, 'tekadm', 'Teknisk/administrativt ansatt')
    affiliation_status_ansatt_perm = _PersonAffStatusCode(
        affiliation_ansatt, 'permisjon', 'Ansatt, men med aktiv permisjon')

    affiliation_student = _PersonAffiliationCode('STUDENT', 'Student ved UiT (i følge FS)') # uit
    affiliation_status_student_sys_x = _PersonAffStatusCode(
        affiliation_student, 'sys_x-student','Manuelt gitt tilgang til SUT (bør nyanseres)')
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
    affiliation_status_student_drgrad = _PersonAffStatusCode(
        affiliation_student, 'drgrad', 'Registrert student på doktorgrad')
    
    
    affiliation_tilknyttet = _PersonAffiliationCode(
        'TILKNYTTET', 'Tilknyttet UiT uten å være student eller ansatt')
    affiliation_tilknyttet_fagperson = _PersonAffStatusCode(
        affiliation_tilknyttet, 'fagperson', 'Registrert som fagperson i FS')
    affiliation_tilknyttet_emeritus = _PersonAffStatusCode(
        affiliation_tilknyttet, 'emeritus',
        'Registrert i LT med gjestetypekode EMERITUS')
    affiliation_tilknyttet_ekst_stip = _PersonAffStatusCode(
        affiliation_tilknyttet, 'ekst_stip',
        'Personer registrert i LT med gjestetypekode=EF-STIP')
    affiliation_manuell = _PersonAffiliationCode(
        'MANUELL', 'Tilknyttet enheter/instutusjoner som UiT har avtale med')
    affiliation_manuell_sito = _PersonAffStatusCode(
        affiliation_manuell, 'sito', 'Sito')
    affiliation_manuell_unn = _PersonAffStatusCode(
        affiliation_manuell, 'UNN', 'Universitets sykheuset i Nord Norge')
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
    affiliation_manuell_konsulent = _PersonAffStatusCode(
        affiliation_manuell, 'konsulent',
        'Konsulent (under utfasing)')

    #affiliation_upersonlig = _PersonAffiliationCode(                   # uit
    #    'UPERSONLIG', 'Fellesbrukere, samt andre brukere uten eier')   # uit
    #affiliation_upersonlig_felles = _PersonAffStatusCode(              # uit
    #    affiliation_upersonlig, 'felles', 'Felles konti')              # uit
    #affiliation_upersonlig_kurs = _PersonAffStatusCode(                # uit
    #    affiliation_upersonlig, 'kurs', 'Kurs konti')                  # uit
    #affiliation_upersonlig_pvare = _PersonAffStatusCode(               # uit
    #    affiliation_upersonlig, 'pvare', 'Programvare konti')          # uit
    #affiliation_upersonlig_term_maskin = _PersonAffStatusCode(         # uit
    #    affiliation_upersonlig, 'term_maskin', 'Terminalstue maskin')  # uit
    #affiliation_upersonlig_bib_felles = _PersonAffStatusCode(          # uit
    #    affiliation_upersonlig, 'bib_felles', 'Bibliotek felles')      # uit
    #affiliation_upersonlig_uit_forening = _PersonAffStatusCode(        # uit
    #    affiliation_upersonlig, 'uit_forening', 'Uit forening')        # uit

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
    spread_uit_fronter = _SpreadCode('fronter@uit', Constants.Constants.entity_group,'fronter user')
    spread_uit_fronter_account = _SpreadCode('fronter_acc@uit',Constants.Constants.entity_account,'fronter account')
    spread_uit_evu = _SpreadCode('evu@uit', Constants.Constants.entity_account,'evu person')
    spread_uit_frida = _SpreadCode('frida@uit',Constants.Constants.entity_account,'Accounts with FRIDA spread')
    spread_uit_fd = _SpreadCode('fd@uit',Constants.Constants.entity_account,'Accounts with FD spread')
    spread_uit_nis_user = _SpreadCode('NIS_user@uit', Constants.Constants.entity_account,
                                      'User in NIS domain "uit"')                         # uit
    spread_uit_sut_user = _SpreadCode('SUT@uit',Constants.Constants.entity_account,'Accounts with SUT spread')    
    spread_uit_ldap_account = _SpreadCode('ldap@uit',Constants.Constants.entity_account,'Accounts with ldap spread')
    #spread_uit_nis_fg = _SpreadCode('NIS_fg@uit', Constants.Constants.entity_group,'File group in NIS domain "uit"')                    # uit
    spread_uit_nis_ng = _SpreadCode('NIS_ng@uit', Constants.Constants.entity_group,'Net group in NIS domain "uit"')                     # uit
    #spread_ifi_nis_user = _SpreadCode('NIS_user@ifi', Constants.Constants.entity_account,# uit
    #                                  'User in NIS domain "ifi"')                        # uit
    #spread_ifi_nis_fg = _SpreadCode('NIS_fg@ifi', Constants.Constants.entity_group,      # uit
    #                                'File group in NIS domain "ifi"')                    # uit
    #spread_ifi_nis_ng = _SpreadCode('NIS_ng@ifi', Constants.Constants.entity_group,      # uit
    #                                'Net group in NIS domain "ifi"')                     # uit
    spread_uit_ldap_person = _SpreadCode('LDAP_person', Constants.Constants.entity_person,# uit
                                         'Person included in LDAP directory')             # uit
    #spread_uit_ldap_ou = _SpreadCode('LDAP_OU', Constants.Constants.entity_ou,           # uit
    #                                 'OU included in LDAP directory')                    # uit
    spread_uit_ad_account = _SpreadCode('AD_account', Constants.Constants.entity_account,'account included in Active Directory')
    spread_uit_ad_group = _SpreadCode('AD_group', Constants.Constants.entity_group,'group included in Active Directory') # uit

    #spread_uit_ua = _SpreadCode('UA@uit', Constants.Constants.entity_person,                                             # uit
    #                            'Person exported to UA')                                                                 # uit
    spread_uit_imap = _SpreadCode('IMAP@uit', Constants.Constants.entity_account,         # uit
                                  'IMAP account')                                         # uit

                                  
    # Email constants: A uit value earlier stored in Cerebrum/modules/Email.py
    # moved here to prevent loosing a constant when checking out a newer Email.py from cvs
    email_server_type_exchange_imap= _EmailServerTypeCode(
            'exchange_imap',
            "Server is an Exchange server, which keeps mailboxes in a Microsoft spesific format")

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
    quarantine_auto_emailonly = _QuarantineCode('auto_emailonly','Ikke ordinær student, tilgang')
    quarantine_auto_inaktiv = _QuarantineCode('auto_inaktiv', 'Ikke aktiv student, utestengt')
    auth_type_md4_nt =  _AuthenticationCode('MD4-NT',
                                            "MD4-derived password hash with Microsoft-added security.")
    auth_type_md5_crypt_hex = _AuthenticationCode('MD5-crypt2',
                                                  "MD5-derived 32 bit password non unix style, no salt")
    auth_type_md5_b64= _AuthenticationCode('MD5-crypt_base64',
                                           "MD5-derived 32 bit password base 64 encoded")
    
# arch-tag: bb60794e-b4ef-11da-9ffc-ae0881dfefd1
