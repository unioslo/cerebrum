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
import getopt

import xml.sax

from Cerebrum import Errors
from Cerebrum import Person
import cereconf
from Cerebrum.modules.no import fodselsnr
from Cerebrum.Utils import Factory

default_personfile = "/cerebrum/dumps/FS/persons.xml"

class FSData(object):
    """This class is used to iterate over FS students in the XML dump."""

    def __init__(self, filename):
        # Ugly memory-wasting, inflexible way:
        self.tp = TrivialParser()
        xml.sax.parse(filename, self.tp)

    def __iter__(self):
        return self

    def next(self):
        """Returns a dict with data about the next user in LT."""
        try:
            return self.tp.personer.pop(0)
        except IndexError:
            raise StopIteration, "End of file"

class TrivialParser(xml.sax.ContentHandler):
    def __init__(self):
        self.personer = []

    def startElement(self, name, attrs):
        if name in ('fagperson', 'student', 'evu'):
            tmp = {'type': name}
            for k in attrs.keys():
                tmp[k] = attrs[k].encode('iso8859-1')
            self.personer.append(tmp)

    def endElement(self, name):
        pass

def main():
    global verbose
    verbose = 0
    opts, args = getopt.getopt(sys.argv[1:], 'vp', ['verbose', 'person-file'])
    personfile = default_personfile
    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
        elif opt in ('p', '--person-file'):
            personfile = val

    Cerebrum = Factory.get('Database')()
    if getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1:
        print "Warning: ENABLE_MKTIME_WORKAROUND is set"
    for persondta in FSData(personfile):
        process_person(Cerebrum, persondta)
    Cerebrum.commit()

def process_person(Cerebrum, persondta):
    try:
        fnr = fodselsnr.personnr_ok("%06d%05d" % (
            int(persondta['fodselsdato']), int(persondta['personnr'])))
        if verbose:
            print "Process %s %s %s " % (fnr, persondta['fornavn'],
                                         persondta['etternavn']),
        (year, mon, day) = fodselsnr.fodt_dato(fnr)
        if (year < 1970
            and getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1):
            # Seems to be a bug in time.mktime on some machines
            year = 1970
    except fodselsnr.InvalidFnrError:
        print "Ugyldig fødselsnr: %s%s" % (persondta['fodselsdato'],
                                           persondta['personnr'])
        return

    new_person = Person.Person(Cerebrum)
    co = Factory.get('Constants')(Cerebrum)
    try:
        new_person.find_by_external_id(co.externalid_fodselsnr, fnr, co.system_fs)
    except Errors.NotFoundError:
        pass

    gender = co.gender_male
    if(fodselsnr.er_kvinne(fnr)):
        gender = co.gender_female

    new_person.populate(Cerebrum.Date(year, mon, day), gender)
    new_person.affect_names(co.system_fs, co.name_full)
    new_person.populate_name(co.name_full,
                             "%s %s" % (persondta['etternavn'],
                                        persondta['fornavn']))

    new_person.populate_external_id(co.system_fs, co.externalid_fodselsnr, fnr)

    sko_info = ()
    aff_type, aff_status = (co.affiliation_student,
                            co.affiliation_status_student_valid)
    if persondta['type'] == 'fagperson':
        atype = 'arbeide'
        sko_info = (persondta['faknr'], persondta['instituttnr'],
                    persondta['gruppenr'])
        aff_type, aff_status = (co.affiliation_employee,
                                co.affiliation_status_employee_valid)
    elif persondta['type'] == 'student':
        atype = 'semadr'  # Evt. hjemsted
    elif persondta['type'] == 'evu':
        atype = 'hjem'   # Evt. hjemsted
    # TODO: Trenger kanskje noen tester på gyldighet av addr før vi
    # legger den inn?
    new_person.populate_address(co.system_fs, co.address_post, address_text="%s\n%s" %
                                (persondta.get('adrlin1_%s' % atype, ''),
                                 persondta.get('adrlin2_%s' % atype, '')),
                                postal_number=persondta.get('postnr_%s' % atype, ''),
                                city=persondta.get('adrlin3_%s' % atype, ''))

    for i in range(0, len(sko_info), 3):
        ou = Factory.get('OU')(Cerebrum)
        ou.find_stedkode(int(sko_info[i]), int(sko_info[i+1]),
                         int(sko_info[i+2]))

        new_person.populate_affiliation(co.system_fs, ou.ou_id, aff_type, aff_status)

    op = new_person.write_db()
    if verbose:
        if op is None:
            print "**** EQUAL ****"
        elif op == True:
            print "**** NEW ****"
        elif op == False:
            print "**** UPDATE ****"

if __name__ == '__main__':
    main()
