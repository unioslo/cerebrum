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
import getopt

import cereconf
from Cerebrum import Person
from Cerebrum import Errors
from Cerebrum.modules.no import fodselsnr
from Cerebrum.Utils import Factory

import xml.sax
import pprint

default_personfile = "/cerebrum/dumps/LT/person.xml"

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
    opts, args = getopt.getopt(sys.argv[1:], 'vp:', ['verbose', 'person-file'])
    verbose = 0
    personfile = default_personfile
    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
        elif opt in ('-p', '--person-file'):
            personfile = val
            
    db = Factory.get('Database')()
    db.cl_init(change_program='import_LT')
    ou = Factory.get('OU')(db)
    personObj = Person.Person(db)
    co = Factory.get('Constants')(db)

    pp = pprint.PrettyPrinter(indent=4)
    new_person = Person.Person(db)

    if getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1:
        print "Warning: ENABLE_MKTIME_WORKAROUND is set"

    for person in LTData(personfile):
        person['fnr'] = fodselsnr.personnr_ok(
            "%02d%02d%02d%05d" % (int(person['fodtdag']), int(person['fodtmnd']),
                                  int(person['fodtar']), int(person['personnr'])))
        if verbose:
            print "Got %s" % person['fnr'],
        # pp.pprint(person)
        new_person.clear()
        gender = co.gender_male
        if(fodselsnr.er_kvinne(person['fnr'])):
            gender = co.gender_female

        (year, mon, day) = fodselsnr.fodt_dato(person['fnr'])
        if(year < 1970 and getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1):
            year = 1970   # Seems to be a bug in time.mktime on some machines
        try:
            new_person.find_by_external_id(co.externalid_fodselsnr, person['fnr'])
        except Errors.NotFoundError:
            pass
        except Errors.TooManyRowsError:
            try:
                new_person.find_by_external_id(co.externalid_fodselsnr, person['fnr'], co.system_lt)
            except Errors.NotFoundError:
                pass

        new_person.populate(db.Date(year, mon, day), gender)

        new_person.affect_names(co.system_lt, co.name_full)
        new_person.affect_external_id(co.system_lt, co.externalid_fodselsnr)
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
        if stedkode == '' and person.has_key('fakultetnr_for_lonnsslip'):
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
            new_person.populate_contact_info(co.system_lt, co.contact_phone, tlf)
        for fax in faxer:
            new_person.populate_contact_info(co.system_lt, co.contact_fax, fax)

        if person.has_key('adresselinje1_privatadresse'):
            new_person.populate_address(co.system_lt, co.address_post, address_text="%s\n%s" %
                                       (person['adresselinje1_privatadresse'],
                                        person.get('adresselinje2_privatadresse', '')),
                                       postal_number=person.get('poststednr_privatadresse', None),
                                       city=person.get('poststednavn_privatadresse', None))
        if stedkode <> '':
            try:
                fak, inst, gruppe = stedkode[0:2], stedkode[2:4], stedkode[4:6]
                ou.clear()
                ou.find_stedkode(int(fak), int(inst), int(gruppe))
                new_person.populate_affiliation(co.system_lt, ou.ou_id, co.affiliation_ansatt,
                                                co.affiliation_status_ansatt_bil)
            except Errors.NotFoundError:
                print "Error setting stedkode %s" % stedkode

        op = new_person.write_db()
        if verbose:
            if op is None:
                print "**** EQUAL ****"
            elif op == True:
                print "**** NEW ****"
            elif op == False:
                print "**** UPDATE ****"
        db.commit()

if __name__ == '__main__':
    main()
