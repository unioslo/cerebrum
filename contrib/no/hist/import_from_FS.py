#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

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
import getopt
import cereconf

from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum.Utils import XMLHelper
from Cerebrum.modules.no.hist.access_FS import HistFS

default_person_file = "/cerebrum/dumps/FS/hist_stud.xml"
default_topics_file = "/cerebrum/dumps/FS/topics.xml"
default_studieprogram_file = "/cerebrum/dumps/FS/studieprogrammer.xml"
default_regkort_file = "/cerebrum/dumps/FS/regkort.xml"
default_ou_file = "/cerebrum/dumps/FS/ou.xml"

xml = XMLHelper()
fs = None

def write_hist_studinfo(outfile):
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    #Hist-studenter
    cols, histstudenter = fs.GetHistStudent()
    for hs in histstudenter:
        f.write(xml.xmlify_dbrow(hs,xml.conv_colnames(cols),'aktiv') + "\n")
    f.write("</data>\n")

def write_ou_info(outfile):
    """Lager fil med informasjon om alle OU-er"""
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, ouer = fs.GetAlleOUer(cereconf.ORGANIZATIONAL_INSTNR)  # TODO
    for o in ouer:
        f.write(xml.xmlify_dbrow(o, xml.conv_colnames(cols), 'sted') + "\n")
    f.write("</data>\n")

def write_topic_info(outfile):
    """Lager fil med informasjon om alle XXX"""
    # TODO: Denne filen blir endret med det nye opplegget :-(
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, topics = fs.GetAlleEksamener()
    for t in topics:
        # The Oracle driver thinks the result of a union of ints is float
        fix_float(t)
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'topic') + "\n")
    f.write("</data>\n")

def write_regkort_info(outfile):
    """Lager fil med informasjon om semesterregistreringer for
    inneværende semester"""
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, regkort = fs.GetStudinfRegkort()
    for r in regkort:
        f.write(xml.xmlify_dbrow(r, xml.conv_colnames(cols), 'regkort') + "\n")
    f.write("</data>\n")

def write_studprog_info(outfile):
    """Lager fil med informasjon om alle definerte studieprogrammer"""
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta = fs.GetStudieproginf()
    for t in dta:
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'studprog') + "\n")
    f.write("</data>\n")


def fix_float(row):
    for n in range(len(row)):
        if isinstance(row[n], float):
            row[n] = int(row[n])

def usage(exitcode=0):
    print """Usage: [options]
    --topics-file name: override topics xml filename
    --studprog-file name: override studprog xml filename
    --regkort-file name: override regkort xml filename
    --hist-studinfo-file: override hist person xml filename
    --ou-file name: override ou xml filename
    --db-user name: connect with given database username
    --db-service name: connect to given database
    -t: generate topics xml file
    -s: generate studprog xml file
    -r: generate regkort xml file
    -o: generate ou xml (sted.xml) file
    -a: generate active-students file
    """
    sys.exit(exitcode)

def assert_connected(user="HISTBAS", service="FSHIST.uio.no"):
    global fs
    if fs is None:
        db = Database.connect(user=user, service=service,
                              DB_driver='Oracle')
        fs = HistFS(db)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "tsroa",
                                   ["hist-studinfo-file=", "topics-file=",
                                    "studprog-file=", "regkort-file=",
                                    "ou-file=", "db-user=", "db-service="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    person_file = default_person_file
    topics_file = default_topics_file
    studprog_file = default_studieprogram_file
    regkort_file = default_regkort_file
    ou_file = default_ou_file
    db_user = None         # TBD: cereconf value?
    db_service = None      # TBD: cereconf value?
    for o, val in opts:
        if o in ('--hist-studinfo-file',):
            person_file = val
        elif o in ('--topics-file',):
            topics_file = val
        elif o in ('--studprog-file',):
            studprog_file = val
        elif o in ('--regkort-file',):
            regkort_file = val
        elif o in ('--ou-file',):
            ou_file = val
        elif o in ('--db-user',):
            db_user = val
        elif o in ('--db-service',):
            db_service = val
    assert_connected(user=db_user, service=db_service)
    for o, val in opts:
        if o in ('-a',):
            write_hist_studinfo(person_file)
        elif o in ('-t',):
            write_topic_info(topics_file)
        elif o in ('-s',):
            write_studprog_info(studprog_file)
        elif o in ('-r',):
            write_regkort_info(regkort_file)
        elif o in ('-o',):
            write_ou_info(ou_file)

if __name__ == '__main__':
    main()
