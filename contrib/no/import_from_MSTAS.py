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
import cereconf

from Cerebrum import Database,Errors
from Utils import XMLHelper

default_personfile = "/cerebrum/dumps/MSTAS/persons.dat"

Cerebrum = Database.connect(user="cerebrum", service="MSTAS.hiof.no",
                            DB_driver='Oracle')
xml = XMLHelper()

LIMIT="rownum < 100"       # Vært snill mot db under testing

class MSTAS(object):
    """..."""

    def __init__(self, db):
        self.db = db

    def GetSchemaVersion(self):
        return self.db.query_1("SELECT version FROM dpsys000.schema_version")

    def GetPersons(self):
        qry = """SELECT s_objectid, fornavn, etternavn, foedselsnr, ansatt
        FROM dpsys005.person
        WHERE %s""" % LIMIT
        r = self.db.query(qry)
        return ([x[0] for x in self.db.description], r)

    def GetAdresseTyper(self):
        qry = """SELECT * FROM dpsys005.adressetype"""
        r = self.db.query(qry)
        return ([x[0] for x in self.db.description], r)

    def GetPersonAdresse(self, id):
        qry = """SELECT adressetype_kode, adresse1, adresse2, adresse3, postnr, poststed, land, telefon
        FROM dpsys005.adresse WHERE adresseeier_id=:id"""
        r = self.db.query(qry, {'id': id})
        return ([x[0] for x in self.db.description], r)

    def GetStudent(self, id):
        # Muligens ikke interessant tabell, men har bla bibsysid og student_nr
        qry = """SELECT * FROM dpsys300.student WHERE s_objectid=:id"""
        r = self.db.query(qry, {'id': id})
        return ([x[0] for x in self.db.description], r)


MC = MSTAS(Cerebrum)

def get_person_info():
    f=open(default_personfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, persons = MC.GetPersons()
    for p in persons:
        f.write(xml.xmlify_dbrow(p, xml.conv_colnames(cols), 'person', 1) + "\n")
        adrcols, adr = MC.GetPersonAdresse(p['s_objectid'])
        for a in adr:
            f.write(xml.xmlify_dbrow(a, xml.conv_colnames(adrcols), 'adr') + "\n")
        studcols, stud = MC.GetStudent(p['s_objectid'])
        for s in stud:
            f.write(xml.xmlify_dbrow(s, xml.conv_colnames(studcols), 'stud') + "\n")
        f.write("</person>\n")
    f.write("</data>\n")

def main():
    get_person_info()

if __name__ == '__main__':
    main()
