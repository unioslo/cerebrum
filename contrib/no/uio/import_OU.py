#!/usr/bin/env python2.2

import cerebrum_path

import re
import pickle
import sys
import getopt

import xml.sax

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
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        if name == 'data':
            pass
        elif name == "sted":
            self.steder.append(tmp)
        elif name == "komm":
            self.steder[-1].setdefault("komm", []).append(tmp)
        else:
            raise ValueError, "Unknown XML element %s" % name

    def endElement(self, name):
        pass


if len(sys.argv) == 2:
    stedfile = sys.argv[1]


def main():
    # Parse command line options and arguments
    opts, args = getopt.getopt(sys.argv[1:], 'v', ['verbose'])

    verbose = 0
    stedfile = "/cerebrum/dumps/LT/sted.xml"

    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
    if args:
        stedfile = args.pop(0)

    Cerebrum = Factory.get('Database')()
    steder = {}
    co = Factory.get('Constants')(Cerebrum)
    ou = OU_class(Cerebrum)
    i = 1
    stedkode2ou = {}
    for k in StedData(stedfile):
        i += 1
        steder[get_stedkode_str(k)] = k
        if verbose:
            print "Processing %s '%s'" % (get_stedkode_str(k),
                                          k['forkstednavn']),
        ou.clear()
        try:
            ou.find_stedkode(k['fakultetnr'], k['instituttnr'], k['gruppenr'])
        except Errors.NotFoundError:
            pass
        ou.populate(k['stednavn'], k['fakultetnr'],
                    k['instituttnr'], k['gruppenr'],
                    acronym=k.get('akronym', None),
                    short_name=k['forkstednavn'],
                    display_name=k['stednavn'],
                    sort_name=k['stednavn'])
        if k.has_key('adresselinje1_intern_adr'):
            ou.populate_address(co.system_lt, co.address_post,
                                address_text="%s\n%s" %
                                (k['adresselinje1_intern_adr'],
                                 k.get('adresselinje2_intern_adr', '')),
                                postal_number=k.get('poststednr_intern_adr',
                                                    ''),
                                city=k.get('poststednavn_intern_adr', ''))
        if k.has_key('adresselinje1_besok_adr'):
            ou.populate_address(co.system_lt, co.address_street,
                                address_text="%s\n%s" %
                                (k['adresselinje1_besok_adr'],
                                 k.get('adresselinje2_besok_adr', '')),
                                postal_number=k.get('poststednr_besok_adr',
                                                    None),
                                city=k.get('poststednavn_besok_adr', None))
        n = 0
        for t in k.get('komm', []):
            n += 1       # TODO: set contact_pref properly
            if t['kommtypekode'] == 'FAX': 
                ou.populate_contact_info(co.system_lt, co.contact_fax,
                                         t['telefonnr'], contact_pref=n)
            elif t['kommtypekode'] == 'TLF': 
                if len(t['telefonnr']) == 5:
                    t['telefonnr'] = "228%s" % t['telefonnr']
                ou.populate_contact_info(co.system_lt, co.contact_fax,
                                         t['telefonnr'], contact_pref=n)
            elif t['kommtypekode'] == 'EPOST': 
                ou.populate_contact_info(co.system_lt, co.contact_email,
                                         t['kommnrverdi'], contact_pref=n)
        op = ou.write_db()
        if op is None:
            print "**** EQUAL ****"
        elif op:
            print "**** NEW ****"
        else:
            print "**** UPDATE ****"
            
        stedkode = get_stedkode_str(k)
        # Not sure why this casting to int is required for PostgreSQL
        stedkode2ou[stedkode] = int(ou.entity_id)
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
    org_stedkode = get_stedkode_str(sted, suffix='_for_org_sted')
    if not stedkode2ou.has_key(org_stedkode):
        print "Error in dataset:"\
              "  %s references missing STEDKODE: %s, using None" % (
            stedkode, org_stedkode)
        org_stedkode = None
        org_stedkode_ou = None
    else:
        org_stedkode_ou = stedkode2ou[org_stedkode]

    if existing_ou_mappings.has_key(stedkode2ou[stedkode]):
        if existing_ou_mappings[stedkode2ou[stedkode]] != org_stedkode_ou:
            print "Mapping for %s changed TODO (%s != %s)" % (
                stedkode, existing_ou_mappings[stedkode2ou[stedkode]],
                org_stedkode_ou)
        return

    if (org_stedkode_ou is not None
        and (stedkode != org_stedkode)
        and (not existing_ou_mappings.has_key(org_stedkode_ou))):
        rec_make_stedkode(org_stedkode, ou, existing_ou_mappings, steder,
                          stedkode2ou, co)

    ou.clear()
    ou.find(stedkode2ou[stedkode])
    if stedkode2ou.has_key(org_stedkode):
        ou.set_parent(co.perspective_lt, stedkode2ou[org_stedkode])
    else:
        ou.set_parent(co.perspective_lt, None)
    existing_ou_mappings[stedkode2ou[stedkode]] = org_stedkode_ou

def get_stedkode_str(row, suffix=""):
    elems = []
    for key in ('fakultetnr', 'instituttnr', 'gruppenr'):
        elems.append("%02d" % int(row[key+suffix]))
    return "-".join(elems)

if __name__ == '__main__':
    main()
