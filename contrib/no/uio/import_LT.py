#!/usr/bin/env python2

import re
import os

from Cerebrum import Database
from Cerebrum import Person
from Cerebrum.modules.no.uio import OU
from Cerebrum.modules.no import fodselsnr
from DCOracle2 import Date
import pprint

personfile = "/u2/dumps/LT/persons.dat";
FEMALE = 'F'
MALE = 'M'

class LTData(object):
    """This class is used to iterate over all users in LT. """

    def __init__(self, filename):
        self.file = file(filename)
        self.prev_data = None

    def __iter__(self):
        return self

    def next(self):
        """Returns a dict with data about the next user in LT."""
        self.info = {}
        while 1:
            line = self.file.readline()
            if not line:
                if self.prev_data == None:
                    raise StopIteration, "End of file"
                else:
                    data = None
            else:
                line = line.strip()
                data = line.split('\034')
                what, data = data[0], data[1:]
            if not line or what == 'PERSON':
                if self.prev_data != None:
                    pd = self.prev_data
                    #  Dunno the syntax for this: "%02d%02d%02d%05d" %   [int(x) for x in data[0:3]]
                    fnr = fodselsnr.personnr_ok("%02d%02d%02d%05d" % (int(pd[0]), int(pd[1]),
                                                                      int(pd[2]), int(pd[3])))
                    self.info['fnr'] = fnr
                    pd = pd[4:]
                    for x in ('navn' , 'p_title', 'faknr', 'instnr', 'gruppenr', 'adr1', 'adr2',
                              'poststednr', 'poststednavn', 'landnavn', 'ptlf'):
                        self.info[x] = pd.pop(0)
                    self.prev_data = data
                    return self.info
                self.prev_data = data
            elif what == 'KOMM':
                self.info['komm'] = self.info.get('komm', []) + [data]
            elif what == 'TILS':
                self.info['tils'] = self.info.get('tils', []) + [data]
                self.info['A'] = 1  # redundant, remove?
                if data[7] == 'VIT':
                    self.info['V'] = 1
            elif what == 'BIL':
                self.info['bil'] = self.info.get('bil', []) +  [data]
                self.info['M'] = 1  # redundant, remove?
        return line

def conv_name(fullname):
    fullname = fullname.strip()
    return fullname.split(None, 1)

Cerebrum = Database.connect(user="cerebrum")
ou = OU.OU(Cerebrum)
personObj = Person.Person(Cerebrum)

def main():
    pp = pprint.PrettyPrinter(indent=4)
    
    for person in LTData(personfile):
        print "Got %s" % person['fnr']
        pp.pprint(person)

        if(fodselsnr.er_kvinne(person['fnr'])):
            gender = FEMALE
        else:
            gender = MALE

        try:
            personObj.find_by_external_id('fodselsnr', person['fnr'])
            print " Already exists"

            # Todo: cmp
        except:
            print " Is new"
            (year, mon, day) = fodselsnr.fodt_dato(person['fnr'])
            if(year < 1970): year = 1970   # Seems to be a bug in time.mktime on some machines

            id = personObj.new(Date(year, mon, day), gender)
            personObj.find(id)
            personObj.set_external_id('fodselsnr', person['fnr'])
            lname, fname = conv_name(person['navn'])
            personObj.set_name('full', 'LT', "%s %s" % (fname, lname))
            personObj.entity_id = personObj.person_id

            personObj.add_entity_address('LT', 'p', addr="%s\n%s" %
                                      (person['adr1'],
                                       person['adr2']),
                                      zip=person['poststednr'],
                                      city=person['poststednavn'])
            if 0 and person['tlf_arb'].strip() != '':
                personObj.add_entity_phone('LT', FAST_TELEFON, person['tlf_arb'])
                
            if(person.has_key('faknr')):
                try:
                    ou.get_stedkode(int(person['faknr']), int(person['instnr']), int(person['gruppenr']))
                    # TODO: Not sure how status/code is supposed to be used
                    personObj.set_affiliation(ou.ou_id, 'valid')
                except:
                    print "Error setting stedkode "

if __name__ == '__main__':
    main()

