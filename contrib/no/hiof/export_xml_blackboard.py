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

"""
This script is a part of the Cerebrum -> BlacbBoard LMS sync.

The script generates an IMS Enterprise XML v1.1 file, see
http://www.imsglobal.org/enterprise/entv1p1/imsent_bindv1p1.html for
more information about the standard. The file is imported into
Blackboard such that information about persons, courses, memberships,
etc are updated. Thes script is implemented after the specification
found in cerebrum_eksterne/docs/HIOF/spec/blackboard_hiof.rst.

"""

import sys
import locale
import os
import getopt
import time

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import access_FS
from Cerebrum.modules.no import Stedkode
from Cerebrum.extlib import xmlprinter


## Globals
db = const = logger = None

##
## Data gathering methods 
##

def fetch_person_data():
    """
    Fetch information about persons and return as a data strucure:
    TODO: describe data structure
    """


def fetch_course_data():
    """
    Fetch information about courses, memberships, categories and
    return as a data strucure:
    TODO: describe data structure
    """


##
## Output methods
##

def out(element, element_data, attributes={}):
    """
    Small helper function for XML output.
    """
    if element_data or attributes:
        xmlwriter.dataElement(element, element_data, attributes)


def out_id(id, source):
    """
    Output sourcedid element
    """
    xmlwriter.startElement("sourcedid")
    out('source', source)
    out('id', id)
    xmlwriter.endElement("sourcedid")

    
def out_name(family_name, given_name):
    """
    Output name element
    """
    xmlwriter.startElement("name")
    out('fn', "%s %s" % (given_name, family_name))
    xmlwriter.startElement("n")
    out('family', family_name)
    out('given', given_name)
    xmlwriter.endElement("n")
    xmlwriter.endElement("name")


# TODO: Dette er ikke all informasjon...
def output_person(person):
    """
    Output person element
    """    
    xmlwriter.startElement("person")
    out_id(person['uname'], 'Cerebrum')
    out('userid', person['uname'])
    out_name(person['family_name'], person['given_name'])
    out('email', person['email'])
    xmlwriter.endElement("person")
    

# TBD: hva skal vi skrive av info egentlig? Må diskuteres med hiof
def output_properties():
    """
    Output properties element
    """    
    xmlwriter.startElement("properties")
    out("datasource", "cerebrum")
    out("target", "Blackboard LMS")
    out("datetime", time.strftime("%Y-%m-%dT%H:%M:%S"))
    xmlwriter.endElement("properties")


def generate_document(persons, courses):
    """
    Write the boilerplate part of the document.
    """
    xmlwriter.startDocument(encoding="UTF-8")
    xmlwriter.startElement("enterprise")
    
    output_properties()
    # Write all persons
    for person in persons:
        output_person(person)
    # Write all courses
    for course in courses:
        output_course(course)
    # Write course memberships (kursdeltagelse)
    # ...
    # Write staff assignments (undervisningsoppdrag)
    # ...
    # Write category data (kurskategori)
    # ...
    # Write category memberships (kurskategorimedlemskap)
    # ...    
    xmlwriter.endElement("enterprise")
    xmlwriter.endDocument()
    


def usage(exitcode=0):
    print """Usage: export_xml_blackboard.py [options]
    -o, --out-file: XML output file
    """
    sys.exit(exitcode)


def main():
    """Main driver for the file generation."""

    global xmlwriter, db, const, logger

    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)
    logger = Factory.get_logger("cronjob")

    try:
        opts, args = getopt.getopt(sys.argv[1:], "o:",
                                   ["out-file="])
    except getopt.GetoptError:
        usage(1)

    filename = None
    for opt, val in opts:
        if opt in ('-o', '--out-file'):
            filename = val
    if not filename:
        usage(1)    
    
    stream = Utils.AtomicFileWriter(filename)
    xmlwriter = xmlprinter.xmlprinter(stream,
                                      indent_level=2,
                                      # human-friendly output
                                      data_mode=True,
                                      input_encoding="UTF-8")
    # Get information about persons
    persons = fetch_person_data()
    # Get information about courses (kurs)
    courses = fetch_course_data()
    # Generate and write document
    generate_document(persons, courses)
    stream.close()


if __name__ == '__main__':
    main()
