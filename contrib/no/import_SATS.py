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
import sys
import os

import cereconf
from Cerebrum import Errors
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr

pp = pprint.PrettyPrinter(indent=4)

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
account = Account.Account(Cerebrum)
account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)

school2ouid = {}
show_warnings = False
verbose = 0
BASE_DUMPDIR = os.path.join(os.environ['HOME'], 'project/private/fiberskolen')
# TODO: Calculate `dette_skolear` from time.
dette_skolear = '2002/2003'

class AutoFlushWriter(file):
    __slots__ = ()
    def write(self, data):
        ret = super(AutoFlushWriter, self).write(data)
        self.flush()
        return ret

class ProgressWriter(AutoFlushWriter):
    def __init__(self, *args, **kws):
        super(ProgressWriter, self).__init__(*args)
        self._col = 0
        self._margin = kws.get('margin', 4)
        self._lw = kws.get('linewidth', 80)

    def _get_margin(self, raw):
        if raw: return 0
        return max(self._margin, 0)

    def _write_continued(self, data, raw):
        if not data:
            return
        margin = self._get_margin(raw)
        if (# Have we written to the current line already?
            (self._col > margin) and
            # Is there room for `data` on the current line?
            (self._col + len(data)) > (self._lw - margin)):
            # Write a newline.
            self._write_new("", raw)
        # Prepend margin to `data`, if needed.
        if self._col < margin:
            whitespace = " " * (margin - self._col)
            data = whitespace + data
        super(ProgressWriter, self).write(data)
        self._col += len(data)

    def _write_new(self, data, raw):
        super(ProgressWriter, self).write("\n")
        self._col = 0
        self._write_continued(data, raw)

    def write(self, data, raw=False):
        # Split data into lines; necessary to keep track of current
        # column.
        lines = data.split("\n")
        self._write_continued(lines[0], raw)
        for line in lines[1:]:
            self._write_new(line, raw)

progress = ProgressWriter("/dev/stdout", 'w')

class DataRowHolder(object):
    __slots__ = ()
    data_source = None

    def __init__(self, *args, **kws):
        if not (args or kws):
            return
        attrs = self.get_attrs()
        for i in range(len(args)):
            attr = attrs[i]
            setattr(self, attr, args[i])
        for k, v in kws.iteritems():
            if not hasattr(self, k):
                setattr(self, k, v)
            else:
                raise ValueError, "Attribute '%s' given more than once" % k
        for a in attrs:
            if not hasattr(self, a):
                setattr(self, a, None)

    def _get_spec(self):
        return [x.split("=") for x in self.file_fields]

    def get_attrs(self): return [x[1] for x in self._get_spec()]

    def get_fields(self): return [x[0] for x in self._get_spec()]

    def check_file_format(self, line):
        model_fields = self.get_fields()
        file_fields = [x.strip() for x in line.split(";")]
        if len(model_fields) <> len(file_fields):
            raise ValueError, "File spec is not of same length as model."
        for a, b in zip(file_fields, model_fields):
            if a <> b:
                raise ValueError, \
                      "File field (%s) differs from model (%s)." % (a, b)

    def __repr__(self):
        fields = self.file_fields
        attrs = self.get_attrs()
        return "<%(cls)s %(attrs)s>" % {
            'cls': self.__class__.__name__,
            'attrs': ", ".join(["%s=%r" % (fields[i],
                                           getattr(self, attrs[i], '<undef>'))
                                for i in range(len(attrs))])
            }


class SkoleRow(DataRowHolder):
    # Fra skole_sted_(GS|VG).txt
    __slots__ = ('skole_oid', 'skole', 'skolenavn', 'gateadr',
                 'postadr', 'tlf', 'fax')
    file_fields = (
        'SchoolOID=skole_oid', 'Institusjon=skole', 'Skolenavn=skolenavn',
        'Gataaddress=gateadr', 'Postaddress=postadr', 'Telefon=tlf',
        'Faks=fax')

class PersonRow(DataRowHolder):
    __slots__ = (
        # Felles attributter fra
        #   ansatt_(GS|VG).txt
        #   elev_(GS|VG).txt
        #   foreldre_(GS|VG).txt
        # (dog med ørlite variasjon i hva ekvivalente attributter
        # "kalles" i de forskjellige dumpene).
        'person_oid', 'fnr', 'skole', 'fornavn', 'etternavn', 'kjonn',
        'gateadr', 'postadr', 'tlf', 'fax', 'email')

class ElevRow(PersonRow):
    # Fra elev_(GS|VG).txt
    __slots__ = ('klasse', 'klassetrinn', 'skolear',
                 # Avledet av foreldre_(GS|VG).txt:
                 'foresatte')
    # ??? Hvordan er forholdet mellom 'klasse' for Elev og
    #     'oppgavekode'/'elevgruppekode' for Lærer ???
    file_fields = (
        'SkoleNavn=skole', 'PersonOID=person_oid', 'Klassekode=klasse',
        'Klassetrinn=klassetrinn', 'ElevFor=fornavn',
        'ElevEtter=etternavn', 'FødselNr=fnr', 'Kjønn=kjonn',
        'GataAddress=gateadr', 'PostAddress=postadr', 'Telefon=tlf',
        'Faks=fax', 'Email=email', 'Skoleår=skolear')

class ForesattRow(PersonRow):
    # Fra foreldre_(GS|VG).txt
    __slots__ = (
        'klasse', 'klassetrinn', 'barn_person_oid', 'barn_fnr',
        'relasjon', 'skolear')
    file_fields = (
        'Skolekode=skole', 'Klassekode=klasse',
        'Klassetrinn=klassetrinn', 'B_PersonOID=barn_person_oid',
        'B_Fødselnr=barn_fnr', 'F_personOID=person_oid',
        'F_Fornavn=fornavn', 'F_Etternavn=etternavn', 'Fødselnr=fnr',
        'Kjønn=kjonn', 'Relationtypecode=relasjon',
        'GataAddress=gateadr', 'PostAddress=postadr', 'Telefon=tlf',
        'Faks=fax', 'Email=email', 'Skoleår=skolear')

class AnsattRow(PersonRow):
    # Fra ansatt_(GS|VG).txt
    __slots__ = ('funksjon', 'pedag_kode')
    file_fields = (
        'Institusjon=skole', 'PersonOID=person_oid',
        'AnsattFor=fornavn', 'AnsattEtter=etternavn', 'FødselNr=fnr',
        'Kjønn=kjonn', 'GataAddress=gateadr', 'PostAddress=postadr',
        'Telefon=tlf', 'Faks=fax', 'Email=email', 'Funksjon=funksjon',
        'Pedagogiskskode=pedag_kode')

class KlasseRow(DataRowHolder):
    # Fra klasse_fag_emne_(GS|VG).txt
    __slots__ = (
        'skole', 'larer_person_oid', 'larer_fnr', 'oppgavekode',
        'oppgavebeskrivelse', 'klassetrinn', 'elevgruppekode',
        'studieretning', 'skolear')
    # 'studieretning' finnes kun for VG-skoler.
    file_fields = (
        'Skolenavn=skole', 'PersonOID=larer_person_oid',
        'Fødselnr=larer_fnr', 'Oppgavekode=oppgavekode',
        'OppgaveBeskrivelse=oppgavebeskrivelse',
        'KLassetrinn=klassetrinn', 'Elevgruppekode=elevgruppekode',
        'Studierettning=studieretning', 'Skoleår=skolear')

## class Admin(Ansatt):
##     # Fra andre_ansatt_<SKOLENAVN>.txt
##     __slots__ = ()
##     # pedag_kode må være 0.
##     file_fields = (
##         'institution=skole', 'AnsattFor=fornavn',
##         'AnsattEtter=etternavn', 'FødselNr=fnr', 'Kjønn=kjonn',
##         'GataAddress=gateadr', 'PostAddress=postadr', 'Telefon=tlf',
##         'Faks=fax', 'Email=email', 'Funksjon=funksjon',
##         'pedagogiskskode=pedag_kode')

## class Larer(DataRowHolder):
##     # Fra ansatt_larer_(GS|VG).txt
##     __slots__ = ('person_oid', 'fnr','funksjon', 'oppgavekode',
##                  'elevgruppekode', 'skolear')
##     file_fields = (
##         'PersonOID=person_oid', 'FødselNr=fnr', 'Funksjon=funksjon',
##         'OppgaveKode=oppgavekode', 'Elevgruppekode=elevgruppekode',
##         'Skoleår=skolear')

## class Oppgavekode(DataRowHolder):
##     # Fra oppgavekode_(GS|VG).txt
##     __slots__ = (
##         'oppgavekode', 'oppgavebeskrivelse')
##     file_fields = ('Oppgavekode=oppgavekode',
##                    'OppgaveBeskrivelse=oppgavebeskrivelse')


IFS = ";"
def split_line(line, sep=IFS):
    return [x.strip() for x in line.split(sep)]

def read_file(fname, cls):
    """Generate objects of class ``cls`` from file ``fname``."""
    if cls.data_source is None:
        cls.data_source = [fname]
    elif fname not in cls.data_source:
        cls.data_source.append(fname)
    f = file(fname)
    cls().check_file_format(f.readline())
    ret = []
    while True:
        line = f.readline()
        if not line:
            break
        ret.append(cls(*(split_line(line))))
    f.close()
    return ret

def uniq(seq):
    foo = {}
    for i in seq:
        foo[i] = None
    return foo.keys()

def multi_getattr(objs, attr):
    ret = []
    for o in objs:
        ret.append(getattr(o, attr))
    return ret

def multi_getattr_uniq(objs, attr):
    vals = uniq(multi_getattr(objs, attr))
    if len(vals) <> 1:
        raise ValueError, \
              "Couldn't find single value for attr '%s' (%r)" % (attr, objs)
    return vals[0]

def import_all():
    import_spec = {
        'GS': {'datakilde': co.system_sats_oslo_gs,
               'skoler': ('VAHL', 'JORDAL')},
        'VG': {'datakilde': co.system_sats_oslo_vg,
               'skoler': ('ELV', )},
        }
    for level, spec in import_spec.items():
        skoler = spec['skoler']
        src_sys = spec['datakilde']
        dumpdir = os.path.join(BASE_DUMPDIR, level)

        progress.write("OU/%s: " % level, raw=True)
        # Opprett rot-noder for OU.
        parent_ou = bootstrap_ou(level, src_sys)
        # Importer 'skole_sted'.
        fname = os.path.join(dumpdir, "skole_sted_%s.txt" % level)
        skole2ou_id = {}
        for row in read_file(fname, SkoleRow):
            if row.skole in skoler:
                skole2ou_id[row.skole] = write_ou(row, parent_ou, src_sys)
        progress.write("\n")
        Cerebrum.commit()

        # Importer 'elev'.
        fname = os.path.join(dumpdir, "elev_%s.txt" % level)
        person2row = {}
        for row in read_file(fname, ElevRow):
            if row.skole in skoler and row.skolear == dette_skolear:
                person2row.setdefault(row.person_oid, []).append(row)

        # Importer 'foreldre'.
        fname = os.path.join(dumpdir, "foreldre_%s.txt" % level)
        for row in read_file(fname, ForesattRow):
            if row.skole in skoler and row.skolear == dette_skolear:
                person2row.setdefault(row.person_oid, []).append(row)

        # Importer 'ansatt'.
        fname = os.path.join(dumpdir, "ansatt_%s.txt" % level)
        for row in read_file(fname, AnsattRow):
            if row.skole in skoler:
                person2row.setdefault(row.person_oid, []).append(row)

        # Datagrunnlag for automatisk opprettelse/vedlikehold av
        # grupper.
        # {'group_name': [person_id, ...], ...}
        groups = {}

        poid2person_id = {}
        progress.write("Person/%s: " % level, raw=True)
        for oid, rows in person2row.items():
            person_id = write_person(rows, skole2ou_id, src_sys)
            poid2person_id[oid] = person_id
            for row in rows:
                if isinstance(row, ElevRow):
                    # Gruppe med elever per kombinasjon (skole, klasse)
                    gname = '%s_%s_elev' % (row.skole, row.klasse)
                    groups.setdefault(gname, []).append(person_id)
                elif isinstance(row, ForesattRow):
                    # Gruppe med foresatte per kombinasjon (skole, klasse)
                    gname = '%s_%s_foresatt' % (row.skole, row.klasse)
                    groups.setdefault(gname, []).append(person_id)
        progress.write("\n")
        Cerebrum.commit()

        progress.write("Group/%s: " % level, raw=True)
        # Importer 'klasse_fag_emne'.
        fname = os.path.join(dumpdir, "klasse_fag_emne_%s.txt" % level)
        for row in read_file(fname, KlasseRow):
            if row.skole in skoler:
                person_id = poid2person_id.get(row.larer_person_oid, None)
                if person_id is None:
                    continue
                # Gruppe med lærere per kombinasjon (skole, elevgruppekode)
                gname = '%s_%s_larer' % (row.skole, row.elevgruppekode)
                groups.setdefault(gname, []).append(person_id)

        progress.write("\n")

        continue

        elev_info = read_extra_person_info('elev', level, spec['skoler'])
        pp.pprint(elev_info)
        elevoids2info = populate_people(level, 'elev', espec, elev_info)

        # Populate parents for the already imported students
        elevoid2entity_id = populate_people(level, 'foreldre', [],
                                            elevoids2info)

        tspec, teacheriod2info = read_extra_person_info('lærer', level,
                                                        schools[level])
        populate_people(level, 'lærer', tspec, teacheriod2info)

        aspec, adminoid2info = read_extra_person_info('admin', level,
                                                      schools[level])
        populate_people(level, 'ansatt', aspec, adminoid2info)
    return
    Cerebrum.commit()

def read_inputfile(filename, separator="\t"):
    print "Processing %s" % filename
    f = file(filename, 'rb')
    # Første linje er en spesifikasjon på hva de forskjellige feltene
    # heter.
    line = f.readline().replace(separator, "¦")
    if line[0] <> '':
        warn("WARNING: Første tegn av første linje er ikke ^L")
    fields = [x.strip() for x in line.split("¦")]
    spec = {}
    n = 0
    t = f.readline().replace("\t", "¦")
    for k in t.strip().split("¦"):

        spec[k.lower()] = n
        n += 1
    ret = []
    nlegal = nillegal = 0
    lineno = 1
    while True:
        lineno += 1
        line = f.readline()
        if not line:
            break
        line = line.replace("\t", "¦")
        dta = line.strip().split("¦")
        if len(dta) != n:
            warn("WARNING: Illegal line #%i: '%s'" % (lineno, line[:-2]))
            nillegal += 1
            continue
        nlegal += 1
        ret.append(dta)
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
    """Returns dict {oid: [person_object, ...]}."""
    config = {'elev': ('elev_%(level)s.txt', Elev, 'person_oid'),
              'ansatt': ('ansatt_%(level)s.txt', Ansatt, 'person_oid'),
              'foresatt': ('foreldre_%(level)s.txt', Foresatt, 'person_oid'),
              }
    fname_format, cls, key_attr = config[ptype]
    fname = os.path.join(DUMPDIR, level, fname_format % {'level': level})
    ret = {}
    for obj in generate_objects(cls, fname):
        if ((obj.skole not in schools) or
            (getattr(obj, 'skolear', dette_skolear) <> dette_skolear)):
            continue
        oid = getattr(obj, key_attr)
        ret.setdefault(oid, []).append(obj)
    return ret

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
        postno, city = p[spec['address3']].split(maxsplit=1)
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

def import_OU(import_spec):
    """Registers or updates information about all schools listed in the
    'schools' dict."""

    ret = {}
    for level, spec in import_spec.items():
        source_system = spec['datakilde']
        # Ingen av disse første tre OUene er vel egentlig "Skoler"...
        top_ou = create_OU(Skole(
            skole='{UFD}', skolenavn='Utdannings- og forskningsdepartementet',
            postadr='0000 Norge'),
                           None,
                           source_system)
        top_ou = create_OU(Skole(skole='{OSLO}', skolenavn='Oslo',
                                 postadr='0000 Norge'),
                           top_ou.entity_id,
                           source_system)
        parent_ou = create_OU(Skole(skole=level,
                                    skolenavn=source_system.description,
                                    postadr='0000 Norge'),
                              top_ou.entity_id,
                              source_system)
        fname = os.path.join(DUMPDIR, level,
                             'skole_sted_%s.txt' % level)
##         spec, dta = read_inputfile("sats/sted_%s.txt" % level)
        for skole in generate_objects(Skole, fname):
            if not (skole.skole in spec['skoler']):
                continue
            sys.stdout.write('.')
            sys.stdout.flush()
            ou = create_OU(skole, parent_ou.entity_id, source_system)
            ret["%s:%s" % (level, skole.skole)] = ou.entity_id
        print
    Cerebrum.commit()
    return ret


def bootstrap_ou(level, src_sys):
    root_ou = write_ou(SkoleRow(
        skole='{UFD}', skolenavn='Utdannings- og forskningsdepartementet',
        postadr='0000 Norge'),
                       None,
                       src_sys)
    top_ou = write_ou(SkoleRow(skole='{OSLO}', skolenavn='Oslo',
                            postadr='0000 Norge'),
                      root_ou,
                      src_sys)
    return write_ou(SkoleRow(skole=level,
                          skolenavn=src_sys.description,
                          postadr='0000 Norge'),
                    top_ou,
                    src_sys)


# skole = ('navn', 'institusjonskode', 'tlf, 'fax', 'adr1', 'adr3')
#   => <Skole object>
#   TODO: Må huske å verifisere at ingen skole.skole er lengre enn 15
#         tegn (under innlesing fra fil?); sjekk også at dette ikke
#         skaper kollisjoner mellom forskjellige skoler.
#
# spec = dict(...)
#   => Not needed, use skole.get_attrs()
#
# parent = entity_id
#
# source_system = <_AuthoritativeSystemCode object>
def write_ou(skole, parent_id, source_system):
    ou = Factory.get('OU')(Cerebrum)
    should_set_parent = True
    try:
        ou.find_by_parent(skole.skole, co.perspective_sats, parent_id)
        should_set_parent = False
    except Errors.NotFoundError:
        pass
    ou.populate(skole.skolenavn,
                acronym=skole.skole,
                short_name=skole.skolenavn[:30],
                display_name=skole.skolenavn,
                sort_name=skole.skolenavn)

    ou.populate_address(source_system)
    ou.populate_contact_info(source_system)
    if not skole.postadr:
        print "Bad info for %s" % skole.skolenavn
        pp.pprint(skole)
    else:
        postno, city = skole.postadr.split()
        ou.populate_address(source_system, co.address_post,
                            address_text=skole.gateadr,
                            postal_number=postno, city=city)
    if skole.tlf:
        ou.populate_contact_info(source_system, co.contact_phone, skole.tlf)
    if skole.fax:
        ou.populate_contact_info(source_system, co.contact_fax, skole.fax)

    op = ou.write_db()
    if should_set_parent:
        ou.set_parent(co.perspective_sats, parent_id)
    if op is None:
        progress.write("-")            # No change
    elif op:
        progress.write("O")            # New OU
    else:
        progress.write("o")            # Updated
    return ou.entity_id

def write_person(rows, skole2ou_id, src_sys):
    person = Factory.get('Person')(Cerebrum)
    oid = multi_getattr_uniq(rows, 'person_oid')
    try:
        person.find_by_external_id(co.externalid_personoid, oid, src_sys)
    except Errors.NotFoundError:
        pass
    gender = multi_getattr_uniq(rows, 'kjonn')
    if gender == 0:
        gender = co.gender_female
    elif gender == 1:
        gender = co.gender_male
    else:
        gender = co.gender_unknown
    fnr = multi_getattr_uniq(rows, 'fnr')
    # TODO: Sjekke at kjønn fra 'fnr' matcher 'gender'.

    # Regn ut fødselsdato fra 'fnr'; dette er ikke 100% pålitelig for
    # midlertidige fødselsnummer.
    try:
        birthdate = fodselsnr.fodt_dato(fnr)
        birthdate = Cerebrum.Date(*birthdate)
    except fodselsnr.InvalidFnrError:
        fnr = birthdate = None
    person.populate(birthdate, gender)
    # Registrer eksterne IDer: Person_OID og fødselsnummer.
    person.populate_external_id(src_sys, co.externalid_personoid, oid)
    if fnr:
        person.populate_external_id(src_sys, co.externalid_fodselsnr, fnr)

    # Personens navn
    fornavn = multi_getattr_uniq(rows, 'fornavn')
    etternavn = multi_getattr_uniq(rows, 'etternavn')
    person.affect_names(src_sys, co.name_first, co.name_last)
    if fornavn:
        person.populate_name(co.name_first, fornavn)
    if etternavn:
        person.populate_name(co.name_last, etternavn)

    # Personens adresse
    poststed = multi_getattr_uniq(rows, 'postadr')
    gateadr = multi_getattr_uniq(rows, 'gateadr')
    person.populate_address(src_sys)
    try:
        postno, city = poststed.split(None, 1)
    except ValueError:
        warn("Bad address for %s" % oid)
    else:
        if postno.isdigit():
            person.populate_address(src_sys, co.address_post,
                                    address_text=gateadr,
                                    postal_number=postno, city=city)
        else:
            warn("Bad address for %s" % oid)

    # Kontakt-info; telefon, fax, mailadresse...
    person.populate_contact_info(src_sys)
    for attr, contact_type in (('tlf', co.contact_phone),
                               ('fax', co.contact_fax),
                               ('email', co.contact_email)):
        val = multi_getattr_uniq(rows, attr)
        if val:
            person.populate_contact_info(src_sys, contact_type, val)

    # Affiliations.
    cls2aff = {ElevRow: (co.affiliation_student,
                         co.affiliation_status_student_valid),
               ForesattRow: (co.affiliation_foresatt,
                             co.affiliation_status_foresatt_valid),
               AnsattRow: (co.affiliation_employee,
                           co.affiliation_status_employee_valid)}
    person.populate_affiliation(src_sys)
    for row in rows:
        ou_id = skole2ou_id[row.skole]
        affiliation, status = cls2aff[type(row)]
        person.populate_affiliation(src_sys, ou_id, affiliation, status)

    # Skriv til database.
    op = person.write_db()
    if op is None:
        progress.write("-")            # No change
    elif op:
        progress.write("P")            # New person
    else:
        progress.write("p")            # Updated

##     person_affils = {}
##     for row in person.get_affiliations():
##         if row.source_system <> src_sys:
##             continue
##         person_affils.setdefault(int(row.ou_id), []).append(row)

##     for row in rows:
##         affils = person_affils.get(ou_id, [])
##         aff = (ou_id, aff, src_sys, stat)
##         try:
##             idx = affils.index(aff)
##         except ValueError:

##         else:
##             del affils[idx]

##         if aff not in [tuple(x) for x in person_affils.get(ou_id, ())]:

##     # TODO: Add affiliations.
    return person.entity_id

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

def usage(exitcode=0):
    print """import_SATS.py [-w | -v] {-i}
    -w : show warnings
    -v : verbose
    -i : run import"""
    sys.exit(exitcode)

def main():
    import getopt

    try:
        opts, args = getopt.getopt(sys.argv[1:], "wvic",
                                   ["warn", "verbose", "import", "convert",
                                    "help"])
    except getopt.GetoptError:
        usage(exitcode=2)
    if len(opts) == 0:
        usage(exitcode=1)
    global show_warnings, verbose
    for o, a in opts:
        if o in ('-w', '--warn'):
            show_warnings = True
        elif o in ('-v', '--verbose'):
            verbose += 1
        elif o in ('-i', '--import'):
            import_all()
##         elif o in ('-c', '--convert'):
##             convert_all()
        elif o == '--help':
            usage()
        else:
            usage(exitcode=1)

if __name__ == '__main__':
    main()


## def filter_attr(iterator, **attrs):
##     """Return a generator that filters objects from ``iterator``.

##     Filtering criteria is specified by calling the generator with
##     keyword arguments.  Each of these keyword arguments corresponds to
##     an attribute with the same name in objects gathered from
##     ``iterator``.

##     For an object to pass through the filter, all values given as
##     keyword arguments must match that object's corresponding attribute
##     values.

##     """
##     for elem in iterator:
##         match = True
##         for k, v in attrs.iteritems():
##             if getattr(elem, k) <> v:
##                 match = False
##         if match:
##             yield elem

## def collect_list(iterator):
##     """Return list of all elements collected from ``iterator``."""
##     return [elem for elem in iterator]

## def collect_dict(iterator, key_attr):
##     """Return elements of ``iterator`` as dict.

##     All elements found in ``iterator`` must have an attribute with the
##     name given by ``key_attr``, and the value of this attribute is
##     used as key when adding the element to the dict.

##     If two (or more) elements' ``key_attr`` attributes have the same
##     value, KeyError is raised.

##     """
##     d = {}
##     for elem in iterator:
##         id = getattr(elem, key_attr)
##         if not d.has_key(id):
##             d[id] = elem
##         else:
## ##             diff = {}
## ##             other = d[id]
## ##             for a in elem.get_attrs():
## ##                 that, this = getattr(other, a), getattr(elem, a)
## ##                 if that <> this:
## ##                     diff[a] = "%r <> %r" % (that, this)
## ##             print "diff: ", diff
##             raise KeyError, \
##                   "elem.%s = '%s', which isn't unique." % (key_attr, id)
##     return d
