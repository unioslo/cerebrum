#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010-2018 University of Oslo, Norway
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

"""This script generates an XML file destined for the Cristin publishing system.

The export contains information about:

- OU: All OUs in the given perspective that are not in quarantine.

- Persons: We fetch a union of persons by different criterias:

  #. All persons that has an *employment* from the given source system. To fetch
     employments we use the Cerebrum module `PersonEmployment`.

  #. All persons that has a *TILKNYTTET* affiliation from the given source
     system.

Relevant docs:

* <http://frida.usit.uio.no/prosjektet/dok/import/institusjonsdata/index.html>
* CVS: cerebrum-sites/doc/intern/uio/archive/frida
* <http://www.cristin.no/institusjonsdata/eksempel.xml>
* <http://www.cristin.no/institusjonsdata/>

"""

from __future__ import unicode_literals

import getopt
import sys
import time
import six

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.extlib import xmlprinter

XML_ENCODING = 'iso8859-1'

logger = None


def output_element_helper(xml, element, value, attributes=dict()):
    """A helper function to output XML elements.

    The output element would look like this:

    <ELEMENT KEY1='VALUE1' KEY2='VALUE2' ... >
      VALUE
    </ELEMENT>

    ... where KEY, VALUE pairs come from ATTRIBUTES

    This function is just a shorthand, to avoid mistyping the element names
    in open and close tags.
    """
    # If there are no attributes and no textual value for the element, we do
    # not need it.
    if not attributes and (value is None or not six.text_type(value)):
        return
    xml.startElement(element, attributes)
    xml.data(six.text_type(value))
    xml.endElement(element)


def output_headers(writer, tag, root_ou):
    """Generate a header with (mostly) static data"""
    writer.startElement("beskrivelse")
    output_element("kilde", tag)
    output_element("dato", time.strftime("%Y-%m-%d %H:%M:%S"))
    writer.endElement("beskrivelse")

    writer.startElement("institusjon")
    output_element("institusjonsnr", cereconf.DEFAULT_INSTITUSJONSNR)
    const = Factory.get("Constants")()
    name = root_ou.get_name_with_language(name_variant=const.ou_name,
                                          name_language=const.language_nb,
                                          default="")
    output_element("navnBokmal", name)
    name = root_ou.get_name_with_language(name_variant=const.ou_name_acronym,
                                          name_language=const.language_nb,
                                          default="")
    output_element("akronym", name)
    writer.endElement("institusjon")


def _cache_ou_data(perspective):
    """Fetch all relevant info for our OUs."""
    logger.debug("Starting caching ou_data")

    db = Factory.get("Database")()
    const = Factory.get("Constants")()
    ou = Factory.get("OU")(db)
    ous = dict((x["ou_id"], {"parent_id": x["parent_id"]})
               for x in ou.get_structure_mappings(perspective))

    # Now collect all sko...
    for row in ou.get_stedkoder():
        ous.setdefault(row["ou_id"], dict()).update(
            {"fakultet": row["fakultet"],
             "institutt": row["institutt"],
             "avdeling": row["avdeling"]})

    # Now collect the address information
    for row in ou.list_entity_addresses(entity_type=const.entity_ou,
                                        address_type=const.address_post):
        ous.setdefault(row["entity_id"], dict()).update(
            {
                "postadresse": ", ".join(row[x]
                                         for x in ("address_text", "p_o_box")
                                         if row[x]),
                "postnrOgPoststed": " ".join(row[x]
                                             for x in ("postal_number", "city")
                                             if row[x]),
                "land": row["country"],
            })
    logger.debug("Ending caching ou_data: %d entries", len(ous))
    return ous


def output_OUs(writer, perspective, spread):
    """Output all OUs exportable to Cristin...

    Cristin spec says absolutely nothing about which OUs should be
    published. Let's grab the unquarantined ones.

    The attributes that must be included are:

      - sko
      - parent sko
      - official name

    It's recommended to include contact info and addresses.

    So, the easiest is probably to collect info in multiple passes.

    + NSDkode (not a problem, since UiO has not exported it since SAP came
      online and it's not a required element).
    + datoAktivFra/datoAktivTil (not a problem. Although these dates are not
      registered in Cerebrum, they are not required required elements XML)
    """
    if spread:
        logger.debug("Outputting OUs with spread %s", spread)
    else:
        logger.debug("Outputting all OUs")

    ous = _cache_ou_data(perspective)
    db = Factory.get("Database")()
    ou = Factory.get("OU")(db)
    const = Factory.get("Constants")()

    writer.startElement("organisasjon")

    filtered_ou_ids = ou.search(spread=spread, filter_quarantined=True)
    for row in filtered_ou_ids:
        ou_id = row["ou_id"]
        if ou_id not in ous:
            logger.warn("No information about ou_id=%s cached", ou_id)
            continue

        data = ous[ou_id]
        writer.startElement("enhet")
        for element, value in (
                ("institusjonsnr", cereconf.DEFAULT_INSTITUSJONSNR),
                ("avdnr", data["fakultet"]),
                ("undavdnr", data["institutt"]),
                ("gruppenr", data["avdeling"])):
            output_element(element, value)
        if "parent_id" in data and ous.get(data["parent_id"]):
            counter = [0, ]
            parent_id = get_ou_for_export(ous, filtered_ou_ids,
                                          data["parent_id"], counter)
            parent = ous[parent_id]
        else:
            logger.debug(
                "OU %s (%s) has no parent",
                ou_id,
                "-".join("%02d" % data[x]
                         for x in ("fakultet", "institutt", "avdeling")))
            parent = data
        for element, value in (
                ("institusjonsnrUnder", cereconf.DEFAULT_INSTITUSJONSNR),
                ("avdnrUnder", parent["fakultet"]),
                ("undavdnrUnder", parent["institutt"]),
                ("gruppenrUnder", parent["avdeling"])):
            output_element(element, value)

        # FIXME: Remove this hardcoded junk (this is for testing only)
        output_element("datoAktivFra", "2007-01-01")
        output_element("datoAktivTil", "9999-12-31")

        ou.clear()
        ou.find(ou_id)
        ou_name = ou.get_name_with_language(name_variant=const.ou_name,
                                            name_language=const.language_nb)
        output_element("navnBokmal", ou_name)
        for element in ("postadresse", "postnrOgPoststed", "land",):
            if element in data:
                output_element(element, data[element])
        writer.endElement("enhet")

    writer.endElement("organisasjon")
    logger.debug("OU output complete")


def _cache_person_names(cache, source_system):
    """Preload the interesting name tidbits."""

    db = Factory.get("Database")()
    person = Factory.get("Person")(db)
    const = Factory.get("Constants")()

    logger.debug("Caching person names")
    # Collect the names...
    for row in person.search_person_names(source_system=source_system,
                                          name_variant=(const.name_first,
                                                        const.name_last)):
        person_id = row["person_id"]
        if person_id not in cache:
            continue
        cache[person_id][int(row["name_variant"])] = row["name"]

    for row in person.search_name_with_language(
            entity_type=const.entity_person,
            name_variant=const.work_title,
            name_language=const.language_nb):
        person_id = row["entity_id"]
        if person_id not in cache:
            continue
        cache[person_id][row["name_variant"]] = row["name"]

    logger.debug("Caching person names complete")
    return cache


def _cache_person_contact_info(cache, source_system):
    """Preload the contact info tidbits."""
    logger.debug("Caching person contact info")
    db = Factory.get("Database")()
    person = Factory.get("Person")(db)
    const = Factory.get("Constants")()
    # Now, collect the contact info (tlf, fax, URL)
    for row in person.list_contact_info(source_system=source_system,
                                        contact_type=(const.contact_phone,
                                                      const.contact_fax,
                                                      const.contact_url,),
                                        entity_type=const.entity_person):
        person_id = row["entity_id"]
        if person_id not in cache:
            continue
        chunk = cache[person_id]
        contact_type = row["contact_type"]
        priority = row["contact_pref"]
        if chunk.get(contact_type, {}).get("contact", priority + 1) < priority:
            continue
        chunk[contact_type] = row.dict()
    logger.debug("Caching person contact info complete")
    return cache


def _cache_person_external_id(cache, source_system):
    """Preload various external ids for our employee set.

    fnr is the only key of interest.
    """
    logger.debug("Caching person external ids")
    db = Factory.get("Database")()
    person = Factory.get("Person")(db)
    const = Factory.get("Constants")()

    for row in person.search_external_ids(source_system=source_system,
                                          id_type=const.externalid_fodselsnr,
                                          entity_type=const.entity_person,
                                          fetchall=False):
        if row["entity_id"] not in cache:
            continue
        cache[row["entity_id"]][int(row["id_type"])] = row["external_id"]
    logger.debug("Caching person external ids complete")
    return cache


def _cache_person_reservation_data(cache, source_system):
    """Tag all employees as reserved/publishable."""
    logger.debug("Caching person reservation data")
    db = Factory.get("Database")()
    group = Factory.get("Group")(db)
    try:
        if not hasattr(cereconf, "HIDDEN_PERSONS_GROUP"):
            return cache
        group.find_by_name(cereconf.HIDDEN_PERSONS_GROUP)
    except Errors.NotFoundError:
        return cache

    for row in group.search_members(group_id=group.entity_id):
        if row["member_id"] not in cache:
            continue
        cache[row["member_id"]]["reserved"] = True
    logger.debug("Caching person reservation data complete")
    return cache


def _cache_person_primary_account(cache, source_system):
    """Locate primary accounts for everybody in cache."""
    # Ugh, this is so inelegant...
    logger.debug("Caching primary accounts")
    # 1. cache person_id -> primary account_id
    db = Factory.get("Database")()
    account = Factory.get("Account")(db)
    const = Factory.get("Constants")()
    pid2aid = dict((x["person_id"], x["account_id"])
                   for x in
                   account.list_accounts_by_type(primary_only=True))
    # 2. load all account_id -> account_name
    aid2uname = dict((x["entity_id"], x["entity_name"])
                     for x in
                     account.list_names(const.account_namespace))
    # 3. finally, fixup the cache
    for pid in cache:
        uname = aid2uname.get(pid2aid.get(pid))
        if not uname:
            continue
        data = cache[pid]
        data["account_name"] = uname
    logger.debug("Caching primary accounts complete")
    return cache


def _cache_person_info(perspective, source_system):
    """Preload info for all of our eligible bachelors...

    There is no elegant way of collecting all of the required info. The easiest
    is probably to establish an id set for everybody we want to export, and then
    incrementally augment the data set with what's needed.
    """

    # First, collect the initial set of candidates. They are the ones with the
    # following affs:
    # ANSATT/* (however, NOT ANSATT/bilag), TILKNYTTET/*
    #
    db = Factory.get("Database")()
    person = Factory.get("Person")(db)
    const = Factory.get("Constants")()

    logger.debug("Caching person info")
    ous = _cache_ou_data(perspective)
    # person_id -> <dict with attributes>
    cache = dict()

    # First, collect everybody of value...
    # ... the employees...
    for row in person.search_employment(source_system=source_system):
        person_id = row["person_id"]
        if row["ou_id"] not in ous:
            logger.info("Skipping employment %s, since ou_id=%s is absent "
                        "from output", row, row["ou_id"])
            continue

        if person_id not in cache:
            cache[person_id] = {"employments": list()}
        cache[person_id]["employments"].append(row.dict())
    # ... and the "rest" -- ph.d students and the like.
    # IVR 2011-02-17 FIXME: Should this be affiliation-based?
    # TODO: Should probably be configurable what affiliations we choose.
    for row in person.list_affiliations(
            source_system=source_system,
            affiliation=const.affiliation_tilknyttet):
        if row["ou_id"] not in ous:
            logger.info("Skipping affiliation %s, since ou_id=%s is absent "
                        "from output", row, row["ou_id"])
            continue

        person_id = row["person_id"]
        if person_id not in cache:
            cache[person_id] = {"affiliations": list()}
        if "affiliations" not in cache[person_id]:
            cache[person_id]["affiliations"] = list()
        cache[person_id]["affiliations"].append(row.dict())

    cache = _cache_person_names(cache, source_system)
    cache = _cache_person_contact_info(cache, source_system)
    cache = _cache_person_external_id(cache, source_system)
    cache = _cache_person_reservation_data(cache, source_system)
    cache = _cache_person_primary_account(cache, source_system)

    logger.debug("Caching person data complete: %d entries", len(cache))
    return cache


def output_employment(writer, employment, ou_cache):
    """Output one complete employment element.
    """

    ou_id = employment["ou_id"]
    try:
        ou = ou_cache[ou_id]
    except KeyError:
        logger.warn(
            "Could not find ou_id:%s for employment: %s",
            ou_id, employment)
        return
    writer.startElement("ansettelse")
    for element, value in (
            ("institusjonsnr", cereconf.DEFAULT_INSTITUSJONSNR),
            ("avdnr", ou["fakultet"]),
            ("undavdnr", ou["institutt"]),
            ("gruppenr", ou["avdeling"]),
            ("stillingskode", employment["employment_code"]),
            ("stillingsbetegnelse", employment["description"]),
            ("datoTil", employment["end_date"].strftime("%F")),
            ("stillingsandel", float(employment["percentage"])),
            ("datoFra", employment["start_date"].strftime("%F"))):
        output_element(element, value)
    writer.endElement("ansettelse")


def output_guest(writer, entry, ou_cache):
    """Output one complete guest element (associated, ph.d students, etc).
    """
    ou_id = entry["ou_id"]
    ou = ou_cache[ou_id]
    writer.startElement("gjest")
    for element, value in (("institusjonsnr", cereconf.DEFAULT_INSTITUSJONSNR),
                           ("avdnr", ou["fakultet"]),
                           ("undavdnr", ou["institutt"]),
                           ("gruppenr", ou["avdeling"]),
                           #
                           # FIXME: This MUST BE FIXED.
                           # FIXME: Hardcoded stuffo for the sake of testing.
                           ("gjestebetegnelse", "GJ-FORSKER"),
                           ("datoTil", "9999-12-31"),

                           ("datoFra", entry["create_date"].strftime("%F"))):
        output_element(element, value)
    writer.endElement("gjest")


def output_person(writer, chunk, ou_cache, ou_cache_export):
    """Output data about 1 person."""

    const = Factory.get("Constants")()
    rstatus = {True: "J", False: "N"}

    if const.externalid_fodselsnr not in chunk:
        logger.info("Person %s is missing fnr. Will be skipped from output",
                    repr(chunk))
        return
    if const.name_first not in chunk or const.name_last not in chunk:
        logger.info("Person %s is missing name. Will be skipped from output",
                    repr(chunk))
        return

    writer.startElement("person", {"fnr": chunk[const.externalid_fodselsnr],
                                   "reserved": rstatus[chunk.get("reserved",
                                                                 False)]})
    for element, key in (("etternavn", const.name_last),
                         ("fornavn", const.name_first),
                         ("personligTittel", const.work_title)):
        if key not in chunk:
            continue
        output_element(element, chunk[key])

    output_element("brukernavn", chunk.get("account_name"))

    for element, key in (("telefonnr", const.contact_phone),
                         ("telefaxnr", const.contact_fax),
                         ("URL", const.contact_url)):
        contact_block = chunk.get(key)
        if not contact_block:
            continue
        output_element(element, contact_block["contact_value"])
    employments = chunk.get("employments", tuple())
    if employments:
        prep_employments = prepare_employment(
            employments, ou_cache, ou_cache_export)
        writer.startElement("ansettelser")
        for entry in prep_employments:
            output_employment(writer, entry, ou_cache_export)
        writer.endElement("ansettelser")

    associations = [x for x in chunk.get("affiliations", ())
                    if x["affiliation"] == const.affiliation_tilknyttet]
    if associations:
        prep_associations = prepare_employment(
            associations, ou_cache, ou_cache_export)
        writer.startElement("gjester")
        for entry in prep_associations:
            output_guest(writer, entry, ou_cache_export)
        writer.endElement("gjester")
    writer.endElement("person")


def output_people(writer, perspective, source_system, spread):
    """Output all people of interest.

    We publish people who are:

      - Employees
      - Guests (specific kinds)
      - Ph.D students.

    Whether a person belongs to the specified category is decided by
    affiliations (on that person).

      - Names (first, last, work title)
      - Contact info (tlf, fax, URL)
      - Employment info (from affs).
      - Guest info (from affs)
    """
    logger.debug("Output people started")
    ous = _cache_ou_data(perspective)
    ous_filtered = filter_by_spread(ous, spread)
    logger.debug('cached ous %d, filtered ous %d.',
                 len(ous), len(ous_filtered))
    people = _cache_person_info(perspective, source_system)
    writer.startElement("personer")
    for pid in people:
        data = people[pid]
        output_person(writer, data, ous, ous_filtered)

    writer.endElement("personer")
    logger.debug("Output people complete")


def output_xml(sink, tag, root_ou, perspective, source_system, spread):
    writer = xmlprinter.xmlprinter(sink,
                                   indent_level=2,
                                   data_mode=True)
    global output_element
    output_element = (lambda *rest, **kw:
                      output_element_helper(writer, *rest, **kw))
    # Incredibly enough, latin-1 is a requirement.
    writer.startDocument(encoding=XML_ENCODING)
    writer.startElement("fridaImport")
    output_headers(writer, tag, root_ou)
    output_OUs(writer, perspective, spread)
    output_people(writer, perspective, source_system, spread)
    writer.endElement("fridaImport")
    writer.endDocument()


def find_root_ou(identifier):
    """Try to find the ou referred to by identifier.

    A bit like _get_ou() in bofhd... ou_id/stedkode are acceptable.
    """

    # in case it's a sko with "aa-bb-cc"
    identifier = identifier.replace("-", "")
    db = Factory.get("Database")()
    ou = Factory.get("OU")(db)
    co = Factory.get("Constants")()
    if (isinstance(identifier, (long, int)) or
            isinstance(identifier, (str, unicode)) and identifier.isdigit()):
        try:
            ou.find(int(identifier))
            return ou
        except Errors.NotFoundError:
            pass

        if isinstance(identifier, (str, unicode)) and len(identifier) == 6:
            try:
                ou.find_stedkode(identifier[:2],
                                 identifier[2:4],
                                 identifier[4:6],
                                 cereconf.DEFAULT_INSTITUSJONSNR)
                return ou
            except Errors.NotFoundError:
                pass

    # Before quitting, list every root available
    possible_roots = list(x["ou_id"] for x in ou.root())

    def typesetter(x):
        ou.clear()
        ou.find(x)
        return "%s id=%s (%s)" % (
            ou.get_name_with_language(name_variant=co.ou_name_acronym,
                                      name_language=co.language_nb,
                                      default=""),
            ou.entity_id,
            "-".join("%02d" % y
                     for y in (ou.fakultet, ou.institutt, ou.avdeling)))
    logger.error("Could not find root ou for designation '%s'. "
                 "Available roots: %s", identifier,
                 ", ".join(typesetter(x) for x in
                           sorted(possible_roots)))
    sys.exit(1)


def filter_by_spread(cache, spread):
    """Return a dict where each element has the spread.

    Shallow copy is made for values, so changing them will change the originals.
    @param cache: dict with OU information.
    @param spread: spread code to filter for.
    @return dict with elements from cache that have the given spread.
    """
    db = Factory.get("Database")()
    ou = Factory.get("OU")(db)
    ou_ids = ou.search(spread=spread, filter_quarantined=True)
    filtered_cache = {}
    for elm in ou_ids:
        filtered_cache[elm["ou_id"]] = cache[elm["ou_id"]]

    return filtered_cache


def get_ou_for_export(cache, filtered, ou_id, counter):
    """Return ou_id that can be exported.

    @param cache: dict with ou information.
    @param filtered: ous in this list/dict have spread that defines an exportable ou.
    @param ou_id: current value.
    @param counter: list with one integer to count recursive calls.
    @return ou_id to export.
    """
    counter[0] += 1
    if ou_id in filtered or (ou_id,) in filtered:
        return ou_id
    parent_id = None
    parent_id = cache[ou_id].get("parent_id")
    if parent_id is None:  # ou_id is root ou
        return ou_id
    return get_ou_for_export(cache, filtered, parent_id, counter)


def prepare_employment(alist, cache, filtered):
    """Return a list with employments that are exportable.

    @param alist: employments to process.
    @param cache: dict with ous
    @param filtered: ous in this dict have spread that defines an exportable ou.
    @return list of employments for export.
    """
    counter = [0, ]
    from copy import deepcopy
    res = deepcopy(alist)
    for index, elm in enumerate(alist):
        temp = elm["ou_id"]
        res[index]["ou_id"] = get_ou_for_export(cache, filtered, temp, counter)
    return res


class SimilarSizeStreamRecoder(SimilarSizeWriter):
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
        return super(SimilarSizeStreamRecoder, self).write(data)


def main(argv):
    global logger
    logger = Factory.get_logger("cronjob")

    root_ou = None
    output_file = None
    perspective = None
    source_system = None
    tag = None
    spread = None  # export all OUs
    args, junk = getopt.getopt(argv[1:],
                               "o:r:p:s:t:",
                               ("output-file=",
                                "root-ou=",
                                "perspective=",
                                "source-system=",
                                "tag=",
                                "spread=",))
    for option, value in args:
        if option in ("-o", "--output-file",):
            output_file = value
        elif option in ("-r", "--root-ou",):
            root_ou = value
        elif option in ("-p", "--perspective"):
            perspective = value
        elif option in ("-s", "--source-system",):
            source_system = value
        elif option in ("-t", "--tag",):
            tag = value
        elif option in ("--spread",):
            spread = value

    if output_file is None:
        logger.error("No output file name specified.")
        sys.exit(1)

    if root_ou is None:
        logger.error("No root OU is specified.")
        sys.exit(1)

    if tag is None:
        logger.error("No tag is specified. Can't deduce value for <kilde>")
        sys.exit(1)

    const = Factory.get("Constants")()
    if (not perspective or
            not const.human2constant(perspective, const.OUPerspective)):
        logger.error(
            "Bogus perspective '%s'. Available options are: %s",
            perspective,
            ", ".join(six.text_type(x) for x in
                      const.fetch_constants(const.OUPerspective)))
        sys.exit(1)
    perspective = const.human2constant(perspective, const.OUPerspective)

    if (not source_system or
            not const.human2constant(source_system,
                                     const.AuthoritativeSystem)):
        logger.error(
            "Bogus source '%s'. Available options are: %s",
            source_system,
            ", ".join(six.text_type(x) for x in
                      const.fetch_constants(const.AuthoritativeSystem)))
        sys.exit(1)
    source_system = const.human2constant(source_system,
                                         const.AuthoritativeSystem)

    spread = const.human2constant(spread, const.Spread)
    root_ou_obj = find_root_ou(root_ou)
    if spread and not root_ou_obj.has_spread(spread):
        logger.error(
            'Root OU %s does not have %s spread. To export all OUs '
            'run the script without --spread option.',
            root_ou,
            spread)
        if len(root_ou_obj.list_all_with_spread(spread)) == 0:
            logger.error(
                'No OU has %s spread. To be exported to Cristin an OU'
                ' must have this spread.', spread)
        sys.exit(1)
    with SimilarSizeStreamRecoder(output_file,
                                  mode='w',
                                  encoding=XML_ENCODING) as stream:
        stream.max_pct_change = 15
        output_xml(stream, tag, root_ou_obj, perspective, source_system,
                   spread)


if __name__ == "__main__":
    main(sys.argv)
