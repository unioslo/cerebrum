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

import pprint
import string
import sys
import getopt

import cereconf
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr

pp = pprint.PrettyPrinter(indent=4)

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
OU_class = Factory.get('OU')
account = Account.Account(Cerebrum)
account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)

source_system = co.system_sats
school2ouid = {}
show_warnings = 0
verbose = 0

def read_inputfile(filename):
    print "Processing %s" % filename
    f = open(filename, 'rb')
    spec = {}
    n = 0
    t = f.readline().replace("\t", "¦")
    for k in t.strip().split("¦"):
        spec[k.lower()] = n
        n += 1
    ret = []
    nlegal = nillegal = 0
    lineno = 1
    while 1:
        lineno += 1
        line = f.readline()
        if line == '': break
        line = line.replace("\t", "¦")
        dta = line.strip().split("¦")
        if(len(dta) != n):
            warn("WARNING: Illegal line #%i: '%s'" % (lineno, line[:-2]))
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
    schoolcode_pos = spec['schoolcode']
    ret = {}
    for t in dta:
        if not (t[schoolcode_pos] in schools):
            continue
        ret[t[0]] = ret.get(t[0], []) + [t[1:],]
    for t in spec.keys():
        spec[t] -= 1
    return spec, ret

def populate_people(level, type, pspec, pinfo):
    print "Populating %i entries of type %s" % (len(pinfo), type)
    if type == 'elev':
        fname = 'person_elev_%s.txt' % level
        oidname = 'elevoid'
    elif type == 'ansatt' or type == 'lærer':
        fname = 'person_ansatt_%s.txt' % level
        oidname = 'ansattoid'
    else:
        fname = 'person_foreldre_%s.txt' % level
        oidname = 'parentfid'
        elevoids2info = pinfo
        print "# elever %i" % len(elevoids2info.keys())
    spec, dta = read_inputfile("sats/%s" % fname)
    # Create mapping of locname to locid
    ret = {}
    # Process all people in the input-file
    for p in dta:
        if type == 'foreldre':
            if not elevoids2info.has_key(p[spec['childfid']]):
                continue
        elif not (pinfo.has_key(p[spec[oidname]])):
            continue                          # Skip unknown person
        sys.stdout.write('.')
        sys.stdout.flush()

        # find all affiliations and groups for this person
        affiliations = {}
        groups = {}
        if type == 'foreldre':
            (gh, ah) = elevoids2info[p[spec['childfid']]]
            for k in gh.keys():
                k = k.replace('_elev', '_foreldre')
                groups[k] = 1
            for k in ah.keys():
                affiliations[k] = 1
        else:
            for extra in pinfo[p[spec[oidname]]]:
                school = extra[pspec['schoolcode']]
                affiliations["%s:%s" % (level, school)] = 1
                if type == 'elev':
                    groups["%s_%s_%s" % (school, extra[pspec['klassekode']], type)] = 1
                elif type == 'lærer':
                    groups["%s_%s_%s" % (school, extra[pspec['elevgruppekode']], type)] = 1
        try:
            p_id = update_person(p, spec, type, affiliations.keys(), groups.keys())
            ret[p[spec[oidname]]] = (groups, affiliations)
        except:
            print " Error importing %s" % p[spec[oidname]]
            pp.pprint ((p, spec, type, affiliations, groups.keys() ))
            raise
    return ret

def import_all():
    schools = {'gs': ('VAHL', 'JORDAL'),
               'vg': ('ELV', )}
    global school2ouid
    school2ouid = import_OU(schools)
    for level in schools.keys():

        espec, elev_info =  read_extra_person_info('elev', level, schools[level])
        elevoids2info = populate_people(level, 'elev', espec, elev_info)

        # Populate parents for the already imported students
        elevoid2entity_id = populate_people(level, 'foreldre', [], elevoids2info)

        tspec, teacheriod2info = read_extra_person_info('lærer', level, schools[level])
        populate_people(level, 'lærer', tspec, teacheriod2info)

        aspec, adminoid2info = read_extra_person_info('admin', level, schools[level])
        populate_people(level, 'ansatt', aspec, adminoid2info)
    Cerebrum.commit()

def update_person(p, spec, type, affiliations, groupnames):
    """Create or update the persons name, address and contact info.

    """
    person = Person.Person(Cerebrum)
    gender = co.gender_female
    if p[spec['sex']] == '1':
        gender = co.gender_male
    date = None
    who = "%s@%s.%s" % (p[spec['personoid']], type, affiliations[0])
    print "update_person %s" % who
    try:
        day, mon, year = [int(x) for x in p[spec['birthday']].split('.')]
        date = Cerebrum.Date(year, mon, day)
    except:
        warn("Bad date '%s' for %s" % (p[spec['birthday']], who))
    if p[spec['firstname']] == '' or p[spec['lastname']] == '':
        warn("Bad name for %s" % who)
        return

    person.clear()
    try:
        person.find_by_external_id(co.externalid_personoid,
                                   p[spec['personoid']])
    except Errors.NotFoundError:
        pass
    person.populate(date, gender)
    person.affect_names(source_system, co.name_first, co.name_last)
    person.populate_name(co.name_first, p[spec['firstname']])
    person.populate_name(co.name_last, p[spec['lastname']])
    if p[spec['socialsecno']] <> '':
        # Disabled this one as well until the duplicate oid issue is
        # sorted out.

        #person.populate_external_id(source_system, co.externalid_fodselsnr,
        #                            p[spec['socialsecno']])
        pass
    else:
        warn("No ssid for %s" % who)
    # oid is not unique?
    # person.populate_external_id(source_system, co.externalid_personoid, p[spec['personoid']])

    person.populate_address(source_system)
    try:
        postno, city = string.split(p[spec['address3']], maxsplit=1)
        if postno.isdigit():
            person.populate_address(source_system, co.address_post,
                                    address_text=p[spec['address1']],
                                    postal_number=postno, city=city)
        else:
            warn("Bad address for %s" % who)
    except ValueError:
        warn("Bad address for %s" % who)

    person.populate_contact_info(source_system)
    if p[spec['phoneno']] <> '':
        person.populate_contact_info(source_system, co.contact_phone, p[spec['phoneno']])
    if p[spec['faxno']] <> '':
        person.populate_contact_info(source_system, co.contact_fax, p[spec['faxno']])
    if p[spec['email']] <> '':
        person.populate_contact_info(source_system, co.contact_email, p[spec['email']])
    op = person.write_db()
##     if op is None:
##         print "**** EQUAL ****"
##     elif op == True:
##         print "**** NEW ****"
##     elif op == False:
##         print "**** UPDATE ****"

    if op <> True:          # TODO: handle update/equal
        return person.entity_id

    for a in affiliations:
        if type == 'elev':
            person.add_affiliation(school2ouid[a], co.affiliation_student,
                                   source_system, co.affiliation_status_student_valid)
        elif type == 'admin' or type == 'lærer':
            person.add_affiliation(school2ouid[a], co.affiliation_employee,
                                   source_system, co.affiliation_status_employee_valid)
        elif type == 'foreldre':
            person.add_affiliation(school2ouid[a], co.affiliation_employee,  # TODO: new const
                                   source_system, co.affiliation_status_employee_valid)
    for g in groupnames:
        group = Group.Group(Cerebrum)
        try:
            group.find_by_name(g)
        except Errors.NotFoundError:
            group.populate(account, co.group_visibility_all,
                           g, "autogenerated import group %s" % g)
            group.write_db()
        group.add_member(person, co.group_memberop_union)
    return person.entity_id

def import_OU(schools):
    """Registers or updates information about all schools listed in the
    'schools' dict."""

    ret = {}
    tspec = {'name': 0, 'institutioncode': 1, 'phoneno': 2, 'faxno': 3,
             'address1': 4, 'address3': 5}
    top_ou = create_OU(('UFD', 'UFD', '', '', '', '0000 Norge'), tspec, None)
    top_ou = create_OU(('Oslo', 'Oslo', '', '', '', '0000 Norge'),
                       tspec, top_ou.entity_id)

    for level in schools.keys():
        parent_ou = create_OU((level, level, '', '', '', '0000 Norge'),
                              tspec, top_ou.entity_id)
        spec, dta = read_inputfile("sats/sted_%s.txt" % level)
        for skole in dta:
            if not (skole[spec['institutioncode']] in schools[level]):
                continue
            sys.stdout.write('.')
            sys.stdout.flush()
            ou = create_OU(skole, spec, parent_ou.entity_id)
            ret["%s:%s" % (level, skole[spec['institutioncode']])] = ou.entity_id
        print
    Cerebrum.commit()
    return ret

def create_OU(skole, spec, parent):
    ou = OU_class(Cerebrum)
    ou.clear()
    should_set_parent = True
    try:
        ou.find_by_parent(skole[spec['institutioncode']][:15],
                          co.perspective_sats, parent)
        should_set_parent = False
    except Errors.NotFoundError:
        pass
    ou.populate(skole[spec['name']],
                acronym=skole[spec['institutioncode']][:15],
                short_name=skole[spec['institutioncode']][:30],
                display_name=skole[spec['name']],
                sort_name=skole[spec['name']])

    ou.populate_address(source_system)
    ou.populate_contact_info(source_system)
    if skole[spec['address3']] == '':
        print "Bad info for %s" % skole[spec['name']]
        pp.pprint(skole)
    else:
        postno, city = skole[spec['address3']].split()
        ou.populate_address(source_system, co.address_post,
                            address_text=skole[spec['address1']],
                            postal_number=postno, city=city)
    if skole[spec['phoneno']] <> '':
        ou.populate_contact_info(source_system, co.contact_phone, skole[spec['phoneno']])
    if skole[spec['faxno']] <> '':
        ou.populate_contact_info(source_system, co.contact_fax, skole[spec['faxno']])

    ou.write_db()
    if should_set_parent:
        ou.set_parent(co.perspective_sats, parent)
    return ou

def convert_all():
    files = ("sted_vg.txt", "klasse_fag_emne_gs.txt",
             "klasse_fag_emne_vg.txt", "person_ansatt_gs.txt",
             "person_andre_ansatte_gs.txt",
             "person_andre_ansatte_vg.txt",
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

def warn(msg):
    if show_warnings:
        print "\nWARNING: %s" % msg

def usage():
    print """import_SATS.py [-w | -v] {-i}
    -w : show warnings
    -v : verbose
    -i : run import"""

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], "wvic",
                                   ["warn", "verbose", "import", "convert"])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for o, a in opts:
        if o in ('-w', '--warn'):
            show_warnings = 1
        elif o in ('-v', '--verbose'):
            verbose += 1
        elif o in ('-i', '--import'):
            import_all()
        elif o in ('-c', '--convert'):
            convert_all()
    if(len(opts) == 0):
        usage()
