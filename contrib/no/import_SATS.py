#!/usr/bin/env python2.2

import pprint
import sys
from Cerebrum import Database
from Cerebrum.Utils import Factory

pp = pprint.PrettyPrinter(indent=4)

Cerebrum = Database.connect()
co = Factory.getConstants()(Cerebrum)
OU_class = Factory.get('OU')

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
            ou.add_entity_address(co.system_manual, co.address_post,
                                  address_text=skole[loc['address1']],
                                  postal_number=postno, city=city)
        if skole[loc['phoneno']] <> '':
            ou.add_contact_info(co.system_manual, co.contact_phone, skole[loc['phoneno']])
        if skole[loc['faxno']] <> '':
            ou.add_contact_info(co.system_manual, co.contact_fax, skole[loc['faxno']])
    Cerebrum.commit()
    print
    
def main():
    import_OU('vg')

if __name__ == '__main__':
    main()
