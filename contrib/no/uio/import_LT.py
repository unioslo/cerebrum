#!/usr/bin/env python2.2

import re
import os
import sys

from Cerebrum import Database, Person, Constants, Errors
from Cerebrum import cereconf
from Cerebrum.modules.no.uio import OU
from Cerebrum.modules.no import fodselsnr
import xml.sax
import pprint

default_personfile = "/u2/dumps/LT/person.dat.2"

class LTData(object):
    """This class is used to iterate over all users in LT. """

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
        if name in ("arbtlf", "komm", "tils", "bilag"):
            tmp = {}
            for k in attrs.keys():
                tmp[k] = attrs[k].encode('iso8859-1')
            self.p_data[name] = self.p_data.get(name, []) + [tmp]
        elif name == "person":
            self.p_data = {}
            for k in attrs.keys():
                self.p_data[k] = attrs[k].encode('iso8859-1')

    def endElement(self, name): 
        if name == "person":
            self.personer.append(self.p_data)


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
            
    if getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1:
        print "Warning: ENABLE_MKTIME_WORKAROUND is set"
    if len(sys.argv) == 2:
        personfile = sys.argv[1]
    else:
        personfile = default_personfile
        
    for person in LTData(personfile):
        person['fnr'] = fodselsnr.personnr_ok(
            "%02d%02d%02d%05d" % (int(person['fodtdag']), int(person['fodtmnd']),
                                  int(person['fodtar']), int(person['personnr'])))
        print "Got %s" % person['fnr'],
        # pp.pprint(person)
        new_person.clear()
        gender = co.gender_male
        if(fodselsnr.er_kvinne(person['fnr'])):
            gender = co.gender_female

        (year, mon, day) = fodselsnr.fodt_dato(person['fnr'])
        if(year < 1970 and getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1):
            year = 1970   # Seems to be a bug in time.mktime on some machines
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
                # t_stedkode, snr, skode, pros, t_title = tils[0:5]
                if tils['prosent_tilsetting'] > bigpros:
                    bigpros = tils['prosent_tilsetting']
                    bigtitle = tils['tittel']
                    stedkode =  "%02d%02d%02d" % (int(tils['fakultetnr_utgift']),
                                                  int(tils['instituttnr_utgift']),
                                                  int(tils['gruppenr_utgift']))
        if stedkode == '' and person.has_key('bilag'):
            stedkode = person['bilag'][0]['stedkode']
        if stedkode == '':
            # TODO: Kan være NONE
            stedkode = "%02d%02d%02d" % (int(person['fakultetnr_for_lonnsslip']),
                                         int(person['instituttnr_for_lonnsslip']),
                                         int(person['gruppenr_for_lonnsslip']))

        telefoner = faxer = []
        if person.has_key("komm"):
            telefoner = ["%s%s" % (t['kommnrverdi'], t['telefonnr'])
                         for t in person['komm'] if t['kommtypekode'] == 'ARBTLF']
            telefoner = telefoner + [t['telefonnr'] or t['kommnrverdi']
                                     for t in person['komm'] if t['kommtypekode'] == 'TLF']
            faxer = [t['telefonnr'] or t['kommnrverdi']
                     for t in person['komm'] if t['kommtypekode'] == 'FAX']
        if len(faxer) == 0:
            pass            # TODO: Hente fax fra stedkode 
        for tlf in telefoner:
            new_person.populate_contact_info(co.contact_phone, tlf)
        for fax in faxer:
            new_person.populate_contact_info(co.contact_fax, fax)

        new_person.affect_addresses(co.system_lt, co.address_post)
       if person.has_key('adresselinje1_privatadresse'):
            new_person.populate_address(co.address_post, addr="%s\n%s" %
                                       (person['adresselinje1_privatadresse'],
                                        person.get('adresselinje2_privatadresse', '')),
                                       zip=person.get('poststednr_privatadresse', None),
                                       city=person.get('poststednavn_privatadresse', None))
        if stedkode <> '':
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
