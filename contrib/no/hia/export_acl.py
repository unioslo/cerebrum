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
        (const.EntityExternalId("HiA_SAP_EMP#"), "EMPLNO"),
        (const.EntityExternalId("NO_STUDNO"), "STUDNO"),
        (const.PersonName("FIRST"), "given name"),
        (const.PersonName("LAST"), "family name")):
        _id_type_cache[int(cerebrum_constant)] = xml_name
    # od

    # These will be populated later
    _id_type_cache["kull"] = dict()
    _id_type_cache["affiliation"] = dict()
    _id_type_cache["ue"] = dict()

    for id, xml_name in (("work", "work title"),
                         ("uname", "primary account"),
                         ("email", "primary e-mail address")):
        _id_type_cache[id] = xml_name
    # od
# end _cache

def get_person_id_type(cerebrum_constant):
    if int(cerebrum_constant) not in _id_type_cache:
        logger.warn("%d not found in cache", int(cerebrum_constant))
    return _id_type_cache.get(int(cerebrum_constant), "")
# end _get_person_id_type

def get_name_type(name_type):
    """Maps a name type (partnametype) to a type in XML"""
    return _id_type_cache[name_type]
# end get_name_type

def get_kull_relation_type(sko):
    """Return an XML relationtype, suitable for KULL representation."""

    return _id_type_cache["kull"][sko]
# end get_kull_relation_type

def register_kull_relation_type(sko):
    """Register a kull relation for a given sko."""

    _id_type_cache["kull"][sko] = "kull " + sko
# end register_kull_relation_type

def get_affiliation_relation_type(ou_id):
    """Return an XML relationtype, suitable for affiliation representation."""

    return _id_type_cache["affiliation"][ou_id]
# end get_affiliation_relation_type

def register_affiliation_relation_type(ou_id, sko):
    """Register an affiliation relation for a given OU."""

    _id_type_cache["affiliation"][ou_id] = "affiliation " + sko
# end register_affiliation_relation_type

def get_ue_relation_type(sko):
    """Return an XML relationtype, suitable for UE representation."""

    return _id_type_cache["ue"][sko]
# end get_ue_relation_type

def register_ue_relation_type(sko):
    """Register an affiliation relation for a given OU."""

    _id_type_cache["ue"][sko] = "undervisningsenhet " + sko
# end register_ue_relation_type

def get_group_id_type(kind):
    """Maps a group id kind to a type in XML"""
    return { "affiliation" : "affgroup",
             "kull"        : "kullgroup",
             "ue"          : "uegroup" }[kind]
# end get_group_id_type





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


def make_sko(institusjon, fakultet, institutt, avdeling):
    return "-".join([str(x) for x in (institusjon, fakultet,
                                      institutt, avdeling)])
# end make_sko


def output_elem(writer, elem, elemdata, attributes = {}):
    if elemdata or attributes:
        writer.dataElement(elem, elemdata, attributes)
    # fi
# end output_elem



def output_properties(writer):
    """Write a (semi)fixed header for our XML document.

    All types, that we use later in the XML file, must be declared here.
    """

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

    for c in ("work", "uname", "email"):
        output_elem(writer, "partnametype", get_name_type(c))
    # od

    output_OU_types(writer)

    writer.endElement("types")

    writer.endElement("properties")
# end output_properties



#
# These attribute sets are used several times throughout the script. 
_kull_db_attributes = ("institusjonsnr_studieansv",
                       "faknr_studieansv",
                       "instituttnr_studieansv",
                       "gruppenr_studieansv")
_ue_db_attributes = ("institusjonsnr",
                     "faknr_kontroll",
                     "instituttnr_kontroll",
                     "gruppenr_kontroll")

def output_OU_types(writer):
    """Output all OUs used in various relations.

    This is actually a hack -- as the XML schema does not allow N-ary
    relations, we need to find a workaround for this. We need to represent
    three-way relations in this export and can thus 'bake' one of the parts
    of a relation into the relationtype XML attribute. This approach will
    *obviously* fail in the general case, as:

    * A general N-ary relation cannot be represented
    * Even a ternary relation will be ugly, if all three participating parts
      are quite numerous.

    However, right here it will work. In all cases below, we use OU id for
    the relationtype.
    """

    logger.info("Outputting OU types")

    db = Factory.get("Database")()
    OU = Factory.get("OU")(db)
    person = Factory.get("Person")(db)
    fs = FS(Database.connect(user="cerebrum", service="FSHIA.uio.no",
                          DB_driver="DCOracle2"))

    logger.info("Building OU -> sko cache")
    #
    # Build ou_id -> sko cache
    #
    ouid2sko = dict()
    for item in OU.list_all():
        id = int(item["ou_id"])
        if id in ouid2sko:
            continue
        # fi

        try:
            OU.clear()
            OU.find(id)
        except Errors.NotFoundError:
            logger.warn("OU id %s suddently disappeared", id)
            continue
        # yrt

        ouid2sko[id] = tuple([str(x) for x in
                              (OU.institusjon, OU.fakultet, OU.institutt,
                               OU.avdeling)])
    # od

    #
    # Step 1 -- affiliations.
    logger.info("Processing all affiliations")
    ou_cache = dict()
    for row in person.list_affiliations(fetchall = False):
        id = int(row["ou_id"])
        if id not in ouid2sko:
            continue
        if id in ou_cache:
            continue

        register_affiliation_relation_type(id, make_sko(*ouid2sko[id]))
        output_elem(writer, "relationtype",
                    get_affiliation_relation_type(id), 
                    { "object" : "Person", "subject" : "Group" })
        ou_cache[id] = 1
    # od

    #
    # Step 2 -- kull.
    logger.info("Processing all kull")
    _OU_helper(fs.info.list_kull, _kull_db_attributes,
               register_kull_relation_type, get_kull_relation_type,
               writer)

    #
    # Step 3 -- UE
    logger.info("Processing all UE")
    _OU_helper(fs.undervisning.list_undervisningenheter, _ue_db_attributes,
               register_ue_relation_type, get_ue_relation_type,
               writer)
# end output_OU_types



def _OU_helper(getter, attribute_list, register, lookup, writer):
    """Internal function to help output_OU_types.

    getter -- function to fetch the data from the database
    attribute_list -- which attributes to select from db_rows
    register -- how to register new IDs
    lookup   -- how to look them up
    writer   -- XML helper instance.
    """

    cache = dict()
    for row in getter():
        id = make_sko(*[row[x] for x in attribute_list])
        if id in cache:
            continue
        # fi

        register(id)
        output_elem(writer, "relationtype", lookup(id),
                    { "object" : "Person", "subject" : "Group" })
        cache[id] = 1
    # od
# end _OU_helper



def get_primary_account(person, account):
    acc_id = person.get_primary_account()
    try:
        account.clear()
        account.find(acc_id)
        return account.account_name
    except Errors.NotFoundError:
        logger.warn("No account for person with internal id %s",
                    person.entity_id)
    # yrt

    return None
# end get_primary_account



def output_people(writer):
    db = Factory.get("Database")()
    person = Factory.get("Person")(db)
    account = Factory.get("Account")(db)

    logger.info("Caching email/account information")
    uname2mail = account.getdict_uname2mailaddr()

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
                              ("family", const.PersonName("LAST"))):
            name = person_get_item(person.get_name, cereid)
            if name:
                name_collection.append((xmlid, name))
            # fi
        # od    

        if (not ("given" in [x[0] for x in name_collection]) and 
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

        # 
        # Work title, user name and e-mail...
        primary_uname = get_primary_account(person, account)
        for value, name_type in ((person_get_item(person.get_name,
                                                  const.PersonName("WORKTITLE")),
                                  "work"),
                                 (primary_uname, "uname"),
                                 (uname2mail.get(primary_uname), "email")):
            if value:
                output_elem(writer, "partname", value,
                            { "partnametype" : get_name_type(name_type) })
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
    affgroup_cache = dict()
    
    for row in person.list_affiliations(fetchall = False):
        internal_id = (int(row["affiliation"]),
                       int(row["status"]),
                       int(row["ou_id"]))
        if internal_id in affiliation_cache:
            continue
        # fi
        affiliation_cache[internal_id] = 1

        group_id = int(row["affiliation"]), int(row["status"])
        if group_id in affgroup_cache:
            continue
        # fi
        affgroup_cache[group_id] = 1

        name_for_humans = ("Affiliation status %s" %
                           const.PersonAffStatus(row["status"]))
        writer.startElement("group")
        output_elem(writer, "description", name_for_humans)
        xml_id = make_id(*group_id)
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
        sko = make_sko(*[row[x] for x in _kull_db_attributes])
        kull_cache[internal_id] = sko

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
        sko = make_sko(*[row[x] for x in _ue_db_attributes])
        ue_cache[id] = sko

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



def output_kull_relations(writer, person, person_info, kull_info, fs):
    """Output all relations representing KULL."""

    logger.debug("Writing all kull <relation>s")
    
    for internal_id, sko in kull_info.items():
        # All students have the same OU within the same kull
        writer.startElement("relation", {"relationtype" :
                                         get_kull_relation_type(sko)})
        writer.startElement("subject")
        xml_id = make_id(*internal_id)
        output_elem(writer, "groupid", xml_id,
                    {"groupidtype" : get_group_id_type("kull")})
        writer.endElement("subject")

        writer.startElement("object")
        studieprogram_kode, terminkode, arstall = internal_id
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
# end output_kull_relations



def output_affiliation_relations(writer, person, person_info,
                                 affiliation_info):
    """Output all relations representing affiliations."""

    logger.debug("Writing all affiliation <relation>s")    

    for (aff, status, ou_id), human_name in affiliation_info.items():
        writer.startElement("relation",
                            {"relationtype" :
                             get_affiliation_relation_type(ou_id)})
        writer.startElement("subject")
        xml_id = make_id(aff, status)
        output_elem(writer, "groupid", xml_id,
                    {"groupidtype" : get_group_id_type("affiliation")})
        writer.endElement("subject")

        writer.startElement("object")
        for row in person.list_affiliations(affiliation = aff,
                                            status = status,
                                            ou_id = ou_id):
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
# end output_affiliation_relations



def output_ue_relations(writer, person, person_info, ue_info, fs):
    """Output all relations representing UE."""

    logger.debug("Writing all UE <relation>s")

    for internal_id, sko in ue_info.items():
        writer.startElement("relation", {"relationtype" :
                                         get_ue_relation_type(sko)})
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


# end output_ue_relations



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

    # output_kull_relations(writer, person, person_info, kull_info, fs)

    output_affiliation_relations(writer, person, person_info,
                                 affiliation_info)

    output_ue_relations(writer, person, person_info, ue_info, fs)
# end output_relations



def generate_report(writer):
    """Main driver for the report generation."""

    writer.startDocument(encoding = "iso8859-1")

    output_properties(writer)
    
    person_info = output_people(writer)
    f = open("foobar.info", "w")
    f.write("{")
    for k, value in person_info.items():
        f.write("%d : (%d, '%s'),\n" % (k, value[0], value[1]))
    # od
    f.write("}")

    # person_info = eval(open("foobar.info", "r").read())

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
