#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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

import getopt
import re
import os
import sys

import xml.sax

from Cerebrum.modules.no import fodselsnr
from Cerebrum.Utils import Factory
from Cerebrum import Errors

default_IMS_file = "/u2/dumps/FS/students_IMS.xml"
debug = 0
max = 999999
db = Factory.get('Database')()
const = Factory.get('Constants')(db)

class IMSEnterpriseParser(xml.sax.ContentHandler):
    """Parses an XML file as defined in 'IMS Enterprise XML Binding
    v1.1', available from www.imsproject.org

    The current version only process persons.
    """

    def __init__(self, call_back_object):
        self.call_back_object = call_back_object
        self.elementstack = []
        self.personer = []
        self.inPerson = 0
        self.inName = 0
        self.inN = 0
        self.inDemographics = 0
        self.inTel = 0
        self.inAdr = 0
        self.wantContent = 0
        self.inProperties = 0
        self.inSourcedId = 0
        self.content = ""
        self.count = 0

    def startElement(self, ename, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        ename = ename.encode('iso8859-1').lower()   # FS (incorrectly) dumps in uppercase

        # TBD: Antagelig kan startElement forenkles en god del ved å
        # ta vare på atributtene, appende ename til elementstacken og
        # la self.wantContent alltid være true.

        if self.inProperties:
            if ename == 'datasource':
                self.wantContent = 1
        elif self.inPerson:
            if self.inSourcedId:
                if ename in ("source", "id"):
                    self.wantContent = 1
            elif self.inName:
                if self.inN:
                    if ename in ('family', 'given', 'other'):
                        self.wantContent = 1
                elif ename == 'n':
                    self.inN = 1
                elif ename in ("fn", "sort", "nickname"):
                    self.wantContent = 1
            elif self.inDemographics:
                if ename in ('gender', 'bday'):
                    self.wantContent = 1                    
            elif self.inTel:
                self.wantContent = 1                    
            elif self.inAdr:
                if ename in ('street', 'locality', 'region', 'pcode', 'country'):
                    self.wantContent = 1                    
            else:
                if ename == "sourcedid":
                    self.inSourcedId = 1
                elif ename == 'name':
                    self.inName = 1
                elif ename == 'demographics':
                    self.inDemographics = 1
                elif ename == 'tel':
                    self.inTel = 1
                    self.wantContent = tmp['teltype']   # legal values: 1..4
                elif ename == 'adr':
                    self.inAdr = 1
        else:
            if ename == 'enterprise':
                pass
            elif ename == 'properties':                  # <properties>
                self.inProperties = 1
            elif ename == 'person':                    #   <person>
                self.inPerson = 1
                self.person_ids = {}
                self.phones = []
                self.addr = {}
                self.name = {}
                self.bday = None
                self.gender = None

    def endElement(self, ename):
        ename = ename.encode('iso8859-1').lower()   # FS (incorrectly) dumps in uppercase
        if self.inProperties:                      # </properties>
            if ename == 'properties':
                self.inProperties = 0
            elif ename == 'datasource':
                self.datasource = self._get_content()
        elif self.inPerson:
            if ename == "person":
                # TODO:  recstatus indicates if entry is new, updated or a delete record
                self.call_back_object.person_callback(
                    self.person_ids, self.phones, self.addr,
                    self.name, self.gender, self.bday)
                self.inPerson = 0
                self.count += 1
                if self.count >= max:
                    raise StopIteration()  # SAX doesn't seem to allow one to signal this properly
            elif self.inSourcedId:
                if ename == 'sourcedid':
                    self.inSourcedId = 0
                elif ename == 'source':
                    self.source_key = self._get_content()
                elif ename == 'id':
                    self.person_ids[self.source_key] = self._get_content()
            elif self.inName:
                if self.inN:
                    if ename == 'n':
                        self.inN = 0
                    else:
                        if ename == 'other':
                            self.name.setdefault(ename, []).append(self._get_content())
                        else:
                            self.name[ename] = self._get_content()
                elif ename == 'name':
                    self.inName = 0
                else:
                    self.name[ename] = self._get_content()
            elif self.inDemographics:
                if ename == 'demographics':
                    self.inDemographics = 0
                elif ename == 'gender':
                    self.gender = self._get_content()
                elif ename == 'bday':
                    self.bday = self._get_content()
            elif self.inTel:
                self.phones.append([self.wantContent, self._get_content()])
                self.inTel = 0
            elif self.inAdr:
                if ename == 'adr':
                    self.inAdr = 0
                elif ename == 'street':
                    self.addr.setdefault(ename, []).append(self._get_content())
                else:
                    self.addr[ename] = self._get_content()
        if self.wantContent:
            self.wantContent = 0
            self.content = ""

    def _get_content(self):
        # time with 10**6 lines XML:
        #   no-8859-1 encoding:     0m49.473s
        #   encode in characters(): 0m51.585s
        #   using _get_content():   0m53.425s
        #   with whitespace trim:   0m54.314s
        return ' '.join(self.content.encode('iso8859-1').split())
            
    def characters(self, content):
        if self.wantContent:
            self.content += content

class DataProcesser(object):
    def __init__(self, filename, config):
        self.config = config
        self.ss = None
        self.name_types = {
            'family': const.name_family,
            'given': const.name_given,
            'full': const.name_full,
            'sort': const.name_sort,
            'nick': const.name_nick
            }
        self.phonetypes = {
            '1': const.contact_phone,
            '2': const.contact_fax,
            '3': const.contact_phone,  # TODO: const for 3+4
            '4': const.contact_fax,
            'Voice': const.contact_phone,
            'Fax': const.contact_fax,
            'Mobile': const.contact_phone,
            'Pager': const.contact_fax
            }
        self.tp = IMSEnterpriseParser(self)
        xml.sax.parse(filename, self.tp)
        
    def person_callback(self, person_ids, phones, addr, name, gender, bday):
        if debug > 1:
            print "\n".join(("person_callback", 
                             "  pids: %s" % str(person_ids),
                             "  phones:%s" % str(phones),
                             "  addr:%s" % str(addr),
                             "  name:%s" % str(name),
                             "  gender:%s" % str(gender),
                             "  bday:%s" % str(bday)))

        if self.ss is None:
            if self.tp.datasource <> self.config.source_system_name:
                raise "Bad source system: %s" % self.ss
            self.ss = self.config.source_system_value
        try:
            id = person_ids[self.config.personid_key]
        except KeyError:
            raise "Fatal error, record did not set %s" % self.config.personid_key

        if self.config.personid_type == const.externalid_fodselsnr:
            id = fodselsnr.personnr_ok(id)
            if bday is None:
                bday = "%04i-%02i-%02i" % fodselsnr.fodt_dato(id)
            if gender is None:
                if fodselsnr.er_kvinne(id):
                    gender = 2
                else:
                    gender = 1
        if int(gender) == 2:
            gender = const.gender_male
        else:
            gender = const.gender_female
        if debug:
            print "Process %s" % id,
        new_person = Factory.get('Person')(db)
        try:
            new_person.find_by_external_id(self.config.personid_type, id, self.ss)
        except Errors.NotFoundError:
            pass
        new_person.populate(db.Date(*[int(x) for x in bday.split("-")]),
                            gender)
        new_person.populate_external_id(self.ss, self.config.personid_type, id)

        new_person.affect_names(self.ss, const.name_family,
                                const.name_given, const.name_other,
                                const.name_full, const.name_sort,
                                const.name_nick)

        for k in self.name_types.keys():
            if name.has_key(k):
                new_person.populate_name(self.name_types[k],
                                         name[k])
        if name.has_key('other'):
            new_person.populate_name(const.name_other,
                                     " ".join(name[other]))
        addr['country'] = None
        new_person.populate_address(
            self.ss, self.config.address_type,
            address_text="\n".join(addr['street']), postal_number=addr['pcode'],
            city=addr['locality'], country=addr['country'])
        for p in phones:
            new_person.populate_contact_info(self.ss, self.phonetypes[p[0]], p[1])

        op = new_person.write_db()
        if debug:
            if op is None:
                print "**** EQUAL ****"
            elif op == True:
                print "**** NEW ****"
            elif op == False:
                print "**** UPDATE ****"
        db.commit()
        
class Config(object):
    """Defines how things like <sourcedid>.<source> is mapped to
    authoritative_system_code
    """
    
    def __init__(self, filename):
        f = file(filename, "r")
        for line in f.readlines():
            key, value = line.split("=", 2)
            value = value.rstrip()
            if value.startswith("const."):
                value = getattr(const, value[6:])
            setattr(self, key, value)

def import_students(filename, config):
    try:
        dp = DataProcesser(filename, config)
    except StopIteration:
        print "Reached max limit"

def main():
    global debug, max
    sf = default_IMS_file
    opts, args = getopt.getopt(sys.argv[1:], 'dsS:c:m:',
                               ['debug', 'students', 'student-file=',
                                'config=', 'max='])
    for opt, val in opts:
        if opt in ('-d', '--debug'):
            debug += 1
        elif opt in ('-S', '--student-file'):
            sf = val
        elif opt in ('-s', '--students'):
            import_students(sf, config)
        elif opt in ('-c', '--config'):
            config = Config(val)
        elif opt in ('-m', '--max'):
            max = int(val)
        else:
            usage()
    if len(opts) == 0:
        usage()

def usage():
    print """Usage: -c configfile [-d | -S xmlfile | -s]

The config file has a number of key=value settings that controls how
certain XML attributes are mapped to cerebrum code values.  Values
starting with const. are interpreted as references to constants in
Constants.py.  Example file:

source_system_name=NO-FS
source_system_value=const.system_fs
personid_key=NO-FS
personid_type=const.externalid_fodselsnr
address_type=const.address_post

For this utility to work, you must add the following lines to one of
your Constants file:

    name_family = _PersonNameCode('FAMILY', 'Family name')
    name_given = _PersonNameCode('GIVEN', 'Given name')
    name_other = _PersonNameCode('OTHER', 'Other name')
    name_sort = _PersonNameCode('SORT', 'Sort name')
    name_nick = _PersonNameCode('NICK', 'Nick name')

"""
    
    sys.exit(0)


if __name__ == '__main__':
    main()
