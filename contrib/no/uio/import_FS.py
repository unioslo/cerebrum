#!/usr/bin/env python2

import re
import os

from Cerebrum import Database
from Cerebrum import Person
from Cerebrum.modules.no.uio import OU
from Cerebrum.modules.no import fodselsnr
from DCOracle2 import Date

class FSData(object):
    cols_n = """fdato, pnr, lname, fname, adr1, adr2, postnr,adr3,
	     adrland, adr1_hjem, adr2_hjem, postnr_hjem, adr3_hjem,
	     adrland_hjem"""
    cols_f = """fdato, pnr, lname, fname, adr1, adr2, postnr, adr3,
	     adrland, tlf_arb, fax_arb, tlf_hjem, title, institusjon,
	     fak, inst, gruppe"""

    def parse_line(self, line):
	info = line.split("','")
        type = info.pop(0)

        if(type == 'F'):
            colnames = self.cols_f
        else:   # S || E
            colnames = self.cols_n
        re_cols = re.compile(r"\s+", re.DOTALL)
        colnames = re.sub(re_cols, "", colnames)
        colnames = colnames.split(",")
        persondta = {}
        for c in colnames:
            persondta[c] = info.pop(0)
        return persondta

# These should be set in constants.py or similar
FEMALE = 'F'
MALE = 'M'
FAST_TELEFON = 'f'

personfile = "/u2/dumps/FS/persons.dat";
Cerebrum = Database.connect(user="cerebrum")
ou = OU.OU(Cerebrum)
person = Person.Person(Cerebrum)

def main():
    f = os.popen("sort -u "+personfile)

    dta = FSData()
    i = 0
    for line in f.readlines():
        persondta = dta.parse_line(line)
        process_person(person, persondta)
        i = i + 1
#        if(i > 10): break

def process_person(person, persondta):
    print "Process %06d%05d %s %s " % (
        int(persondta['fdato']), int(persondta['pnr']),
        persondta['fname'], persondta['lname']),
    (year, mon, day) = fnrdato2dato(persondta['fdato'])
    if(year < 1970): year = 1970      # Seems to be a bug in DCOracle2
    try:
        fnr = fodselsnr.personnr_ok(persondta['fdato'] + persondta['pnr'])
    except fodselsnr.InvalidFnrError:
        print "Ugyldig fødselsnr: %s%s" % persondta['fdato'], persondta['pnr']

    if(fodselsnr.er_kvinne(fnr)):
        gender = FEMALE
    else:
        gender = MALE

    try:
        person.find_by_external_id('fodselsnr', fnr)
        print " Already exists"

        # Todo: cmp
    except:
        print " Is new"
        id = person.new(Date(year, mon, day), gender)
        person.find(id)
        person.set_external_id('fodselsnr', fnr)
        person.set_name('full', 'FS', "%s %s" % (persondta['fname'], persondta['lname']))
        person.entity_id = person.person_id
        person.add_entity_address('FS', 'p', addr="%s\n%s" %
                                  (persondta['adr1'],
                                   persondta['adr2']),
                                  zip=persondta['postnr'],
                                  city=persondta['adr3'])
        if persondta['tlf_arb'].strip() != '':
            person.add_entity_phone('FS', FAST_TELEFON, persondta['tlf_arb'])

        if(persondta.has_key('fak')):
            try:
                ou.get_stedkode(int(persondta['fak']), int(persondta['inst']), int(persondta['gruppe']))
                # TODO: Not sure how status/code is supposed to be used
                person.set_affiliation(ou.ou_id, 'valid')
            except:
                print "Error setting stedkode "

# TODO: Update to get correct century
def fnrdato2dato(dato):
    return (int(dato[4:6]) + 1900, int(dato[2:4]), int(dato[0:2]))

if __name__ == '__main__':
    main()

