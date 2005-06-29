#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
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


"""
This file is a HiA-specific extension of Cerebrum. This script generates an
XML file containing all the information necessary for the access control
system at HiA (adgangssystem).

The XML is shaped in accordance with ABC-enterprise schema.
"""

import getopt, sys, time

import cerebrum_path
import cereconf
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum import Database
from Cerebrum.Utils import Factory
from Cerebrum.extlib import xmlprinter
from Cerebrum.modules.no.hia.access_FS import FS





#
# This contains a mapping for all "*type" attributes in the ABC-schema that
# we actually use.
# 1) Do NOT poke in the _id_type_cache directly
# 2) Do NOT write out the values in the code, but register them in
#    _id_type_cache and use a suitable get_-function.
_id_type_cache = dict()
def _cache_id_types():

    for cerebrum_constant, xml_name in (
        (const.EntityExternalId("NO_BIRTHNO"), "FNR"),
        (const.EntityExternalId("HiA_SAP_EMP#"), "HIA-SAP"),
        (const.EntityExternalId("NO_STUDNO"), "STUDNO"),
        (const.PersonName("FIRST"), "given name"),
        (const.PersonName("LAST"), "family name")):
        _id_type_cache[int(cerebrum_constant)] = xml_name
    # od

    for kind, grouptype, reltype in (
        ("affiliation", "affgroup", "affrelation"),
        ("kull", "kullgroup", "kullrelation"),
        ("ue", "uegroup", "uerelation")):
        _id_type_cache[kind] = { "groupidtype" : grouptype,
                                 "relationtype" : reltype }
    # od
# end _cache


def get_person_id_type(cerebrum_constant):
    if int(cerebrum_constant) not in _id_type_cache:
        logger.warn("%d not found in cache", int(cerebrum_constant))
    return _id_type_cache.get(int(cerebrum_constant), "")
# end _get_person_id_type


def get_group_id_type(kind):
    """Maps a group id kind to a type in XML"""
    return _id_type_cache[kind]["groupidtype"]
# end get_group_id_type


def get_relation_type(kind):
    """Maps a relation kind to a type in XML"""
    return _id_type_cache[kind]["relationtype"]
# end get_relation_type



def person_get_item(getter, item_variant):
    """Fetch a suitable version of a person's attribute (name, id, etc.).

    Walk through cereconf.SYSTEM_LOOKUP_ORDER and return the first found
    item of the specified kind.
    """

    for system in cereconf.SYSTEM_LOOKUP_ORDER:
        try:
            item = getter(getattr(const, system), item_variant)
            if not item:
                continue
            elif type(item) == type(list()):
                item = item[0]
            # fi
            return item
        except Errors.NotFoundError:
            pass
        # yrt
    # od

    return ""
# end person_get_item



def make_id(*rest):
    """Make an ID out of a sequence"""

    return ":".join([str(x) for x in rest])
# end make_id



def output_elem(writer, elem, elemdata, attributes = {}):
    if elemdata or attributes:
        writer.dataElement(elem, elemdata, attributes)
    # fi
# end output_elem



def output_properties(writer):
    """Write a (semi)fixed header for our XML document."""

    writer.startElement("properties")

    output_elem(writer, "datasource", "cerebrum")
    output_elem(writer, "target", "aksesskontrol")
    output_elem(writer, "timestamp", time.strftime("%Y-%m-%dT%H:%M:%S"))

    #
    # All ID types used must be declared first.
    writer.startElement("types")
    for c in (const.EntityExternalId("NO_BIRTHNO"),
              const.EntityExternalId("HiA_SAP_EMP#"),
              const.EntityExternalId("NO_STUDNO")):
        output_elem(writer, "personidtype", get_person_id_type(c))
    # od

    for c in ("affiliation", "kull", "ue"):
        output_elem(writer, "groupidtype", get_group_id_type(c))
    # od

    for c in ("affiliation", "kull", "ue"):
        output_elem(writer, "relationtype", get_relation_type(c),
                    { "subject" : "Group",
                      "object"  : "Person" })
    # od
    writer.endElement("types")

    writer.endElement("properties")
# end output_properties



def output_people(writer):
    db = Factory.get("Database")()
    person = Factory.get("Person")(db)

    logger.info("Generating <person>-elements")
    # cache for mapping person_id's to external IDs
    person_info = dict()

    for row in person.list_persons():
        id = row["person_id"]
        try:
            person.clear()
            person.find(id)
        except Errors.NotFoundError:
            logger.warn("Person id %s reported by list_persons(), "
                        "but find() failed", id)
            continue
        # yrt

        # We have to delay outputting person information, until we know that
        # (s)he has a name.
        name_collection = list()
        for xmlid, cereid in (("given", const.PersonName("FIRST")),
                              ("family", const.PersonName("LAST")),
                              ("other", const.PersonName("WORKTITLE"))):
            name = person_get_item(person.get_name, cereid)
            if name:
                name_collection.append((xmlid, name))
            # fi
        # od    

        if (not ("given" in [x[0] for x in name_collection]) or 
            not ("family" in [x[0] for x in name_collection])):
            # Don't make it a warn() -- there are too damn many
            logger.debug("Person id %s has no names and will be ignored", id)
            continue
        # fi    

        writer.startElement("person")

        #
        # Output all IDs
        for i in (const.EntityExternalId("NO_STUDNO"),
                  const.EntityExternalId("HiA_SAP_EMP#"),
                  const.EntityExternalId("NO_BIRTHNO"),):
            value = person_get_item(person.get_external_id, i)
            if not value:
                continue
            else:
                # We need some (any, actually) ID for identifying the person
                # later for <relation>s
                value = value["external_id"]
                person_info[int(id)] = (i, value)
            # fi
            output_elem(writer, "personid", value,
                        { "personidtype" : get_person_id_type(i) })
        # od

        #
        # Output all the names
        writer.startElement("name")
        writer.startElement("n")
        for xmlid, value in name_collection:
            output_elem(writer, xmlid, value)
        # od    
        writer.endElement("n")
        writer.endElement("name")
                        
        writer.endElement("person")
    # od

    logger.info("Done with <person>-elements (%d elements)",
                len(person_info))
    return person_info
# end output_people



def prepare_affiliations(writer):
    """Prepare all affiliation-related information.

    Affiliations are expressed through the group concept in the ABC-schema.

    First we define all affiliation + aff.status as <group>s. Then we use
    <relation> to link up people to their affiliations (i.e. <group>s). 
    """

    db = Factory.get("Database")()
    person = Factory.get("Person")(db)

    logger.info("Generating <group>-elements for affiliations")
    affiliation_cache = dict()
    
    for row in person.list_affiliations(fetchall = False):
        internal_id = int(row["affiliation"]), int(row["status"])
        if internal_id in affiliation_cache:
            continue
        # fi

        # NB! The code is based on status uniqueness (it is indeed the case,
        # but it is not (yet) enforced in the DB schema (patch pending from
        # NTNU)). 
        name_for_humans = ("Affiliation status %s" %
                           const.PersonAffStatus(row["status"]))
        affiliation_cache[internal_id] = const.PersonAffStatus(row["status"])

        writer.startElement("group")
        output_elem(writer, "description", name_for_humans)
        xml_id = make_id(*internal_id)
        output_elem(writer, "groupid", xml_id,
                    {"groupidtype" : get_group_id_type("affiliation")})
        writer.endElement("group")
    # od 
        
    logger.info("Done with affiliation <group>-elements (%d elements)",
                len(affiliation_cache))
    return affiliation_cache
# end prepare_affiliations



def prepare_kull(writer):
    """Output all kull-related information.

    'Kull' relationships are expressed through the group concept in the
    ABC-schema. First we define all 'kull' as <group>s. Then we use <relation>
    to link up people to their respective 'kull's (i.e. <group>s).
    """

    db = Database.connect(user="cerebrum", service="FSHIA.uio.no",
                          DB_driver="DCOracle2")
    fs = FS(db)

    logger.info("Generating <group>-elements for kull")    
    kull_cache = dict()

    for row in fs.info.list_kull():
        studieprogram = str(row["studieprogramkode"])
        terminkode = str(row["terminkode"])
        arstall = int(row["arstall"])

        internal_id = studieprogram, terminkode, arstall
        if internal_id in kull_cache:
            continue
        # fi

        xml_id = make_id(*internal_id)
        name_for_humans = "Studiekull %s" % row["studiekullnavn"]
        kull_cache[internal_id] = name_for_humans

        writer.startElement("group")
        output_elem(writer, "description", name_for_humans)
        output_elem(writer, "groupid", xml_id,
                    {"groupidtype" : get_group_id_type("kull")})
        writer.endElement("group")
    # od

    logger.info("Done with <group>-elements for kull (%d elements)",
                len(kull_cache))
    return kull_cache
# end prepare_kull



def prepare_ue(writer):
    """Prepare all undervisningsenhet-related information.

    The procedure is the same as for affiliations.
    """

    db = Database.connect(user="cerebrum", service="FSHIA.uio.no",
                          DB_driver="DCOracle2")
    fs = FS(db)

    logger.info("Generating <group>-elements for UE")
    ue_cache = dict()

    for row in fs.undervisning.list_undervisningenheter():
        id = tuple([row[field] for field in
                   ("institusjonsnr", "emnekode", "versjonskode",
                    "terminkode", "arstall", "terminnr")])
        if id in ue_cache:
            continue
        # fi

        xml_id = make_id(*id)
        name_for_humans = "Undervisningsenhet %s" % xml_id
        ue_cache[id] = name_for_humans

        writer.startElement("group")
        output_elem(writer, "description", name_for_humans)
        output_elem(writer, "groupid", xml_id,
                    {"groupidtype" : get_group_id_type("ue")})
        writer.endElement("group")
    # od

    logger.info("Done with <group>-elements for UE (%d elements)",
                len(ue_cache))
    return ue_cache
# end prepare_ue



def fnr_to_external_id(fnr, person, person_info):
    """Helper function for output_relations.

    Map an fnr to an external id that we *know* exists in the list of
    <person>-elements output earlier.
    """
    
    try:
        person.clear()
        person.find_by_external_id(const.EntityExternalId("NO_BIRTHNO"),
                                   fnr,
                                   const.AuthoritativeSystem("FS"))
    except Errors.NotFoundError:
        # logger.warn("fnr %s is in FS, but not in Cerebrum", fnr)
        return None, None
    # yrt

    if int(person.entity_id) not in person_info:
        logger.warn("fnr %s (person_id %d) are in Cerebrum, but not "
                    "in cached data", fnr, person.entity_id)
        return None, None
    # fi

    id_type, person_external_id = person_info[int(person.entity_id)]
    return id_type, person_external_id
# end fnr_to_external_id



def output_relations(writer, person_info, affiliation_info,
                     kull_info, ue_info):
    """Output all information about affiliations, kull and UE.

    We have already listed all people and defined all the necessary
    groups. Now we simply output the membership information represented as
    <relation>s.
    """
    db = Factory.get("Database")()
    person = Factory.get("Person")(db)
    db = Database.connect(user="cerebrum", service="FSHIA.uio.no",
                          DB_driver="DCOracle2")
    fs = FS(db)

    #
    # Output all kull-related information
    #
    logger.debug("Writing all kull <relation>s")
    for internal_id in kull_info:

        writer.startElement("relation", {"relationtype" :
                                         get_relation_type("kull")})
        writer.startElement("subject")
        xml_id = make_id(*internal_id)
        output_elem(writer, "groupid", xml_id,
                    {"groupidtype" : get_group_id_type("kull")})
        writer.endElement("subject")

        studieprogram_kode, terminkode, arstall = internal_id
        writer.startElement("object")
        for row in fs.undervisning.list_studenter_kull(studieprogram_kode,
                                                       terminkode,
                                                       arstall):
            fnr = "%06d%05d" % (row["fodselsdato"], row["personnr"])
            id_type, peid = fnr_to_external_id(fnr, person, person_info)
            if id_type is None:
                continue
            # fi

            output_elem(writer, "personid", peid,
                        {"personidtype" : get_person_id_type(id_type)})
        # od
        writer.endElement("object")
        writer.endElement("relation")
    # od
    logger.debug("Done with all kull <relation>s")

    #
    # Output all affiliations...
    #
    logger.debug("Writing all affiliation <relation>s")
    for internal_id, human_name in affiliation_info.items():
        writer.startElement("relation", {"relationtype" :
                                         get_relation_type("affiliation")})
        writer.startElement("subject")
        xml_id = make_id(*internal_id)
        output_elem(writer, "groupid", xml_id,
                    {"groupidtype" : get_group_id_type("affiliation")})
        writer.endElement("subject")

        writer.startElement("object")
        for row in person.list_affiliations(affiliation = internal_id[0],
                                            status = internal_id[1]):
            person_id = int(row["person_id"])
            if person_id not in person_info:
                logger.warn("person_id %s has affiliation %s but not present "
                            "in person_id cache", person_id, human_name)
                continue
            # fi

            id_type, person_external_id = person_info[person_id]
            output_elem(writer, "personid", person_external_id,
                        {"personidtype" : get_person_id_type(id_type)})
        # od
        writer.endElement("object")
        writer.endElement("relation")
    # od
    logger.debug("Done with all affiliation <relation>s")

    #
    # Output all undervisningsenheter
    #
    logger.debug("Writing all UE <relation>s")
    for internal_id, human_name in ue_info.items():
        writer.startElement("relation", {"relationtype" :
                                         get_relation_type("ue")})
        writer.startElement("subject")
        xml_id = make_id(*internal_id)
        output_elem(writer, "groupid", xml_id,
                    {"groupidtype" : get_group_id_type("ue")})
        writer.endElement("subject")

        writer.startElement("object")
        instnr, emnekode, versjon, termk, aar, termnr = internal_id
        parameters = { "institusjonsnr" : instnr,
                       "emnekode" : emnekode,
                       "versjonskode" : versjon,
                       "terminkode" : termk,
                       "arstall" : aar,
                       "terminnr" : termnr }
        for row in fs.undervisning.list_studenter_underv_enhet(**parameters):
            # We cannot publish fnr from FS in the xml, as there is no
            # guarantee that Cerebrum has these fnrs. The id translation goes
            # like this: we locate the person in Cerebrum using the supplied
            # fnr and look him/her up in person_info. The id from person_info
            # will be the one used to identify the individual.
            fnr = "%06d%05d" % (row["fodselsdato"], row["personnr"])
            id_type, peid = fnr_to_external_id(fnr, person, person_info)
            if id_type is None:
                continue
            # fi

            output_elem(writer, "personid", peid,
                        {"personidtype" : get_person_id_type(id_type)})
        # od
        writer.endElement("object")
        writer.endElement("relation")
    # od
    logger.debug("Done with all UE <relation>s")
# end output_relations



def generate_report(writer):
    """Main driver for the report generation."""

    writer.startDocument(encoding = "iso8859-1")

    output_properties(writer)
    
    person_info = output_people(writer)

    affiliation_info = prepare_affiliations(writer)

    kull_info = prepare_kull(writer)

    ue_info = prepare_ue(writer)

    output_relations(writer, person_info, affiliation_info, kull_info, ue_info)

    writer.endDocument()
# end generate_report



def main():
    global logger
    logger = Factory.get_logger()
    logger.info("generating a new XML for export_ACL")

    global const
    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)

    opts, rest = getopt.getopt(sys.argv[1:], "f:",
                               ["--out-file=",])
    filename = None
    for option, value in opts:
        if option in ("-f", "--out-file"):
            filename = value
        # fi
    # od

    _cache_id_types()
    stream = Utils.AtomicFileWriter(filename)
    writer = xmlprinter.xmlprinter(stream,
                                   indent_level = 2,
                                   # Human-readable output
                                   data_mode = True,
                                   input_encoding = "latin1")
    generate_report(writer)
    stream.close()
# end main





if __name__ == "__main__":
    main()
# fi

# arch-tag: 0f371464-e7dd-11d9-845d-85bcc9ab2fe6
