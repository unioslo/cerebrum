#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
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
"""Export person information in ABC Enterprise format.

This file is an extension of Cerebrum. It generates an XML file containing
person and OU information which may be used for e.g. access control systems at
various institutions (adgangskontrollsystem). Such a file can be generated for
any of the Norwegian institutions using FS and Cerebrum.

The XML description and schema are available here:

<URL: http://uninettabc.no/?p=publikasjoner&sub=abc-enterprise>

There are roughly these categories of data being output:

* preliminary header with various id and relationship types being used.
* organizational information (OUs)
* information about people (ids, names, account and e-mail information)
* various relations involving people and OUs:
** kull
** undervisningsenhet
** affiliations
** payment information (semester fee (semesteravgift)).

When adding extra contact-fields, be sure to quote the input string so that
the argument is parsed correctly. When adding several contact fields, separate
them by commas.

Example: "cellular private:contact_private_mobile:system_sap,
          cellular work:contact_mobile_phone:system_sap"

These two fields will be added as extra contactinfo-tags, like this:

<contactinfo contacttype="cellular private">value</contactinfo>
<contactinfo contacttype="cellular work">value</contactinfo>
"""

import argparse
import logging
import time

from six import text_type

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


logger = logging.getLogger(__name__)


def text_decoder(encoding, allow_none=True):
    def to_text(value):
        if allow_none and value is None:
            return None
        if isinstance(value, bytes):
            return value.decode(encoding)
        return text_type(value)
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
        text_type(cereconf.DEFAULT_INSTITUSJONSNR),
        {"orgidtype": "institusjonsnummer"})
    out("ouid", sko, {"ouidtype": "sko"})
    xmlwriter.endElement("org")


def make_sko(fakultet, institutt, avdeling):
    return "".join(["%02d" % int(x)
                    for x in (fakultet, institutt, avdeling)])


def make_id(*rest):
    """Make an ID out of a sequence."""
    return u":".join([text_type(x) for x in rest])


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
        _id_type_cache["affiliation"][aff, status] = text_type(tmp.description)


def get_name_type(name_type):
    return _id_type_cache[name_type]


def get_contact_type(name):
    return _id_type_cache[name]


def get_person_id_type(external_id):
    # FIXME: Perhaps we ought to validate whatever is fed in here.
    return text_type(external_id)


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
        name_for_humans = u"Studiekull %s" % u(row["studiekullnavn"])
        sko = make_sko(*[row[x] for x in ("faknr_studieansv",
                                          "instituttnr_studieansv",
                                          "gruppenr_studieansv")])
        kull_cache[internal_id] = sko

        xmlwriter.startElement("group")
        out("groupid", xml_id, {"groupidtype": get_group_id_type("kull")})
        out("description", name_for_humans)
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
        name_for_humans = u"Undervisningsenhet %s" % xml_id
        sko = make_sko(*[row[x] for x in ("faknr_kontroll",
                                          "instituttnr_kontroll",
                                          "gruppenr_kontroll")])
        ue_cache[id] = sko

        xmlwriter.startElement("group")
        out("groupid", xml_id, {"groupidtype": get_group_id_type("ue")})
        out("description", name_for_humans)
        xmlwriter.endElement("group")

    return ue_cache


def fetch_external_ids(db_person):
    """Fetch all external-ids for everyone, respecting SYSTEM_LOOKUP_ORDER.

    If a person has several external-ids of the same type but coming from
    different source systems, the one with the 'more important' source system
    will be used. 'more important' refers to the placement in
    SYSTEM_LOOKUP_ORDER: more important systems come earlier in that sequence.

    @type db_person: an instance of Factory.get('Person')(db)
    @type constants: an instance of Factory.get('Constants')(db)
    @rtype: dict
    @return:
      Returns a dictionary D1 mapping entity_id (for people) to D2. Each D2 is
      a dictionary mapping external id type to its value.
    """

    # First, we assign weights to all source systems. The greater the number,
    # the less important the system. 'None' is also included, to help deal
    # with non-existing entries. Any source_system is more important than
    # None.
    system_weights = dict()
    u = text_decoder(cerebrum_db.encoding)
    for counter, system in enumerate([int(getattr(constants, s))
                                      for s in cereconf.SYSTEM_LOOKUP_ORDER]):
        system_weights[system] = counter
    # If an id is registered to some now-unknown system (like migrate), it is
    # less important than the "official" systems.
    unknown_weight = counter + 1
    system_weights[None] = unknown_weight + 1

    tmp = dict()
    seq = db_person.search_external_ids(entity_type=constants.entity_person,
                                        fetchall=False)
    for entity_id, entity_type, id_type, source, external_id in seq:
        external_id = u(external_id)
        entity_id, id_type, source = map(int, (entity_id, id_type, source))

        e_dict = tmp.get(entity_id, dict())
        old_source, old_ext_id = e_dict.get(id_type, (None, None))
        # if the source system for this id is more important, take it
        if (system_weights.get(source, unknown_weight) <
                system_weights.get(old_source, unknown_weight)):
            e_dict[id_type] = (source, external_id)
        tmp[entity_id] = e_dict

    # stage 2 -- remove the source system from all the values. We do not need
    # the source system anymore.
    for e_dict in tmp.itervalues():
        for key, value in e_dict.iteritems():
            e_dict[key] = value[1]  # strip away the source system

    return tmp


def cache_person_info(db_person, db_account):
    """Fetch all person info for all people for this export.

    This is a potential memory hog.

    Returns a 5-tuple:

    * person_id -> names, where names is a dictionary indexed by name type
    * person_id -> eids, where eids is a dictionary external_id -> value
    * fnr -> primary uname
    * uname -> email
    * person_id -> cell, where cell is the persons cellphone number
    """

    logger.debug("Populating all person caches")
    logger.debug("person-id -> names")
    u = text_decoder(cerebrum_db.encoding)

    person_id2names = db_person.getdict_persons_names(
        source_system=constants.system_cached,
        name_types=(constants.name_full, constants.name_last,
                    constants.name_first))
    for k in person_id2names:
        for v in person_id2names[k]:
            person_id2names[k][v] = u(person_id2names[k][v])

    variant = int(constants.work_title)
    for row in db_person.search_name_with_language(
                            entity_type=constants.entity_person,
                            name_variant=variant,
                            name_language=constants.language_nb):
        person_id = row["entity_id"]
        person_id2names.setdefault(person_id, dict())[variant] = u(row["name"])

    logger.debug("person-id -> external ids")
    # IVR 2007-11-06: We cannot blindly grab external ids, since there may be
    # several of them. The only sensible thing to do is to respect
    # SYSTEM_LOOKUP_ORDER.
    person_id2external_ids = fetch_external_ids(db_person)

    logger.debug("fnr -> primary uname")
    fnr2uname = dict(
        (u(fnr), u(uname))
        for fnr, uname in db_person.getdict_external_id2primary_account(
                constants.externalid_fodselsnr).items())

    if with_email:
        logger.debug("uname -> e-mail")
        uname2mail = db_account.getdict_uname2mailaddr()
    else:
        uname2mail = dict()

    eid2cell = dict()
    if with_cell:
        # Helper function for ordering items.
        def lookup_order_index(system):
            i = 0
            system = text_type(constants.AuthoritativeSystem(system))
            for x in cereconf.SYSTEM_LOOKUP_ORDER:
                if text_type(getattr(constants, x)) == system:
                    return i
                else:
                    i = i + 1
            return i

        logger.debug("eid -> cell")
        for x in db_person.list_contact_info(
                contact_type=constants.contact_mobile_phone):
            eid2cell.setdefault(x['entity_id'], []).append(
                    (x['source_system'], u(x['contact_value']),))

        # Sort according to SYSTEM_LOOKUP_ORDER and pick the first.
        for x in eid2cell:
            eid2cell[x] = sorted(
                eid2cell[x],
                cmp=lambda p, n: (lookup_order_index(p[1]) -
                                  lookup_order_index(n[1])))[0][1]

    extra_fields = dict()
    if extra_contact_fields is not None:
        for contact_field in extra_contact_fields:
            cont_type = constants.human2constant(contact_field['contact_type'])
            src_sys = constants.human2constant(contact_field['source_system'])
            eid2contact_field = dict()
            contact_info_entries = db_person.list_contact_info(
                    contact_type=cont_type,
                    source_system=src_sys)
            for x in contact_info_entries:
                eid2contact_field[x['entity_id']] = u(x['contact_value'])
            extra_fields[contact_field['xml_name']] = eid2contact_field

    logger.debug("person caching complete")
    return (person_id2names, person_id2external_ids, fnr2uname, uname2mail,
            eid2cell, extra_fields)


def output_people():
    """Output all information about people."""

    person = Factory.get("Person")(cerebrum_db)
    account = Factory.get("Account")(cerebrum_db)

    # IVR 2006-12-10 Although no caching is necessary strictly speaking, this
    # function takes over 3 hours to complete at UiO. This is unacceptable,
    # and we trade some of the clarity and memory for running time.
    (person_id2name,
     person_id2external_ids,
     fnr2uname, uname2mail,
     eid2cell, extra_fields) = cache_person_info(person, account)

    # cache for person_id -> external-IDs
    person_info = dict()
    fnr_const = int(constants.externalid_fodselsnr)

    for row in person.list_persons():
        id = int(row["person_id"])
        birth_date = row["birth_date"]

        name_collection = dict()
        # We have to delay person output, until we are sure that a few key
        # attributes are present.
        names = person_id2name.get(id, {})
        for tmp, xml_name in ((constants.name_full, "fn"),
                              (constants.name_last, "family"),
                              (constants.name_first, "given")):
            name = names.get(int(tmp))
            if name:
                name_collection[xml_name] = transliterate(name)

        id_collection = dict()
        ids = person_id2external_ids.get(id, {})
        for tmp in constants.fetch_constants(constants.EntityExternalId):
            value = ids.get(int(tmp))
            if value:
                id_collection[int(tmp)] = (tmp, value)

        if ("fn" not in name_collection) or (fnr_const not in id_collection):
            logger.debug("Person (%s) lacks some name/ID attributes. Skipped",
                         id)
            logger.debug("name_collection %s; id_collection: %s",
                         name_collection, id_collection)
            continue

        # people need at least one valid affiliation to be output.
        if not person.list_affiliations(person_id=id):
            logger.debug("Person (e_id:%s; %s) has no affiliations. Skipped",
                         id, id_collection)
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
        person_info[int(id)] = (constants.externalid_fodselsnr, current_fnr)

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

        work_title = names.get(int(constants.work_title))
        if work_title:
            out("partname",
                work_title,
                {"partnametype": get_name_type("work")})

        xmlwriter.endElement("n")
        xmlwriter.endElement("name")

        #
        # ... then the "rest"
        # (date == YYYY-MM-DD).
        # FIXME: Should we skip people without birth dates?
        if birth_date:
            out("birthdate", birth_date.date)

        primary_uname = fnr2uname.get(current_fnr)
        for value, contact_type in ((primary_uname, "uname"),
                                    (uname2mail.get(primary_uname), "email"),
                                    (eid2cell.get(id), "cell")):
            if value:
                out("contactinfo", value, {"contacttype":
                                           get_contact_type(contact_type)})

        for field in extra_fields:
            value = extra_fields[field].get(id)
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
                        text_type(row["affiliation"]),
                        text_type(row["status"]),
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

    Although the schema permits more that [0, \inf) ouid, we will use exactly
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

    person_info = output_people()

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
