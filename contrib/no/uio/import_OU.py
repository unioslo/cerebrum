#!/usr/bin/env python2

import re
import pickle
import sys

from Cerebrum import Database
from Cerebrum.modules.no.uio import UioOU

class StedData(object):
    colnames = """fakultetnr, instituttnr, gruppenr, forkstednavn, stednavn,
        akronym, stedpostboks, fakultetnr_for_org_sted,
        instituttnr_for_org_sted, gruppenr_for_org_sted,
        opprettetmerke_for_oppf_i_kat, telefonnr,
        adrtypekode_besok_adr, adresselinje1_besok_adr,
        adresselinje2_besok_adr, poststednr_besok_adr,
        poststednavn_besok_adr, landnavn_besok_adr,
        adrtypekode_intern_adr, adresselinje1_intern_adr,
        adresselinje2_intern_adr, poststednr_intern_adr,
        poststednavn_intern_adr, landnavn_intern_adr,
        adrtypekode_alternativ_adr, adresselinje1_alternativ_adr,
        adresselinje2_alternativ_adr, poststednr_alternativ_adr,
        poststednavn_alternativ_adr, landnavn_alternativ_adr"""
    re_cols = re.compile(r"\s+", re.DOTALL)
    colnames = re.sub(re_cols, "", colnames)
    colnames = colnames.split(",")

    def parse_line(self, line):
	info = line.split("\034")
        stedinfo = {}
        for c in self.colnames:
            stedinfo[c] = info.pop(0)
        return stedinfo

stedfile = "/u2/dumps/LT/sted.dta";

def main():
    Cerebrum = Database.connect(user="cerebrum", service="DRESDEN.uio.no")
    steder = les_sted_info()
    ou = UioOU.UioOU(Cerebrum)
    i = 1
    sko2ou = {}
    for k in steder:
        i = i + 1
#        if (x > 10): break
        print "OU: %s" % ou,
        try:
            ou.get_sko(k['fakultetnr'], k['instituttnr'], k['gruppenr'])
            print " Exists"
            sko = "%s-%s-%s" % (k['fakultetnr'], k['instituttnr'], k['gruppenr'])
            sko2ou[sko] = ou.ou_id

            # Todo: compare old and new
        except : # Cerebrum.Errors.NotFoundError:
            id = ou.new(k['stednavn'], k['akronym'], k['forkstednavn'],
                        k['stednavn'], k['stednavn'])
            sko = "%s-%s-%s" % (k['fakultetnr'], k['instituttnr'], k['gruppenr'])
            sko2ou[sko] = id
            ou.find(id)             # new setter ikke denne i self (bug?)
            ou.add_sko(k['fakultetnr'], k['instituttnr'], k['gruppenr'])
            ou.add_entity_address('LT', 'p', addr="%s\n%s" %
                                  (k['adresselinje1_intern_adr'],
                                   k['adresselinje2_intern_adr']),
                                  zip=k['poststednr_intern_adr'],
                                  city=k['poststednavn_intern_adr'])
            #                      country=k['landnavn_intern_adr'])
            ou.add_entity_address('LT', 's', addr="%s\n%s" %
                                  (k['adresselinje1_besok_adr'],
                                   k['adresselinje2_besok_adr']),
                                  zip=k['poststednr_besok_adr'],
                                  city=k['poststednavn_besok_adr'])
#                                  country=k['landnavn_besok_adr'])
            if k['telefonnr'].strip() != '':
                ou.add_entity_phone('LT', 'f', k['telefonnr'])
            print "Created"
    # Now populate ou_structure
    # TODO: This must be done in the right order
    for k in steder:
        sko = "%s-%s-%s" % (k['fakultetnr'], k['instituttnr'], k['gruppenr'])
        org_sko = "%s-%s-%s" % (k['fakultetnr_for_org_sted'],
                                k['instituttnr_for_org_sted'],
                                k['gruppenr_for_org_sted'])
        ou.find(sko2ou[sko])
        try:
            print "Map %s -> %s (%s -> %s)" % (sko, org_sko, sko2ou[sko], sko2ou[org_sko])
            rec_make_sko(k, steder, sko2ou)
        except KeyError:
            print "no key: <%s>" % org_sko
        except:
            print "Other error: %s " % sys.exc_info()[1]

def rec_make_sko(sted, steder, sko2ou):

    # while s (exists(sko2ou[sted])):
    #   rec_make_sko(s, steder, sko2ou)
    # if(! exists mapping): make_sko(s)

    #  ou.add_structure_maping('LT', sko2ou[org_sko])

    pass

def les_sted_info():
    steder = []
    f = file(stedfile)

    dta = StedData()

    for line in f.readlines():
        steder.append( dta.parse_line(line) )
    return steder

if __name__ == '__main__':
    main()

