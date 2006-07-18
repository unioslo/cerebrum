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

"""This script exports some employee data to SAP.

Specifically, this script generates an XML file according to schema
specified:

<URL: http://folk.uio.no/baardj/BAS2SAP/BAS2SAP.html>

Only the employees are exported. We export the following data items:

e-mail, uname, phone number, URL. Right now only e-mail and uname are
implemented.

An example of a person element might look something like this:

<Person ID="12345678901">
    <email>olebrumm@usit.uio.no</email>
    <userid>olebrumm</userid>
    <Telephone Type="Jobb" Prioritet="1">22222222</Telephone>
    <Telephone Type="mobil-jobb" Prioritet="1">22222222</Telephone>
    <BibsysID></BibsysID>
    <Picture></Picture>
    <IDCardNumber></IDCardNumber>
    <URL>http://folk.uio.no/olebrumm</URL>
</Person>

The elements for which we have no values are left empty. If no data items
for a given employee have values, we skip that employee altogether.
"""

import sys, time, getopt

import cerebrum_path, cereconf
from Cerebrum.Utils import Factory, AtomicFileWriter
from Cerebrum.extlib import xmlprinter


# We can process these export IDs only
selectors = { "uname" : { "xmlname"  : "userid",
                          "function" : lambda fnr: person2uname(fnr) },
              "mail"  : { "xmlname"  : "email",
                          "function" : lambda fnr: person2email(fnr) }, }


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


def person2uname(fnr):
    """Find the primary user name for the given person.

    Return None if no uname is found.
    """

    return __cache_fnr2uname.get(fnr)


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
    writer.startElement("BAS2SAP")

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
            value = selectors[id_kind]["function"](fnr)
            if value: tmp[id_kind] = value

        # Skip entries for which we have to elements at all
        if not tmp:
            continue

        output_person(writer, fnr, tmp)

    logger.info("Processed %d fnrs", len(processed))
    writer.endElement("BAS2SAP")
    writer.endDocument()


def output_person(writer, fnr, data):
    """Output data pertaining to one person.

    data is a dictionary mapping id kind to id value.
    """

    writer.startElement("person", { "ID" : fnr })

    for key, value in data.items():
        writer.dataElement(selectors[key]["xmlname"], value)

    writer.endElement("person")


def generate_static_headers(writer):
    """Generate the fixed headers for the export."""

    writer.startElement("properties")
    writer.dataElement("datasource", "Cerebrum@UiO")
    writer.dataElement("target", "SAP@UiO")
    writer.dataElement("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))
    writer.endElement("properties")
    logger.info("done writing static headers")


def usage():
    print """
Usage: export_to_SAP.py [OPTION]

OPTIONS:
        -i, --id <idtype>
             include <idtype> into the export. Only those specified will
             be included. The legal values are %s.
        -f, --file <filename>
             filename to export to.
""" % str(selectors.keys())


def main():
    global logger
    logger = Factory.get_logger("cronjob")

    try:
        options, rest = getopt.getopt(sys.argv[1:],
                                      "i:f:", ["id=", "file="])
    except getopt.GetoptError, value:
        print "Wrong option", value
        usage()
        sys.exit(1)

    # Which ids we want to export
    id_list = list()
    # XML-filename
    output_file = None
    
    for option, value in options:
        if option in ("-i", "--id"):
            if value not in selectors.keys():
                logger.warn("Illegal ID value %s (ignored)", value)
            elif value in id_list:
                logger.warn("Duplicate ID value %s (duplicate ignored)", value)
            else:
                id_list.append(value)

        elif option in ("-f", "--file"):
            output_file = value

    if not id_list:
        logger.warn("No IDs specified for export. No XML file generated")
        sys.exit(0)

    stream = AtomicFileWriter(output_file, "w")
    writer = xmlprinter.xmlprinter(stream,
                                   indent_level = 2,
                                   # Human-readable output
                                   data_mode = True,
                                   input_encoding = "latin1")
    generate_export(writer, id_list)
    stream.close()


if __name__ == "__main__":
    main()


# arch-tag: 847aacd7-5551-48b3-8d11-5fab60dcb87e
