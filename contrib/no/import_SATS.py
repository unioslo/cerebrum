#!/usr/bin/env python2.2

import cerebrum_path

import pprint
import string
import sys

from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr

pp = pprint.PrettyPrinter(indent=4)

Cerebrum = Database.connect()
co = Factory.getConstants()(Cerebrum)
OU_class = Factory.get('OU')

source_system = co.system_sats

def read_inputfile(filename):
    print "Processing %s" % filename
    f = open(filename, 'rb')
    spec = f.readline().strip().split(",")
    ret = []
    nlegal = nillegal = 0
    while 1:
        line = f.readline()
        if line == '': break
        
        dta = line.strip().split(",")
        if(len(dta) != len(spec)):
            # print "WARNING: Illegal line: '%s'" % line
            nillegal += 1
            continue
        nlegal += 1
        ret += [dta, ]
    print "Result: %i / %i" % (nlegal, nillegal)
    return (spec, ret)

def save_outputfile(filename, hdr, lst):
    """Save outputfile in a sorted format without duplicates or
    errenous lines """
    lst.sort(lambda a,b: cmp(",".join(a), ",".join(b)))
    prev = None
    f = open(filename, 'wb')
    f.write(",".join(hdr) + "\n")
    for t in lst:
        if prev <> t:
            f.write(",".join(t) + "\n")
        prev = t
    f.close()

def convert_all():
    files = ("sted_vg.txt", "klasse_fag_emne_gs.txt",
             "klasse_fag_emne_vg.txt", "person_ansatt_gs.txt",
             "person_ansatt_ikkeLærer_gs.txt",
             "person_ansatt_ikkeLærer_vg.txt",
             "person_ansatt_lærere_gs.txt",
             "person_ansatt_lærere_vg.txt",
             "person_ansatt_vg.txt",
             "person_elev_ekstra_opplys_gs.txt",
             "person_elev_ekstra_opplys_vg.txt",
             "person_elev_gs.txt", "person_elev_vg.txt",
             "person_foreldre_gs.txt", "person_foreldre_vg.txt",
             "sted_gs.txt", "sted_vg.txt")
    
    for f in files:
        spec, ret = read_inputfile("sats/%s" % f)
        save_outputfile(f, spec, ret)

def import_OU(gs_vg):
    ou = OU_class(Cerebrum)
    spec, dta = read_inputfile("sats/sted_%s.txt" % gs_vg)
    loc = {}
    n = 0
    for k in spec:
        loc[k.lower()] = n
        n += 1

    for skole in dta:
        sys.stdout.write('.')
        sys.stdout.flush()
        ou.clear()
        # TODO: ou.find_by_name(skole[loc['name']])
        ou.populate(skole[loc['name']],
                    acronym=skole[loc['institutioncode']][:15],
                    short_name=skole[loc['institutioncode']][:30],
                    display_name=skole[loc['name']],
                    sort_name=skole[loc['name']])
        ou.write_db()
        # TODO: Handle existing data
        if skole[loc['address3']] == '': # or skole[loc['address1']] == '':
            print "\nWARNING: Bad info for %s" % skole[loc['name']]
            pp.pprint(skole)
        else:
            postno, city = skole[loc['address3']].split()
            ou.add_entity_address(source_system, co.address_post,
                                  address_text=skole[loc['address1']],
                                  postal_number=postno, city=city)
        if skole[loc['phoneno']] <> '':
            ou.add_contact_info(source_system, co.contact_phone, skole[loc['phoneno']])
        if skole[loc['faxno']] <> '':
            ou.add_contact_info(source_system, co.contact_fax, skole[loc['faxno']])
    Cerebrum.commit()
    print

def import_elever(gs_vg):

    # TODO: Ved en triviell omskriving av denne vil den også kunne
    # importere foreldre og ansatte.  Tipper den da bør returnere en
    # dict som mapper personoid -> entityid.
    # 
    # En spesialisert rutine kan deretter gjøre nødvendig populering
    # av foreldre -> barn, samt melde inn i grupper.  Hvordan dette
    # skal gjøres må diskuteres nærmere, da jeg ikke vet hva som er
    # ønsket.

    person = Person.Person(Cerebrum)
    spec, dta = read_inputfile("sats/person_elev_%s.txt" % gs_vg)
    loc = {}
    n = 0
    for k in spec:
        loc[k.lower()] = n
        n += 1

    # Note: mange records har ikke fnr.

    for elev in dta:
        sys.stdout.write('.')
        sys.stdout.flush()
        gender = co.gender_female
        if elev[loc['sex']] == '1':
            gender = co.gender_male

        date = None
        try:
            day, mon, year = [int(x) for x in elev[loc['birthday']].split('.')]
            # if year < 1990: continue  # Speedup while testing
            date = Cerebrum.Date(year, mon, day)
        except:
            print "\nWARNING: Bad date %s for %s" % (elev[loc['birthday']],
                                                     elev[loc['personoid']])
        person.clear()
        try:
            person.find_by_external_id(co.externalid_personoid,
                                       elev[loc['personoid']])
        except Errors.NotFoundError:
            pass     # It is a new entry
        person.populate(date, gender)
        person.affect_names(source_system, co.name_first, co.name_last)
        if elev[loc['firstname']] == '' or elev[loc['lastname']] == '':
            print "\nWARNING: bad name for %s" % elev[loc['personoid']]
            continue
        person.populate_name(co.name_first, elev[loc['firstname']])
        person.populate_name(co.name_last, elev[loc['lastname']])
        if elev[loc['socialsecno']] <> '':
            person.populate_external_id(source_system, co.externalid_fodselsnr,
                                        elev[loc['socialsecno']])
        else:
            print "\nWARNING: no ssid for %s" % elev[loc['personoid']]
        person.populate_external_id(source_system, co.externalid_personoid,
                                    elev[loc['personoid']])
        try:
            person.write_db()
        except:
            print "Error"  # TODO: log
            continue
        if elev[loc['address3']] == '': # or elev[loc['address1']] == '':
            print "\nWARNING: Bad address for %s" % elev[loc['socialsecno']]
            pp.pprint(elev)
        else:
            postno, city = string.split(elev[loc['address3']], maxsplit=1)
            if postno.isdigit():
                person.add_entity_address(source_system, co.address_post,
                                          address_text=elev[loc['address1']],
                                          postal_number=postno, city=city)
            else:
                print "\nWARNING: Bad address for %s" % elev[loc['personoid']]
        if elev[loc['phoneno']] <> '':
            person.add_contact_info(source_system, co.contact_phone, elev[loc['phoneno']])
        if elev[loc['faxno']] <> '':
            person.add_contact_info(source_system, co.contact_fax, elev[loc['faxno']])
        if elev[loc['email']] <> '':
            person.add_contact_info(source_system, co.contact_email, elev[loc['email']])

    Cerebrum.commit()
    print
    
def main():
    # convert_all()
    # import_OU('vg')
    import_elever('vg')

if __name__ == '__main__':
    main()
