#!/usr/bin/env python2.2

import cerebrum_path

import re
import pickle
import sys

import xml.sax

from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum.Utils import Factory

OU_class = Factory.get('OU')

class StedData(xml.sax.ContentHandler):
    def __init__(self, filename):
        # What I'd like to do, it something like:
        #   self.parser = xml.sax.make_parser()
        #   self.parser.setContentHandler(self)
        #   self.parser.setErrorHandler(xml.sax.handler.ErrorHandler())
        # and have next() call self.parser.parse(file.readline())
        # whenever more data needs to be parsed to fetch the next
        # record. TODO

        # Ugly memory-wasting, inflexible way:
        self.tp = TrivialParser()
        xml.sax.parse(filename, self.tp)

    def __iter__(self):
        return self

    def next(self):
        try:
            return self.tp.steder.pop(0)
        except IndexError:
            raise StopIteration, "End of file"

class TrivialParser(xml.sax.ContentHandler):
    def __init__(self):
        self.steder = []

    def startElement(self, name, attrs):
        if name == "sted":
            tmp = {}
            for k in attrs.keys():
                tmp[k] = attrs[k].encode('iso8859-1')
            self.steder.append(tmp)

    def endElement(self, name): 
        pass

verbose = 1
stedfile = "/u2/dumps/LT/sted.xml"

if len(sys.argv) == 2:
    stedfile = sys.argv[1]

def main():
    Cerebrum = Database.connect()
    steder = {}
    co = Factory.getConstants()(Cerebrum)
    ou = OU_class(Cerebrum)
    if getattr(ou, 'find_stedkode', None) is None:
        raise ValueError, "Wrong OU class, override CLASS_OU in cereconf.py"
    new_ou = OU_class(Cerebrum)
    i = 1
    stedkode2ou = {}
    ou.clear()
    for k in StedData(stedfile):
        i = i + 1
        steder[get_stedkode_str(k['fakultetnr'],
                                k['instituttnr'],
                                k['gruppenr'])] = k
        if verbose:
            print "Processing %s '%s'" % (
                get_stedkode_str(k['fakultetnr'], k['instituttnr'],
                                 k['gruppenr']),
                k['forkstednavn']),
        new_ou.clear()
        try:
            new_ou.find_stedkode(k['fakultetnr'], k['instituttnr'], k['gruppenr'])
        except Errors.NotFoundError:
            pass

        new_ou.populate(k['stednavn'], k['fakultetnr'],
                        k['instituttnr'], k['gruppenr'], acronym=k.get('akronym', None),
                        short_name=k['forkstednavn'],
                        display_name=k['stednavn'],
                        sort_name=k['stednavn'])
        new_ou.affect_addresses(co.system_lt, co.address_street,
                                co.address_post)
        if k.has_key('adresselinje1_intern_adr'):
            new_ou.populate_address(co.address_post, addr="%s\n%s" %
                                    (k['adresselinje1_intern_adr'],
                                     k.get('adresselinje2_intern_adr', '')),
                                    zip=k.get('poststednr_intern_adr', ''),
                                    city=k.get('poststednavn_intern_adr', ''))
        if k.has_key('adresselinje1_besok_adr'):
            new_ou.populate_address(co.address_street, addr="%s\n%s" %
                                    (k['adresselinje1_besok_adr'],
                                     k.get('adresselinje2_besok_adr', '')),
                                    zip=k.get('poststednr_besok_adr', None),
                                    city=k.get('poststednavn_besok_adr', None))

        op = new_ou.write_db()
        if op is None:
            print "**** EQUAL ****"
        elif op == True:
            print "**** NEW ****"
        elif op == False:
            print "**** UPDATE ****"
            
        stedkode = get_stedkode_str(k['fakultetnr'], k['instituttnr'],
                                    k['gruppenr'])
        # Not sure why this casting to int is required for PostgreSQL
        stedkode2ou[stedkode] = int(new_ou.entity_id)
        Cerebrum.commit()

    existing_ou_mappings = {}
    for node in ou.get_structure_mappings(co.perspective_lt):
        existing_ou_mappings[int(node.ou_id)] = node.parent_id

    # Now populate ou_structure
    if verbose:
        print "Populate ou_structure"
    for stedkode in steder.keys():
        rec_make_stedkode(stedkode, ou, existing_ou_mappings, steder,
                          stedkode2ou, co)
    Cerebrum.commit()

def rec_make_stedkode(stedkode, ou, existing_ou_mappings, steder,
                      stedkode2ou, co):
    """Recursively create the ou_id -> parent_id mapping"""
    sted = steder[stedkode]
    org_stedkode = get_stedkode_str(sted['fakultetnr_for_org_sted'],
                                    sted['instituttnr_for_org_sted'],
                                    sted['gruppenr_for_org_sted'])
    if(not stedkode2ou.has_key(org_stedkode)):
        print "Error in dataset, %s references missing STEDKODE: %s, using None" % \
              (stedkode, org_stedkode)
        org_stedkode = None
        org_stedkode_ou = None
    else:
        org_stedkode_ou = stedkode2ou[org_stedkode]

    if(existing_ou_mappings.has_key(stedkode2ou[stedkode])):
        if(existing_ou_mappings[stedkode2ou[stedkode]] != org_stedkode_ou):
            print "Mapping for %s changed TODO (%s != %s)" % (
                stedkode, existing_ou_mappings[stedkode2ou[stedkode]],
                org_stedkode_ou)
        return

    if(org_stedkode_ou is not None and (stedkode != org_stedkode) and
       (not existing_ou_mappings.has_key(org_stedkode_ou))):
        rec_make_stedkode(org_stedkode, ou, existing_ou_mappings, steder,
                          stedkode2ou, co)

    ou.clear()
    ou.find(stedkode2ou[stedkode])
    if stedkode2ou.has_key(org_stedkode):
        ou.set_parent(co.perspective_lt, stedkode2ou[org_stedkode])
    else:
        ou.set_parent(co.perspective_lt, None)
    existing_ou_mappings[stedkode2ou[stedkode]] = org_stedkode_ou

def get_stedkode_str(faknr, instnr, groupnr):
    str = "%02d-%02d-%02d" % ( int(faknr), int(instnr), int(groupnr) )
    return str

if __name__ == '__main__':
    main()
