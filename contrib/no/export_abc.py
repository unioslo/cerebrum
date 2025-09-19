#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006-2025 University of Oslo, Norway
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
Export person information in the ABC Enterprise format.

ABC Enterprise is (or was?) a standard by Uninett (now Sikt) to exchange data
between user management systems (BAS) and student management systems (SAS).

The standard consists of a data model and XML schema definition (XSD).  The
schema includes objects to represent persons, groups, and org units.

The XML description and schema used to be available at
`<http://uninettabc.no/?p=publikasjoner&sub=abc-enterprise>`_.

A typical ABC XML file from Cerebrum would include:

1. A preliminary header with ID and relationship types
2. Organization object and org units
3. Person objects and personal data (ids, names, username, email addresses)
4. Relationships between objects, e.g.:

   - Educational courses/units, and course participation
   - Affiliation - person roles at org units
   - Semester fee payment
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import argparse
import logging
import time

import six

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.argutils
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.utils.transliterate import for_encoding
from Cerebrum.extlib import xmlprinter
from Cerebrum.modules.no import Stedkode
from Cerebrum.modules.no.access_FS import make_fs
from Cerebrum.utils import aggregate
from Cerebrum.utils import sorting
from Cerebrum.utils import date_compat


logger = logging.getLogger(__name__)


def text_decoder(encoding, allow_none=True):
    def to_text(value):
        if allow_none and value is None:
            return None
        if isinstance(value, bytes):
            return value.decode(encoding)
        return six.text_type(value)
    return to_text


def out(element, element_data, attributes={}):
    """Small helper function for XML output.

    The testing happens quite often and I am lazy.
    """
    if element_data or attributes:
        xmlwriter.dataElement(element, element_data, attributes)


def output_ou(sko):
    """Typeset exactly one OU (this happens often enough)."""

    xmlwriter.startElement("org")
    out("orgid",
        six.text_type(cereconf.DEFAULT_INSTITUSJONSNR),
        {"orgidtype": "institusjonsnummer"})
    out("ouid", sko, {"ouidtype": "sko"})
    xmlwriter.endElement("org")


def make_sko(fakultet, institutt, avdeling):
    return "".join(
        format(int(x), '02d')
        for x in (fakultet, institutt, avdeling)
    )


def make_id(*rest):
    """Make an ID out of a sequence."""
    return ":".join(six.text_type(x) for x in rest)


def fnr_to_external_id(fnr, person, person_info):
    """Remap an FNR from FS to an ID we know exists in Cerebrum.

    FS people queries are 'indexed' by fnr. However, it is NOT certain that
    people are in fact identified by FS' fnrs in the XML file. Therefore, a
    remapping takes place.
    """

    try:
        person.clear()
        person.find_by_external_id(constants.externalid_fodselsnr,
                                   fnr,
                                   constants.system_fs)
    except Errors.NotFoundError:
        logger.info("fnr %s is in FS, but not in Cerebrum", fnr)
        return None, None

    if int(person.entity_id) not in person_info:
        logger.info("fnr %s (person_id %d) is in Cerebrum, but not "
                    "in cached data", fnr, person.entity_id)
        return None, None

    id_type, person_external_id = person_info[int(person.entity_id)]
    return id_type, person_external_id


def remap_fnrs(sequence, person, person_info):
    """Remap fnrs in sequence to fnrs that exist in Cerebrum.

    We cannot publish fnr from FS in the xml, as there is no guarantee that
    Cerebrum has these fnrs. The id translation goes like this: we locate
    the person in Cerebrum using the supplied fnr and look him/her up in
    person_info. The id from person_info will be the one used to identify
    the individual.
    """

    result = list()
    for row in sequence:
        fnr = "%06d%05d" % (row["fodselsdato"], row["personnr"])
        id_type, peid = fnr_to_external_id(fnr, person, person_info)
        if id_type is None:
            continue

        result.append((id_type, peid))

    return result


#
# Dictionary for mapping entities/names in cerebrum into XML attribute names
#
_id_type_cache = dict()


def _cache_id_types():
    """Create a cache for looking up various IDs later."""

    c = constants
    for id, xml_name in (("work", "work title"),
                         ("uname", "primary account"),
                         ("email", "primary e-mail address"),
                         ("cell", "cellular phone")):
        _id_type_cache[id] = xml_name

    # <affiliation, status> -> description
    _id_type_cache["affiliation"] = dict()
    for tmp in c.fetch_constants(c.PersonAffStatus):
        aff, status = int(tmp.affiliation), int(tmp)
        _id_type_cache["affiliation"][aff, status] = six.text_type(
            tmp.description)


def get_name_type(name_type):
    return _id_type_cache[name_type]


def get_contact_type(name):
    return _id_type_cache[name]


def get_person_id_type(external_id):
    # FIXME: Perhaps we ought to validate whatever is fed in here.
    return six.text_type(external_id)


def get_affiliation_type(affiliation, status):
    """Return a human-friendly description for a given affiliation/status."""

    title = _id_type_cache["affiliation"][int(affiliation), int(status)]

    # The number pair is for uniqueness (we cannot guarantee that the titles
    # would be unique, and in order to identify a relationship we need a
    # candidate key.
    return title + " (%d:%d)" % (int(affiliation), int(status))


def get_group_id_type(kind):
    """Maps a group id kind to a type in XML"""
    return {"pay": "paid-group",
            "kull": "kullgroup",
            "ue": "uegroup", }[kind]


def get_all_affiliations():
    """Returns all affiliation/status pairs registered."""
    return _id_type_cache["affiliation"].keys()


def _cache_ou2sko(ou):
    """Cache all ou_id -> sko mappings."""

    _cache_ou2sko.cache = dict()
    for row in ou.get_stedkoder():
        sko = make_sko(row["fakultet"], row["institutt"], row["avdeling"])
        _cache_ou2sko.cache[int(row["ou_id"])] = sko


def ou_id2sko(ou_id):
    return _cache_ou2sko.cache.get(int(ou_id))


def prepare_kull():
    """Register all 'kull' groups.

    'Kull' relationships are expressed through the group concept in the
    ABC-schema. Each 'kull' is a <group> entity, and such a group participates
    in two <relation>s -- one that designates the OU that a 'kull' is
    associated with; the other that lists the students that are part of a
    'kull'.

    This function prepares a cache, mapping 'kull' IDs (studieprogramkode,
    terminkode, årstall) to the OU associated with that particular 'kull' ID.
    It also output the corresponding <group> elements.
    """

    logger.debug("Generating <group>-elements for kull")
    kull_cache = dict()
    u = text_decoder(fs_db.db.encoding)

    for row in fs_db.info.list_kull():
        studieprogram = u(row["studieprogramkode"])
        terminkode = u(row["terminkode"])
        arstall = int(row["arstall"])

        internal_id = studieprogram, terminkode, arstall
        if internal_id in kull_cache:
            continue

        xml_id = make_id(*internal_id)
        name_for_humans = "Studiekull %s" % u(row["studiekullnavn"])
        sko = make_sko(*[row[x] for x in ("faknr_studieansv",
                                          "instituttnr_studieansv",
                                          "gruppenr_studieansv")])
        kull_cache[internal_id] = sko

        xmlwriter.startElement("group")
        out("groupid", xml_id, {"groupidtype": get_group_id_type("kull")})
        out("description", transliterate(name_for_humans))
        xmlwriter.endElement("group")

    return kull_cache


def prepare_ue():
    """Output all undervisningsenhet groups.

    The procedure is quite similar to kull.
    """

    logger.debug("Generating <group>-elements for ue")
    ue_cache = dict()
    u = text_decoder(fs_db.db.encoding)

    for row in fs_db.undervisning.list_undervisningenheter():
        id = tuple([u(row[field]) for field in
                   ("institusjonsnr", "emnekode", "versjonskode",
                    "terminkode", "arstall", "terminnr")])
        if id in ue_cache:
            continue

        xml_id = make_id(*id)
        name_for_humans = "Undervisningsenhet %s" % xml_id
        sko = make_sko(*[row[x] for x in ("faknr_kontroll",
                                          "instituttnr_kontroll",
                                          "gruppenr_kontroll")])
        ue_cache[id] = sko

        xmlwriter.startElement("group")
        out("groupid", xml_id, {"groupidtype": get_group_id_type("ue")})
        out("description", transliterate(name_for_humans))
        xmlwriter.endElement("group")

    return ue_cache


class _GenericCache(object):

    description = "entries"
    default = None

    def __init__(self, db):
        self._db = db
        self._cache = {}

    @classmethod
    def build_cache(cls, db):
        return {}

    def update_cache(self):
        logger.debug("caching %s...", self.description)
        self._cache = self.build_cache(self._db)
        logger.info("found %d %s", len(self._cache), self.description)

    def __call__(self, key):
        return self._cache.get(key, self.default)


class SystemLookupOrder(object):
    """
    The ABC system lookup order has always been a bit weird.

    SYSTEM_LOOKUP_ORDER is respected, but data from remaining
    AuthoritativeSystem codes are used as a fallback.
    """
    def __init__(self, const):
        fallback_lookup_order = sorted(
            const.fetch_constants(const.AuthoritativeSystem),
            key=six.text_type)
        lookup_order = tuple(aggregate.unique(const.get_system_lookup_order()
                                              + tuple(fallback_lookup_order)))
        self.get_pri = sorting.make_priority_lookup(lookup_order)
        self.max_pri = len(lookup_order)

    def __call__(self, system):
        return self.get_pri(system)


class PersonNameCache(_GenericCache):
    """ Person name cache and xml type remapper.  """

    description = "person names"

    name_map = {
        'FULL': "fn",
        'FIRST': "given",
        'LAST': "family",
    }

    @classmethod
    def build_cache(cls, db):
        person = Factory.get("Person")(db)
        const_map = {
            int(person.const.get_constant(person.const.PersonName, name)): attr
            for name, attr in cls.name_map.items()
        }
        names = {}
        for row in person.search_person_names(
                source_system=person.const.system_cached,
                name_variant=list(const_map)):
            p_id = row['person_id']
            attr = const_map[row['name_variant']]
            if p_id in names:
                names[p_id][attr] = row['name']
            else:
                names[p_id] = {attr: row['name']}
        return names


class WorkTitleCache(_GenericCache):
    """
    Person work title cache.

    Note that this uses the EntityNameWithLanguage implementation of
    localized work titles, and not the PersonName implementation.
    """
    description = "person work titles"

    @classmethod
    def build_cache(cls, db):
        person = Factory.get("Person")(db)
        names = {}
        for row in person.search_name_with_language(
                entity_type=int(person.const.entity_person),
                name_variant=int(person.const.work_title),
                name_language=int(person.const.language_nb)):
            p_id = row['entity_id']
            names[p_id] = row['name']
        return names


class PersonIdCache(_GenericCache):
    """
    Person external id cache.

    A cache of all available external ids from the highest prioritized source
    system (:see:`SystemLookupOrder`), grouped by (person_id, id_type):
    ::

        get_ids = PersonIdCache(db)
        get_ids.update_cache()
        ids = get_ids(int(person_id)) or {}
        fnr = ids.get(int(co.externalid_fodselsnr))
    """
    description = "external ids"

    # This is all a bit dumb - we should really define which external ids to
    # define (not just cache and export *all id types* and *from any system*

    @classmethod
    def build_cache(cls, db):
        person = Factory.get("Person")(db)
        const = person.const

        # This is dumb, but this export has always included external ids from
        # systems outside of the system lookup order, if no other id of the
        # type is set
        lookup_order = SystemLookupOrder(const)

        id_cache = {}
        priority = {}
        for row in person.search_external_ids(entity_type=const.entity_person):
            (entity_id, id_type) = pri_key = (row['entity_id'], row['id_type'])
            pri = lookup_order(row['source_system'])
            if pri < priority.get(pri_key, lookup_order.max_pri):
                # we found a better value
                if entity_id in id_cache:
                    id_cache[entity_id][id_type] = row['external_id']
                else:
                    id_cache[entity_id] = {
                        id_type: row['external_id'],
                    }
                priority[pri_key] = pri
        return id_cache


class PersonMobilePhoneCache(_GenericCache):
    """
    Person external id cache.

    A cache of all the highest prioritized mobile phone numbers (MOBILE).
    Prioritized by source system (:see:`SystemLookupOrder`) and
    ``contact_pref``.
    ::

        get_mobile = PersonMobilePhoneCache(db)
        get_mobile.update_cache()
        mobile = get_mobile(int(person_id))
    """
    description = "mobile phone numbers"

    @classmethod
    def build_cache(cls, db):
        person = Factory.get("Person")(db)
        const = person.const

        # See PersonIdCache...
        lookup_order = SystemLookupOrder(const)

        phone_cache = {}
        priority = {}
        for row in person.list_contact_info(
                contact_type=const.contact_mobile_phone):
            entity_id = row['entity_id']
            pri = (lookup_order(row['source_system']), row['contact_pref'])
            if pri < priority.get(entity_id, (lookup_order.max_pri, 0)):
                # we found a better value
                phone_cache[entity_id] = row['contact_value']
                priority[entity_id] = pri
        return phone_cache


class _ContactInfoCache(_GenericCache):
    """
    A cache of an arbitrary contact info source + type in Cerebrum
    ::

        get_fs_mobile = _ContactInfoCache(db, "fs-mobile", "MOBILE", "FS")
        get_fs_mobile.update_cache()
        fs_mobile = get_fs_mobile(person_id)
    """
    description = "contact info"

    def __init__(self, db, attr, c_type, c_source):
        """
        :type db: Cerebrum.database.Database
        :param str attr: an attr-hint for debugging
        :param str c_type: a ContactInfo code
        :param str c_source: an AuthoritativeSystem code
        """
        super(_ContactInfoCache, self).__init__(db)
        const = Factory.get("Constants")(db)
        self.attr = attr
        # human2constant for legacy reasons
        self.c_type = int(const.human2constant(c_type))
        self.c_source = int(const.human2constant(c_source))

    def update_cache(self):
        logger.debug("caching %s of type %s ...", self.description, self.attr)
        self._cache = self.build_cache(self._db, self.c_type, self.c_source)
        logger.info("found %d %s of type %s", len(self._cache),
                    self.description, self.attr)

    @classmethod
    def build_cache(cls, db, c_type, c_source):
        person = Factory.get("Person")(db)
        c_cache = {}
        # *sigh* - we should really get rid of the contact info priority system
        priority = {}
        for row in person.list_contact_info(
                contact_type=int(c_type),
                source_system=int(c_source)):
            entity_id = row['entity_id']
            pri = row['contact_pref']
            if entity_id not in priority or pri < priority[entity_id]:
                # we found a better value
                c_cache[entity_id] = row['contact_value']
                priority[entity_id] = pri
        return c_cache


class ExtraContactFields(object):
    """
    A cache of arbitrary contact info fields to include.
    """
    def __init__(self, db, spec_list):
        """
        :type db: Cerebrum.database.Database
        :param list spec_list:
            A list of contact info fields to cache.

            Example:
            ::

                [{
                    'xml_name': "fs-mobile",
                    'contact_type': "MOBILE",
                    'source_system': "FS",
                }]
        """
        self.fields = {}

        for fields in (spec_list or []):
            field_name = fields['xml_name']
            c_type = fields['contact_type']
            c_source = fields['source_system']
            self.fields[field_name] = _ContactInfoCache(db, field_name, c_type,
                                                        c_source)

    def update_cache(self):
        for cache in self.fields.values():
            cache.update_cache()

    def __call__(self, key):
        results = {}
        for field_name, cache in self.fields.items():
            value = cache(key)
            if value:
                results[field_name] = value

        return results


class PrimaryAccountCache(_GenericCache):
    """ A legacy cache of primary accounts in Cerebrum. """
    # This is extremely silly - why use fnr here?!  Maybe the legacy
    # getdict_external_id2primary_account was the only way to get a list of
    # primary accounts?
    description = "primary account"

    @classmethod
    def build_cache(cls, db):
        person = Factory.get("Person")(db)
        const = person.const

        return person.getdict_external_id2primary_account(
            const.externalid_fodselsnr)


class EmailCache(_GenericCache):
    """ A cache of primary email addresses for accounts in Cerebrum. """
    description = "email address"

    @classmethod
    def build_cache(cls, db):
        account = Factory.get("Account")(db)
        return account.getdict_uname2mailaddr()


class PersonCache(object):
    """
    A cache of all relevant person info.

    The cache decides which elements to include for ``<person>` elements.
    """

    def __init__(self, db, use_email=False, use_mobile=False,
                 contact_fields=None):
        """
        :type db: Cerebrum.database.Database
        :param bool use_email: if email addresses should be cached
        :param bool use_mobile: if mobile numbers should be cached
        :param list contact_fields:
            a list of extra contact fields to cache and include.

            :see:`ExtraContactFields` and ``spec_list`` for details.
        """
        self._db = db
        self._const = Factory.get("Constants")(db)
        self.get_names = PersonNameCache(db)
        self.get_work_title = WorkTitleCache(db)
        self.get_ids = PersonIdCache(db)

        self.get_mobile = PersonMobilePhoneCache(db)
        self.use_mobile = use_mobile

        self.get_contacts = ExtraContactFields(db, contact_fields)

        self._get_primary_uname = PrimaryAccountCache(db)

        self.use_email = use_email
        self._get_email_addr = EmailCache(db)

    def get_primary_uname(self, person_id):
        """ person-id -> primary user account name """
        id_type = int(self._const.externalid_fodselsnr)
        ext_ids = self.get_ids(person_id)
        fnr = ext_ids.get(id_type)
        if fnr:
            return self._get_primary_uname(fnr)
        return None

    def get_email_addr(self, person_id):
        """ person-id -> user account -> account email address """
        if self.use_email:
            uname = self.get_primary_uname(person_id)
            if uname:
                return self._get_email_addr(uname)
        return None

    @classmethod
    def make_cache(cls, *args, **kwargs):
        cache = cls(*args, **kwargs)
        cache.update_cache()
        return cache

    def update_cache(self):
        self.get_names.update_cache()
        self.get_work_title.update_cache()
        self.get_ids.update_cache()
        self.get_contacts.update_cache()
        self._get_primary_uname.update_cache()
        if self.use_mobile:
            self.get_mobile.update_cache()
        if self.use_email:
            self._get_email_addr.update_cache()


def output_people(db, use_email=False, use_mobile=False,
                  add_contact_fields=None):
    """Output all information about people."""
    person = Factory.get("Person")(db)
    const = person.const

    # IVR 2006-12-10 Although no caching is necessary strictly speaking, this
    # function takes over 3 hours to complete at UiO. This is unacceptable,
    # and we trade some of the clarity and memory for running time.
    person_cache = PersonCache.make_cache(
        db,
        use_mobile=use_mobile,
        use_email=use_email,
        contact_fields=add_contact_fields,
    )

    # cache for person_id -> external-IDs
    person_info = dict()
    fnr_const = int(const.externalid_fodselsnr)

    for row in person.list_persons():
        person_id = int(row["person_id"])
        birth_date = date_compat.get_date(row["birth_date"])

        name_collection = {
            attr: transliterate(name)
            for attr, name in (person_cache.get_names(person_id) or {}).items()
        }
        id_collection = dict()
        ids = person_cache.get_ids(person_id) or {}
        for tmp in const.fetch_constants(const.EntityExternalId):
            value = ids.get(int(tmp))
            if value:
                id_collection[int(tmp)] = (tmp, value)

        if ("fn" not in name_collection) or (fnr_const not in id_collection):
            logger.debug("Person (%s) lacks some name/ID attributes. Skipped",
                         person_id)
            logger.debug("name_collection %s; id_collection: %s",
                         name_collection, id_collection)
            continue

        # people need at least one valid affiliation to be output.
        if not person.list_affiliations(person_id=person_id):
            logger.debug("Person (e_id:%s; %s) has no affiliations. Skipped",
                         person_id, id_collection)
            continue

        # Cache the mapping. It does not really matter which external ID we
        # use to identify people, but since FNR is ubiquitous, we settle for
        # that.
        #
        # NB! Do NOT cache, unless we are sure the person is being
        # output. Since the cache is always consulted when an fnr from FS is
        # mapped to an fnr in Cerebrum, we neatly (?) avoid a situation when a
        # person has no affiliations (and thus is skipped from the list of
        # people in the ABC-file), but is nevertheless present in
        # kull/und.enhet/whatever, since (s)he is registered in FS.
        current_fnr = id_collection[fnr_const][1]
        person_info[person_id] = (const.externalid_fodselsnr, current_fnr)

        #
        # we start with the IDs
        xmlwriter.startElement("person")
        for id_type, value in id_collection.values():
            out("personid", value,
                {"personidtype": get_person_id_type(id_type)})

        #
        # ... then the names (they are structured too)
        xmlwriter.startElement("name")
        out("fn", name_collection["fn"])
        del name_collection["fn"]

        xmlwriter.startElement("n")
        for xml_name, value in name_collection.items():
            out(xml_name, value)

        work_title = person_cache.get_work_title(person_id)
        if work_title:
            out("partname", transliterate(work_title),
                {"partnametype": get_name_type("work")})

        xmlwriter.endElement("n")
        xmlwriter.endElement("name")

        # ... then the "rest"
        # (date == YYYY-MM-DD).
        if birth_date:
            out("birthdate", birth_date.isoformat())

        for value, contact_type in (
                (person_cache.get_primary_uname(person_id), "uname"),
                (person_cache.get_email_addr(person_id), "email"),
                (person_cache.get_mobile(person_id), "cell"),
        ):
            if value:
                out("contactinfo", value, {"contacttype":
                                           get_contact_type(contact_type)})

        for field, value in person_cache.get_contacts(person_id).items():
            if value:
                out('contactinfo', value, {'contacttype': field})

        xmlwriter.endElement("person")

    return person_info


def output_all_ous(orgname):
    """Output all OUs in target organization."""

    logger.debug("outputting all OUs")

    u = text_decoder(cerebrum_db.encoding)
    ou = Stedkode.Stedkode(cerebrum_db)
    _cache_ou2sko(ou)

    xmlwriter.startElement("organization")
    out("orgid", str(cereconf.DEFAULT_INSTITUSJONSNR),
        {"orgidtype": "institusjonsnummer"})
    out("orgname", orgname, {"lang": "no", "orgnametype": "name"})
    out("realm", cereconf.INSTITUTION_DOMAIN_NAME)

    # for each OU, output name and ID
    for row in ou.get_stedkoder():
        ou_id = row["ou_id"]
        sko = ou_id2sko(ou_id)
        assert sko

        try:
            ou.clear()
            ou.find(ou_id)
        except Errors.NotFoundError:
            logger.warn("OU ID %s does not exist, but its sko (%s) does",
                        ou_id, sko)

        xmlwriter.startElement("ou")
        out("ouid", sko, {"ouidtype": "sko"})
        # FIXME: Is there any guarantee that lang==no holds?
        out("ouname", u(ou.get_name_with_language(constants.ou_name_display,
                                                  constants.language_nb)),
            {"ounametype": "name", "lang": "no"})
        xmlwriter.endElement("ou")

    xmlwriter.endElement("organization")


def output_properties():
    """Write a (semi)fixed header for out target XML document.

    All types that we use later in the XML file, must be declared here.
    """

    logger.debug("outputting semifixed header")
    xmlwriter.startElement("properties")

    out("datasource", "cerebrum")
    out("target", "aksesskontroll")
    out("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S"))

    # All ID types must be declared before usage. The order is significant.
    xmlwriter.startElement("types")

    for contact_name in ("uname", "email", "cell"):
        out("contacttype", get_contact_type(contact_name),
            {"subject": "person"})

    out("orgidtype", "institusjonsnummer")

    out("orgnametype", "name")

    out("ouidtype", "sko")

    out("ounametype", "name")

    all_ids = constants.fetch_constants(constants.EntityExternalId)
    for external_id in all_ids:
        out("personidtype", get_person_id_type(external_id))

    out("partnametype", get_name_type("work"))

    for group_name in ("kull", "ue", "pay"):
        out("groupidtype", get_group_id_type(group_name))

    #
    # For N-ary relationships with N > 2, we split each such relationship into
    # a number of pairs. E.g. "kull" is an association between an OU, people
    # and "kull" designation:
    #
    # kull = (ou, people, kull) =>
    #      => kullgroup + (kullgroup + org/ou) + (kullgroup + people)
    # 'kull group' is the key binding all three together (the ABC schema
    # provides for binary relations only)
    for prefix in ("kull", "ue"):
        out("relationtype", prefix + "-ou",
            {"subject": "organization", "object": "group"})
        out("relationtype", prefix + "-people",
            {"subject": "group", "object": "person"})

    # Students who paid semester fee
    out("relationtype", "paid-people",
        {"subject": "group", "object": "person"})

    for affiliation, status in get_all_affiliations():
        out("relationtype", get_affiliation_type(affiliation, status),
            {"subject": "organization", "object": "person"})

    xmlwriter.endElement("types")

    xmlwriter.endElement("properties")


def prepare_pay():
    """Output a group for all students who paid semavgift."""

    xmlwriter.startElement("group")
    out("groupid", "paid-group", {"groupidtype": get_group_id_type("pay")})
    out("description", "Studenter som har betalt semavgift")
    xmlwriter.endElement("group")


def output_pay_relation(person_info):
    """Output a group with all students who paid semester fee (semavgift)."""

    person = Factory.get("Person")(cerebrum_db)

    xmlwriter.startElement("relation", {"relationtype": "paid-people"})
    xmlwriter.startElement("subject")
    out("groupid", "paid-group", {"groupidtype": get_group_id_type("pay")})
    xmlwriter.endElement("subject")

    xmlwriter.startElement("object")
    for row in fs_db.student.list_betalt_semesteravgift():
        fnr = "%06d%05d" % (row["fodselsdato"], row["personnr"])

        # IVR 2006-12-08: We cannot trust fnr from FS blindly (also, it's not
        # certain that people in the XML are identified through the fnr (it is
        # like that now, but it does not have to be like that all the time)).
        id_type, peid = fnr_to_external_id(fnr, person, person_info)
        if id_type is None:
            logger.debug("Missing external ID in Cerebrum for FS fnr %s", fnr)
            continue

        out("personid", peid, {"personidtype": get_person_id_type(id_type)})

    xmlwriter.endElement("object")
    xmlwriter.endElement("relation")


def sort_affiliations(sequence):
    """Sort all aff/status entries in sequence by ou_id.

    Given all people with a given aff/status, we re-structure them (the
    sequence) according to the OU.
    """

    # ou -> people
    result = dict()
    for row in sequence:
        sko = ou_id2sko(row["ou_id"])
        if not sko:
            logger.warn("Aiee! There is an affiliation %s:%s with ou_id %s "
                        "but there is no sko for that ou_id",
                        six.text_type(row["affiliation"]),
                        six.text_type(row["status"]),
                        row["ou_id"])
            continue

        result.setdefault(sko, list()).append(row)

    return result


def output_affiliation_relation(affiliation, status, sko, people, person_info):
    """Output one <relation>-element as described in output_affiliations."""

    xmlwriter.startElement("relation",
                           {"relationtype":
                            get_affiliation_type(affiliation, status)})
    xmlwriter.startElement("subject")
    output_ou(sko)
    xmlwriter.endElement("subject")

    xmlwriter.startElement("object")
    for person in people:
        pid = int(person["person_id"])
        if pid not in person_info:
            logger.info("person_id %d is in Cerebrum, but (s)he has no "
                        "external id in cached data", pid)
            continue

        idtype, value = person_info[pid]
        out("personid", value, {"personidtype": get_person_id_type(idtype)})

    xmlwriter.endElement("object")
    xmlwriter.endElement("relation")


def output_affiliations(person_info):
    '''Output all affiliation-related information.

    Affiliations are represented with a <relation>-element. Each element
    represents a group of people that have the same affiliation/status at a
    given OU. The relationtype attribute contains affiliation/status. The
    <subject> of the <relation> is the OU. The <object> of the relation is
    all the people. E.g.:

    <relation relationtype = "ANSATT/manuell">
      <subject>
        <org>
          <orgid>201</orgid>
          <ouid ouidtype="sko">010203</ouid>
        </org>
      </subject>
      <object>
        <personid ...>...</personid>
        <personid ...>...</personid>
        ...
      </object>
    </relation>

    Although the schema permits more that [0, inf) ouid, we will use exactly
    one.
    '''

    person = Factory.get("Person")(cerebrum_db)

    # The affiliations have already been cached.
    for affiliation, status in get_all_affiliations():
        #
        # Locate everyone with that particular aff/status combination
        bulk = person.list_affiliations(affiliation=affiliation,
                                        status=status)
        for sko, people in sort_affiliations(bulk).items():
            output_affiliation_relation(affiliation, status, sko,
                                        people, person_info)


def output_kull_relations(kull_info, person_info):
    """Output all relations representing 'kull'.

    Each 'kull' is represented by two <relation>s: one to link 'kull' up
    against an OU; one to list all people registered to that 'kull'.
    """

    logger.debug("Writing all kull <relation>s")
    person = Factory.get("Person")(cerebrum_db)

    for internal_id, sko in kull_info.items():
        xml_id = make_id(*internal_id)

        studieprogram_kode, terminkode, arstall = internal_id
        tmpseq = fs_db.undervisning.list_studenter_kull(studieprogram_kode,
                                                        terminkode,
                                                        arstall)
        students = remap_fnrs(tmpseq, person, person_info)
        if not students:
            logger.info("No students for kull %s. No groups will be generated",
                        internal_id)
            continue

        #
        # Output a relation linking kull and OU:
        xmlwriter.startElement("relation", {"relationtype": "kull-ou"})
        xmlwriter.startElement("subject")
        output_ou(sko)
        xmlwriter.endElement("subject")
        xmlwriter.startElement("object")
        out("groupid", xml_id, {"groupidtype": get_group_id_type("kull")})
        xmlwriter.endElement("object")
        xmlwriter.endElement("relation")

        #
        # Output a relation linking kull and its students:
        xmlwriter.startElement("relation", {"relationtype": "kull-people"})
        xmlwriter.startElement("subject")
        out("groupid", xml_id, {"groupidtype": get_group_id_type("kull")})
        xmlwriter.endElement("subject")

        # All students have the same OU within the same kull. 'relationtype'
        # attribute will contain this information.
        xmlwriter.startElement("object")
        for item in students:
            id_type, peid = item
            out("personid",
                peid,
                {"personidtype": get_person_id_type(id_type)})

        xmlwriter.endElement("object")
        xmlwriter.endElement("relation")

    logger.debug("Done with all kull <relation>s")


def output_ue_relations(ue_info, person_info):
    """Output all relations representing UE.

    Each UE is represented by two <relation>s: one to link UE up against an
    OU; one to list all people registered under that UE.
    """

    logger.debug("Writing all UE <relation>s")
    person = Factory.get("Person")(cerebrum_db)

    for internal_id, sko in ue_info.items():
        xml_id = make_id(*internal_id)

        instnr, emnekode, versjon, termk, aar, termnr = internal_id
        parameters = {"institusjonsnr": instnr,
                      "emnekode": emnekode,
                      "versjonskode": versjon,
                      "terminkode": termk,
                      "arstall": aar,
                      "terminnr": termnr, }
        students = remap_fnrs(
            fs_db.undervisning.list_studenter_underv_enhet(**parameters),
            person, person_info)
        if not students:
            logger.info("No students for UE %s. No groups will be generated",
                        internal_id)
            continue

        #
        # Output a relation linking UE and OU:
        xmlwriter.startElement("relation", {"relationtype": "ue-ou"})
        xmlwriter.startElement("subject")
        output_ou(sko)
        xmlwriter.endElement("subject")
        xmlwriter.startElement("object")
        out("groupid", xml_id, {"groupidtype": get_group_id_type("ue")})
        xmlwriter.endElement("object")
        xmlwriter.endElement("relation")

        #
        # Output a relation linking UE and its people:
        xmlwriter.startElement("relation", {"relationtype": "ue-people"})
        xmlwriter.startElement("subject")
        out("groupid", xml_id, {"groupidtype": get_group_id_type("ue")})
        xmlwriter.endElement("subject")
        xmlwriter.startElement("object")
        for item in students:
            id_type, peid = item
            out("personid",
                peid,
                {"personidtype": get_person_id_type(id_type)})

        xmlwriter.endElement("object")
        xmlwriter.endElement("relation")

    logger.debug("Done with all UE <relation>s")


def generate_report(orgname, encoding):
    """Main driver for the report generation."""

    xmlwriter.startDocument(encoding=encoding)
    xmlwriter.startElement("document")

    # Write out the "header" with all the IDs used later in the file.
    output_properties()

    # Write out OU information
    output_all_ous(orgname)

    person_info = output_people(
        cerebrum_db,
        use_email=with_email,
        use_mobile=with_cell,
        add_contact_fields=extra_contact_fields,
    )

    kull_info = prepare_kull()

    ue_info = prepare_ue()

    prepare_pay()

    output_pay_relation(person_info)

    output_affiliations(person_info)

    output_kull_relations(kull_info, person_info)

    output_ue_relations(ue_info, person_info)

    xmlwriter.endElement("document")
    xmlwriter.endDocument()


class AtomicStreamRecoder(AtomicFileWriter):
    """ file writer encoding hack.

    xmlprinter.xmlprinter encodes data in the desired encoding before writing
    to the stream, and AtomicFileWriter *requires* unicode-objects to be
    written.

    This hack turns AtomicFileWriter into a bytestring writer. Just make sure
    the AtomicStreamRecoder is configured to use the same encoding as the
    xmlprinter.

    The *proper* fix would be to retire the xmlprinter module, and replace it
    with something better.
    """

    def write(self, data):
        if isinstance(data, bytes) and self.encoding:
            # will be re-encoded in the same encoding by 'write'
            data = data.decode(self.encoding)
        return super(AtomicStreamRecoder, self).write(data)


def main(inargs=None):
    global cerebrum_db, constants, fs_db, xmlwriter
    global with_email, with_cell, extra_contact_fields
    # Sorry, but the alternative is to rewrite this whole thing.
    global transliterate

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-f', '--out-file', dest='filename',
                        help='XML-file to be generated',
                        required=True)
    parser.add_argument('-i', '--institution',
                        dest='institution',
                        type=Cerebrum.utils.argutils.UnicodeType(),
                        help='Name of institution to put in report',
                        required=True)
    parser.add_argument('-e', '--with-email',
                        dest='with_email',
                        action='store_true',
                        default=False,
                        help='Include email info')
    parser.add_argument('-c', '--with-cellular',
                        dest='with_cell',
                        action='store_true',
                        default=False,
                        help='Include cellphone data')
    parser.add_argument('-x', '--extra-contact-fields',
                        dest='extra_contact_fields',
                        default=None,
                        help=('Add extra contact-fields to the export. '
                              'Format: xml_name:contact_type:source_system. '
                              'contact_type and source_system must be valid '
                              'constant names.'))
    parser.add_argument('-o', '--encoding',
                        dest='encoding',
                        default='iso8859-1',
                        help='Override the default encoding (iso8859-1)')
    parser.add_argument('-r', '--errors',
                        dest='encoding_errors',
                        default='strict',
                        help=('Override default encoding error handler '
                              '(strict). Common handlers: strict, ignore, '
                              'replace. See Python Codec Base Classes for all '
                              'supported handlers.'))
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    cerebrum_db = Factory.get("Database")()
    constants = Factory.get("Constants")(cerebrum_db)

    transliterate = for_encoding(args.encoding)

    if args.extra_contact_fields is not None:
        extra_fields_unparsed = args.extra_contact_fields.split(',')
        extra_fields_unparsed = [field_entry.strip()
                                 for field_entry in extra_fields_unparsed]
        extra_contact_fields = []
        for unparsed_field in extra_fields_unparsed:
            field_raw_data = unparsed_field.split(':')
            field_dict = dict()
            field_dict['xml_name'] = field_raw_data[0]
            field_dict['contact_type'] = field_raw_data[1]
            field_dict['source_system'] = field_raw_data[2]
            extra_contact_fields.append(field_dict)
    else:
        extra_contact_fields = None

    logger.info("generating ABC export")

    with_email = args.with_email
    with_cell = args.with_cell
    encoding_errors = args.encoding_errors

    _cache_id_types()
    fs_db = make_fs()
    with AtomicStreamRecoder(args.filename,
                             mode='w',
                             encoding=args.encoding) as stream:
        xmlwriter = xmlprinter.xmlprinter(stream,
                                          indent_level=2,
                                          # human-friendly output
                                          data_mode=True,
                                          encoding_errors=encoding_errors)
        generate_report(args.institution, args.encoding)
        logger.info('Report written to %s', stream.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == "__main__":
    main()
