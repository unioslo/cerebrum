# -*- coding: utf-8 -*-
#
# Copyright 2005-2026 University of Oslo, Norway
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
This module provides an interface to store objects representing XML
information in Cerebrum. It is intended to go together with xml2object
module (and its various incarnations (SAP, LT, etc.).
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import collections
import cereconf
import datetime

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.ou_import import legacy_xml2ou
from Cerebrum.modules.ou_import import ou_sync
from Cerebrum.modules.xmlutils.xml2object import DataAddress, DataContact
from Cerebrum.modules.xmlutils.xml2object import HRDataPerson
from Cerebrum.utils import date_compat


class XML2Cerebrum(object):

    # Map a legacy xml DataOU object to a PreparedOrgUnit for the ou writer.
    ou_mapper = legacy_xml2ou.LegacyObjectMapper()

    def __init__(self, db, source_system, logger, ou_ldap_visible=True):
        self.db = db
        # IVR 2007-01-22 TBD: Do we really want this here? Should db
        # not have this set already?
        self.db.cl_init(change_program="XML->Cerebrum")
        self.source_system = source_system
        self.ou_ldap_visible = ou_ldap_visible
        self.ou_writer = ou_sync.OuWriter(db, source_system,
                                          publish_all=ou_ldap_visible)

        self.stedkode = Factory.get("OU")(db)
        self.person = Factory.get("Person")(db)
        self.constants = Factory.get("Constants")(db)
        self.lang_priority = ("no", "en")
        self.logger = logger

        const = self.constants
        # Hammer in contact information
        self.xmlcontact2db = {DataContact.CONTACT_PHONE: const.contact_phone,
                              DataContact.CONTACT_FAX: const.contact_fax,
                              DataContact.CONTACT_URL: const.contact_url,
                              DataContact.CONTACT_EMAIL: const.contact_email,
                              DataContact.CONTACT_PRIVPHONE:
                              const.contact_phone_private,
                              DataContact.CONTACT_MOBILE_WORK:
                              const.contact_mobile_phone,
                              DataContact.CONTACT_MOBILE_PRIVATE:
                              const.contact_private_mobile,
                              DataContact.CONTACT_MOBILE_PRIVATE_PUBLIC:
                              const.contact_private_mobile_visible}

        self.xmladdr2db = {DataAddress.ADDRESS_BESOK: const.address_street,
                           DataAddress.ADDRESS_POST: const.address_post,
                           DataAddress.ADDRESS_PRIVATE:
                           const.address_post_private}
        if hasattr(const, 'address_other_post'):
            self.xmladdr2db[
                DataAddress.ADDRESS_OTHER_POST] = const.address_other_post
        if hasattr(const, 'address_other_street'):
            self.xmladdr2db[
                DataAddress.ADDRESS_OTHER_BESOK] = const.address_other_street

        self.idxml2db = {
            HRDataPerson.NO_SSN: const.externalid_fodselsnr,
            HRDataPerson.PASSNR: const.externalid_pass_number,
        }

    def locate_or_create_person(self, xmlperson, dbperson):
        """Locate (or indeed create) the proper person entity in the db.

        An external system (e.g. SAP) uses several external IDs to identify a
        person. None of the IDs are permanent in practice. This means that
        logically the 'same' person can change (some of the) IDs between runs
        of this script.

        This method looks up all IDs present in xmlperson, and associates
        dbperson with the proper person object in Cerebrum, provided that:

        - All external IDs point to the same person_id in Cerebrum (this is
          the situation when there are no ID changes for the person)
        - Some external IDs point to the same person_id in Cerebrum, whereas
          others do not exist in Cerebrum (this is the situation when new IDs
          are given to the person)
        - The IDs point to different person_ids in Cerebrum. This is
          potentially an error, so we implement the following changes:

          * const.externalid_fodselsnr can be changed. All other IDs have to
            match.
          * SAP ansatt# cannot be changed (they are supposed to be permanent
            and unique).

        @param xmlperson
          Object representation of the source XML element describing one
          person.
        @type xmlperson : instance of L{HRDataPerson}

        @param dbperson
          Object to associate with a person's representation in Cerebrum
        @type dbperson : instance of Factory.get('Person')(db)

        @return
          dbperson is clear()'ed and re-populated. If the person cannot be
          assigned IDs from xmlperson, no guarantees are made about the state
          of dbperson.
        """

        id_collection = list()
        for kind, id_on_file in xmlperson.iterids():
            # If a new ID appears, do not roll over and die
            if kind not in self.idxml2db:
                self.logger.error("New(?) external ID type %s will be ignored "
                                  "while locating person %s",
                                  kind, list(xmlperson.iterids()))
                continue

            # Now the ID type is known and we can try to locate the person
            try:
                dbperson.clear()
                dbperson.find_by_external_id(self.idxml2db[kind], id_on_file)
                if int(dbperson.entity_id) not in id_collection:
                    id_collection.append(int(dbperson.entity_id))
            except Errors.NotFoundError:
                # This is a new ID of this type for this source system; that
                # is perfectly fine.
                self.logger.debug("New or changing ID from file (type: %s "
                                  "value %s)", kind, id_on_file)
            except Errors.TooManyRowsError:
                dbperson.clear()
                try:
                    dbperson.find_by_external_id(self.idxml2db[kind],
                                                 id_on_file,
                                                 self.source_system)
                    if int(dbperson.entity_id) not in id_collection:
                        id_collection.append(int(dbperson.entity_id))
                except Errors.NotFoundError:
                    # Same as before
                    self.logger.debug(
                        "New ID from file for source %s (type: %s value %s)",
                        self.source_system, kind, id_on_file)

        # Now that we are done with the IDs, we can run some checks and report
        # on the inconsistencies
        if len(id_collection) > 1:
            self.logger.error("Person on file with IDs %s maps to several"
                              " person_ids in Cerebrum (%s)."
                              " Manual intervention"
                              " required. No changes made in Cerebrum",
                              list(xmlperson.iterids()), id_collection)
            return False

        dbperson.clear()
        # We have a person_id that we have to update (potentially with some of
        # the new IDs)
        if len(id_collection) == 1:
            self.logger.debug("One person_id exists for %s: %s",
                              list(xmlperson.iterids()), id_collection)
            dbperson.find(id_collection[0])

            # IVR 2007-08-21 We cannot allow automatic ansatt# changes
            if not self.match_sap_ids(xmlperson, dbperson):
                self.logger.error(
                    "SAP ID on file does not match SAP ID in Cerebrum for "
                    "file ids %s. This is an error. Person is "
                    "ignored. This has to be corrected manually.",
                    list(xmlperson.iterids()))
                return False
        else:
            self.logger.debug(
                "No person in cerebrum located for XML element with IDs: %s",
                list(xmlperson.iterids()))

        return True

    def match_sap_ids(self, xmlperson, dbperson):
        "Check if SAP IDs (ansatt#) on file matches the value in Cerebrum."

        sap_id_on_file = xmlperson.get_id(xmlperson.SAP_NR)
        sap_id_in_db = ""
        row = dbperson.get_external_id(self.source_system,
                                       self.constants.externalid_sap_ansattnr)
        if row:
            sap_id_in_db = row[0]["external_id"]

        # Either the DB is empty (a new ID is allowed) or they *MUST* match
        return (sap_id_in_db == "") or (sap_id_on_file == sap_id_in_db)

    def store_person(self, xmlperson, work_titles, affiliations, traits):
        """Store all information we can from xmlperson.

        @type xmlperson:
          An instance of xml2object.DataPerson or its subclasses.
        @param xmlperson:
          An object representing the person we want to register. This person
          may already exist in the database, and the IDs of xmlperson may be
          inconsistent with the information in Cerebrum.

        @type work_titles: sequence of DataName entries.
        @param work_title:
          Work titles for a person. There may be several, since we support
          multiple languages.

        @type affiliations: set (of quadruples)
        @param affiliations:
          A set of affiliations to be assigned to this person. The
          affiliations are calculated elsewhere on the basis of employment
          information available in L{xmlperson}.

          The structure of the set is described in
          L{import_HR_person.py:determine_affiliations}.

        @type traits: sequence (of triples)
        @param traits:
          A sequence of traits to be assigned to this person. The traits are
          calculated elsewhere on the basis of employment and role information
          available in L{xmlperson}. Each element of the sequence is a triple
          (trait, ou_id, roleid), with the trait, ou and a textual role
          description for that trait.

        @rtype: tuple (basestring, int)
        @return:
          The method returns a pair (status, p_id), where status is the update
          status of the operation, and p_id is the entity_id in Cerebrum of a
          person corresponding to xmlperson.

          If the update failed for some reasong, the tuple ('INVALID', <junk>)
          is returned; no guarantees are made about the type/content of
          <junk>.

          If the update succeeds, status is one of 'NEW', 'UPDATE' or 'EQUAL',
          representing a new person entity, an update for an existing person
          entity or a no-op respectively. The p_id is the person_id of the
          person affected by the operation.
        """

        person = self.person
        const = self.constants
        source_system = self.source_system

        gender2db = {xmlperson.GENDER_MALE: const.gender_male,
                     xmlperson.GENDER_FEMALE: const.gender_female, }
        name2db = {xmlperson.NAME_FIRST: const.name_first,
                   xmlperson.NAME_LAST: const.name_last, }

        idxml2db = self.idxml2db
        xmlcontact2db = self.xmlcontact2db

        # If we cannot coincide IDs on file with IDs on Cerebrum, the person
        # is skipped.
        if not self.locate_or_create_person(xmlperson, person):
            return "INVALID", None

        person.populate(xmlperson.birth_date, gender2db[xmlperson.gender])
        person.affect_names(source_system, *name2db.values())
        # TBD: This may be too permissive
        person.affect_external_id(source_system, *idxml2db.values())

        # We *require* certain names
        for id in (xmlperson.NAME_FIRST, xmlperson.NAME_LAST,):
            # There should be exactly one, actually
            assert len(xmlperson.get_name(id, None)) == 1
            name = xmlperson.get_name(id)[0].value
            person.populate_name(name2db[id], name)
        # od

        # TBD: The implicit assumption here is that idxml2db contains all the
        # mappings
        for xmlkind, value in xmlperson.iterids():
            person.populate_external_id(
                source_system,
                idxml2db[xmlkind],
                value)
        op = person.write_db()

        # remove existing personal titles to make sure that personal
        # titles removed from SAP are removed from Cerebrum as well
        # all such titles are removed for each run, this may be very
        # slightly inefficient
        if xmlperson.get_name(xmlperson.NAME_TITLE, ()) == ():
            person.delete_name_with_language(name_variant=const.personal_title)
            # updating op2 here is void as we remove every title every run
            person.write_db()
            self.logger.debug(
                "Dropped all personal titles for person %s",
                person.entity_id)

        # add personal titles if any are found in the file
        for personal_title in xmlperson.get_name(xmlperson.NAME_TITLE, ()):
            # self.logger.debug('personal_title %s, lang %s',
            #                   personal_title.value,
            #                   personal_title.language)
            language = int(const.LanguageCode(personal_title.language))
            person.add_name_with_language(name_variant=const.personal_title,
                                          name_language=language,
                                          name=personal_title.value)

        for work_title in work_titles:
            language = int(const.LanguageCode(work_title.language))
            person.add_name_with_language(name_variant=const.work_title,
                                          name_language=language,
                                          name=work_title.value)
        #
        # FIXME: LT data.
        #
        # This one isn't pretty. The problem is that in LT some of the
        # addresses (e.g. ADDRESS_POST) have to be derived from the addresses
        # of the "corresponding" OUs. This breaks quite a few abstractions in
        # this code.
        #

        for addr_kind in (DataAddress.ADDRESS_BESOK, DataAddress.ADDRESS_POST,
                          DataAddress.ADDRESS_PRIVATE,
                          DataAddress.ADDRESS_OTHER_POST,
                          DataAddress.ADDRESS_OTHER_BESOK,):
            addr = xmlperson.get_address(addr_kind)
            if not addr:
                continue

            # FIXME: country-table is not populated in the database. We cannot
            # write anything to the country-slot, until that table is
            # populated.
            person.populate_address(source_system,
                                    type=self.xmladdr2db[addr_kind],
                                    address_text=addr.street or None,
                                    postal_number=addr.zip or None,
                                    city=addr.city or None,)
        # od

        self._assign_person_affiliations(person, source_system, affiliations)
        self._assign_person_traits(person, traits)

        person.populate_contact_info(source_system)
        for ct in xmlperson.itercontacts():
            person.populate_contact_info(source_system,
                                         xmlcontact2db[ct.kind],
                                         ct.value, ct.priority)
        op2 = person.write_db()

        if op is None and op2 is None:
            status = "EQUAL"
        elif bool(op):
            status = "NEW"
        else:
            status = "UPDATE"

        return status, person.entity_id

    @staticmethod
    def _calculate_precedence(source_system, main):
        """Helper method for getting precedence for main employment."""
        if main:
            p = cereconf.PERSON_AFFILIATION_PRECEDENCE_RULE
            p = p[str(source_system)] if str(source_system) in p else p['*']
            if isinstance(p, collections.Mapping):
                key = 'xmlutils:main'
                return p.get(key)
        return None

    def _assign_person_affiliations(self, person, source_system, affiliations):
        """Assign affiliations to person.

        @type person: An instance of Factory.get('Person')
        @param person:
          A Person object representing an *existing* person entity in
          Cerebrum.

        @param source_system:
          Source_system for which the affiliation assignment is to be
          performed.

        @type affiliations: set (of quadruples)
        @param affiliations:
          See L{import_HR_person.py:determine_affiliations} for the
          description.

        @return: Nothing
        """

        person.populate_affiliation(source_system)
        for ou_id, aff, aff_stat, main_empl in affiliations:
            person.populate_affiliation(source_system, ou_id,
                                        int(aff), int(aff_stat),
                                        self._calculate_precedence(
                                            source_system, main_empl))
            self.logger.info("Person id=%s acquires affiliation "
                             "aff=%s status=%s ou_id=%s",
                             person.entity_id,
                             self.constants.PersonAffiliation(aff),
                             self.constants.PersonAffStatus(aff_stat),
                             ou_id)

    def _assign_person_traits(self, person, traits):
        """Assign HR-data originated traits to a person.

        HR source data contains some information which we want to mirror in
        Cerebrum as traits. The traits pertinent to each person are collected
        elsewhere and passed to this method for registering in Cerebrum.

        @type person: an instance of Factory.get('Person')
        @param person:
          A Person object representing an *existing* person entity in
          Cerebrum. This person will receive traits.

        @type traits: sequence
        @param traits:
          Cf. L{store_person}
        """

        # 2008-01-15 IVR: Potentially, we may have to do much more than this.
        for trait, ou_id, roleid in traits:
            # strval is mainly to make it easier to deduce the role that gave
            # a certain trait. This is needed later (in populate-auto-groups)
            # to *automatically* create group descriptions with sensible
            # names.
            person.populate_trait(trait, target_id=ou_id, strval=roleid)
            self.logger.info("Person id=%s acquires trait %s "
                             "target_id=%s strval=%s",
                             person.entity_id,
                             self.constants.EntityTrait(trait),
                             ou_id, roleid)

    def __ou_is_expired(self, xmlou):
        """Check if OU is expired compared to today's date."""
        end_date = date_compat.get_date(xmlou.end_date)
        return end_date and end_date < datetime.date.today()

    def store_ou(self, xmlou):
        """
        Store DataOU data in Cerebrum.

        :param DataOU xmlou:
            Object parsed from xml file using system2parser

        :rtype: Cerebrum.OU.OU
        """
        prepared_ou = self.ou_mapper.prepare(xmlou)
        return self.ou_writer.sync_ou(prepared_ou)
