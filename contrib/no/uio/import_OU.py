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
        stedkode = "%s-%s-%s" % (stedinfo['fakultetnr'], stedinfo['instituttnr'], stedinfo['gruppenr'])
        return (stedkode, stedinfo)

stedfile = "/u2/dumps/LT/sted.dta";

def main():
    Cerebrum = Database.connect(user="cerebrum")
    steder = les_sted_info()
    ou = OU.OU(Cerebrum)
    i = 1
    stedkode2ou = {}
    for k in steder.values():
        i = i + 1
        try:
            stedkode = "%s-%s-%s" % (k['fakultetnr'], k['instituttnr'], k['gruppenr'])
            ou.get_stedkode(k['fakultetnr'], k['instituttnr'], k['gruppenr'])
            stedkode2ou[stedkode] = ou.ou_id

            

            # Todo: compare old and new
        except : # Cerebrum.Errors.NotFoundError:
            id = ou.new(k['stednavn'], k['akronym'], k['forkstednavn'],
                        k['stednavn'], k['stednavn'])
            stedkode = "%s-%s-%s" % (k['fakultetnr'], k['instituttnr'], k['gruppenr'])
            stedkode2ou[stedkode] = id
            ou.find(id)             # new setter ikke denne i self (bug?)
            ou.add_stedkode(k['fakultetnr'], k['instituttnr'], k['gruppenr'])
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
    for stedkode in steder.keys():
        rec_make_stedkode(stedkode, ou, existing_ou_mappings, steder, stedkode2ou)

def rec_make_stedkode(stedkode, ou, existing_ou_mappings, steder, stedkode2ou):
    """Recursively create the ou_id -> parent_id mapping"""
    sted = steder[stedkode]
    org_stedkode = "%s-%s-%s" % (sted['fakultetnr_for_org_sted'],
                            sted['instituttnr_for_org_sted'],
                            sted['gruppenr_for_org_sted'])
    if(not stedkode2ou.has_key(org_stedkode)):
        print "Error in dataset, missing STEDKODE: %s, using None" % org_stedkode
        org_stedkode = None
        org_stedkode_ou = None
    else:
        org_stedkode_ou = stedkode2ou[org_stedkode]
        
    if(existing_ou_mappings.has_key(stedkode2ou[stedkode])):
        if(existing_ou_mappings[stedkode2ou[stedkode]] != org_stedkode_ou):
            print "Mapping for %s changed TODO (%s != %s)" % (
                stedkode, existing_ou_mappings[stedkode2ou[stedkode]], org_stedkode_ou)
        return

    if(org_stedkode_ou != None and (stedkode != org_stedkode) and
       (not existing_ou_mappings.has_key(org_stedkode_ou))):
        rec_make_stedkode(org_stedkode, ou, existing_ou_mappings, steder, stedkode2ou)

    ou.find(stedkode2ou[stedkode])
    if stedkode2ou.has_key(org_stedkode):
        ou.set_parent('LT', stedkode2ou[org_stedkode])
    else:
        ou.set_parent('LT', None)
    existing_ou_mappings[stedkode2ou[stedkode]] = org_stedkode_ou

def les_sted_info():
    steder = {}
    f = file(stedfile)

    dta = StedData()

    for line in f.readlines():
        (stedkode, sted) = dta.parse_line(line)
        steder[stedkode] = sted
    return steder

if __name__ == '__main__':
    main()

