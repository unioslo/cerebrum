# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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
Address, Gender etc. type.

"""
from Cerebrum import Constants
from Cerebrum.modules.PosixConstants import _PosixShellCode
from Cerebrum.modules import EmailConstants
from Cerebrum.modules.EntityTraitConstants import _EntityTraitCode
from Cerebrum.modules.bofhd.bofhd_constants import _AuthRoleOpCode
from Cerebrum.modules.consent import Consent
from Cerebrum.modules.dns import DnsConstants


class Constants(Constants.Constants):

    #
    # Bofhd Auth
    #
    auth_set_password_important = _AuthRoleOpCode(
        'set_password_imp', 'Set password for important/critical accounts')

    #
    # Authoritative systems/source systems
    #
    system_lt = Constants._AuthoritativeSystemCode(
        'LT',
        'LT')
    system_ureg = Constants._AuthoritativeSystemCode(
        'Ureg',
        'Migrerte data, utdatert')
    system_fs_derived = Constants._AuthoritativeSystemCode(
        'FS-auto',
        'Utledet av FS data')
    system_folk_uio_no = Constants._AuthoritativeSystemCode(
        'folk.uio.no',
        'http://folk.uio.no/')

    #
    # OU perspectives
    #
    perspective_lt = Constants._OUPerspectiveCode(
        'LT',
        'LT')

    account_test = Constants._AccountCode(
        'testbruker',
        'Testkonto')
    account_kurs = Constants._AccountCode(
        'kursbruker',
        'Kurskonto')
    account_uio_guest = Constants._AccountCode(
        'gjestebruker_uio',
        'Manuell gjestekonto')

    #
    # Affiliation ANSATT
    #
    affiliation_ansatt = Constants._PersonAffiliationCode(
        'ANSATT',
        'Registrert som aktiv ansatt ved UiO')
    affiliation_status_ansatt_vit = Constants._PersonAffStatusCode(
        affiliation_ansatt,
        'vitenskapelig',
        'Vitenskapelig ansatt')
    affiliation_status_ansatt_bil = Constants._PersonAffStatusCode(
        affiliation_ansatt,
        'bilag',
        'Bilagslønnet')
    affiliation_status_ansatt_tekadm = Constants._PersonAffStatusCode(
        affiliation_ansatt,
        'tekadm',
        'Teknisk/administrativt ansatt')
    affiliation_status_ansatt_perm = Constants._PersonAffStatusCode(
        affiliation_ansatt,
        'permisjon',
        'Ansatt, for tiden i permisjon')

    #
    # Affiliation STUDENT
    #
    affiliation_student = Constants._PersonAffiliationCode(
        'STUDENT',
        'Student ved UiO, registrert i FS')
    affiliation_status_student_soker = Constants._PersonAffStatusCode(
        affiliation_student,
        'soker',
        'Registrert med søknad i FS')
    affiliation_status_student_tilbud = Constants._PersonAffStatusCode(
        affiliation_student,
        'tilbud',
        'Registrert tilbud om opptak i FS')
    affiliation_status_student_opptak = Constants._PersonAffStatusCode(
        affiliation_student,
        'opptak',
        'Registrert med gyldig studierett i FS ')
    affiliation_status_student_ny = Constants._PersonAffStatusCode(
        affiliation_student,
        'ny',
        'Registrert med ny, gyldig studierett i FS')
    affiliation_status_student_aktiv = Constants._PersonAffStatusCode(
        affiliation_student,
        'aktiv',
        'Registrert som aktiv student i FS')
    affiliation_status_student_emnestud = Constants._PersonAffStatusCode(
        affiliation_student,
        'emnestud',
        'Registrert som aktiv emnestudent i FS')
    affiliation_status_student_drgrad = Constants._PersonAffStatusCode(
        affiliation_student,
        'drgrad',
        'Registrert som aktiv doktorgradsstudent i FS')
    affiliation_status_student_privatist = Constants._PersonAffStatusCode(
        affiliation_student,
        'privatist',
        'Registrert som privatist i FS')
    affiliation_status_student_evu = Constants._PersonAffStatusCode(
        affiliation_student,
        'evu',
        'Registrert som EVU-student i FS')
    affiliation_status_student_perm = Constants._PersonAffStatusCode(
        affiliation_student,
        'permisjon',
        'Registrert med gyldig permisjon i FS')
    affiliation_status_student_alumni = Constants._PersonAffStatusCode(
        affiliation_student,
        'alumni',
        'Har fullført studieprogram i FS')

    #
    # Affiliation TILKNYTTET
    #
    affiliation_tilknyttet = Constants._PersonAffiliationCode(
        'TILKNYTTET',
        'Tilknyttet UiO uten å være student eller ansatt')
    affiliation_tilknyttet_fagperson = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'fagperson', 'Registrert som fagperson i FS')
    affiliation_tilknyttet_emeritus = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'emeritus',
        'Registrert med rolle EMERITUS i SAPUiO')
    affiliation_tilknyttet_bilag = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'bilag',
        'Registrert med rolle BILAGSLØN i SAPUiO')
    affiliation_tilknyttet_ekst_forsker = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'ekst_forsker',
        'Registrert med rolle EF-FORSKER eller SENIORFORS i SAPUiO')
    affiliation_tilknyttet_gjesteforsker = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'gjesteforsker',
        'Registrert med rolle GJ-FORSKER i SAPUiO')
    affiliation_tilknyttet_assosiert_person = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'assosiert_person',
        'Registrert med rolle ASSOSIERT i SAPUiO')
    affiliation_tilknyttet_frida_reg = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'frida_reg',
        'Registrert med rolle REGANSV og REG-ANSV i SAPUiO')
    affiliation_tilknyttet_ekst_stip = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'ekst_stip',
        'Registrert med rolle EF-STIP i SAPUiO')
    affiliation_tilknyttet_sivilarbeider = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'sivilarbeider',
        'Personer registrert i LT med gjestetypekode=SIVILARB')
    affiliation_tilknyttet_diverse = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'diverse',
        'Personer registrert i LT med gjestetypekode=IKKE ANGITT')
    affiliation_tilknyttet_pcvakt = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'pcvakt',
        'Personer registrert i LT med gjestetypekode=PCVAKT')
    affiliation_tilknyttet_unirand = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'unirand',
        'Personer registrert i LT med gjestetypekode=UNIRAND')
    affiliation_tilknyttet_grlaerer = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'grlaerer',
        'Personer registrert i LT med gjestetypekode=GRUPPELÆRER')
    affiliation_tilknyttet_ekst_partner = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'ekst_partner',
        'Personer registrert i LT med gjestetypekode=EKST. PART')
    affiliation_tilknyttet_studpol = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'studpol',
        'Personer registrert i LT'
        ' med gjestetypekode=ST-POL FRI eller ST-POL UTV')
    affiliation_tilknyttet_studorg = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'studorg',
        'Personer registrert i LT'
        ' med gjestetypekode=ST-ORG FRI eller ST-ORG UTV')
    affiliation_tilknyttet_innkjoper = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'innkjoper',
        'Registrert med rolle INNKJØPER i SAPUiO')
    affiliation_tilknyttet_isf = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'isf',
        'Person tilknyttet Institutt for samfunnsforskning')
    affiliation_tilknyttet_ekstern = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'ekstern',
        'Person tilknyttet enhet med avtale om utvidede IT-tilganger (FEIDE)')

    affiliation_tilknyttet_komitemedlem = Constants._PersonAffStatusCode(
        affiliation_tilknyttet,
        'komitemedlem',
        'Registrert med rolle KOMITEMEDLEM i SAPUiO ')
    #
    # Affiliation MANUELL
    #
    affiliation_manuell = Constants._PersonAffiliationCode(
        'MANUELL',
        'Tilknyttet enheter/institusjoner som USIT har avtale med')
    affiliation_manuell_alumni = Constants._PersonAffStatusCode(
        affiliation_manuell,
        'alumni',
        'Uteksaminerte studenter')
    affiliation_manuell_ekstern = Constants._PersonAffStatusCode(
        affiliation_manuell,
        'ekstern',
        'Person tilknyttet enhet med avtale om begrensede IT-tilganger')

    #
    # Shell settings for PosixUser
    #
    # We override the default settings for shells, thus this file
    # should be before PosixUser in cereconf.CLASS_CONSTANTS
    posix_shell_bash = _PosixShellCode(
        'bash',
        '/local/gnu/bin/bash')
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

    #
    # Spreads
    #
    spread_uio_nis_user = Constants._SpreadCode(
        'NIS_user@uio',
        Constants.Constants.entity_account,
        'User in NIS domain "uio"')
    spread_uio_nis_fg = Constants._SpreadCode(
        'NIS_fg@uio',
        Constants.Constants.entity_group,
        'File group in NIS domain "uio"')
    spread_uio_nis_ng = Constants._SpreadCode(
        'NIS_ng@uio',
        Constants.Constants.entity_group,
        'Net group in NIS domain "uio"')
    spread_ifi_nis_user = Constants._SpreadCode(
        'NIS_user@ifi',
        Constants.Constants.entity_account,
        'User in NIS domain "ifi"')
    spread_ifi_nis_fg = Constants._SpreadCode(
        'NIS_fg@ifi',
        Constants.Constants.entity_group,
        'File group in NIS domain "ifi"')
    spread_ifi_nis_ng = Constants._SpreadCode(
        'NIS_ng@ifi',
        Constants.Constants.entity_group,
        'Net group in NIS domain "ifi"')
    spread_hpc_nis_user = Constants._SpreadCode(
        'NIS_user@hpc',
        Constants.Constants.entity_account,
        'User in NIS domain, exported to HPC')
    spread_hpc_nis_fg = Constants._SpreadCode(
        'NIS_fg@hpc',
        Constants.Constants.entity_group,
        'File group in NIS domain "uio" exported to HPC')
    spread_isf_ldap_person = Constants._SpreadCode(
        'LDAP_isf_person',
        Constants.Constants.entity_person,
        'Person included in ISF-s LDAP directory')
    spread_uio_ldap_ou = Constants._SpreadCode(
        'LDAP_OU',
        Constants.Constants.entity_ou,
        'OU included in LDAP directory')
    spread_uio_ldap_account = Constants._SpreadCode(
        'LDAP_account',
        Constants.Constants.entity_account,
        'Account included the LDAP directory')
    spread_uio_org_ou = Constants._SpreadCode(
        'ORG_OU',
        Constants.Constants.entity_ou,
        'OU defined as part of UiOs org.structure proper')
    spread_uio_ad_account = Constants._SpreadCode(
        'AD_account',
        Constants.Constants.entity_account,
        'Account included in Active Directory at UiO')
    spread_uio_ad_group = Constants._SpreadCode(
        'AD_group',
        Constants.Constants.entity_group,
        'Group included in Active Directory at UiO')
    spread_uio_ad_xpand = Constants._SpreadCode(
        'Xpand_group',
        Constants.Constants.entity_group,
        "Group included in Xpand's AD-OU")

    # Spreads for Exchange
    spread_exchange_account = Constants._SpreadCode(
        'exchange_acc@uio',
        Constants.Constants.entity_account,
        'An account with an Exchange-mailbox at UiO')
    spread_exchange_group = Constants._SpreadCode(
        'exch_group@uio',
        Constants.Constants.entity_group,
        'A mail enabled security group for Exchange')
    spread_exchange_shared_mbox = Constants._SpreadCode(
        'exch_shared_mbox',
        Constants.Constants.entity_group,
        'Group exposed as a shared mailbox in Exchange')

    spread_uio_ldap_guest = Constants._SpreadCode(
        'guest@ldap',
        Constants.Constants.entity_account,
        'LDAP/RADIUS spread for wireless accounts')

    # exchange-related-jazz
    # this code should be removed from the cerebrum-db as soon as
    # migration to Exchange is completed. Removal will serve two
    # purposes; firstly as a code clean-up, secondly as a check that
    # the migration was completed properly and no mailboxes are
    # registered as IMAP-accounts.
    spread_uio_imap = Constants._SpreadCode(
        'IMAP@uio',
        Constants.Constants.entity_account,
        'E-mail user at UiO')
    spread_fronter_kladdebok = Constants._SpreadCode(
        'CF@uio_kladdebok',
        Constants.Constants.entity_group,
        'Group representing a course that should be exported to the '
        'ClassFronter instance on kladdebok.uio.no. Should only be given to '
        'groups that have been automatically generated from FS.')
    spread_fronter_blyant = Constants._SpreadCode(
        'CF@uio_blyant',
        Constants.Constants.entity_group,
        'Group representing a course that should be exported to the '
        'ClassFronter instance on blyant.uio.no. Should only be given to '
        'groups that have been automatically generated from FS.''')
    spread_fronter_petra = Constants._SpreadCode(
        'CF@uio_petra',
        Constants.Constants.entity_group,
        'Group representing a course that should be exported to the '
        'ClassFronter instance on petra.uio.no. Should only be given to '
        'groups that have been automatically generated from FS.')
    spread_fronter_dotcom = Constants._SpreadCode(
        'CF@fronter.com',
        Constants.Constants.entity_group,
        'Group representing a course that should be exported to the '
        'ClassFronter instance on fronter.com. Should only be given to '
        'groups that have been automatically generated from FS.')

    # LDAP: Brukere, grupper

    # TODO: Kunne begrense tillatte spreads for spesielt priviligerte
    # brukere.

    #
    # Quarantines
    #
    quarantine_generell = Constants._QuarantineCode(
        'generell',
        'Generell splatt')
    quarantine_teppe = Constants._QuarantineCode(
        'teppe',
        'Kalt inn på teppet til drift')
    quarantine_system = Constants._QuarantineCode(
        'system',
        'Systembrukar som ikke skal logge inn')
    quarantine_permisjon = Constants._QuarantineCode(
        'permisjon',
        'Brukeren har permisjon')
    quarantine_svakt_passord = Constants._QuarantineCode(
        'svakt_passord',
        'For dårlig passord')
    quarantine_autopassord = Constants._QuarantineCode(
        'autopassord',
        'Passord ikke skiftet trass pålegg')
    quarantine_auto_emailonly = Constants._QuarantineCode(
        'auto_kunepost',
        'Ikke ordinær student, tilgang til bare e-post')
    quarantine_auto_inaktiv = Constants._QuarantineCode(
        'auto_inaktiv',
        'Ikke aktiv student, utestengt')
    quarantine_autoekstern = Constants._QuarantineCode(
        'autoekstern',
        'Ekstern konto gått ut på dato')
    quarantine_autointsomm = Constants._QuarantineCode(
        'autointsomm',
        'Sommerskolen er ferdig for i år')
    quarantine_nologin = Constants._QuarantineCode(
        'nologin',
        'Gammel ureg karantene nologin')
    quarantine_nologin_brk = Constants._QuarantineCode(
        'nologin_brk',
        'Gammel ureg karantene nologin_brk')
    quarantine_nologin_ftpuser = Constants._QuarantineCode(
        'nologin_ftpuser',
        'Gammel ureg karantene nologin_ftpuser')
    quarantine_nologin_nystudent = Constants._QuarantineCode(
        'nologin_nystuden',
        'Gammel ureg karantene nologin_nystudent')
    quarantine_nologin_sh = Constants._QuarantineCode(
        'nologin_sh',
        'Gammel ureg karantene nologin_sh')
    quarantine_nologin_stengt = Constants._QuarantineCode(
        'nologin_stengt',
        'Gammel ureg karantene nologin_stengt')
    quarantine_ou_notvalid = Constants._QuarantineCode(
        'ou_notvalid',
        'OU not valid from external source')
    quarantine_ou_remove = Constants._QuarantineCode(
        'ou_remove',
        'OU is clean and may be removed')
    quarantine_guest_release = Constants._QuarantineCode(
        'guest_release',
        'Guest user is released but not available.')
    quarantine_oppringt = Constants._QuarantineCode(
        'oppringt',
        'Brukeren er sperret for oppringt-tjenesten.')
    quarantine_vpn = Constants._QuarantineCode(
        'vpn',
        'Brukeren er sperret for VPN-tjenesten.')
    quarantine_equant = Constants._QuarantineCode(
        'equant',
        'Brukeren er sperret for Equant tjenesten.')
    quarantine_radius = Constants._QuarantineCode(
        'radius',
        'Bruker er sperret for RADIUS-innlogging.')
    quarantine_cert = Constants._QuarantineCode(
        'cert',
        'Bruker er sperret av CERT.')
    quarantine_auto_tmp_student = Constants._QuarantineCode(
        'auto_tmp_student',
        'Account is no longer active')

    #
    # Email domains
    #
    email_domain_category_uio_globals = \
        EmailConstants._EmailDomainCategoryCode(
            'UIO_GLOBALS',
            "All local_parts defined in domain 'UIO_GLOBALS' are treated"
            " as overrides for all domains posessing this category.")

    #
    # Email spam settings
    #
    email_spam_level_none = EmailConstants._EmailSpamLevelCode(
        'no_filter',
        9999,
        "No email will be filtered as spam")
    email_spam_level_standard = EmailConstants._EmailSpamLevelCode(
        'standard_spam',
        7,
        "Only filter email that obviously is spam")
    email_spam_level_heightened = EmailConstants._EmailSpamLevelCode(
        'most_spam',
        5,
        "Filter most emails that look like spam")
    email_spam_level_aggressive = EmailConstants._EmailSpamLevelCode(
        'aggressive_spam',
        3,
        "Filter everything that resembles spam")

    email_spam_action_none = EmailConstants._EmailSpamActionCode(
        'noaction',
        "Deliver spam just like legitimate email")
    email_spam_action_folder = EmailConstants._EmailSpamActionCode(
        'spamfolder',
        "Deliver spam to a separate IMAP folder")
    email_spam_action_delete = EmailConstants._EmailSpamActionCode(
        'dropspam',
        "Reject messages classified as spam")

    #
    # Email traits
    #
    trait_email_server_weight = _EntityTraitCode(
        'em_server_weight',
        Constants.Constants.entity_host,
        "The relative weight of this server when assigning new users to "
        "an e-mail server.")

    trait_email_pause = _EntityTraitCode(
        'email_pause',
        EmailConstants.EmailConstants.entity_email_target,
        'Pauses delivery of email')

    # Owner trait for GuestUsers module.
    trait_uio_guest_owner = _EntityTraitCode(
        'guest_owner_uio',
        Constants.Constants.entity_account,
        "When a guest account is requested a group must be set as "
        "owner for the account for the given time.")

    trait_account_generation = _EntityTraitCode(
        'ac_generation',
        Constants.Constants.entity_account,
        "When a users homedir is archived, this value is increased.")

    trait_student_disk = _EntityTraitCode(
        'student_disk',
        Constants.Constants.entity_disk,
        "When set, the disk in question is designated as"
        " hosting students' home areas")

    # Trait for tagging a person's primary affiliation, to be used by the web
    # presentations.
    trait_primary_aff = _EntityTraitCode(
        "primary_aff",
        Constants.Constants.entity_person,
        "A person's chosen primary affiliation,"
        " for use at the web presentations")

    # Trait for tagging -adm,-drift,-null accounts
    trait_sysadm_account = _EntityTraitCode(
        "sysadm_account",
        Constants.Constants.entity_account,
        "An account used for system administration,"
        " e.g. foo-adm, foo-drift and foo-null users")

    # Trait for passphrase stats
    trait_has_passphrase = _EntityTraitCode(
        'has_passphrase',
        Constants.Constants.entity_account,
        "Account uses passphrase")

    # Trait to tag students with temporary access to IT-services
    trait_tmp_student = _EntityTraitCode(
        'tmp_student',
        Constants.Constants.entity_account,
        'Account is granted temporary access')

    #
    # Address types
    #
    address_other_street = Constants._AddressCode(
        'OTHER_STREET',
        'Other street address')
    address_other_post = Constants._AddressCode(
        'OTHER_POST',
        'Other post address')

    #
    # Consents
    #

    # Office 365
    consent_office365 = Consent.Constants.EntityConsent(
        'office365',
        entity_type=Constants.Constants.entity_person,
        consent_type=Consent.Constants.consent_opt_in,
        description="Export to office365?")

    # Gsuite
    consent_gsuite = Consent.Constants.EntityConsent(
        'gsuite',
        entity_type=Constants.Constants.entity_person,
        consent_type=Consent.Constants.consent_opt_in,
        description="Export to Google for Education")

    # cristin
    consent_cristin = Consent.Constants.EntityConsent(
        'cristin',
        entity_type=Constants.Constants.entity_person,
        consent_type=Consent.Constants.consent_opt_in,
        description="Export to Cristin")

    #
    # DNS Zones
    #
    uio_zone = DnsConstants._DnsZoneCode(
        "uio",
        ".uio.no.")
    ifi_zone = DnsConstants._DnsZoneCode(
        "ifi_uio",
        ".ifi.uio.no.")
