#!/usr/bin/env python2.2

import cerebrum_path

import pprint
import string
import sys

from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr


pp = pprint.PrettyPrinter(indent=4)

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
OU_class = Factory.get('OU')

source_system = co.system_sats
school2ouid = {}
elevoids2group = {}

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

def read_extra_person_info(ptype, level, schools):
    """Returns format_spec, dict{'oid': [[person_info]]}."""

    if ptype == 'lærer':
        fname = 'person_ansatt_lærere_%s.txt' % level
    elif ptype == 'admin':
        fname = 'person_ansatt_ikkeLærer_%s.txt' % level
    elif ptype == 'elev':
        fname = 'person_elev_ekstra_opplys_%s.txt' % level

    spec, dta = read_inputfile("sats/%s" % fname)
    n = 0
    schoolcode_pos = None
    for k in spec:
        if(k.lower() == 'schoolcode'):
            schoolcode_pos = n
        n += 1
    ret = {}
    for t in dta:
        if not (t[schoolcode_pos] in schools):
            continue
        ret[t[0]] = ret.get(t[0], []) + [t[1:],]
    return spec[1:], ret

def populate_people(level, type, pspec, pinfo):
    if type == 'elev':
        fname = 'person_elev_%s.txt' % level
        oidname = 'elevoid'
    elif type == 'admin' or type == 'lærer':
        fname = 'person_ansatt_%s.txt' % level
        oidname = 'ansattoid'
    else:
        fname = 'person_foreldre_%s.txt' % level
        oidname = 'parentfid'
    spec, dta = read_inputfile("sats/%s" % fname)
    # Create mapping of locname to locid
    loc = {}
    n = 0
    for k in spec:
        loc[k.lower()] = n
        n += 1
    ploc = {}
    n = 0
    for k in pspec:
        ploc[k.lower()] = n
        n += 1
    ret = {}
    # Process all people in the input-file
    for p in dta:
        if type <> 'foreldre' and (not (pinfo.has_key(p[loc[oidname]]))):
            continue                          # Skip unknown person
        sys.stdout.write('.')
        sys.stdout.flush()

        # find all affiliations and groups for this person
        affiliations = []
        groups = {}
        for extra in pinfo[p[loc[oidname]]]:
            school = extra[ploc['schoolcode']]
            affiliations += school
            if type eq 'elev':
                groups["%s_%s_%s" % (school, extra[ploc['klassekode']], type)] = 1
            elif type eq 'lærer':
                groups["%s_%s_%s" % (school, extra[ploc['elevgruppekode']], type)] = 1
        if type eq 'foreldre':
            groups = elevoids2group[p[loc['childfid']]]
            
        p_id = update_person(p, loc, type, affiliations, groups.keys())
        ret[p_id] = groups
    return ret

def do_all():
    schools = {'gs': ('VAHL', 'JORDAL'),
               'vg': ('ELV', )}

    school2ouid = import_OU(schools)
    for level in schools.keys():

        espec, elev_info =  read_extra_person_info('elev', level, schools[level])
        elevoids2group = populate_people(level, 'elev', elev_info)

        # Populate parents for the already imported students
        elevoid2entity_id = populate_people(level, 'foreldre', level, None)


        aspec, adminoid2info = read_extra_person_info('admin', level, schools[level])
        populate_people(level, 'lærer', tspec, teacheriod2info)

        tspec, teacheriod2info = read_extra_person_info('lærer', level, schools[level])
        populate_people(level, 'ansatt', aspec, adminoid2info)

    # fordel å legge inn åpning for foreldre->barn rolle-mapping

def update_person(p, loc, affiliations):
    """Create or update the persons name, address and contact info.

    TODO: Also set affiliation
    """
    person = Person.Person(Cerebrum)
    gender = co.gender_female
    if p[loc['sex']] == '1':
        gender = co.gender_male
    date = None
    try:
        day, mon, year = [int(x) for x in p[loc['birthday']].split('.')]
        date = Cerebrum.Date(year, mon, day)
    except:
        print "\nWARNING: Bad date %s for %s" % (p[loc['birthday']],
                                                 p[loc['personoid']])
    if p[loc['firstname']] == '' or p[loc['lastname']] == '':
        print "\nWARNING: bad name for %s" % p[loc['personoid']]
        continue

    person.clear()
    try:
        person.find_by_external_id(co.externalid_personoid,
                                   p[loc['personoid']])
    except Errors.NotFoundError:
        pass
    person.populate(date, gender)
    person.affect_names(source_system, co.name_first, co.name_last)
    person.populate_name(co.name_first, p[loc['firstname']])
    person.populate_name(co.name_last, p[loc['lastname']])
    if p[loc['socialsecno']] <> '':
        person.populate_external_id(source_system, co.externalid_fodselsnr,
                                    p[loc['socialsecno']])
    else:
        print "\nWARNING: no ssid for %s" % p[loc['personoid']]
    person.populate_external_id(source_system, co.externalid_personoid,
                                p[loc['personoid']])

    op = person.write_db()
    if op is None:
        print "**** EQUAL ****"
    elif op == True:
        print "**** NEW ****"
    elif op == False:
        print "**** UPDATE ****"

    if p[loc['address3']] == '': # or elev[loc['address1']] == '':
        print "\nWARNING: Bad address for %s" % p[loc['personoid']]
    else:
        postno, city = string.split(p[loc['address3']], maxsplit=1)
        if postno.isdigit():
            person.add_entity_address(source_system, co.address_post,
                                      address_text=p[loc['address1']],
                                      postal_number=postno, city=city)
        else:
            print "\nWARNING: Bad address for %s" % p[loc['personoid']]
    if p[loc['phoneno']] <> '':
        person.add_contact_info(source_system, co.contact_phone, elev[loc['phoneno']])
    if p[loc['faxno']] <> '':
        person.add_contact_info(source_system, co.contact_fax, elev[loc['faxno']])
    if p[loc['email']] <> '':
        person.add_contact_info(source_system, co.contact_email, elev[loc['email']])
    return person.entity_id

def import_OU(schools):
    """Registers or updates information about all schools listed in the
    'schools' dict."""   # TODO: handle update
                         #       handle location in tree
    
    ou = OU_class(Cerebrum)
    ret = {}         # Python *****: can't declare a variable as local
    for level in schools.keys():
        spec, dta = read_inputfile("sats/sted_%s.txt" % level)
        loc = {}
        n = 0
        for k in spec:
            loc[k.lower()] = n
            n += 1
        for skole in dta:
            if not school2ouid[level].contains(skole[loc['institutioncode']]):
                continue
            sys.stdout.write('.')
            sys.stdout.flush()
            ou.clear()

            ou.populate(skole[loc['name']],
                        acronym=skole[loc['institutioncode']][:15],
                        short_name=skole[loc['institutioncode']][:30],
                        display_name=skole[loc['name']],
                        sort_name=skole[loc['name']])
            ou.write_db()
            ret["%s:%s" % (level, skole[loc['institutioncode']])] = ou.entity_id

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
    return ret

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


def main():
    #x = read_extra_person_info('lærer', 'vg', ('ELV', ))
    #pp.pprint(x)
    #do_all()
    pass
    # convert_all()
##     import_OU('vg')
##     elev_filter = 
##     import_elever('vg')
    

if __name__ == '__main__':
    main()
