# -*- coding: utf-8 -*-
# Copyright 2006-2018 University of Oslo, Norway
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
"""
Constants common for higher education institutions in Norway.
"""
from __future__ import unicode_literals


from Cerebrum import Constants
from Cerebrum.Constants import (
    _AccountCode,
    _AuthoritativeSystemCode,
    _ContactInfoCode,
    _EntityExternalIdCode,
    _GroupTypeCode,
    _OUPerspectiveCode,
    _PersonAffStatusCode,
    _PersonAffiliationCode,
    _PersonNameCode,
    _QuarantineCode,
    _SpreadCode,
)
from Cerebrum.modules.bofhd.bofhd_constants import _AuthRoleOpCode
from Cerebrum.modules.EntityTraitConstants import _EntityTraitCode


class ConstantsActiveDirectory(Constants.Constants):

    """ AD constants for the old AD-sync.

    Should be removed when everyone has migrated to the AD sync from 2013.

    """

    # FIXME: This Constants-class will eventually be moved to an AD-modul.
    # Jazz, 2009-03-18
    system_ad = _AuthoritativeSystemCode(
        'AD', 'Information from Active Directory')

    externalid_groupsid = _EntityExternalIdCode(
        'AD_GRPSID', Constants.Constants.entity_group,
        "Group's SID, fetched from Active Directory")
    externalid_accountsid = _EntityExternalIdCode(
        'AD_ACCSID', Constants.Constants.entity_account,
        "Account's SID, fetched from Active Directory")
    trait_exchange_mdb = _EntityTraitCode(
        'exchange_mdb', Constants.Constants.entity_account,
        "The assigned mailbox-database in Exchange for the given account.")
    # traits used to "exempt" entities from being exported to AD2
    trait_account_exempt = _EntityTraitCode(
        'account_exempt', Constants.Constants.entity_account,
        'Exempt the given account from being exported')
    trait_group_exempt = _EntityTraitCode(
        'group_exempt', Constants.Constants.entity_group,
        'Exempt the given group from being exported')


class ConstantsCommon(Constants.Constants):
    """ Constants that every instance should have. """

    """ Common constants for all Norwegian installations. """

    # external id definitions (NO_NIN, norwegian national id number)
    externalid_fodselsnr = _EntityExternalIdCode(
        'NO_BIRTHNO', Constants.Constants.entity_person,
        'Norwegian national ID number')

    @staticmethod
    def make_passport_number(country, passport_number):
        return '{}-{}'.format(country, passport_number)

    # External IDs related to A-melding.
    externalid_pass_number = _EntityExternalIdCode(
        'PASSNR', Constants.Constants.entity_person,
        "A persons passport number")

    system_override = _AuthoritativeSystemCode(
        'Override', 'Override information fetched from authoritative systems')

    spread_ou_publishable = _SpreadCode(
        'publishable_ou', Constants.Constants.entity_ou,
        'OUs publishable in online directories')

    quarantine_autopassord = _QuarantineCode(
        'autopassord', 'Passord ikke skiftet trass pålegg')

    quarantine_svakt_passord = _QuarantineCode(
        'svakt_passord', 'For dårlig passord')

    trait_auto_group = _EntityTraitCode(
        'auto_group', Constants.Constants.entity_group,
        "Trait marking automatically administered groups with person members.")

    trait_auto_meta_group = _EntityTraitCode(
        'auto_meta_group', Constants.Constants.entity_group,
        "Trait marking automatically administered groups with group members.")

    trait_personal_dfg = _EntityTraitCode(
        'personal_group', Constants.Constants.entity_group,
        "Group is a personal file group.")

    trait_group_entitlement = _EntityTraitCode(
        'entitlement', Constants.Constants.entity_group,
        "Trait listing entitlement that members of this group have")

    trait_group_expire_notify = _EntityTraitCode(
        'expire_notify', Constants.Constants.entity_group,
        "If an admin has been notified that the group is expiring soon")

    # Traits for the password service (Individuation)
    trait_password_token = _EntityTraitCode(
        "password_token", Constants.Constants.entity_account,
        "Store a one time password for an account")

    trait_browser_token = _EntityTraitCode(
        "browser_token", Constants.Constants.entity_account,
        "Store a browser token for an account")

    trait_password_failed_attempts = _EntityTraitCode(
        "passw_attempts", Constants.Constants.entity_account,
        "Number of times an account has tried to use sms password service")

    # Trait for reservation from the new password service
    # TODO: should be replaced by a reservation table later
    trait_reservation_sms_password = _EntityTraitCode(
        'reserve_passw', Constants.Constants.entity_account,
        "Reserving account from using the forgotten password service (SMS)")

    # Trait for reservation from being published at the web
    # TODO: should be replaced by a reservation table later
    trait_public_reservation = _EntityTraitCode(
        'reserve_public', Constants.Constants.entity_person,
        "Reserved from being published at the web pages")

    # Trait for storing if a user has gotten a welcome SMS.
    trait_sms_welcome = _EntityTraitCode(
        'sms_welcome', Constants.Constants.entity_account,
        "If a user has retrieved a welcome message by SMS")

    # Trait for showing that a user account is either newly created or
    # restored.
    # Used to e.g. send welcome message by SMS. This trait is for all accounts,
    # the trait_student_new should be used for only targeting student accounts.
    trait_account_new = _EntityTraitCode(
        'new_account', Constants.Constants.entity_account,
        "The account is newly created or restored")

    # Trait for tagging important accounts.
    # Special permission is needed to change password for these accounts.
    trait_important_account = _EntityTraitCode(
        "important_acc", Constants.Constants.entity_account,
        "The account is important")

    # Trait for showing that a student account is either newly created or
    # restored. Used to send welcome message by SMS.
    trait_student_new = _EntityTraitCode(
        'new_student', Constants.Constants.entity_account,
        "If the student account is newly created or restored")

    # Traits for SAP medarbeidergrupper
    trait_sap_mg = _EntityTraitCode(
        'sap_mg', Constants.Constants.entity_account,
        "MG from SAP - medarbeidergruppe")
    trait_sap_mug = _EntityTraitCode(
        'sap_mug', Constants.Constants.entity_account,
        "MUG from SAP - medarbeiderundergruppe")

    # Quarantine to be set automatically when cleaning up in persons that are
    # no longer affiliated with the instance
    quarantine_auto_no_aff = _QuarantineCode(
        'auto_no_aff',
        'Ikke tilknyttet person, utestengt')
    quarantine_slutta = _QuarantineCode(
        'slutta',
        'Personen har slutta')


class ConstantsHigherEdu(Constants.Constants):

    # authoritative source systems (FS = student registry, SAP = common
    # HR-system)
    system_fs = _AuthoritativeSystemCode('FS', 'FS')
    system_sap = _AuthoritativeSystemCode('SAP', 'SAP')

    # external id definitions (student and employee id)
    externalid_studentnr = _EntityExternalIdCode(
        'NO_STUDNO', Constants.Constants.entity_person,
        'Student ID number')

    externalid_sap_ansattnr = _EntityExternalIdCode(
        'NO_SAPNO', Constants.Constants.entity_person,
        'Employee ID number')

    externalid_sap_ou = _EntityExternalIdCode(
        "SAP_OU_ID", Constants.Constants.entity_ou,
        'SAP OU identification')

    externalid_uname = _EntityExternalIdCode(
        'UNAME', Constants.Constants.entity_person,
        'User name (external system)')

    # OU-structure perspectives
    perspective_fs = _OUPerspectiveCode('FS', 'FS')
    perspective_sap = _OUPerspectiveCode('SAP', 'SAP')

    # Affiliations for students
    affiliation_student = _PersonAffiliationCode('STUDENT', 'Student')
    affiliation_status_student_evu = _PersonAffStatusCode(
        affiliation_student, 'evu', 'Student, etter og videre utdanning')
    affiliation_status_student_aktiv = _PersonAffStatusCode(
        affiliation_student, 'aktiv', 'Student, aktiv')
    affiliation_status_student_privatist = _PersonAffStatusCode(
        affiliation_student, 'privatist', 'Student, privatist')
    affiliation_status_student_drgrad = _PersonAffStatusCode(
        affiliation_student, 'drgrad', 'Student, drgrad')
    affiliation_status_student_ekstern = _PersonAffStatusCode(
        affiliation_student, 'ekstern', 'Student, ekstern')

    # Affiliations for employees
    affiliation_ansatt = _PersonAffiliationCode('ANSATT', 'Ansatt')
    affiliation_status_ansatt_vitenskapelig = _PersonAffStatusCode(
        affiliation_ansatt, 'vitenskapelig', 'Ansatt, vitenskapelig')
    affiliation_status_ansatt_tekadm = _PersonAffStatusCode(
        affiliation_ansatt, 'tekadm', 'Ansatt, teknisk-administrativ')

    spread_ldap_group = _SpreadCode(
        'group@ldap', Constants.Constants.entity_group,
        'Gruppen eksporteres til gruppetreet i LDAP')

    # this should not really be her and it will be removed when the
    # bofhd-restructuring is done. for now it solves our problems
    # with bofhd_uio_cmds-copies in use.
    # bofhd constants
    auth_rt_create = _AuthRoleOpCode(
        'rt_create', 'Create e-mail target for Request Tracker')
    auth_rt_replace = _AuthRoleOpCode(
        'rt_replace', 'Replace existing mailing list with Request Tracker')
    auth_rt_addr_add = _AuthRoleOpCode(
        'rt_addr_add', 'Add e-mail address to Request Tracker target')

    # group type for <inst>/populate-fronter-groups.py
    group_type_lms = _GroupTypeCode(
        'lms-group',
        'Automatic group - generated for LMS from FS student roles')


class ConstantsUniversityColleges(Constants.Constants):

    # Source systems
    system_migrate = _AuthoritativeSystemCode('MIGRATE', 'Migrate from files')
    system_manual = _AuthoritativeSystemCode('MANUELL',
                                             'Manually added information')

    # Affiliation for associated people
    affiliation_tilknyttet = _PersonAffiliationCode(
        'TILKNYTTET', 'Assosiert, reg. i kildesystem')
    affiliation_status_tilknyttet_fagperson = _PersonAffStatusCode(
        affiliation_tilknyttet,
        'fagperson',
        'Registrert i FS, fagperson')
    affiliation_status_tilknyttet_pensjonist = _PersonAffStatusCode(
        affiliation_tilknyttet,
        'pensjonist',
        'Registrert i HR, pensjonist')
    affiliation_status_tilknyttet_bilag = _PersonAffStatusCode(
        affiliation_tilknyttet,
        'bilag',
        'Registrert i HR, bilagslønnet')
    affiliation_status_tilknyttet_time = _PersonAffStatusCode(
        affiliation_tilknyttet,
        'timelønnet',
        'Registrert i HR, timelønnet')
    affiliation_status_tilknyttet_gjest = _PersonAffStatusCode(
        affiliation_tilknyttet,
        'gjest',
        'Registrert i HR, gjest')
    affiliation_status_tilknyttet_gjestefors = _PersonAffStatusCode(
        affiliation_tilknyttet,
        'gjesteforsker',
        'Registrert i HR, gjesteforsker')

    affiliation_status_tilknyttet_nosrc = _PersonAffStatusCode(
        affiliation_tilknyttet,
        'nosource',
        'Ekstern person, ltilknyttet uten rgistrering')
    affiliation_tilknyttet_fagperson = _PersonAffStatusCode(
        affiliation_tilknyttet,
        'fperson',
        'Dummy, do not use')

    # quarantine definitions
    quarantine_generell = _QuarantineCode(
        'generell', 'Generell sperring')
    quarantine_teppe = _QuarantineCode(
        'teppe', 'Kalt inn til samtale')
    quarantine_auto_emailonly = _QuarantineCode(
        'kunepost', 'Ikke ordinær student, tilgang til bare e-post')

    quarantine_system = _QuarantineCode(
        'system', 'Systembruker som ikke skal logge inn')

    # Cerebrum (internal), used by automagic only
    quarantine_auto_inaktiv = _QuarantineCode(
        'auto_inaktiv', 'Ikke aktiv student, utestengt')

    quarantine_autoemailonly = _QuarantineCode(
        'auto_kunepost', 'Privatist, kun tilgang til e-post')

    quarantine_ou_notvalid = _QuarantineCode(
        'ou_notvalid', 'Sted ugyldig i autoritativ kildesystem')

    quarantine_ou_remove = _QuarantineCode(
        'ou_remove', 'Sted fjernet fra autoritativ kildesystem')

    # Non-personal account codes
    account_test = _AccountCode('testbruker', 'Testkonto')
    account_kurs = _AccountCode('kursbruker', 'Kurskonto')
    account_studorg = _AccountCode(
        'studorgbruker',
        'Studentorganisasjonsbruker')
    account_felles = _AccountCode('fellesbruker', 'Fellesbruker')
    account_system = _AccountCode('systembruker', 'Systembruker')

    # SAP name constants
    name_middle = _PersonNameCode('MIDDLE', 'Mellomnavn')
    name_initials = _PersonNameCode('INITIALS', 'Initialer')

    # Contact info
    contact_office = _ContactInfoCode(
        'OFFICE',
        'Office address (building code and room number')

    # SAP comm. constants
    contact_phone_cellular = _ContactInfoCode(
        "CELLPHONE", "Mobiltelefonnr")

    contact_phone_cellular_private = _ContactInfoCode(
        "PRIVCELLPHONE", "Privat mobiltefonnr")

    # Spread definitions - user related
    spread_ldap_account = _SpreadCode(
        'account@ldap', Constants.Constants.entity_account,
        'Brukeren kjent i LDAP (FEIDE)')

    spread_lms_account = _SpreadCode(
        'account@lms', Constants.Constants.entity_account,
        'Brukeren kjent i LMSen')

    # Spread definitions - guest user related
    spread_ad_guest = _SpreadCode(
        'guest_account@ad', Constants.Constants.entity_account,
        'Guest account included in Active Directory')

    # Spread definitions - person related
    spread_ldap_person = _SpreadCode(
        'person@ldap', Constants.Constants.entity_person,
        'Person kjent i organisasjonstreet (FEIDE-person)')

    spread_lms_person = _SpreadCode(
        'person@lms', Constants.Constants.entity_person,
        'Person kjent i organisasjonens LMS')

    # Spread definitions - group related
    spread_lms_group = _SpreadCode(
        'group@lms', Constants.Constants.entity_group,
        'Gruppen kjent i LMS')

    # Spread definitions - ou related
    spread_ou_to_cristin = _SpreadCode(
        'CRIS_OU', Constants.Constants.entity_ou,
        'OU to be exported to Cristin')
#
#  SAP magic below
#
#  stillingstype        - hoved/bistilling
#  lønnstittel          - work title (sendemann, ekspedisjonssjef, etc)


class SAPStillingsTypeKode(Constants._CerebrumCode):

    """ This class represents HOVEDSTILLING, BISTILLING codes. """

    _lookup_table = "[:table schema=cerebrum name=sap_stillingstype]"
# end SAPStillingsType


class SAPLonnsTittelKode(Constants._CerebrumCode):

    """ This class represents lonnstittel (SAP.STELL) codes. """

    _lookup_table = "[:table schema=cerebrum name=sap_lonnstittel]"

    def __init__(self, code, description=None, kategori=None):
        super(SAPLonnsTittelKode, self).__init__(code, description)
        self.kategori = kategori
    # end __init__

    def insert(self):
        self.sql.execute("""
          INSERT INTO %(code_table)s
            (%(code_col)s, %(str_col)s, %(desc_col)s, kategori)
          VALUES
            (%(code_seq)s, :str, :desc, :kategori) """ % {
                         "code_table": self._lookup_table,
                         "code_col": self._lookup_code_column,
                         "str_col": self._lookup_str_column,
                         "desc_col": self._lookup_desc_column,
                         "code_seq": self._code_sequence
                         },
                         {'str': self.str,
                          'desc': self._desc,
                          'kategori': self.kategori,
                          })
    # end insert

    def get_kategori(self):
        if self.kategori is not None:
            return self.kategori
        # fi

        return self.sql.query_1("SELECT kategori FROM %s WHERE code = :code" %
                                self._lookup_table, {'code': int(self)})

    def update(self):
        """
        Updates the description and/or kategori-values for the given constant
        if there are changes from the current database entry.

        :returns: a list with strings containing details about the updates that
                  were performed, or None if no updates were performed.
        :rtype: list or None
        """
        updated_desc = super(SAPLonnsTittelKode, self).update()
        updated_kat = self._update_kategori()

        if updated_desc or updated_kat is not None:
            results = []

            if updated_desc is not None:
                results.extend(updated_desc)
            if updated_kat is not None:
                results.extend(updated_kat)
            return results

    def _update_kategori(self):
        """
        Updates the kategori-value for the given constant if value has changed
        from the current database entry.

        :returns: a string with details of the update that was made.
        :rtype: list or None
        """
        db_kat = self.sql.query_1("SELECT kategori FROM %s WHERE code = %s" %
                                  (self._lookup_table, int(self)))
        if self.kategori != db_kat:
            self.sql.execute("UPDATE %s SET kategori = '%s' WHERE code = %s" %
                             (self._lookup_table, self.kategori, int(self)))
            return ["Updated kategori for '%s': '%s'" % (self, self.kategori)]


class SAPCommonConstants(Constants.Constants):

    """ Common SAP Constants.

    This class embodies all constants common to Cerebrum installations with
    SAP.

    """

    sap_hovedstilling = SAPStillingsTypeKode(
        "H", "Hovedstilling")

    sap_bistilling = SAPStillingsTypeKode(
        "B", "Bistilling")
