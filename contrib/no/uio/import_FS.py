#!/usr/bin/env python2.2

import re
import os
import sys

from Cerebrum import Database,Constants,Errors
from Cerebrum import Person
from Cerebrum.modules.no.uio import OU
from Cerebrum.modules.no import fodselsnr
# import pprint

personfile = "/u2/dumps/FS/persons.dat";

class FSData(object):
    cols_n = """fdato, pnr, lname, fname, adr1, adr2, postnr,adr3,
	     adrland, adr1_hjem, adr2_hjem, postnr_hjem, adr3_hjem,
	     adrland_hjem"""
    cols_f = """fdato, pnr, lname, fname, adr1, adr2, postnr, adr3,
	     adrland, tlf_arb, fax_arb, tlf_hjem, title, institusjon,
	     fak, inst, gruppe"""

    # TODO: Denne datakilden skal neppe brukes.  Den fremtidige
    # implementasjonen må håndtere tilhørighet til multiple stedkoder.

    def parse_line(self, line):
	info = line.split("','")
        type = info.pop(0)

        if(type == 'F'):
            colnames = self.cols_f
        else:   # S || E
            # Not really handle yet.  The fak, inst and gruppe fields
            # are missing
            colnames = self.cols_n
            return None

        re_cols = re.compile(r"\s+", re.DOTALL)
        colnames = re.sub(re_cols, "", colnames)
        colnames = colnames.split(",")
        persondta = {}
        for c in colnames:
            persondta[c] = info.pop(0)
            if(persondta[c] == ''):
                persondta[c] = None
        return persondta

def main():
    Cerebrum = Database.connect()

    if len(sys.argv) == 2:
        personfile = sys.argv[1]

    f = os.popen("sort -u "+personfile)

    dta = FSData()
    for line in f.readlines():
        persondta = dta.parse_line(line)
        if persondta is not None:
            process_person(Cerebrum, persondta)
        else:
            print "Unhandled format: ",line
    Cerebrum.commit()

def process_person(Cerebrum, persondta):
    print "Process %06d%05d %s %s " % (
        int(persondta['fdato']), int(persondta['pnr']),
        persondta['fname'], persondta['lname']),
    
    try:
        (year, mon, day) = fodselsnr.fodt_dato(persondta['fdato'] + persondta['pnr'])
        if(year < 1970): year = 1970   # Seems to be a bug in time.mktime on some machines
        
        fnr = fodselsnr.personnr_ok(persondta['fdato'] + persondta['pnr'])
    except fodselsnr.InvalidFnrError:
        print "Ugyldig fødselsnr: %s%s" % (persondta['fdato'],
                                           persondta['pnr'])
        return


    new_person = Person.Person(Cerebrum)
    co = Constants.Constants(Cerebrum)
    
    gender = co.gender_male
    if(fodselsnr.er_kvinne(fnr)):
        gender = co.gender_female

    new_person.populate(Cerebrum.Date(year, mon, day), gender)
    new_person.affect_names(co.system_fs, co.name_full)
    new_person.populate_name(co.name_full, "%s %s" % (persondta['lname'], persondta['fname']))

    new_person.populate_external_id(co.system_fs, co.externalid_fodselsnr, fnr)

    new_person.affect_addresses(co.system_fs, co.address_post)
    if persondta['adr2'] is None:   # None is inserted in the string for some reason
        persondta['adr2'] = ''
    new_person.populate_address(co.address_post, addr="%s\n%s" %
                                (persondta['adr1'],
                                 persondta['adr2']),
                                zip=persondta['postnr'],
                                city=persondta['adr3'])
    ou = OU.OU(Cerebrum)
    ou.find_stedkode(int(persondta['fak']), int(persondta['inst']), int(persondta['gruppe']))

    new_person.affect_affiliations(co.system_fs, co.affiliation_student)
    new_person.populate_affiliation(ou.ou_id, co.affiliation_student, co.affiliation_status_student_valid)

    try:
        person = Person.Person(Cerebrum)
        person.find_by_external_id(co.externalid_fodselsnr, fnr)
        if not (new_person == person):
            print "**** UPDATE ****"
            new_person.write_db(person)
        else:
            print "**** EQUAL ****"
    except Errors.NotFoundError:
        print "**** NEW ****"
        new_person.write_db()

if __name__ == '__main__':
    main()


