#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2005-2018 University of Oslo, Norway
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

The XML is shaped in accordance with ABC-enterprise schema. e.g.:

<URL: http://folk.uio.no/baardj/ABC/ABC-Enterprise_schema.html>
"""

#
# FIXME: Too many magic constants!
#

import getopt
import sys
import time

import cereconf

from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum import Errors
from Cerebrum import database
from Cerebrum.Utils import Factory
from Cerebrum.extlib import xmlprinter
from Cerebrum.modules.no.hia.access_FS import FS
from Cerebrum.modules.no import Stedkode


#
# A few global variables...
logger = None
cerebrum_db = None
const = None
xmlwriter = None


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

    for id, xml_name in (("work", "work title"),
                         ("uname", "primary account"),
                         ("email", "primary e-mail address")):
        _id_type_cache[id] = xml_name
    # od

    # Affiliations
    _id_type_cache["affiliation"] = dict()
    for c in const.fetch_constants(const.PersonAffStatus):
        aff, status = int(c.affiliation), int(c)
        _id_type_cache["affiliation"][aff, status] = c.description
    # od
# end _cache_id_types

def get_person_id_type(cerebrum_constant):
    if int(cerebrum_constant) not in _id_type_cache:
        logger.warn("%d not found in cache", int(cerebrum_constant))
    return _id_type_cache.get(int(cerebrum_constant), "")
# end _get_person_id_type

def get_name_type(name_type):
    """Maps a name type (partnametype) to a type in XML"""
    return _id_type_cache[name_type]
# end get_name_type

def get_contact_type(contact_type):
    return _id_type_cache[contact_type]
# end get_contact_type

def get_group_id_type(kind):
    """Maps a group id kind to a type in XML"""
    return { "pay"         : "paid-group",
             "kull"        : "kullgroup",
             "ue"          : "uegroup" }[kind]
# end get_group_id_type

def get_all_affiliations():
    """Returns all aff/status pairs registered."""
    return _id_type_cache["affiliation"].keys()
# end get_all_affiliations

def get_affiliation_type(affiliation, status):
    """Return a human-friendly description for a given aff/status."""
    title = _id_type_cache["affiliation"][(int(affiliation),
                                           int(status))]
    return title + " (%d:%d)" % (affiliation, status)
# end get_affiliation_type





def person_get_item(getter, item_variant,
                    srcs = cereconf.SYSTEM_LOOKUP_ORDER + ("system_cached",)):
    """Fetch a suitable version of a person's attribute (name, id, etc.).

    Walk through cereconf.SYSTEM_LOOKUP_ORDER and return the first found
    item of the specified kind.
    """

    for system in srcs:
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
    """Make an ID out of a sequence."""

    return ":".join([str(x) for x in rest])
# end make_id



def make_sko(fakultet, institutt, avdeling):
    return "".join(["%02d" % x
                    for x in (fakultet, institutt, avdeling)])
# end make_sko



def output_elem(elem, elemdata, attributes = {}):
    """Small helper function for XML writing.

    if-test happens quite often.
    """
    
    if elemdata or attributes:
        xmlwriter.dataElement(elem, elemdata, attributes)
    # fi
# end output_elem



def output_properties():
    """Write a (semi)fixed header for our XML document.

    All types, that we use later in the XML file, must be declared here.
    """

    xmlwriter.startElement("properties")

    output_elem("datasource", "cerebrum")
    output_elem("target", "aksesskontrol")
    output_elem("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S"))

    # All ID types used must be declared first. The types are to be declared
    # in a certain order!
    xmlwriter.startElement("types")

    for c in ("uname", "email"):
        output_elem("contacttype", get_contact_type(c),
                    { "subject" : "person" })
    # od

    output_elem("orgidtype", "institusjonsnummer")

    output_elem("orgnametype", "name")

    # We identify OUs by their sko (fak, inst, avd)
    output_elem("ouidtype", "sko")

    # We output plain names
    output_elem("ounametype", "name")

    for c in (const.EntityExternalId("NO_BIRTHNO"),
              const.EntityExternalId("HiA_SAP_EMP#"),
              const.EntityExternalId("NO_STUDNO")):
        output_elem("personidtype", get_person_id_type(c))
    # od

    for c in ("work",):
        output_elem("partnametype", get_name_type(c))
    # od

    for c in ("kull", "ue", "pay"):
        output_elem("groupidtype", get_group_id_type(c))
    # od

    # We have to split N-ary relationships with N > 2:
    # kull == (ou, people, kull)
    #      == (kullgroup + (kullgroup + org/ou) + (kullgroup + people))
    # ue == (ou, people, ue)
    #    == (uegroup + (uegroup + org/ou) + (uegroup + people))
    for prefix in ("kull", "ue"):
        output_elem("relationtype", prefix + "-ou",
                    { "subject" : "organization", "object" : "group" })
        output_elem("relationtype", prefix + "-people",
                    { "subject" : "group", "object"  : "person" })
    # od

    # Students who paid semavgift
    output_elem("relationtype", "paid-people",
                { "subject" : "group", "object" : "person" })

    # Affiliations are a bit more tricky. We make a new relationtype for each
    # aff/status pair.
    for aff, status in get_all_affiliations():
        output_elem("relationtype", get_affiliation_type(aff, status),
                    { "subject" : "organization", "object" : "person" })
    # od
    
    xmlwriter.endElement("types")

    xmlwriter.endElement("properties")
# end output_properties



def get_primary_account(person, account):
    acc_id = person.get_primary_account()
    try:
        account.clear()
        account.find(acc_id)
        return account.account_name
    except Errors.NotFoundError:
        logger.info("No account for person with internal id %s",
                    person.entity_id)
    # yrt

    return None
# end get_primary_account



def output_people():
    """Output (some) XML elements describing people.

    The relationships of those people (affiliations, kull, UE) will be dealt
    with elsewhere.
    """
    
    person = Factory.get("Person")(cerebrum_db)
    account = Factory.get("Account")(cerebrum_db)

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
        # (s)he has a number of attributes.
        name_collection = list()
        for xmlid, cereid in (("fn", const.PersonName("FULL")),
                              ("family", const.PersonName("LAST")),
                              ("given", const.PersonName("FIRST"))):
            name = person_get_item(person.get_name, cereid)
            if name:
                name_collection.append((xmlid, name))
            # fi
        # od

        id_collection = list()
        for cereid in (const.EntityExternalId("NO_STUDNO"),
                       const.EntityExternalId("HiA_SAP_EMP#"),
                       const.EntityExternalId("NO_BIRTHNO"),):
            value = person_get_item(person.get_external_id, cereid)
            if value:
                id_collection.append((cereid, value["external_id"]))
            # fi
        # od

        if ((not name_collection) or
            (name_collection[0][0] != "fn") or
            (not id_collection)):
            # Don't make it a warn() -- there are too damn many
            logger.debug("Person id %s lacks some attributes. Skipped", id)
            continue
        # fi

        xmlwriter.startElement("person")
        #
        # Output all IDs
        for i in id_collection:
            # We need some (any, actually) ID for identifying the person
            # later for <relation>s
            id_type, value = i
            person_info[int(id)] = (id_type, value)
            output_elem("personid", value,
                        { "personidtype" : get_person_id_type(id_type) })
        # od

        #
        # Output all the names
        xmlwriter.startElement("name")
        output_elem(*(name_collection[0]))
        
        xmlwriter.startElement("n")
        for xmlid, value in name_collection[1:]:
            output_elem(xmlid, value)
        # od    

        # 
        # Work title, user name and e-mail...
        work_title = person_get_item(person.get_name, const.PersonName("WORKTITLE"))
        if work_title:
            output_elem("partname", work_title,
                        { "partnametype" : get_name_type("work") })
        # fi
        xmlwriter.endElement("n")
        xmlwriter.endElement("name")

        # ISO-style. 
        output_elem("birthdate", person.birth_date.date)
        
        primary_uname = get_primary_account(person, account)
        for value, contact_type in ((primary_uname, "uname"),
                                    (uname2mail.get(primary_uname), "email")):
            if value:
                output_elem("contactinfo", value,
                            { "contacttype" : get_contact_type(contact_type) })
            # fi
        # od
                        
        xmlwriter.endElement("person")
    # od

    logger.info("Done with <person>-elements (%d elements)",
                len(person_info))
    return person_info
# end output_people



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
                        row["affiation"], row["status"], row["ou_id"])
            continue
        # fi
        result.setdefault(sko, list()).append(row)
    # od

    return result
# end sort_affiliations



def output_OU(sko):
    """Typeset exactly one OU (this happens often enough)."""

    xmlwriter.startElement("org")
    output_elem("orgid", str(cereconf.DEFAULT_INSTITUSJONSNR),
                { "orgidtype" : "institusjonsnummer" })
    output_elem("ouid", sko, { "ouidtype" : "sko" })
    xmlwriter.endElement("org")
# end output_OU



def output_affiliation_relation(affiliation, status, sko, people, person_info):
    """Output one <relation>-element as described in output_affiliations."""

    xmlwriter.startElement("relation", { "relationtype" :
                                         get_affiliation_type(affiliation,
                                                              status) })
    xmlwriter.startElement("subject")
    output_OU(sko)
    xmlwriter.endElement("subject")

    xmlwriter.startElement("object")
    for person in people:
        pid = int(person["person_id"])
        if pid not in person_info:
            logger.debug("person_id %d is in Cerebrum, but (s)he has no "
                         "external id in cached data", pid)
            continue
        # fi
            
        idtype, value = person_info[pid]
        output_elem("personid", value,
                    { "personidtype" : get_person_id_type(idtype) })
    # od
    xmlwriter.endElement("object")
    
    xmlwriter.endElement("relation")
# end output_affiliation_relation

    

def output_affiliations(person_info):
    '''Output all affiliation-related information.

    Affiliations are represented with a <relation>-element. Each element
    represents a group of people who have the same affiliation/status at a
    given place. The relationtype attribute contains affiliation/status. The
    <subject> of the <relation> is the OU. The <object> of the  relation is
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
        bulk = person.list_affiliations(affiliation = affiliation,
                                        status = status)
        for sko, people in sort_affiliations(bulk).items():
            output_affiliation_relation(affiliation, status, sko,
                                        people, person_info)
        # od
    # od
# end output_affiliations



def prepare_kull():
    """Output all kull groups.

    'Kull' relationships are expressed through the group concept in the
    ABC-schema. First we define all 'kull' as <group>s. Then we use <relation>
    to link up people to their respective 'kull's (i.e. <group>s).
    """

    db = database.connect(user="I0201_cerebrum", service="FSUIA.uio.no",
                          DB_driver=cereconf.DB_DRIVER_ORACLE)
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
        sko = make_sko(*[row[x] for x in ("faknr_studieansv",
                                          "instituttnr_studieansv",
                                          "gruppenr_studieansv")])
        kull_cache[internal_id] = sko

        xmlwriter.startElement("group")
        output_elem("groupid", xml_id,
                    {"groupidtype" : get_group_id_type("kull")})
        output_elem("description", name_for_humans)
        xmlwriter.endElement("group")
    # od

    logger.info("Done with <group>-elements for kull (%d elements)",
                len(kull_cache))
    return kull_cache
# end prepare_kull



def prepare_ue():
    """Output all undervisningsenhet groups.

    The procedure is the same as for kull (prepare_kull).
    """

    db = database.connect(user="I0201_cerebrum", service="FSUIA.uio.no",
                          DB_driver=cereconf.DB_DRIVER_ORACLE)
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
        sko = make_sko(*[row[x] for x in ("faknr_kontroll",
                                          "instituttnr_kontroll",
                                          "gruppenr_kontroll")])
        ue_cache[id] = sko

        xmlwriter.startElement("group")
        output_elem("groupid", xml_id, 
                    {"groupidtype" : get_group_id_type("ue")})
        output_elem("description", name_for_humans)
        xmlwriter.endElement("group")
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
        logger.info("fnr %s is in FS, but not in Cerebrum", fnr)
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
            logger.debug("Missing external ID in Cerebrum for FS fnr %s",
                         fnr)
            continue
        # fi

        result.append((id_type, peid))
    # od

    return result
# end remap_fnr
        


def output_kull_relations(kull_info, person_info, fs):
    """Output all relations representing KULL.

    Each kull is represented by two <relation>s: one to link kull up against
    an OU; one to list all people registered to that kull.
    """

    logger.debug("Writing all kull <relation>s")
    person = Factory.get("Person")(cerebrum_db)
    
    for internal_id, sko in kull_info.items():
        xml_id = make_id(*internal_id)

        studieprogram_kode, terminkode, arstall = internal_id
        tmpseq = fs.undervisning.list_studenter_kull(studieprogram_kode,
                                                     terminkode,
                                                     arstall)
        logger.debug("FS returned %d students for %s:%s:%s",
                     len(tmpseq), studieprogram_kode, terminkode, arstall)
        students = remap_fnrs(tmpseq, person, person_info)
        if not students:
            logger.info("No students for kull %s. No groups will be generated",
                        internal_id)
            continue
        # fi

        # 
        # Output a relation linking kull and OU:
        xmlwriter.startElement("relation", {"relationtype" : "kull-ou"})
        xmlwriter.startElement("subject")
        output_OU(sko)
        xmlwriter.endElement("subject")
        xmlwriter.startElement("object")
        output_elem("groupid", xml_id,
                    {"groupidtype" : get_group_id_type("kull")})
        xmlwriter.endElement("object")
        xmlwriter.endElement("relation")

        # 
        # Output a relation linking kull and its students:
        xmlwriter.startElement("relation", {"relationtype" : "kull-people"})
        xmlwriter.startElement("subject")
        output_elem("groupid", xml_id,
                    {"groupidtype" : get_group_id_type("kull")})
        xmlwriter.endElement("subject")
        
        # All students have the same OU within the same kull. 'relationtype'
        # attribute will contain this information.
        xmlwriter.startElement("object")
        for item in students:
            id_type, peid = item
            output_elem("personid", peid, 
                        {"personidtype" : get_person_id_type(id_type)})
        # od
        xmlwriter.endElement("object")
        xmlwriter.endElement("relation")
    # od

    logger.debug("Done with all kull <relation>s")
# end output_kull_relations



def output_ue_relations(ue_info, person_info, fs):
    """Output all relations representing UE.

    Each UE is represented by two <relation>s: one to link UE up against an
    OU; one to list all people registered under that UE.
    """

    logger.debug("Writing all UE <relation>s")
    person = Factory.get("Person")(cerebrum_db)

    for internal_id, sko in ue_info.items():
        xml_id = make_id(*internal_id)

        instnr, emnekode, versjon, termk, aar, termnr = internal_id
        parameters = { "institusjonsnr" : instnr,
                       "emnekode" : emnekode,
                       "versjonskode" : versjon,
                       "terminkode" : termk,
                       "arstall" : aar,
                       "terminnr" : termnr }
        students = remap_fnrs(
            fs.undervisning.list_studenter_underv_enhet(**parameters),
            person, person_info)
        if not students:
            logger.info("No students for UE %s. No groups will be generated",
                        internal_id)
            continue
        # fi

        #
        # Output a relation linking UE and OU:
        xmlwriter.startElement("relation", {"relationtype" : "ue-ou"})
        xmlwriter.startElement("subject")
        output_OU(sko)
        xmlwriter.endElement("subject")
        xmlwriter.startElement("object")
        output_elem("groupid", xml_id,
                    {"groupidtype" : get_group_id_type("ue")})
        xmlwriter.endElement("object")
        xmlwriter.endElement("relation")

        #
        # Output a relation linking UE and its people:
        xmlwriter.startElement("relation", {"relationtype" : "ue-people"})
        xmlwriter.startElement("subject")
        output_elem("groupid", xml_id,
                    {"groupidtype" : get_group_id_type("ue")})
        xmlwriter.endElement("subject")
        xmlwriter.startElement("object")
        for item in students:
            id_type, peid = item
            output_elem("personid", peid,
                        {"personidtype" : get_person_id_type(id_type)})
        # od
        xmlwriter.endElement("object")
        xmlwriter.endElement("relation")
    # od
    logger.debug("Done with all UE <relation>s")
# end output_ue_relations



def prepare_pay():
    """Output a group for all students who paid semavgift."""

    xmlwriter.startElement("group")
    output_elem("groupid", "paid-group",
                {"groupidtype" : get_group_id_type("pay")})
    output_elem("description", "Studenter som har betalt semavgift")
    xmlwriter.endElement("group")
# end prepare_pay
    


def output_pay_relation(person_info, fs):
    """Output a group with all students who paid semavgift."""

    person = Factory.get("Person")(cerebrum_db)

    xmlwriter.startElement("relation", { "relationtype" : "paid-people" })
    xmlwriter.startElement("subject")
    output_elem("groupid", "paid-group",
                {"groupidtype" : get_group_id_type("pay")})
    xmlwriter.endElement("subject")

    xmlwriter.startElement("object")
    for row in fs.student.list_betalt_semesteravgift():
        fnr = "%06d%05d" % (row["fodselsdato"], row["personnr"])
        id_type, peid = fnr_to_external_id(fnr, person, person_info)
        if id_type is None:
            logger.debug("Missing external ID in Cerebrum for FS fnr %s",
                         fnr)
            continue
        # fi

        output_elem("personid", peid, 
                    {"personidtype" : get_person_id_type(id_type)})
    # od
    xmlwriter.endElement("object")
    xmlwriter.endElement("relation")
# end output_pay_relation
    


_ou2sko_cache = dict()
def _cache_ou2sko(ou):
    """Fill up cache with ou_id -> sko mappings."""

    ou = Stedkode.Stedkode(cerebrum_db)
    for row in ou.get_stedkoder():
        sko = make_sko(row["fakultet"], row["institutt"], row["avdeling"])
        _ou2sko_cache[int(row["ou_id"])] = sko
    # od
# end _cache_ou2sko
        
def ou_id2sko(ou_id):
    return _ou2sko_cache.get(int(ou_id))
# end ou_id2sko
    


def ou_id2parent_sko(ou):
    """Return a sko corresponding to a given OU's parent."""

    try:
        parent_id = int(ou.get_parent(const.system_fs))
    except Errors.NotFoundError:
        return None
    # yrt

    return ou_id2sko(parent_id)
# end ou_id2parent_sko



def output_all_OUs():
    """Output all information about OUs."""

    ou = Stedkode.Stedkode(cerebrum_db)
    # Fill up the cache for later usage.
    _cache_ou2sko(ou)

    xmlwriter.startElement("organization")
    output_elem("orgid", str(cereconf.DEFAULT_INSTITUSJONSNR),
                { "orgidtype" : "institusjonsnummer" })
    output_elem("orgname", "Høyskolen i Agder",
                { "lang"        : "no",
                  "orgnametype" : "name" })
    output_elem("realm", "hia.no")

    # Now, output all OUs
    for r in ou.get_stedkoder():
        sko = ou_id2sko(r["ou_id"])
        assert sko, "No sko?"

        try:
            ou.clear()
            ou.find(r["ou_id"])
        except Errors.NotFoundError:
            logger.warn("OU id %s does not exist, but its sko (%s) does",
                        r["ou_id"], sko)
            continue
        # yrt
            
        xmlwriter.startElement("ou")
        output_elem("ouid", sko, { "ouidtype" : "sko" })
        output_elem("ouname", ou.name,
                    { "ounametype" : "name",
                      "lang"       : "no" })
        # TBD: Do we need parent_id?
        # parent_id = ou_id2parent_sko(ou)
        # if parent_id:
        #     output_elem("parentid", parent_id, { "ouidtype" : "sko" })
        # # fi
        xmlwriter.endElement("ou")
    # od

    xmlwriter.endElement("organization")
# end output_all_OUs



def generate_report():
    """Main driver for the report generation."""

    xmlwriter.startDocument(encoding = "iso8859-1")
    xmlwriter.startElement("document")

    output_properties()

    output_all_OUs()
    
    person_info = output_people()

    kull_info = prepare_kull()

    ue_info = prepare_ue()

    prepare_pay()

    #
    # All the relations
    db = database.connect(user="I0201_cerebrum", service="FSUIA.uio.no",
                          DB_driver=cereconf.DB_DRIVER_ORACLE)
    fs = FS(db)

    output_pay_relation(person_info, fs)

    output_affiliations(person_info)

    output_kull_relations(kull_info, person_info, fs)

    output_ue_relations(ue_info, person_info, fs)

    xmlwriter.endElement("document")
    xmlwriter.endDocument()
# end generate_report



def main():
    global logger, const, cerebrum_db, xmlwriter
    logger = Factory.get_logger("cronjob")
    logger.info("generating a new XML for export_ACL")

    cerebrum_db = Factory.get("Database")()
    const = Factory.get("Constants")(cerebrum_db)

    opts, rest = getopt.getopt(sys.argv[1:], "f:",
                               ["--out-file=",])
    filename = None
    for option, value in opts:
        if option in ("-f", "--out-file"):
            filename = value
        # fi
    # od

    _cache_id_types()
    stream = AtomicFileWriter(filename)
    xmlwriter = xmlprinter.xmlprinter(stream,
                                      indent_level = 2,
                                      # Human-readable output
                                      data_mode = True,
                                      input_encoding = "latin1")
    generate_report()
    stream.close()
# end main


if __name__ == "__main__":
    main()
