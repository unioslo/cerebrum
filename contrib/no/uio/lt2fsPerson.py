#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-


import getopt
import sys
import time
import cerebrum_path

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.modules.no import fodselsnr

"""
==================================
Overføring av data fra LT til FS
==================================

Data som overføres
===========================

Personer
--------

FS.PERSON

  For alle personer som ligger i LT med minst en aktiv tilsetting
  eller minst en aktiv gjest registrering skal man sette inn en linje
  i FS.person for denne personen med:
    - Fodselsdato
    - personnr
    - Fornavn
    - Etternavn
    - emailadresser
    - kjønn
    - dato_fodt

  medmindre personen er kjent i FS fra før.  Ingen update eller
  delete, kun insert.

  *MERK*: Dette gjelder ikke de personer som i LT er utstyrt med
          midlertidige fødselsnummer der har '9' som første siffer i
          personnummer delen.
  

FS.FAGPERSON

  Alle personer i LT med minst en aktiv tilsetting i kategegorien
  vitenskaplig eller med minst en aktiv gjest registrering med
  gjestetypekode 'GRP-LÆRER' skal man sette inn en linje i
  FS.FAGPERSON for denne personen:

    - Fodselsdato
    - personnr
    - Institusjonsnr_Ansatt (*1)
    - Faknr_Ansatt (*1)
    - Instituttnr_Ansatt (*1)
    - Gruppenr_Ansatt (*1)
    - Telefonnr_Arbeide
    - Telefonnr_Fax_Arb
    - Status_aktiv
    - Stillingstittel_Norsk

  (*1) sted for primære ansatt affiliation Primær i denne sammenheng
       utledes ved å:

         - finn høyest prioriterte ou_id i account_type som primært
           har aff_status=vitenskapelig, sekundært en vilkårlig annen
           ansatt affiliation.

         - dersom personen ikke har noen account_type m/ansatt
           affiliation, velges laveste ou_id der personen primært har
           aff_status=vitenskapelig, sekundært en vilkårlig annen
           ansatt affiliation.

         - dersom sted ikke finnes i FS brukes overordnet sted fra LT
           i stede.  Dette gjøres rekursivt inntil et sted som er
           kjent i FS finnes.

  Der skal kun gjøres update på telefon og fax.

  Det foretas ingen sletting fra fs.fagperson.

Spesielle merknader
--------------------
  Dersom personen i følge Cerebrum finnes i FS og LT, men har
  forskjellig fødselsnummer, skal logges en feilmelding.  Ingen data
  skal endres for slike personen.

"""

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
logger = Factory.get_logger("cronjob")

ou_id2stedkode = {}
ou_id2parent_id = {}

def get_fs_stedkoder():
    """Returnere en mapping fra ou_id til data om stedet fra FS. """

    stedkode2ou_id = {}
    ou = Factory.get('OU')(db)
    for row in ou.get_stedkoder():
        stedkode = tuple([int(row[c]) for c in (
            'institusjon', 'fakultet', 'institutt', 'avdeling')])
        stedkode2ou_id[stedkode] = long(row['ou_id'])
        ou_id2stedkode[long(row['ou_id'])] = stedkode

    sted_info = {}
    for row in fs.info.list_ou(institusjonsnr=185):
        stedkode = tuple([int(row[c]) for c in (
            'institusjonsnr', 'faknr', 'instituttnr', 'gruppenr')])
        if not stedkode2ou_id.has_key(stedkode):
            logger.warn("Ukjent sted: %s" % repr(stedkode))
            continue
        sted_info[stedkode2ou_id[stedkode]] = row
    return sted_info

def get_termin():
    t = time.localtime()[0:2]
    if t[1] <= 6:
        return t[0], 'VÅR'
    return t[0], 'HØST'

class SimplePerson(object):
    def __init__(self):
        self.affiliations = []
        self.account_priority = []
        self.name_first = None
        self.name_last = None
        self.work_title = None
        self.fnr11 = None   # 11 sifret fødselsnr
        self.fnr = None     # dato del av fødselsnr
        self.pnr = None     # personnummer del av fødselsnr
        self.email = None
        self.birth_date = None
        self.gender = None
        self.phone = None
        self.fax = None
        self.fnr_mismatch = None

    def should_reg_fagperson(self):
        for aff in self.affiliations:
            if aff['status'] in (int(co.affiliation_status_ansatt_vit),
                                 int(co.affiliation_tilknyttet_grlaerer)):
                return True
        return False

    def get_primary_sted(self):
        # Beregn primær-affiliation m/prioritet på
        # affiliation_status_ansatt_vit
        self.account_priority.sort(
            lambda x, y: cmp(x['priority'], y['priority']))
        # Primær-konto m/status=ansatt_vitenskapelig
        for row in self.account_priority:
            for aff in self.affiliations:
                if (aff['ou_id'] == row['ou_id'] and
                    aff['affiliation'] == row['affiliation'] and
                    aff['status'] == int(co.affiliation_status_ansatt_vit)):
                    return int(aff['ou_id'])
        # Annen primær-konto m/ansatt affiliation 
        if self.account_priority:
            return int(self.account_priority[0]['ou_id'])

        # laveste ou_id m/status=ansatt_vitenskapelig
        self.affiliations.sort(
            lambda x, y: cmp(x['ou_id'], y['ou_id']))
        for aff in self.affiliations:
            if aff['status'] == int(co.affiliation_status_ansatt_vit):
                return int(aff['ou_id'])
        # laveste ou_id
        return int(self.affiliations[0]['ou_id'])

    def __str__(self):
        return ("affs=%s, pri=%s, name_first=%s, name_last=%s, work_title=%s, "
                "fnr11=%s, fnr=%s, pnr=%s, email=%s, bdate=%s, gender=%s, "
                "phone=%s, fax=%s" % (
            ["%s/%s@%s" % (row['affiliation'], row['status'], row['ou_id'])
             for row in self.affiliations],
            ["%s, %s, %s" % (row['priority'], row['affiliation'], row['ou_id']
                             ) for row in self.account_priority],
            self.name_first, self.name_last, self.work_title,
            self.fnr11, self.fnr, self.pnr, self.email,
            self.birth_date, self.gender, self.phone, self.fax))

def prefetch_person_info():
    ac = Factory.get('Account')(db)
    logger.debug("Prefetch affiliations...")
    pid2person = {}
    # Finn alle personenes ansatt-affiliations
    for row in person.list_affiliations(
        source_system=co.system_lt,
        affiliation=(co.affiliation_ansatt, co.affiliation_tilknyttet)):
        if (int(row['affiliation']) == int(co.affiliation_ansatt) or
            int(row['status']) == int(co.affiliation_tilknyttet_grlaerer)):
            sp = pid2person.setdefault(long(row['person_id']), SimplePerson())
            sp.affiliations.append(row)

    logger.debug("Prefetch account_type (priority)...")
    for row in ac.list_accounts_by_type(affiliation=co.affiliation_ansatt):
        sp = pid2person.get(long(row['person_id']), None)
        if sp:
            sp.account_priority.append(row)

    logger.debug("Prefetch names...")
    # Finn autoritativt navn og tittel på personene
    for name_type, attr_name in ((co.name_first, 'name_first'),
                                 (co.name_last, 'name_last'),
                                 (co.name_work_title, 'work_title')):
        for row in person.list_persons_name(source_system=co.system_lt,
                                            name_type=name_type):
            sp = pid2person.get(long(row['person_id']), None)
            if sp:
                setattr(sp, attr_name, row['name'])

    logger.debug("Prefetch fødselsnummer...")
    # Finn alle personenes fødselsnummer
    for row in person.list_external_ids(source_system=co.system_lt,
                                        id_type=co.externalid_fodselsnr):
        sp = pid2person.get(long(row['person_id']), None)
        if not sp:
            continue
        sp.fnr11 = row['external_id']
        sp.fnr, sp.pnr = fodselsnr.del_fnr(sp.fnr11)
        sp.birth_date = fodselsnr.fodt_dato(sp.fnr11)
        sp.gender = fodselsnr.er_mann(sp.fnr11) and 'M' or 'K'
    for row in person.list_external_ids(source_system=co.system_fs,
                                        id_type=co.externalid_fodselsnr):
        sp = pid2person.get(long(row['person_id']), None)
        if sp:
            if row['external_id'] != sp.fnr11:
                sp.fnr_mismatch = "FS:%s LT:%s" % (row['external_id'], sp.fnr11)

    logger.debug("Prefetch contact info...")
    # Finn telefon-nr og fax-nr på personene
    for name_type, attr_name in ((co.contact_phone, 'phone'),
                                 (co.contact_fax, 'fax')):
        for row in person.list_contact_info(source_system=co.system_lt,
                                            contact_type=name_type):
            sp = pid2person.get(long(row['entity_id']), None)
            if sp:
                if len(row['contact_value']) > 8:
                    logger.warn("Ignoring too long contact: %s for %s" % (
                        sp.fnr11, row['contact_value']))
                    continue
                setattr(sp, attr_name, row['contact_value'])

    logger.debug("Prefetch mail address...")
    # Finn alle personenes primære e-post adresse
    for pid, email in person.list_primary_email_address(co.entity_person):
        sp = pid2person.get(long(pid), None)
        if sp:
            sp.email = email

    logger.debug("Prefetch completed")
    return pid2person

def process_person(pdata):
    status = 'J'
    status_publ = 'N'

    logger.debug("Process %s" % pdata.fnr11)
    logger.debug2("pdata=%s" % pdata)
    if not fs.person.get_person(pdata.fnr, pdata.pnr):
        logger.debug("...add person")
        fs.person.add_person(pdata.fnr, pdata.pnr, pdata.name_first,
                             pdata.name_last, pdata.email, pdata.gender,
                             "%4i-%02i-%02i" % pdata.birth_date)

    if not pdata.should_reg_fagperson():
        return

    # Fra sted: $adr1, $adr2, $postnr, $adr3, $arbsted, $instinr,
    #           $fak, $inst, $gruppe
    # Fra uio_info: $tlf, $title, $fax
    # Statisk: $status

    ou_id = pdata.get_primary_sted()
    while ou_id is not None and not fs_stedinfo.has_key(ou_id):
        logger.debug("%s ukjent i FS, sjekk parent-ou" % ou_id)
        ou_id = ou_id2parent_id[ou_id]

    if ou_id is None:
        logger.warn("Sted %s (%s) er ukjent i FS" % (ou_id, ou_id2stedkode[ou_id]))
        return
    new_data = [None, None, None, None, None]  # SFA didn't want address
    new_data.extend([fs_stedinfo[ou_id][c] for c in (
        'institusjonsnr', 'faknr', 'instituttnr', 'gruppenr')])
    new_data.extend([pdata.phone, pdata.work_title, pdata.fax, status])

    fagperson = fs.person.get_fagperson(pdata.fnr, pdata.pnr)
    logger.debug2("... er fp?: %s" % fagperson)
    if not fagperson:
        logger.debug("...add fagperson (%s)" % (repr((pdata.fnr11, pdata.fnr, pdata.pnr, new_data))))
        fs.person.add_fagperson(pdata.fnr, pdata.pnr, *new_data)
    else:
        # Only update fax/tlf columns
        fs_data = [str(fagperson[0][c]) for c in (
            'telefonnr_arbeide', 'telefonnr_fax_arb')]
        new_data = (new_data[-4], new_data[-2])
        if [str(t) for t in new_data] != fs_data:
            logger.debug("...update fagperson")
            fs.person.update_fagperson(pdata.fnr, pdata.pnr, tlf=new_data[0],
                                       fax=new_data[1])

def update_from_lt():
    global fs_stedinfo, arstall, termin
    
    fs_stedinfo = get_fs_stedkoder()
    arstall, termin = get_termin()

    ou = Factory.get("OU")(db)
    for row in ou.get_structure_mappings(co.perspective_lt):
        parent_id = None
        if row['parent_id'] is not None and (
            int(row['parent_id']) != int(row['ou_id'])):
            parent_id = int(row['parent_id'])
        ou_id2parent_id[ int(row['ou_id']) ] = parent_id

    for person_id, pdata in prefetch_person_info().items():
        if pdata.fnr_mismatch:
            logger.warn("Fnr-mismatch, skipping: %s" % pdata.fnr_mismatch)
            continue
        if pdata.pnr >= 90000:
            continue  # Midlertidig fødselsnummer uønsket
        try:
            process_person(pdata)
            fs.db.commit()
        except fs.db.DatabaseError, msg:
            logger.warn("Error processing %s: %s" % (pdata, msg))
            fs.db.rollback()
        
def main():
    global fs
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['help', 'db-service=',
                                                      'db-user=', 'dryrun'])
    except getopt.GetoptError, msg:
        print "GetoptError: %s" % msg
        usage(1)

    database = "FSDEMO.uio.no"
    user = "ureg2000"
    dryrun = False
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--db-user',):
            user = val
        elif opt in ('--db-service',):
            database = val
        elif opt in ('--dryrun',):
            dryrun = True
    if not opts:  # enforce atleast one argument to avoid accidential runs
        usage(1)

    fs = FS(user=user, database=database)
    if dryrun:
        fs.db.commit = fs.db.rollback
    update_from_lt()

def usage(exitcode=0):
    print """Usage: lt2fsPerson [opsjoner]
    --db-user name: connect with given database username (FS)
    --db-service name: connect to given database (FS)
    --dryrun : rollback changes to db
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

# arch-tag: c1c0ba3f-c8cb-44cf-99f0-1ff191793464
