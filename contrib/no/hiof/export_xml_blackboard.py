#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2007 University of Oslo, Norway
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

# http://imsproject.org/enterprise/entv1p1/imsent_bindv1p1.html

import sys
import getopt
import time

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import AtomicFileWriter
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


def out_extension(element, element_data, attributes={}):
    """
    Output extension elements
    """
    xmlwriter.startElement("extension")
    out(element, element_data, attributes)
    xmlwriter.endElement("extensions")
    

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


def out_description(short, long, full):
    """
    Output description element
    """
    xmlwriter.startElement("description")
    out('short', short)
    out('long', long)
    out('full', full)
    xmlwriter.endElement("description")


# TODO: ikke ferdig
def out_role(role):
    xmlwriter.startElement("role")
    # status
    xmlwriter.endElement("role")


def out_member(member_id, id_source, role, status):
    xmlwriter.startElement("member")
    out_id(member_id, id_source)
    out_role(role)
    xmlwriter.endElement("member")


# TBD: hva skal vi skrive av info egentlig? Må diskuteres med hiof
def output_properties():
    """
    Output properties element
    """
    # TBD specify lang?
    xmlwriter.startElement("properties")
    # TBD: output comments?
    out("datasource", "cerebrum")
    out("target", "Blackboard LMS")
    # TBD: output type?
    out("datetime", time.strftime("%Y-%m-%dT%H:%M:%S"))
    xmlwriter.endElement("properties")


# TODO: Antar at person info er en dict. Mulig at det må endres.
def output_person(person):
    """
    Output person element
    """    
    xmlwriter.startElement("person")
    # spec: EXTERNAL_PERSON_KEY
    out_id(person['uname'], 'Cerebrum')
    # spec: USER_ID
    out('userid', person['uname'])
    # spec: SYSTEM_ROLE
    out('systemroletype', {'systemroletypetype': 'None'})
    # spec: FIRSTNAME, LASTNAME
    out_name(person['family_name'], person['given_name'])
    # spec: EMAIL
    out('email', person['primary_email_address'])
    # spec: INSTITUTION_ROLE
    out('institutionrole', {'institutionroletype': 'Student'})
    # spec: PASSWD
    # TODO: spec ikke ferdig
    out_extension('x_bb_password', person['passwd'])
    # spec: STUDENT_ID
    out_extension('x_bb_studentid', person['studentid'])
    # spec: JOB_TITLE
    # TODO: spec ikke ferdig
    out_extension('x_bb_?', person['job_title'])
    # spec: DEPARTMENT
    # TODO: spec ikke ferdig
    out_extension('x_bb_?', person['department'])
    # spec: M_PHONE
    out('tel', person['tel'], {'teltype': 'mobile'})
    # spec: PUBLIC_IND
    out_extension('x_bb_public_indicator', 'N')
    xmlwriter.endElement("person")
    

# TODO: datastruktur...
def output_course(course):
    """
    Output course information for a course
    """
    xmlwriter.startElement("group")
    # spec: COURSE_ID
    out_id(course['course_id'], 'FS')
    # TODO: avklar om EXTERNAL_COURSE_KEY == <description><short>
    # spec: EXTERNAL_COURSE_KEY, COURSE_NAME, DESCRIPTION
    output_description(**course['description'])
    xmlwriter.endElement("group")
    

def output_membership(membership):
    xmlwriter.startElement("membership")
    # spec: EXTERNAL_COURSE_KEY
    out_id(membership['course_id'], 'FS')
    # spec: EXTERNAL_PERSON_KEY, ROLE, STATUS
    out_member(membership['person_id'], membership['id_source'],
               membership['person_role'], membership['person_status'])
    xmlwriter.endElement("membership")


def generate_document(persons, courses, course_memberships, assignements):
    """
    Write the boilerplate part of the document.
    """
    xmlwriter.startDocument(encoding="UTF-8")
    xmlwriter.startElement("enterprise")
    # TBD: output comments?
    output_properties()
    # Write all persons
    for person in persons:
        output_person(person)
    # Write all courses
    for course in courses:
        output_course(course)
    # Write course memberships (kursdeltagelse)
    for membership in course_memberships:
        output_membership(membership)
    # Write staff assignments (undervisningsoppdrag)
    for membership in assignments:
        output_membership(membership)
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

    stream = AtomicFileWriter(filename)
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
