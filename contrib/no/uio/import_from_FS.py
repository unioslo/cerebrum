#!/usr/bin/env python2.2

import re
import os
import sys
from Cerebrum import cereconf

from Cerebrum.modules.no.uio.access_FS import FSPerson
from Cerebrum import Database,Errors
from Utils import XMLHelper

default_personfile = "/cerebrum/dumps/FS/persons.xml"

cereconf.DATABASE_DRIVER='Oracle'
Cerebrum = Database.connect(user="ureg2000", service="FSDEMO.uio.no")
FSP = FSPerson(Cerebrum)
xml = XMLHelper()

def get_person_info():
    # KURS & EVU fagpersoner
    # Employees from FS related to ordinary courses KURS.
    # Prefix: F
    # !!! Mulig at dette er den eneste spørringen som trengs !!!

    f=open(default_personfile, 'w')
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

def main():
    get_person_info()

if __name__ == '__main__':
    main()
