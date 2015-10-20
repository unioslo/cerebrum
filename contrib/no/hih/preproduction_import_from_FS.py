#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2009 University of Oslo, Norway
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


import re
import sys

import cerebrum_path
import cereconf
from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum.extlib import xmlprinter
from Cerebrum.Utils import XMLHelper, MinimumSizeWriter, AtomicFileWriter
from Cerebrum.modules.no.hih.access_FS import FS
from Cerebrum.Utils import Factory

default_person_file = "/cerebrum/var/cache/FS/person-temporary.xml"
xml = XMLHelper()
fs = None

def _ext_cols(db_rows):
    # TBD: One might consider letting xmlify_dbrow handle this
    cols = None
    if db_rows:
        cols = list(db_rows[0].keys())
    return cols, db_rows

def write_person_info(outfile):
    f = MinimumSizeWriter(outfile)
    f.set_minimum_size_limit(0)
    f.write(xml.xml_hdr + "<data>\n")

    # Aktive ordinære studenter ved HIH
    cols, student = _ext_cols(fs.student.list_aktiv_midlertidig())
    for a in student:
        f.write(xml.xmlify_dbrow(a, xml.conv_colnames(cols), 'aktiv') + "\n")
        
    f.write("</data>\n")
    f.close()

def assert_connected(user="cerebrum", service="FSHIH.uio.no"):
    global fs
    if fs is None:
        db = Database.connect(user=user, service=service,
                              DB_driver='cx_Oracle')
        fs = FS(db)

def main():
    person_file = default_person_file
    
    assert_connected()

    write_person_info(person_file)
    
if __name__ == '__main__':
    main()
