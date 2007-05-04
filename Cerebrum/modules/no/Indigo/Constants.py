# -*- coding: iso-8859-1 -*-
# Copyright 2005 University of Oslo, Norway
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
from Cerebrum.Constants import _AuthoritativeSystemCode, \
                               _EntityExternalIdCode, \
                               _SpreadCode, \
                               _PersonAffiliationCode, \
                               _PersonAffStatusCode, \
                               _AccountCode, \
                               _AuthenticationCode, \
                               _OUPerspectiveCode, \
                               _ContactInfoCode
from Cerebrum.modules.EntityTrait import _EntityTraitCode

class Constants(Constants.Constants):

## Org. hierarchy perspective
    perspective_ekstens = _OUPerspectiveCode('Ekstens', 'Ekstens')
    perspective_sats = _OUPerspectiveCode('SATS', 'SATS')

## Authoritative system codes
    system_sats = _AuthoritativeSystemCode('SATS',
                                           'Personopplysninger hentet fra skolesystemet SATS')
    system_ekstens = _AuthoritativeSystemCode('EKSTENS',
                                              'Personopplysninger hentet fra skolesystemet EKSTENS')
    system_tpsys = _AuthoritativeSystemCode('TPSYS',
                                            'Personopplysninger hentet fra skolesystemet TPSYS')
    system_migrate =_AuthoritativeSystemCode('MIGRATE',
                                            'Personopplysninger hentet fra tidligere brukte systemer')
    
## External ID codes
    externalid_orgnr = _EntityExternalIdCode('ORGNR',
                                             Constants.Constants.entity_ou,
                                             'Organisasjonsnummer (fra SAS)')
## Disse kodene er det foreløpig usikkert om skal brukes
    externalid_ouid = _EntityExternalIdCode('OUID',
                                            Constants.Constants.entity_ou,
                                            'Organisasjonens unike identifikator')
##     externalid_vigonr = _EntityExternalIdCode('VIGONR',
##                                               Constants.Constants.entity_ou,
##                                               'VIGO-nummer')
    externalid_skolenr = _EntityExternalIdCode('SKOLENR',
                                               Constants.Constants.entity_ou,
                                               'Skolenummer')
    externalid_kommunenr = _EntityExternalIdCode('KOMMNR',
                                                 Constants.Constants.entity_ou,
                                                 'Kommunenummer')
    externalid_ou_oid = _EntityExternalIdCode('OUOID',
                                              Constants.Constants.entity_ou,
                                              'OU OID')
    externalid_elevnr = _EntityExternalIdCode('ELEVNR',
                                              Constants.Constants.entity_person,
                                              'Unik elevnummer fra SAS.')
    externalid_ansattnr = _EntityExternalIdCode('ANSATTNR',
                                                Constants.Constants.entity_person,
                                                'Unik ansattnummer fra SAS')
    externalid_userid = _EntityExternalIdCode('USERID',
                                              Constants.Constants.entity_person,
                                              'Bruker ID')
    externalid_person_oid = _EntityExternalIdCode('POID',
                                                  Constants.Constants.entity_person,
                                                  'Person OID')
    externalid_klasse = _EntityExternalIdCode('kl-ID',
                                                Constants.Constants.entity_group,
                                                'Klasse ID')
    externalid_faggruppe = _EntityExternalIdCode('fg-ID',
                                              Constants.Constants.entity_group,
                                              'Faggruppe ID')
    externalid_klassegruppe = _EntityExternalIdCode('kg-ID',
                                                  Constants.Constants.entity_group,
                                                  'klassegruppe ID')


## Spread codes
    ## AD
    spread_ad_acc = _SpreadCode('account@ad', Constants.Constants.entity_account,
                                'Brukeren kan logge inn på Windows PC-er.')
    spread_ad_grp = _SpreadCode('group@ad', Constants.Constants.entity_group,
                                'Gruppen brukes av Active Directory.')
    spread_ad_ou = _SpreadCode('ou@ad', Constants.Constants.entity_ou,
                                'OUen brukes av Active Directory.')
    ## LMS
    spread_lms_acc = _SpreadCode('account@lms', Constants.Constants.entity_account,
                                 'Brukeren kan logge inn på LMS (f.eks. Classfronter).')
    spread_lms_grp = _SpreadCode('group@lms', Constants.Constants.entity_group,
                                 'Gruppen brukes av LMS-et.')
    spread_lms_per = _SpreadCode('person@lms', Constants.Constants.entity_person,
                                 'Person kjent i organisasjonens LMS')
    ## OID
    spread_oid_acc = _SpreadCode('account@oid', Constants.Constants.entity_account,
                                 'Brukeren kan logge inn på webportalen (OCS).')
    spread_oid_grp = _SpreadCode('group@oid', Constants.Constants.entity_group,
                                 'Gruppen brukes av webportalen (OCS).')
    ## LDAP
    spread_ldap_per = _SpreadCode('person@ldap', Constants.Constants.entity_person,
                                  'Brukeren kan benytte seg av FEIDE-innlogging.')
    spread_ldap_grp = _SpreadCode('group@ldap', Constants.Constants.entity_group,
                                  'Gruppen brukes i LDAP.')
    
## Affiliation codes
    affiliation_ansatt = _PersonAffiliationCode('ANSATT',
                                                'Personen er registrert som ansatt i SAS.')
    affiliation_status_ansatt_aktiv = _PersonAffStatusCode(affiliation_ansatt,
                                                           'aktiv',
                                                           'Personen har aktiv tilsetting, registrert i SAS.')
    affiliation_elev = _PersonAffiliationCode('ELEV',
                                              'Personen er registrert som elev i SAS.')
    affiliation_status_elev_aktiv = _PersonAffStatusCode(affiliation_elev,
                                                         'aktiv',
                                                         'Eleven har en aktiv tilknytning til skolen, registrert i SAS.')
    affiliation_foresatt = _PersonAffiliationCode('FORESATT',
                                                  'Foresatt registrert i SAS.')
    affiliation_status_foresatt_aktiv = _PersonAffStatusCode(affiliation_foresatt,
                                                             'aktiv',
                                                             'Foresatt for elev med aktiv tilknytning til skole, registrert i SAS.')
    affiliation_manuell = _PersonAffiliationCode('MANUELL',
                                                 'Personen er ikke registrert i SAS.')
    affiliation_status_manuell_gjest = _PersonAffStatusCode(affiliation_manuell,
                                                            'gjest',
                                                             'Personen er tilknyttet skolen som gjest.')
    affiliation_teacher = _PersonAffiliationCode('LÆRER',
                                                  'Lærer registrert i SAS.')
    affiliation_status_teacher_aktiv = _PersonAffStatusCode(affiliation_teacher,
                                                             'aktiv',
                                                             'Lærer aktiv ved en skole.')

## Account_type codes

    account_test = _AccountCode('test', 'Testkonto')

## Contact_types

    contact_job_mobile = _ContactInfoCode('JOBMOBILE', 'JOBMOBILE')
    contact_private_mobile = _ContactInfoCode('PRIVATEMOBILE', 'PRIVATEMOBILE')
    contact_private_email = _ContactInfoCode('PRIVATEEMAIL', 'PRIVATEEMAIL')

## Group traits
    trait_group_imported = _EntityTraitCode(
        'imported_group', Constants.Constants.entity_group,
        'Register last_seen date for groups imported from by ABC')
    trait_group_derived = _EntityTraitCode(
        'internal_group', Constants.Constants.entity_group,
        'Register last_seen date for internaly created groups')
    trait_group_affiliation = _EntityTraitCode(
        'aff_group', Constants.Constants.entity_group,
        'Tag groups created to become affiliation groups.')
    
# arch-tag: 82109000-67f8-11da-8454-871df49a59c9
