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
import pprint

import xml.sax

from Cerebrum import Errors
from Cerebrum import Person
import cereconf
from Cerebrum.modules.no import fodselsnr
from Cerebrum.Utils import Factory

default_personfile = "/cerebrum/dumps/FS/person_file.xml"
default_studieprogramfile = "/cerebrum/dumps/FS/studieprogrammer.xml"
pp = pprint.PrettyPrinter(indent=4)

studieprog2sko = {}
ou_cache = {}

"""Importerer personer fra FS iht. fs_import.txt.  Rekkefølgen på
personer i XML dumpen er: fagperson, opptak, evu, perm, tilbud."""

class FSData(object):
    """This class is used to iterate over FS students in the XML dump."""

    def __init__(self, filename):
        self.tp = TrivialParser()
        xml.sax.parse(filename, self.tp)

    def __iter__(self):
        return self

    def next(self):
        """Returns a dict with data about the next person in FS."""
        try:
            return self.tp.personer.popitem()
        except KeyError:
            raise StopIteration, "End of file"

class TrivialParser(xml.sax.ContentHandler):
    """We gather all information known about the person so that we can
    provide all information about a person in one go.  This is
    currently done in memory, but this should not be a problem for
    current hardware."""

    def __init__(self):
        self.personer = {}

    def startElement(self, name, attrs):
        if name in ('fagperson', 'opptak', 'evu', 'perm', 'tilbud'):
            tmp = {'type': name}
            for k in attrs.keys():
                tmp[k] = attrs[k].encode('iso8859-1')
            fnr = "%06d%05d" % (int(tmp['fodselsdato']), int(tmp['personnr']))
            self.personer.setdefault(fnr, []).append(tmp)
        elif name == 'data':
            pass
        else:
            print "WARNING: unknown element: %s" % name

    def endElement(self, name):
        pass

class StudieprogramData(xml.sax.ContentHandler):
    def __init__(self, filename):
        self.entries = []
        xml.sax.parse(filename, self)


    def startElement(self, name, attrs):
        if name == 'studprog':
            tmp = {}
            for k in attrs.keys():
                tmp[k] = attrs[k].encode('iso8859-1')
            self.entries.append(tmp)
    
    def __iter__(self):
        return self

    def next(self):
        try:
            return self.entries.pop()
        except IndexError:
            raise StopIteration, "End of file"

def _get_sko(a_dict, kfak, kinst, kgr, kinstitusjon=None):
    key = "-".join((a_dict[kfak], a_dict[kinst], a_dict[kgr]))
    if not ou_cache.has_key(key):
        ou = Factory.get('OU')(db)
        try:
            ou.find_stedkode(int(a_dict[kfak]), int(a_dict[kinst]), int(a_dict[kgr]))
            ou_cache[key] = ou.ou_id
        except Errors.NotFoundError:
            print "WARNING: bad stedkode: %s" % key
            ou_cache[key] = None
    return ou_cache[key]

def _process_affiliation(aff, aff_status, new_affs, ou):
    # TBD: Should we for example remove the 'opptak' affiliation if we
    # also have the 'aktiv' affiliation?
    if ou is not None:
        new_affs.append((ou, aff, aff_status))

def _ext_address_info(a_dict, kline1, kline2, kline3, kpost, kland):
    ret = {}
    ret['address_text'] = "\n".join((a_dict.get(kline1, ''), a_dict.get(kline2, '')))
    ret['postal_number'] = a_dict.get(kpost, '')
    ret['city'] =  a_dict.get(kline3, '')
    if len(ret['address_text']) < 2:
        return None
    return ret

def process_person(db, dta):
    """Called when we have fetched all data on a person from the xml
    file.  Updates/inserts name, address and affiliation
    information."""
    
    fnr, persondta = dta
    try:
        fnr = fodselsnr.personnr_ok(fnr)
        if verbose:
            print "Process %s" % (fnr),
        (year, mon, day) = fodselsnr.fodt_dato(fnr)
        if (year < 1970
            and getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1):
            # Seems to be a bug in time.mktime on some machines
            year = 1970
    except fodselsnr.InvalidFnrError:
        print "Ugyldig fødselsnr: %s" % fnr
        return

    gender = co.gender_male
    if(fodselsnr.er_kvinne(fnr)):
        gender = co.gender_female

    etternavn = fornavn = None
    studentnr = None
    affiliations = []
    address_info = None
    # Iterate over all persondta entries and extract relevant data    
    for p in persondta:
        # Get name
        if p['type'] in ('fagperson', 'opptak', 'tilbud', 'evu'):
            etternavn = p['etternavn']
            fornavn = p['fornavn']
        if p.has_key('studentnr_tildelt'):
            studentnr = p['studentnr_tildelt']
        # Get address
        if address_info is None:
            if p['type'] in ('fagperson',):
                address_info = _ext_address_info(p, 'adrlin1_arbeide',
                    'adrlin2_arbeide', 'adrlin3_arbeide',
                    'postnr_arbeide', 'adresseland_arbeide')
                if address_info is None:
                    address_info = _ext_address_info(p,
                    'adrlin1_hjemsted', 'adrlin2_hjemsted',
                    'adrlin3_hjemsted', 'postnr_hjemsted',
                    'adresseland_hjemsted')
            elif p['type'] in ('opptak',):
                address_info = _ext_address_info(p, 'adrlin1_semadr',
                    'adrlin2_semadr', 'adrlin3_semadr',
                    'postnr_semadr', 'adresseland_semadr')
                if address_info is None:
                    address_info = _ext_address_info( p,
                        'adrlin1_hjemsted', 'adrlin2_hjemsted',
                        'adrlin3_hjemsted', 'postnr_hjemsted',
                        'adresseland_hjemsted')
            elif p['type'] in ('evu',):
                address_info = _ext_address_info(p, 'adrlin1_hjem',
                    'adrlin2_hjem', 'adrlin3_hjem', 'postnr_hjem',
                    'adresseland_hjem')
                if address_info is None:
                    address_info = _ext_address_info(p,
                        'adrlin1_hjemsted', 'adrlin2_hjemsted',
                        'adrlin3_hjemsted', 'postnr_hjemsted',
                        'adresseland_hjemsted')
            elif p['type'] in ('tilbud',):
                # TODO: adresse informasjon mangler i xml fila
                pass

        # Get affiliations
        if p['type'] in ('fagperson',):
            _process_affiliation(co.affiliation_ansatt,
                                 co.affiliation_status_ansatt_vit,
                                 affiliations, _get_sko(p, 'faknr',
                                 'instituttnr', 'gruppenr', 'institusjonsnr'))
        elif p['type'] in ('aktiv', ):
            # TODO: Ikke noe som genererer disse entriene foreløbig.
            # Skal kanskje leses fra topics, men det er uvvist hvilket
            # format topic fila vil få
            pass
        elif p['type'] in ('opptak', ):
            subtype = co.affiliation_status_student_opptak
            if p['studierettstatkode'] == 'EVU':
                subtype = co.affiliation_status_student_evu
            elif p['studierettstatkode'] == 'PRIVATIST':
                subtype = co.affiliation_status_student_privatist
            elif p['studierettstatkode'] == 'FULLFØRT':
                subtype = co.affiliation_status_student_alumni
            _process_affiliation(co.affiliation_student,
                                 subtype,
                                 affiliations, studieprog2sko[p['studieprogramkode']])
        elif p['type'] in ('perm',):
            _process_affiliation(co.affiliation_student,
                                 co.affiliation_status_student_aktiv,
                                 affiliations, studieprog2sko[p['studieprogramkode']])
        elif p['type'] in ('tilbud',):
            _process_affiliation(co.affiliation_student,
                                 co.affiliation_status_student_tilbud,
                                 affiliations, studieprog2sko[p['studieprogramkode']])
        elif p['type'] in ('evu', ):
            _process_affiliation(co.affiliation_student,
                                 co.affiliation_status_student_evu,
                                 affiliations, _get_sko(p, 'faknr_adm_ansvar',
                                 'instituttnr_adm_ansvar', 'gruppenr_adm_ansvar'))
            
    if etternavn is None:
        print "WARNING: Ikke noe navn på %s" % fnr
        return

    # TODO: If the person already exist and has conflicting data from
    # another source-system, some mecanism is needed to determine the
    # superior setting.
    
    new_person = Person.Person(db)
    try:
        new_person.find_by_external_id(co.externalid_fodselsnr, fnr)
    except Errors.NotFoundError:
        pass
    except Errors.TooManyRowsError:
        try:
            new_person.find_by_external_id(co.externalid_fodselsnr, fnr, co.system_fs)
        except Errors.NotFoundError:
            pass

    new_person.populate(db.Date(year, mon, day), gender)

    new_person.affect_names(co.system_fs, co.name_first, co.name_last)
    new_person.populate_name(co.name_first, etternavn)
    new_person.populate_name(co.name_last, fornavn)

    if studentnr is not None:
        new_person.affect_external_id(co.system_fs,
                                      co.externalid_fodselsnr,
                                      co.externalid_studentnr)
        new_person.populate_external_id(co.system_fs, co.externalid_studentnr,
                                        studentnr)
    else:
        new_person.affect_external_id(co.system_fs,
                                      co.externalid_fodselsnr)
    new_person.populate_external_id(co.system_fs, co.externalid_fodselsnr, fnr)

    if address_info is not None:
        new_person.populate_address(co.system_fs, co.address_post, **address_info)

    for a in affiliations:
        ou, aff, aff_status = a
        new_person.populate_affiliation(co.system_fs, ou, aff, aff_status)

    op = new_person.write_db()
    if verbose:
        if op is None:
            print "**** EQUAL ****"
        elif op == True:
            print "**** NEW ****"
        elif op == False:
            print "**** UPDATE ****"

def main():
    global verbose, ou, db, co
    verbose = 0
    opts, args = getopt.getopt(sys.argv[1:], 'vp:s:', ['verbose', 'person-file=',
                                                       'studieprogram-file='])
    personfile = default_personfile
    studieprogramfile = default_studieprogramfile
    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
        elif opt in ('-p', '--person-file'):
            personfile = val
        elif opt in ('-s', '--studieprogram-file'):
            studieprogramfile = val

    db = Factory.get('Database')()
    db.cl_init(change_program='import_FS')
    ou = Factory.get('OU')(db)
    co = Factory.get('Constants')(db)
    if getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1:
        print "Warning: ENABLE_MKTIME_WORKAROUND is set"

    for s in StudieprogramData(studieprogramfile):
        studieprog2sko[s['studieprogramkode']] = \
            _get_sko(s, 'faknr_studieansv', 'instituttnr_studieansv',
                     'gruppenr_studieansv')
    for persondta in FSData(personfile):
        print persondta
        process_person(db, persondta)
    db.commit()

if __name__ == '__main__':
    main()
