#!/usr/bin/env python2.2

import re
import os
import sys

from Cerebrum import Database, Person, Constants, Errors
from Cerebrum.modules.no.uio import OU
from Cerebrum.modules.no import fodselsnr
import pprint

personfile = "/u2/dumps/LT/persons.dat";

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
                if self.prev_data is None:
                    raise StopIteration, "End of file"
                else:
                    data = None
            else:
                line = line.strip()
                data = line.split('\034')
                what, data = data[0], data[1:]
            if not line or what == 'PERSON':
                if self.prev_data is not None:
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
                if data[1] == '0': data[1] = ''
                if len(data[2]) == 5 and not data[1]: data[1] = "228"
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

def main():
    Cerebrum = Database.connect()
    ou = OU.OU(Cerebrum)
    personObj = Person.Person(Cerebrum)
    co = Constants.Constants(Cerebrum)

    pp = pprint.PrettyPrinter(indent=4)
    new_person = Person.Person(Cerebrum)
            
    if len(sys.argv) == 2:
        personfile = sys.argv[1]

    for person in LTData(personfile):
        print "Got %s" % person['fnr'],
        # pp.pprint(person)
        new_person.clear()
        gender = co.gender_male
        if(fodselsnr.er_kvinne(person['fnr'])):
            gender = co.gender_female

        (year, mon, day) = fodselsnr.fodt_dato(person['fnr'])
        if(year < 1970): year = 1970   # Seems to be a bug in time.mktime on some machines
        new_person.populate(Cerebrum.Date(year, mon, day), gender)

        new_person.affect_names(co.system_lt, co.name_full)
        lname, fname = conv_name(person['navn'])
        new_person.populate_name(co.name_full, "%s %s" % (lname, fname))

        new_person.populate_external_id(co.system_lt, co.externalid_fodselsnr, person['fnr'])

        # Gå gjennom tils+bil for å finne riktig STEDKODE, og bruk denne
        bigpros = 0
        bigtitle = stedkode = ''
        if person.has_key('tils'):
            for tils in person['tils']:
                t_stedkode, snr, skode, pros, t_title = tils[0:5]
                if pros > bigpros:
                    bigpros = pros
                    bigtitle = t_title
                    if t_stedkode[0] != 0: stedkode = t_stedkode
        if stedkode == '' and person.has_key('bil'):
            stedkode = person['bil'][0][0]
        if stedkode == '':
            stedkode = "%02d%02d%02d" % (int(person['faknr']), int(person['instnr']),
                                    int(person['gruppenr']))

        telefoner = faxer = []
        if person.has_key("komm"):
            telefoner = ["%s%s" % (t[1], t[2]) for t in person['komm'] if t[0] == 'ARBTLF']
            telefoner = telefoner + [t[2] or t[1] for t in person['komm'] if t[0] == 'TLF']
            faxer = [t[2] or t[1] for t in person['komm'] if t[0] == 'FAX']
        if len(faxer) == 0:
            pass            # TODO: Hente fax fra stedkode 
        for tlf in telefoner:
            new_person.populate_contact_info(co.contact_phone, tlf)
        for fax in faxer:
            new_person.populate_contact_info(co.contact_fax, fax)

        new_person.affect_addresses(co.system_lt, co.address_post)
        new_person.populate_address(co.address_post, addr="%s\n%s" %
                                    (person['adr1'],
                                     person['adr2']),
                                    zip=person['poststednr'],
                                    city=person['poststednavn'])

        if(person.has_key('faknr')):
            try:
                fak, inst, gruppe = stedkode[0:2], stedkode[2:4], stedkode[4:6]
                ou.find_stedkode(int(fak), int(inst), int(gruppe))
                new_person.affect_affiliations(co.system_lt, co.affiliation_employee)
                new_person.populate_affiliation(ou.ou_id, co.affiliation_employee,
                                                co.affiliation_status_employee_valid)
            except:
                print "Error setting stedkode"

        try:
            personObj.find_by_external_id(co.externalid_fodselsnr, person['fnr'])
            if not (new_person == personObj):
                print "**** UPDATE ****"
                new_person.write_db(personObj)
            else:
                print "**** EQUAL ****"
        except Errors.NotFoundError:
            print "**** NEW ****"
            new_person.write_db()
    Cerebrum.commit()

if __name__ == '__main__':
    main()
