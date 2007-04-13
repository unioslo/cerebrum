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
from Cerebrum.Constants import \
     _AuthoritativeSystemCode, \
     _OUPerspectiveCode, \
     _SpreadCode, \
     _QuarantineCode, \
     _EntityExternalIdCode, \
     _PersonAffiliationCode, \
     _PersonAffStatusCode, \
     _AccountCode, \
     _PersonNameCode, \
     _ContactInfoCode, \
     _CerebrumCode, \
     _AddressCode, \
     _AuthenticationCode
from Cerebrum.modules.PosixUser import \
     _PosixShellCode
from Cerebrum.modules.Email import \
     _EmailServerTypeCode
     
from Cerebrum.modules.EntityTrait import \
     _EntityTraitCode
     
##from Cerebrum.modules.bofhd.utils import \
##     _AuthRoleOpCode
     

class Constants(Constants.Constants):

    
    contact_workphone = _ContactInfoCode('PHONE_WORK', 'Work Phone')
    contact_homephone = _ContactInfoCode('PHONE_HOME', 'Home Phone')
    contact_mobile = _ContactInfoCode('PHONE_MOBILE','Mobile phone')
    contact_phone = _ContactInfoCode('CONTACT_PHONE','Contact Phone')
    name_contact_name = _PersonNameCode('CONTACT_NAME', 'Persons contact name')

    #affiliation_language_norwegian = _language_code('NORSK','Norsk') 
    #affiliation_language_english = _language_code('ENGELSK','Engelsk') 
    #affiliation_language_sami = _language_code('SAMISK','Samisk') 
    #affiliation_language_newnorwegian = _language_code('NY_NORSK','Ny Norsk') 

    externalid_fodselsnr = _EntityExternalIdCode(
        'NO_BIRTHNO',
        Constants.Constants.entity_person,
        'Norwegian birth number')
    externalid_student_kort = _EntityExternalIdCode(
        'STUDENT_CARD',
        Constants.Constants.entity_person,
        'Student card number')
    externalid_feide_id = _EntityExternalIdCode(
        'FEIDE_ID',
        Constants.Constants.entity_person,
        'Feide identification')
    externalid_sys_x_id = _EntityExternalIdCode(
        'SYS_X_ID',
        Constants.Constants.entity_person,
        'Internal sys_x identifier')
    externalid_studentnr = _EntityExternalIdCode(
        'STUDENT_NUMBER',
        Constants.Constants.entity_person,
        'Student card number')
    address_post = _AddressCode('POST','Post address')
    
    # Authoritative systems
    system_lt = _AuthoritativeSystemCode('SLP4', 'SLP4')
    system_fs = _AuthoritativeSystemCode('FS', 'FS')
    system_x = _AuthoritativeSystemCode('SYS_X', 'Manuelt personal system')

##    system_fs_derived = _AuthoritativeSystemCode('FS-auto','Utledet av FS data')
##    system_asp = _AuthoritativeSystemCode('ASP', 'ASP')
##    system_sut = _AuthoritativeSystemCode('SUT', 'SUT')
##    system_Bofh = _AuthoritativeSystemCode('BOFH', 'BOFH')

    # OU perspectives
    perspective_slp4 = _OUPerspectiveCode('SLP4', 'SLP4')
    perspective_fs = _OUPerspectiveCode('FS', 'FS')

    # Account codes
    account_test = _AccountCode('T', 'Testkonto')
    account_felles_drift = _AccountCode('FD','Felles Drift') 
    account_felles_intern = _AccountCode('FI','Felles Intern') 
    account_kurs = _AccountCode('K','Kurs') 
    account_forening = _AccountCode('F','Forening') 
    account_maskin = _AccountCode('M','Maskin') 
    account_prosess = _AccountCode('P','Prosess') 

    # Ansatt affiliation and status
    affiliation_ansatt = _PersonAffiliationCode(
        'ANSATT',
        'Ansatt ved UiT (i følge LT)') 
    affiliation_status_ansatt_sys_x = _PersonAffStatusCode(
        affiliation_ansatt, 
        'sys_x-ansatt',
        'Manuelt gitt tilgang til AD (bør nyanseres)')
    affiliation_status_ansatt_vit = _PersonAffStatusCode(
        affiliation_ansatt, 
        'vitenskapelig', 
        'Vitenskapelig ansatt')
    affiliation_status_ansatt_bil = _PersonAffStatusCode(
        affiliation_ansatt, 
        'bilag', 
        'Bilagslønnet')
    affiliation_status_ansatt_tekadm = _PersonAffStatusCode(
        affiliation_ansatt, 
        'tekadm', 
        'Teknisk/administrativt ansatt')
    affiliation_status_ansatt_perm = _PersonAffStatusCode(
        affiliation_ansatt, 
        'permisjon', 
        'Ansatt, men med aktiv permisjon')

    # Student affiliation and status
    affiliation_student = _PersonAffiliationCode(
        'STUDENT', 
        'Student ved UiT (i følge FS)') 
    affiliation_status_student_sys_x = _PersonAffStatusCode(
        affiliation_student, 
        'sys_x-student',
        'Manuelt gitt tilgang til SUT (bør nyanseres)')
    affiliation_status_student_soker = _PersonAffStatusCode(
        affiliation_student, 
        'soker', 
        'Registrert søker i FS')
    affiliation_status_student_tilbud = _PersonAffStatusCode(
        affiliation_student, 
        'tilbud', 
        'Har fått tilbud om opptak')
    affiliation_status_student_opptak = _PersonAffStatusCode(
        affiliation_student, 
        'opptak', 
        'Har studierett ved studieprogram')
    affiliation_status_student_aktiv = _PersonAffStatusCode(
        affiliation_student, 
        'aktiv', 
        'Aktiv student')
    affiliation_status_student_privatist = _PersonAffStatusCode(
        affiliation_student, 
        'privatist', 
        'Registrert som privatist i FS')
    affiliation_status_student_evu = _PersonAffStatusCode(
        affiliation_student, 
        'evu', 
        'Registrert som EVU-student i FS')
    affiliation_status_student_perm = _PersonAffStatusCode(
        affiliation_student, 
        'permisjon', 
        'Har gyldig permisjonstatus i FS')
    affiliation_status_student_alumni = _PersonAffStatusCode(
        affiliation_student, 
        'alumni', 
        'Har fullført studieprogram i FS')
    affiliation_status_student_drgrad = _PersonAffStatusCode(
        affiliation_student, 
        'drgrad', 
        'Registrert student på doktorgrad')
    
    #Tilknyttet affiliation and status
    affiliation_tilknyttet = _PersonAffiliationCode(
        'TILKNYTTET', 
        'Tilknyttet UiT uten å være student eller ansatt')
    affiliation_tilknyttet_fagperson = _PersonAffStatusCode(
        affiliation_tilknyttet, 
        'fagperson', 
        'Registrert som fagperson i FS')
    affiliation_tilknyttet_emeritus = _PersonAffStatusCode(
        affiliation_tilknyttet, 
        'emeritus',
        'Registrert i LT med gjestetypekode EMERITUS')
    affiliation_tilknyttet_ekst_stip = _PersonAffStatusCode(
        affiliation_tilknyttet, 
        'ekst_stip',
        'Personer registrert i LT med gjestetypekode=EF-STIP')
    
    affiliation_manuell = _PersonAffiliationCode(
        'MANUELL', 
        'Tilknyttet enheter/instutusjoner som UiT har avtale med')
    affiliation_manuell_sito = _PersonAffStatusCode(
        affiliation_manuell, 
        'sito', 
        'Sito')
    affiliation_manuell_unn = _PersonAffStatusCode(
        affiliation_manuell,
        'UNN',
        'Universitets sykheuset i Nord Norge')
    affiliation_manuell_notur = _PersonAffStatusCode(
        affiliation_manuell, 
        'notur',
        'Notur')
    affiliation_manuell_gjest = _PersonAffStatusCode(
        affiliation_manuell, 
        'gjest', 
        'Gjest')
    affiliation_manuell_utdanning_no = _PersonAffStatusCode(
        affiliation_manuell, 
        'utdanning_no',
        'Utdanning.no')
    affiliation_manuell_akademisk_kvarter = _PersonAffStatusCode(
        affiliation_manuell, 
        'akademisk_kvart', 
        'Akademisk Kvarter')
    affiliation_manuell_norges_universitetet = _PersonAffStatusCode(
        affiliation_manuell, 
        'norges_universi', 
        'Norgesuniversitetet')
    affiliation_manuell_kirkutdnor = _PersonAffStatusCode(
        affiliation_manuell, 
        'kirkutdnor', 
        'Kirkelig Utdanningssenter Nord-Norge')
    
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

    #affiliation_upersonlig = _PersonAffiliationCode(                   
    #    'UPERSONLIG', 'Fellesbrukere, samt andre brukere uten eier')   
    #affiliation_upersonlig_felles = _PersonAffStatusCode(              
    #    affiliation_upersonlig, 'felles', 'Felles konti')              
    #affiliation_upersonlig_kurs = _PersonAffStatusCode(                
    #    affiliation_upersonlig, 'kurs', 'Kurs konti')                  
    #affiliation_upersonlig_pvare = _PersonAffStatusCode(               
    #    affiliation_upersonlig, 'pvare', 'Programvare konti')          
    #affiliation_upersonlig_term_maskin = _PersonAffStatusCode(         
    #    affiliation_upersonlig, 'term_maskin', 'Terminalstue maskin')  
    #affiliation_upersonlig_bib_felles = _PersonAffStatusCode(          
    #    affiliation_upersonlig, 'bib_felles', 'Bibliotek felles')      
    #affiliation_upersonlig_uit_forening = _PersonAffStatusCode(        
    #    affiliation_upersonlig, 'uit_forening', 'Uit forening')        


    # We override the default settings for shells, thus this file
    # should be before PosixUser in cereconf.CLASS_CONSTANTS
    posix_shell_bash = _PosixShellCode(
        'bash', 
        '/bin/bash')
    posix_shell_csh = _PosixShellCode(
        'csh', 
        '/bin/csh')
    posix_shell_false = _PosixShellCode(
        'false', 
        '/bin/false')
    posix_shell_ksh = _PosixShellCode(
        'ksh', 
        '/bin/ksh')
    posix_shell_ma104 = _PosixShellCode(
        'ma104', 
        '/local/bin/ma104')
    posix_shell_nologin = _PosixShellCode(
        'nologin', 
        '/local/etc/nologin')
    posix_shell_nologin_autostud = _PosixShellCode(
        'nologin.autostud',
        '/local/etc/shells/nologin.autostud')
    posix_shell_nologin_brk = _PosixShellCode(
        'nologin.brk',
        '/local/etc/shells/nologin.brk')
    posix_shell_nologin_chpwd = _PosixShellCode(
        'nologin.chpwd',
        '/local/etc/shells/nologin.chpwd')
    posix_shell_nologin_ftpuser = _PosixShellCode(
        'nologin.ftpuser',
        '/local/etc/shells/nologin.ftpuser')
    posix_shell_nologin_nystudent = _PosixShellCode(
        'nologin.nystuden',
        '/local/etc/shells/nologin.nystudent')
    posix_shell_nologin_permisjon = _PosixShellCode(
        'nologin.permisjo',
        '/local/etc/shells/nologin.permisjon')
    posix_shell_nologin_pwd = _PosixShellCode(
        'nologin.pwd',
        '/local/etc/shells/nologin.pwd')
    posix_shell_nologin_sh = _PosixShellCode(
        'nologin.sh',
        '/local/etc/shells/nologin.sh')
    posix_shell_nologin_sluttet = _PosixShellCode(
        'nologin.sluttet',
        '/local/etc/shells/nologin.sluttet')
    posix_shell_nologin_stengt = _PosixShellCode(
        'nologin.stengt',
        '/local/etc/shells/nologin.stengt')
    posix_shell_nologin_teppe = _PosixShellCode(
        'nologin.teppe',
        '/local/etc/shells/nologin.teppe')
    posix_shell_puberos = _PosixShellCode(
        'puberos', 
        '/local/bin/puberos')
    posix_shell_pwsh = _PosixShellCode(
        'pwsh', 
        '/etc/pw/sh')
    posix_shell_sftp_server = _PosixShellCode(
        'sftp-server',
        '/local/openssh/libexec/sftp-server')
    posix_shell_sh = _PosixShellCode(
        'sh', 
        '/bin/sh')
    posix_shell_simonshell = _PosixShellCode(
        'simonshell',
        '/hom/simon/simonshell')
    posix_shell_sync = _PosixShellCode(
        'sync', 
        '/bin/sync')
    posix_shell_tcsh = _PosixShellCode(
        'tcsh', 
        '/local/bin/tcsh')
    posix_shell_true = _PosixShellCode(
        'true', 
        '/bin/true')
    posix_shell_zsh = _PosixShellCode(
        'zsh',
        '/local/bin/zsh')
    
    # Spread constants
    spread_uit_fronter = _SpreadCode(
        'fronter@uit', 
        Constants.Constants.entity_group,
        'fronter user')
    spread_uit_fronter_account = _SpreadCode(
        'fronter_acc@uit',
        Constants.Constants.entity_account,
        'fronter account')
    spread_uit_evu = _SpreadCode(
        'evu@uit', 
        Constants.Constants.entity_account,
        'evu person')
    spread_uit_frida = _SpreadCode(
        'frida@uit',
        Constants.Constants.entity_account,
        'Accounts with FRIDA spread')
    spread_uit_fd = _SpreadCode(
        'fd@uit',
        Constants.Constants.entity_account,
        'Accounts with FD spread')
    spread_uit_nis_user = _SpreadCode(
        'NIS_user@uit',
        Constants.Constants.entity_account,
        'User in NIS domain "uit"')
    spread_uit_sut_user = _SpreadCode(
        'SUT@uit',
        Constants.Constants.entity_account,
        'Accounts with SUT spread')    
    spread_uit_ldap_account = _SpreadCode(
        'ldap@uit',
        Constants.Constants.entity_account,
        'Accounts with ldap spread')
##    spread_uit_nis_fg = _SpreadCode(
##        'NIS_fg@uit', 
##        Constants.Constants.entity_group,
##        'File group in NIS domain "uit"')
##    spread_uit_nis_ng = _SpreadCode(
##        'NIS_ng@uit', 
##        Constants.Constants.entity_group,
##        'Net group in NIS domain "uit"')       
##    spread_ifi_nis_user = _SpreadCode(
##        'NIS_user@ifi', Constants.Constants.entity_account,
##        'User in NIS domain "ifi"')
##    spread_ifi_nis_fg = _SpreadCode(
##        'NIS_fg@ifi',
##        Constants.Constants.entity_group,
##        'File group in NIS domain "ifi"')
##    spread_ifi_nis_ng = _SpreadCode(
##        'NIS_ng@ifi', 
##        Constants.Constants.entity_group,
##        'Net group in NIS domain "ifi"')
    spread_uit_ldap_person = _SpreadCode(
        'LDAP_person', Constants.Constants.entity_person,
        'Person included in LDAP directory')
    #spread_uit_ldap_ou = _SpreadCode(
    #    'LDAP_OU', Constants.Constants.entity_ou,
    #    'OU included in LDAP directory')
    spread_uit_ad_account = _SpreadCode(
        'AD_account',
        Constants.Constants.entity_account,
        'account included in Active Directory')
    spread_uit_ad_group = _SpreadCode(
        'AD_group',
        Constants.Constants.entity_group,
        'group included in Active Directory')
    spread_uit_ad_lit_admin = _SpreadCode(
        'AD_litadmin',  
        Constants.Constants.entity_account,
        'AD admin local IT') 
    spread_uit_ad_admin = _SpreadCode(
        'AD_admin',
        Constants.Constants.entity_account,
        'AD admin central IT')    
    spread_uit_ad_lit_admingroup = _SpreadCode(
        'AD_group_litadmn',
        Constants.Constants.entity_group,
        'AD admingroup for local IT')

    # Email constants
    spread_uit_imap = _SpreadCode(
        'IMAP@uit', 
        Constants.Constants.entity_account,
        'IMAP account')
    email_server_type_exchange_imap= _EmailServerTypeCode(
            'exchange_imap',
            "Server is an Exchange server")

    # LDAP: Brukere, grupper

    # Quarantine constants
    quarantine_tilbud = _QuarantineCode(
            'Tilbud',
            "Pre-generert konto til studenter som har fått studietilbud,"
            "men som ikke har aktivert kontoen.")
    quarantine_sys_x_approved = _QuarantineCode(
            'sys-x_approved',
            'Konto fra system-x som ikke er godkjent')
    quarantine_generell = _QuarantineCode(
            'generell', 
            'Generell splatt')
    quarantine_teppe = _QuarantineCode(
            'teppe', 
            'Kallt inn på teppet til drift')
    quarantine_slutta = _QuarantineCode(
            'slutta', 
            'Personen har slutta')
    quarantine_system = _QuarantineCode(
            'system', 
            'Systembrukar som ikke skal logge inn')
    quarantine_permisjon = _QuarantineCode(
            'permisjon', 
            'Brukeren har permisjon')
    quarantine_svakt_passord = _QuarantineCode(
            'svakt_passord', 
            'For dårlig passord')
    quarantine_autopassord = _QuarantineCode(
            'autopassord',
            'Passord ikke skiftet trass pålegg')
    quarantine_autostud = _QuarantineCode(
            'autostud', 
            'Ikke aktiv student')
    quarantine_autoekstern = _QuarantineCode(
            'autoekstern',
            'Ekstern konto gått ut på dato')
    quarantine_autointsomm = _QuarantineCode(
            'autointsomm',
            'Sommerskolen er ferdig for i år')
    quarantine_auto_emailonly = _QuarantineCode(
            'auto_emailonly',
            'Ikke ordinær student, tilgang')
    quarantine_auto_inaktiv = _QuarantineCode(
            'auto_inaktiv', 
            'Ikke aktiv student, utestengt')
    quarantine_sut_disk_usage = _QuarantineCode(
            'sut_disk',
            "Bruker for mye disk på sut")
            
    # Auth codes
    auth_type_md4_nt =  _AuthenticationCode(
            'MD4-NT',
            "MD4-derived password hash with Microsoft-added security.")
    auth_type_md5_crypt_hex = _AuthenticationCode(
            'MD5-crypt2',
            "MD5-derived 32 bit password non unix style, no salt")
    auth_type_md5_b64= _AuthenticationCode(
            'MD5-crypt_base64',
            "MD5-derived 32 bit password base 64 encoded")


    # Trait codes
    trait_sysx_registrar_notified = _EntityTraitCode(
        'sysx_reg_mailed', Constants.Constants.entity_account,
        "Trait set on account when systemx processing is done"
        )
    trait_sysx_user_notified = _EntityTraitCode(
        'sysx_user_mailed', Constants.Constants.entity_account,
        "Trait set on account after account created mail is sent to user"
        )
    
# arch-tag: bb60794e-b4ef-11da-9ffc-ae0881dfefd1
