#!/usr/bin/env python2.2

# Copyright 2002, 2003 University of Oslo, Norway
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

import cerebrum_path

import re
import os
import sys
import cereconf

from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum.Utils import XMLHelper
from Cerebrum.modules.no.uio.access_FS import FSPerson

default_person_file = "/cerebrum/dumps/FS/persons.xml"
default_topics_file = "/cerebrum/dumps/FS/topics.xml"
default_studprog_file = "/cerebrum/dumps/FS/studprog.xml"

cereconf.DATABASE_DRIVER='Oracle'
Cerebrum = Database.connect(user="ureg2000", service="FSPROD.uio.no")
FSP = FSPerson(Cerebrum)
xml = XMLHelper()

def write_person_info(outfile):
    # KURS & EVU fagpersoner
    # Employees from FS related to ordinary courses KURS.
    # Prefix: F
    # !!! Mulig at dette er den eneste spørringen som trengs !!!

    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    # Her kan stedkodeinfo utledes direkte ...
    cols, fagpersoner = FSP.GetKursFagpersonundsemester()
    for p in fagpersoner:
        f.write(xml.xmlify_dbrow(p, xml.conv_colnames(cols), 'fagperson') + "\n")

    # STUDENTS
    # Studensts from FS
    # Prefix: S

    cols, students = FSP.GetStudinfRegkort()
    for s in students:
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'student') + "\n")

    cols, students = FSP.GetStudinfNaaKlasse()
    for s in students:
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'student') + "\n")

    cols, students = FSP.GetStudinfStudierett()
    for s in students:
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'student') + "\n")

    # EVU STUDENTS
    # Evu students from FS
    # Prefix: E

    cols, evustud = FSP.GetStudinfEvuKurs()
    for e in evustud:
        f.write(xml.xmlify_dbrow(e, xml.conv_colnames(cols), 'evu') + "\n")
    f.write("</data>\n")

def write_topic_info(outfile):
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, topics = FSP.GetAlleEksamener()
    for t in topics:
        # The Oracle driver thinks the result of a union of ints is float
        fix_float(t)
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'topic') + "\n")
    f.write("</data>\n")

def write_studprog_info(outfile):
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta = FSP.FinnAlleStudprogSko()
    for t in dta:
        # The Oracle driver thinks the result of a union of ints is float
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'studprog') + "\n")
    f.write("</data>\n")

def fix_float(row):
    for n in range(len(row)):
        if isinstance(row[n], float):
            row[n] = int(row[n])

def main():
    write_person_info(default_person_file)
    write_topic_info(default_topics_file)
    write_studprog_info(default_studprog_file)

if __name__ == '__main__':
    main()
