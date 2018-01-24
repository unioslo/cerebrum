#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2005-2016 University of Oslo, Norway
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
import collections
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory

from Cerebrum.modules.xmlutils.xml2object import DataAddress, DataContact
from Cerebrum.modules.xmlutils.xml2object import HRDataPerson
from Cerebrum.modules.xmlutils.sapxml2object import SAPPerson

from mx import DateTime


class XML2Cerebrum:

    def __init__(self, db, source_system, logger, ou_ldap_visible=True):
        self.db = db
        # IVR 2007-01-22 TBD: Do we really want this here? Should db
        # not have this set already?
        self.db.cl_init(change_program="XML->Cerebrum")
        self.source_system = source_system
        self.ou_ldap_visible = ou_ldap_visible

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

        self.idxml2db = {HRDataPerson.NO_SSN: const.externalid_fodselsnr,
                         HRDataPerson.PASSNR: const.externalid_pass_number,
                         SAPPerson.SAP_NR: const.externalid_sap_ansattnr, }
    # end __init__

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
                    self.logger.debug("New ID from file for source %s (type: %s"
                                      " value %s)",
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
                self.logger.error("SAP ID on file does not match SAP ID in "
                                  "Cerebrum for file ids %s. This is an error. "
                                  "Person is "
                                  "ignored. This has to be corrected manually.",
                                  list(xmlperson.iterids()))
                return False
        else:
            self.logger.debug(
                "No person in cerebrum located for XML element with IDs: %s",
                list(xmlperson.iterids()))

        return True
    # end locate_or_create_person

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
    # end match_sap_ids

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
    # end store_person

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
    # end _assign_person_affiliations

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
    # end _assign_person_traits

    def __ou_is_expired(self, xmlou):
        """Check if OU is expired compared to today's date."""

        return xmlou.end_date and xmlou.end_date < DateTime.now()
    # end __ou_is_expired

    def store_ou(self, xmlou, old_ou_cache=None):
        """Store all information we can from xmlou.

        xmlou is a class inheriting from xml2object.DataOU.

        old_ou_cache is a cache of ou_ids that already exist in cerebrum (and
        that we might want to clear).

        NB! No parent information is stored in this method.

        The method returns a pair (status, ou_id), where status is the update
        status of the operation, and ou_id is the entity_id in Cerebrum of an
        OU corresponding to xmlou.
        """

        ou = self.stedkode
        ou.clear()
        const = self.constants

        # We need sko, acronym, short_name, display_name, sort_name and parent.
        sko = xmlou.get_id(xmlou.NO_SKO)
        try:
            ou.find_stedkode(sko[0], sko[1], sko[2],
                             cereconf.DEFAULT_INSTITUSJONSNR)
        except Errors.NotFoundError:
            pass
        else:
            #
            # Although it is impossible for an OU *not* to be in cache when we
            # find its sko in find_stedkode() above, *IF* the data source
            # duplicates an OU (clear error in the data source), then this
            # situation still may happen.
            if old_ou_cache and int(ou.entity_id) in old_ou_cache:
                del old_ou_cache[int(ou.entity_id)]
                for r in ou.get_entity_quarantine():
                    if (r['quarantine_type'] == const.quarantine_ou_notvalid or
                            r['quarantine_type'] == const.quarantine_ou_remove):
                        ou.delete_entity_quarantine(r['quarantine_type'])

        # Do not touch name information for an OU that has been expired. It
        # may not conform to all of our requirements.
        if not self.__ou_is_expired(xmlou):
            ou.populate(sko[0], sko[1], sko[2],
                        institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
        else:
            self.logger.debug("OU ids=%s is expired. Its names will not be "
                              "updated", list(xmlou.iterids()))

        self._sync_all_ou_contacts(ou, xmlou)
        self._sync_all_ou_addresses(ou, xmlou)
        op = ou.write_db()

        self._sync_all_ou_names(ou, xmlou)
        op2 = self._sync_all_ou_spreads(ou, xmlou)
        if op is None and not op2:
            status = "EQUAL"
        elif op:
            status = "NEW"
        else:
            status = "UPDATE"

        return status, ou.entity_id
    # end store_ou

    def _sync_all_ou_contacts(self, ou, xmlou):
        """Register all contact information for ou from xmlou."""

        for contact in xmlou.itercontacts():
            ou.populate_contact_info(self.source_system,
                                     self.xmlcontact2db[contact.kind],
                                     contact.value,
                                     contact_pref=contact.priority)
    # end _sync_all_ou_contacts

    def _sync_all_ou_addresses(self, ou, xmlou):
        """Register all addresses for ou from xmlou."""

        for addr_kind, addr in xmlou.iteraddress():
            ou.populate_address(self.source_system,
                                self.xmladdr2db[addr_kind],
                                address_text=addr.street,
                                postal_number=addr.zip,
                                city=addr.city,
                                # TBD: country code table i Cerebrum is empty
                                country=None)
    # end _sync_all_ou_addresses

    def _sync_all_ou_names(self, ou, xmlou):
        """Synchronise name data in all languages for the specified OU.

        Caveat: ou *must* have an entity_id associated with it (i.e. if it's
        populated for the first time, there must be a prior write_db() call).
        """

        co = self.constants
        name_map = {xmlou.NAME_ACRONYM: (co.ou_name_acronym,),
                    xmlou.NAME_SHORT: (co.ou_name_short,),
                    xmlou.NAME_LONG: (co.ou_name, co.ou_name_display,), }
        for (name_kind, names) in xmlou.iternames():
            db_keys = name_map.get(name_kind, ())
            if not db_keys:
                continue

            if not names:
                # If there are no names of the specified type (i.e. db_keys)
                # from the authoritative system, we drop whatever may exist in
                # the db. This corresponds to name data disappearing from the
                # authoritative source
                ou.delete_name_with_language(name_variant=db_keys)
                continue

            for xml_name in names:
                name_language = co.LanguageCode(xml_name.language)
                for db_key in db_keys:
                    ou.add_name_with_language(name_variant=db_key,
                                              name_language=name_language,
                                              name=xml_name.value)
        return ou
    # end _sync_all_ou_names

    def _sync_all_ou_spreads(self, ou, xmlou):
        """Synchronise all spreads for a specified OU.

        ou and xmlou are different representations of the logically same OU.
        """
        const = self.constants

        # 'publishable' -> spread_ou_publishable
        if ((getattr(xmlou, "publishable", False) or self.ou_ldap_visible) and
            not self.__ou_is_expired(xmlou) and
                not ou.has_spread(const.spread_ou_publishable)):
            ou.add_spread(const.spread_ou_publishable)

        # Before we can give a spread, we need an entity_id. Thus, this
        # operation happens after the first write_db().
        if not self.__ou_is_expired(xmlou):
            op = self._sync_auto_ou_spreads(ou, xmlou.iter_usage_codes())
        # For the expired OUs there is no sync -- they loose all spreads.
        else:
            ou_spreads = [int(row["spread"]) for row in ou.get_spread()]
            if ou_spreads:
                self.logger.debug("OU ids=%s loses all spreads %s, since it "
                                  "has expired",
                                  list(xmlou.iterids()),
                                  [str(const.Spread(x)) for x in ou_spreads])
            for spread in ou_spreads:
                ou.delete_spread(spread)
            op = ou.write_db()

        return op
    # end _sync_all_ou_spreads

    def _sync_auto_ou_spreads(self, ou, usage_codes):
        """Synchronise auto-assigned OU spreads for ou.

        @type ou: instance of Factory.get('OU')
        @param ou:
          OU we are processing in this call. The object must be associated
          with an ou in cerebrum.

        @type usage_codes: iterable (over basestrings)
        @param usage_codes:
          A iterable over usage codes that determine L{ou}'s spreads in this
          run. After the method completes, L{ou} has exactly the spreads
          corresponding to L{usage_codes}.

          Caveat 1: Naturally, it is possible to assign spreads only to those
          usage codes that are actually defined in cereconf. If a usage code
          is unknown in cereconf.OU_USAGE_SPREAD, it is simply ignored.

          Caveat 2: If someone removes a mapping from cereconf.OU_USAGE_SPREAD,
          that spread will no longer be automatically administered.

          Caveat 3: We do a sync, not a simple add.
        """

        status = None
        if not hasattr(cereconf, "OU_USAGE_SPREAD"):
            return status

        tmp = cereconf.OU_USAGE_SPREAD
        # IVR 2008-01-31 TBD: obvious optimization -- do not calculate this
        # set every time.
        all_usage_spreads = self._load_usage_spreads(tmp.itervalues(),
                                                     self.constants.entity_ou)
        ou_usage_spreads = self._load_usage_spreads(
            # select those usage codes, that are actually 'mappable'
            [tmp[x] for x in usage_codes if x in tmp],
            self.constants.entity_ou)

        to_remove = all_usage_spreads.difference(ou_usage_spreads)
        for spread in ou_usage_spreads:
            if not ou.has_spread(spread):
                self.logger.debug("adding spread %s to ou id=%s",
                                  self.constants.Spread(spread), ou.entity_id)
                ou.add_spread(spread)
                status = True
        ou.write_db()

        # and now remove the ones that the OU is NOT supposed to have
        # (anymore)
        for spread in to_remove:
            if ou.has_spread(spread):
                self.logger.debug("removing spread %s from ou id=%s",
                                  self.constants.Spread(spread), ou.entity_id)
                ou.delete_spread(spread)
                status = True
        ou.write_db()

        return status
    # end _sync_ou_spreads

    def _load_usage_spreads(self, iterable, desired_entity_type):
        """Convert a sequence of string codes to spread constants.

        This method is meant for internal usage only. It converts an iterable
        into a set of spread constants (ints) that exist in cerebrum.

        @type iterable: an iterator or an iterable sequence
        @param iterable:
          A sequence of spread code_str that we want to have remapped to the
          actual spread codes.

        @type desired_entity_type: instance of EntityTypeCode
        @param desired_entity_type:
          A constant describing the entity type (OU, Person, Group, etc.) to
          which the spreads must be 'tied' (all spreads have an associated
          entity type).

        @rtype: set of ints
        @return:
          A set of spread codes (ints) that correspond to the items in
          L{iterable}. NB! Some elements in iterable may be skipped, if they
          cannot be remapped to a suitable spread.
        """

        const = self.constants
        result = set()
        for item in iterable:
            try:
                spread = int(const.Spread(item))
                if const.Spread(spread).entity_type != desired_entity_type:
                    self.logger.warn("Spread %s is associate with %s, not %s",
                                     spread, const.Spread(spread).entity_type,
                                     desired_entity_type)
                    continue
                result.add(spread)
            except Errors.NotFoundError:
                self.logger.warn("Cowardly refusing to use unknown spread %s",
                                 item)
        return result
    # end _load_usage_spreads
# end XML2Cerebrum
