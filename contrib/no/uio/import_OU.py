#!/usr/bin/env python2

import re
import pickle
import sys

from Cerebrum import Database
from Cerebrum.modules.no.uio import OU

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
        sko = "%s-%s-%s" % (stedinfo['fakultetnr'], stedinfo['instituttnr'], stedinfo['gruppenr'])
        return (sko, stedinfo)

stedfile = "/u2/dumps/LT/sted.dta";

def main():
    Cerebrum = Database.connect(user="cerebrum")
    steder = les_sted_info()
    ou = OU.OU(Cerebrum)
    i = 1
    sko2ou = {}
    for k in steder.values():
        i = i + 1
        try:
            sko = "%s-%s-%s" % (k['fakultetnr'], k['instituttnr'], k['gruppenr'])
            ou.get_sko(k['fakultetnr'], k['instituttnr'], k['gruppenr'])
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
    existing_ou_mappings = {}
    for t in ou.get_structure_mappings('LT'):
        existing_ou_mappings[t[0]] = t[1]
        
    # Now populate ou_structure
    for sko in steder.keys():
        rec_make_sko(sko, ou, existing_ou_mappings, steder, sko2ou)

def rec_make_sko(sko, ou, existing_ou_mappings, steder, sko2ou):
    """Recursively create the ou_id -> parent_id mapping"""
    sted = steder[sko]
    org_sko = "%s-%s-%s" % (sted['fakultetnr_for_org_sted'],
                            sted['instituttnr_for_org_sted'],
                            sted['gruppenr_for_org_sted'])
    if(not sko2ou.has_key(org_sko)):
        print "Error in dataset, missing SKO: %s, using None" % org_sko
        org_sko = None
        org_sko_ou = None
    else:
        org_sko_ou = sko2ou[org_sko]
        
    if(existing_ou_mappings.has_key(sko2ou[sko])):
        if(existing_ou_mappings[sko2ou[sko]] != org_sko_ou):
            print "Mapping for %s changed TODO (%s != %s)" % (
                sko, existing_ou_mappings[sko2ou[sko]], org_sko_ou)
        return

    if(org_sko_ou != None and (sko != org_sko) and
       (not existing_ou_mappings.has_key(org_sko_ou))):
        rec_make_sko(org_sko, ou, existing_ou_mappings, steder, sko2ou)

    ou.find(sko2ou[sko])
    if sko2ou.has_key(org_sko):
        ou.add_structure_maping('LT', sko2ou[org_sko])
    else:
        ou.add_structure_maping('LT', None)
    existing_ou_mappings[sko2ou[sko]] = org_sko_ou

def les_sted_info():
    steder = {}
    f = file(stedfile)

    dta = StedData()

    for line in f.readlines():
        (sko, sted) = dta.parse_line(line)
        steder[sko] = sted
    return steder

if __name__ == '__main__':
    main()

