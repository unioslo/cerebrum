# -*- coding: utf-8 -*-
# Copyright 2005-2019 University of Oslo, Norway
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

from Cerebrum import Constants
from Cerebrum.Constants import (_AuthoritativeSystemCode,
                                _EntityExternalIdCode,
                                _SpreadCode,
                                _PersonAffiliationCode,
                                _PersonAffStatusCode,
                                _AccountCode,
                                _QuarantineCode,
                                _OUPerspectiveCode,
                                _ContactInfoCode)
from Cerebrum.modules.EntityTrait import _EntityTraitCode


class Constants(Constants.Constants):
    # Org. hierarchy perspective
    perspective_ekstens = _OUPerspectiveCode('Ekstens', 'Ekstens')
    perspective_sats = _OUPerspectiveCode('SATS', 'SATS')

    # Authoritative system codes
    system_sats = _AuthoritativeSystemCode(
        'SATS',
        'Personopplysninger hentet fra skolesystemet SATS')
    system_ekstens = _AuthoritativeSystemCode(
        'EKSTENS',
        'Personopplysninger hentet fra skolesystemet EKSTENS')
    system_tpsys = _AuthoritativeSystemCode(
        'TPSYS',
        'Personopplysninger hentet fra skolesystemet TPSYS')
    system_migrate = _AuthoritativeSystemCode(
        'MIGRATE',
        'Personopplysninger hentet fra tidligere brukte systemer')

    # External ID codes
    externalid_orgnr = _EntityExternalIdCode('ORGNR',
                                             Constants.Constants.entity_ou,
                                             'Organisasjonsnummer (fra SAS)')
    # Disse kodene er det foreløpig usikkert om skal brukes
    externalid_ouid = _EntityExternalIdCode(
        'OUID',
        Constants.Constants.entity_ou,
        'Organisasjonens unike identifikator')
    externalid_skolenr = _EntityExternalIdCode('SKOLENR',
                                               Constants.Constants.entity_ou,
                                               'Skolenummer')
    externalid_kommunenr = _EntityExternalIdCode('KOMMNR',
                                                 Constants.Constants.entity_ou,
                                                 'Kommunenummer')
    externalid_ou_oid = _EntityExternalIdCode('OUOID',
                                              Constants.Constants.entity_ou,
                                              'OU OID')
    externalid_userid = _EntityExternalIdCode(
        'USERID',
        Constants.Constants.entity_person,
        'Bruker ID')
    externalid_klasse = _EntityExternalIdCode(
        'kl-ID',
        Constants.Constants.entity_group,
        'Klasse ID')
    externalid_faggruppe = _EntityExternalIdCode(
        'fg-ID',
        Constants.Constants.entity_group,
        'Faggruppe ID')
    externalid_klassegruppe = _EntityExternalIdCode(
        'kg-ID',
        Constants.Constants.entity_group,
        'klassegruppe ID')


# Spread codes
    # AD
    spread_ad_acc = _SpreadCode(
        'account@ad',
        Constants.Constants.entity_account,
        'Brukeren kan logge inn på Windows PC-er.')
    spread_ad_grp = _SpreadCode(
        'group@ad',
        Constants.Constants.entity_group,
        'Gruppen brukes av Active Directory.')
    spread_ad_ou = _SpreadCode(
        'ou@ad',
        Constants.Constants.entity_ou,
        'OUen brukes av Active Directory.')
    # LMS
    spread_lms_acc = _SpreadCode(
        'account@lms',
        Constants.Constants.entity_account,
        'Brukeren kan logge inn på LMS (f.eks. Classfronter).')
    spread_lms_grp = _SpreadCode(
        'group@lms',
        Constants.Constants.entity_group,
        'Gruppen brukes av LMS-et.')
    spread_lms_per = _SpreadCode(
        'person@lms',
        Constants.Constants.entity_person,
        'Person kjent i organisasjonens LMS')
    spread_lms_ou = _SpreadCode(
        'ou@lms',
        Constants.Constants.entity_ou,
        'Eksportere OU til LMS (f.eks. Classfronter).')
    # OID
    spread_oid_acc = _SpreadCode(
        'account@oid',
        Constants.Constants.entity_account,
        'Brukeren kan logge inn på webportalen (OCS).')
    spread_oid_grp = _SpreadCode(
        'group@oid',
        Constants.Constants.entity_group,
        'Gruppen brukes av webportalen (OCS).')
    spread_oid_ou = _SpreadCode(
        'ou@oid',
        Constants.Constants.entity_ou,
        'OU-en skal eksporteres til OID.')
    # LDAP
    spread_ldap_per = _SpreadCode(
        'person@ldap',
        Constants.Constants.entity_person,
        'Brukeren kan benytte seg av FEIDE-innlogging.')
    spread_ldap_grp = _SpreadCode(
        'group@ldap',
        Constants.Constants.entity_group,
        'Gruppen brukes i LDAP.')

# Quarantine codes
    quarantine_generell = _QuarantineCode('generell',
                                          'Generell sperring')
# Affiliation codes
    affiliation_ansatt = _PersonAffiliationCode(
        'ANSATT',
        'Personen er registrert som ansatt i SAS.')
    affiliation_status_ansatt_aktiv = _PersonAffStatusCode(
        affiliation_ansatt,
        'aktiv',
        'Personen har aktiv tilsetting, registrert i SAS.')
    affiliation_elev = _PersonAffiliationCode(
        'ELEV',
        'Personen er registrert som elev i SAS.')
    affiliation_status_elev_aktiv = _PersonAffStatusCode(
        affiliation_elev,
        'aktiv',
        'Eleven har en aktiv tilknytning til skolen, registrert i SAS.')
    affiliation_foresatt = _PersonAffiliationCode('FORESATT',
                                                  'Foresatt registrert i SAS.')
    affiliation_status_foresatt_aktiv = _PersonAffStatusCode(
        affiliation_foresatt,
        'aktiv',
        'Foresatt for elev med aktiv tilknytning til skole, registrert i SAS.')
    affiliation_manuell = _PersonAffiliationCode(
        'MANUELL',
        'Personen er ikke registrert i SAS.')
    affiliation_status_manuell_gjest = _PersonAffStatusCode(
        affiliation_manuell,
        'gjest',
        'Personen er tilknyttet skolen som gjest.')
    affiliation_teacher = _PersonAffiliationCode(
        'LÆRER',
        'Lærer registrert i SAS.')
    affiliation_status_teacher_aktiv = _PersonAffStatusCode(
        affiliation_teacher,
        'aktiv',
        'Lærer aktiv ved en skole.')
    affiliation_tilknyttet = _PersonAffiliationCode(
        'TILKNYTTET',
        'Personen knyttet til organisasjonen')
    affiliation_status_tilknyttet_aktiv = _PersonAffStatusCode(
        affiliation_tilknyttet,
        'aktiv',
        'Person aktiv ved organisasjonen.')
    affiliation_affiliate = _PersonAffiliationCode(
        'AFFILIATE',
        'Personen knyttet til organisasjonen')
    affiliation_status_affiliate_aktiv = _PersonAffStatusCode(
        affiliation_affiliate,
        'aktiv',
        'Person aktiv ved organisasjonen.')


# Account_type codes

    account_test = _AccountCode('test', 'Testkonto')

# Contact_types
    # TBD: contact_job_mobile should be removed. contact_private_mobile is
    # moved to Cerebrum.Constants.CommonConstants
    contact_job_mobile = _ContactInfoCode('JOBMOBILE', 'JOBMOBILE')
    contact_private_email = _ContactInfoCode('PRIVATEEMAIL', 'PRIVATEEMAIL')

# Mail traits
    trait_homedb_info = _EntityTraitCode(
        'homeMDB', Constants.Constants.entity_account,
        'Register Exchange homeMDB for e-mail accounts')
    trait_x400_addr = _EntityTraitCode(
        'x400address', Constants.Constants.entity_account,
        'Register old addresses for e-mail accounts')
    trait_x500_addr = _EntityTraitCode(
        'x500address', Constants.Constants.entity_account,
        'Register old addresses for e-mail accounts')

    # Traits for migrating between versions of Exchange:

    # Marking accounts that are being migrated. Such accounts should not be
    # updated in AD until the migration is done.
    trait_exchange_under_migration = _EntityTraitCode(
        'under_migration',
        Constants.Constants.entity_account,
        "Accounts that is under migrationt to another Exchange version.")
    # Need to differ between migrated and non-migrated accounts
    trait_exchange_migrated = _EntityTraitCode(
        'exch_migrated',
        Constants.Constants.entity_account,
        "Account that has been migrated to a newer Exchange version.")

# Group traits
    trait_group_imported = _EntityTraitCode(
        'imported_group', Constants.Constants.entity_group,
        'Register last_seen date for groups imported from by ABC')
    trait_group_derived = _EntityTraitCode(
        'internal_group', Constants.Constants.entity_group,
        'Register last_seen date for internaly created groups')
    trait_group_affiliation = _EntityTraitCode(
        'aff_group', Constants.Constants.entity_group,
        'Tag groups created to become affiliation groups.')
    # tag shadow groups as "undervisningsgruppe" and "klassegruppe"
    trait_shdw_undv = _EntityTraitCode(
        'undv_group', Constants.Constants.entity_group,
        'Tag groups created to represent "undervisningsgruppe".')
    trait_shdw_kls = _EntityTraitCode(
        'kls_group', Constants.Constants.entity_group,
        'Tag groups created to represent "klassegruppe".')
    # tag affiliation based auto-groups
    trait_auto_aff = _EntityTraitCode(
        'auto_group', Constants.Constants.entity_group,
        'Tag affiliations based automatic groups.')
    # Guardianship-related traits
    trait_guardian_of = _EntityTraitCode(
        'guardian_of', Constants.Constants.entity_person,
        'Register guardees for this person')
    trait_guardian_urls = _EntityTraitCode(
        'guardian_urls', Constants.Constants.entity_person,
        'Register urls for this person')


# SMS traits
    trait_sms_reminder = _EntityTraitCode(
        'sms_reminder', Constants.Constants.entity_account,
        'Tagging that an SMS has been sent')
