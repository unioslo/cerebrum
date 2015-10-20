#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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

import sys, time, getopt

import cerebrum_path, cereconf
from Cerebrum.Utils import Factory, AtomicFileWriter
from Cerebrum.extlib import xmlprinter


# We can process these export IDs only
selectors = { #"uname"    : { "xmlname"  : "userid",
              #               "function" : lambda fnr, person, const: person2uname(fnr) },
              #"phone"    : { "xmlname"  : "direktetelefon",
              #               "function" : lambda fnr, person, const: person2phone(person, const) },
              "mail"     : { "xmlname"  : "e-mail",
                             "function" : lambda fnr, person, const: person2email(fnr) },
              "fullname" : { "xmlname"  : "persnavn",
                             "function" : lambda fnr, person, const: person2fullname(person, const) },
              "URL"      : { "xmlname"  : "url",
                             "function" : lambda fnr, person, const: person2URL(person, const) }, }

__doc__ = """
Usage: export_to_SAP.py [OPTIONS]

OPTIONS:
        -i, --id <idtype>
             include <idtype> into the export. Only those specified will
             be included. The legal values are %s.
        -a, --all
             alias for including all id-types
        -f, --file <filename>
             filename to export to.

This script exports some employee data to SAP.

Specifically, this script generates an XML file according to schema
specified.

Only the employees are exported. We export the following data items:
#
# Jazz: 2007-08-22
# unames cannot be exported to SAP for now as SSØ did not implement
# functionality for reading uname-tag
e-mail, uname , fullname and URL. Other elements may be added later.

An example of a person element might look something like this:

<perskomm>
    <personnr>12345678901</personnr>
    <persnavn>Ole Brumm</persnavn>
    <e-mail>olebrumm@usit.uio.no</e-mail>
    <url>http://folk.uio.no/olebrumm</url>
</Perskomm>

The elements for which we have no values are left empty. If no data items
for a given employee have values, we skip that employee altogether.

""" % str(selectors.keys())


__version__ = "$Revision$"
# $Source$


__cache_fnr2mail = dict()
__cache_fnr2uname = dict()


def _fill_caches(person, const):
    """Fill all the caches, so that we can save time"""

    logger.info("Caching information")
    
    # person -> e-mail
    global __cache_fnr2mail
    __cache_fnr2mail = person.getdict_external_id2mailaddr(
        const.externalid_fodselsnr)
    logger.info("%d entries in fnr2mail", len(__cache_fnr2mail))

    # person -> uname
    global __cache_fnr2uname
    __cache_fnr2uname = person.getdict_external_id2primary_account(
        const.externalid_fodselsnr)
    logger.info("%d entries in fnr2uname", len(__cache_fnr2uname))


def person2email(fnr):
    """Find the primary e-mail address for the given person.

    Return None if no e-mail address is found.
    """

    return __cache_fnr2mail.get(fnr)


#def person2uname(fnr):
#    """Find the primary user name for the given person.

#    Return None if no uname is found.
#    """

#    return __cache_fnr2uname.get(fnr)


def person2fullname(person, const):
    """Find the full name for the given person.

    Return None if no name is found.
    """

    return person.get_name(const.system_cached, const.name_full)


#def person2phone(person, const):
#    """Find the primary phone number for the given person.

#    Return None if no phone number is found.
#    """

#    phonerows = person.get_contact_info(type=const.contact_phone)
#    if len(phonerows) > 0:
#        return phonerows[0]["contact_value"]

#    return None


def person2URL(person, const):
    """Find the primary URL for the given person.

    Return None if no URL is found.
    """

    URLrows = person.get_contact_info(type=const.contact_url)
    if len(URLrows) > 0:
        return URLrows[0]["contact_value"]

    return None    


def person2fnr(person, const):
    """Map the internal person_id (entity_id) to an fnr"""

    for system in [getattr(const, name) for name in 
                   cereconf.SYSTEM_LOOKUP_ORDER]:
        fnr = person.get_external_id(system, const.externalid_fodselsnr)
        if not fnr:
            continue

        return str(fnr[0]["external_id"])

    return None


def generate_export(writer, id_list):
    """Main routine to drive the export.

    The entire process can be summarize thus:

    * Output static headers
    * For each employee do:
        + locate fnr (it's mandatory)
        + locate all required export IDs
        + output the person element
    """

    writer.startDocument(encoding = "iso8859-1")
    writer.startElement("bas2sap")

    generate_static_headers(writer)
    db = Factory.get("Database")()
    person = Factory.get("Person")(db)
    const = Factory.get("Constants")(db)
    account = Factory.get("Account")(db)
    _fill_caches(person, const)

    processed = dict()
    for row in person.list_affiliations(affiliation = const.affiliation_ansatt,
                                        fetchall = False):
        # FIXME: might fail
        person.clear()
        person.find(row["person_id"])
        fnr = person2fnr(person, const)
        if not fnr or fnr in processed:
            continue
        else:
            processed[fnr] = 1
    
        tmp = dict()
        for id_kind in id_list:
            # selectors is indexed by the ID type we want to export.
            # selectors[id_kind]['function'] gives as a callable object
            # that, given an fnr, returns the proper value.
            tmp[id_kind] = selectors[id_kind]["function"](fnr, person, const)

        # Skip entries for which we have to elements at all
        if not tmp:
            continue

        output_person(writer, fnr, tmp)

    logger.info("Processed %d fnrs", len(processed))
    writer.endElement("bas2sap")
    writer.endDocument()


def output_person(writer, fnr, data):
    """Output data pertaining to one person.

    data is a dictionary mapping id kind to id value.
    """

    key_order = ["fullname", "mail", "URL"]
    #"phone", 
    # "uname"]
    # IVR 2007-08-13 Make sure that we do not forget any keys.
    assert set(key_order) == set(selectors.keys()), \
           "Did you forget to update code?"
    writer.startElement("perskomm")
    writer.dataElement("persnr", fnr)
    
    for k in key_order:
        if data[k] != None:
            writer.dataElement(selectors[k]["xmlname"], data[k])

    writer.endElement("perskomm")


def generate_static_headers(writer):
    """Generate the fixed headers for the export."""

    writer.startElement("properties")
    writer.dataElement("source", "Cerebrum@UiO")
    writer.dataElement("dato", time.strftime("%Y-%m-%d"))
    writer.dataElement("target", "SAP@UiO")
    writer.endElement("properties")
    logger.info("done writing static headers")


def usage():
    print __doc__


def main(argv=None):
    global logger
    logger = Factory.get_logger("cronjob")

    if argv is None:
        argv = sys.argv

    try:
        options, rest = getopt.getopt(argv[1:],
                                      "i:f:a", ["id=", "file=", "all"])
    except getopt.GetoptError, value:
        print "Wrong option", value
        usage()
        return 1

    # Which ids we want to export
    id_list = list()
    # XML-filename
    output_filename = None

    for option, value in options:
        if option in ("-i", "--id"):
            if value not in selectors.keys():
                logger.warn("Illegal ID value %s (ignored)", value)
            elif value in id_list:
                logger.warn("Duplicate ID value %s (duplicate ignored)", value)
            else:
                id_list.append(value)

        elif option in ("-f", "--file"):
            output_filename = value

    # Option "--all" overrides specific id-lists
    for option, value in options:
        if option in ("-a", "--all"):
            logger.info("Option '--all' specified; all id-types will be included")
            id_list = selectors.keys()

    if not id_list:
        logger.warn("No IDs specified for export. No XML file generated")
        return 2

    stream = AtomicFileWriter(output_filename, "w")
    writer = xmlprinter.xmlprinter(stream,
                                   indent_level = 2,
                                   # Human-readable output
                                   data_mode = True,
                                   input_encoding = "latin1")
    generate_export(writer, id_list)
    stream.close()


if __name__ == "__main__":
    sys.exit(main())
