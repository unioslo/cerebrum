#!/usr/bin/env python2.2

import re
import os
import sys
from Cerebrum import cereconf

from Cerebrum.modules.no.uio.access_FS import FSPerson
from Cerebrum import Database,Errors

default_personfile = "/u2/dumps/FS/persons.dat.2"

cereconf.DATABASE_DRIVER='Oracle'
Cerebrum = Database.connect(user="ureg2000", service="FSDEMO.uio.no")
FSP = FSPerson(Cerebrum)
xml_hdr = '<?xml version="1.0" encoding="ISO-8859-1"?>\n'

# TODO: Some of the XML encoding should be placed in a separate file

def get_person_info():
    # KURS & EVU fagpersoner
    # Employees from FS related to ordinary courses KURS.
    # Prefix: F
    # !!! Mulig at dette er den eneste spørringen som trengs !!!

    f=open(default_personfile, 'w')
    f.write(xml_hdr + "<data>\n")
    # Her kan stedkodeinfo utledes direkte ...
    cols, fagpersoner = FSP.GetKursFagpersonundsemester()
    for p in fagpersoner:
        f.write(_xmlify_dbrow(p, _conv_colnames(cols), 'fagperson') + "\n")

    # STUDENTS
    # Studensts from FS
    # Prefix: S

    cols, students = FSP.GetStudinfRegkort()
    for s in students:
        f.write(_xmlify_dbrow(s, _conv_colnames(cols), 'student') + "\n")

    cols, students = FSP.GetStudinfNaaKlasse()
    for s in students:
        f.write(_xmlify_dbrow(s, _conv_colnames(cols), 'student') + "\n")

    cols, students = FSP.GetStudinfStudierett()
    for s in students:
        f.write(_xmlify_dbrow(s, _conv_colnames(cols), 'student') + "\n")

    # EVU STUDENTS
    # Evu students from FS
    # Prefix: E

    cols, evustud = FSP.GetStudinfEvuKurs()
    for e in evustud:
        f.write(_xmlify_dbrow(e, _conv_colnames(cols), 'evu') + "\n")
    f.write("</data>\n")

def _conv_colnames(cols):
    "Strip tablename prefix from column name"
    prefix = re.compile(r"[^.]*\.")
    for i in range(len(cols)):
        cols[i] = re.sub(prefix, "", cols[i]).lower()
    return cols

def _xmlify_dbrow(row, cols, tag):
    return "<%s " % tag + (
        " ".join(["%s=%s" % (cols[i], _escape_xml_attr(row[i]))
                  for i in range(len(cols))])+"/>")

def _escape_xml_attr(a):
    # TODO:  Check XML-spec to find out what to quote
    return '"%s"' % a

def main():
    get_person_info()

if __name__ == '__main__':
    main()
