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
Overf�ring av data fra LT til FS
==================================

Data som overf�res
===========================

Personer
  For alle personer registrert i LT skal man overf�re f�dselsnr,
  fornavn, etternavn, email, kj�nn og f�dselsdato medmindre personen
  er kjent i FS fra f�r (i.e. eksisterende data oppdateres ikke).
  Dataene registreres i fs.person.

Personer med tilsettning av typen vitenskapelig ansatt
  Alle personer registrert i LT som vitenskapelig ansatt skal
  registreres i FS i tabellen fs.fagperson.  Dersom personen er kjent
  fra f�r, skal informasjonen evt. oppdateres.  F�lgende data overf�res:

  * Hent stedet der personen har sin prim�re (*1) ansatt affiliation.
    Bruk denne stedkoden til � hente f�lgende opplysninger fra
    fs.sted: adr1 (adrlin1), adr2 (adrlin2), postnr (postnr), adr3
    (adrlin3), instinr (institusjonsnr), fak (faknr), inst
    (instituttnr), gruppe (gruppenr), arbsted (fra hvor?)
    
  * tlf (cerebrum: contact_phone), title (cerebrum: name_work_title),
    fax (cerebrum: contact_fax), status (statisk='J')

  (*1) Prim�r i denne sammenheng utledes ved �:

    - finn h�yest prioriterte ou_id i account_type som prim�rt har
      aff_status=vitenskapelig, sekund�rt en vilk�rlig annen ansatt
      affiliation.

    - dersom personen ikke har noen account_type m/ansatt affiliation,
      velges laveste ou_id der personen prim�rt har
      aff_status=vitenskapelig, sekund�rt en vilk�rlig annen
      ansatt affiliation.

  Det foretas ingen sletting fra fs.fagperson.

fs.fagpersonundsemester

  For alle vitenskapelig ansatte populerer man i tillegg tabellen
  fs.fagpersonundsemester med dataene:

  * fnr, instinr, fak, inst, gruppe (samme stedkode som over)
  * status, status_publ (begge statisk=J)
  * termin, arstall (V�R/H�ST, �rstall m/4 siffer)

  Det foretas kun innlegging av data i denne tabellen ettersom
  tabellens prim�rn�kkel spenner over alle kolonnene nevnt over med
  untak av status kolonnene.

Spesielle merknader
--------------------
  Dersom personen i f�lge Cerebrum finnes i FS og LT, men har
  forskjellig f�dselsnummer, skal logges en feilmelding.  Ingen data
  skal endres for personen.

"""

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
logger = Factory.get_logger("cronjob")


def get_fs_stedkoder():
    """Returnere en mapping fra ou_id til data om stedet fra FS. """

    stedkode2ou_id = {}
    ou = Factory.get('OU')(db)
    for row in ou.get_stedkoder():
        stedkode = tuple([int(row[c]) for c in (
            'institusjon', 'fakultet', 'institutt', 'avdeling')])
        stedkode2ou_id[stedkode] = long(row['ou_id'])

    sted_info = {}
    for row in fs.GetAlleOUer(institusjonsnr=185)[1]:
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
        return t[0], 'V�R'
    return t[0], 'H�ST'

class SimplePerson(object):
    def __init__(self):
        self.affiliations = []
        self.account_priority = []
        self.name_first = None
        self.name_last = None
        self.work_title = None
        self.fnr11 = None   # 11 sifret f�dselsnr
        self.fnr = None     # dato del av f�dselsnr
        self.pnr = None     # personnummer del av f�dselsnr
        self.email = None
        self.birth_date = None
        self.gender = None
        self.phone = None
        self.fax = None
        self.fnr_mismatch = None

    def is_vitenskapelig_ansatt(self):
        for aff in self.affiliations:
            if aff['status'] == int(co.affiliation_status_ansatt_vit):
                return True
        return False

    def get_primary_sted(self):
        # Beregn prim�r-affiliation m/prioritet p�
        # affiliation_status_ansatt_vit
        self.account_priority.sort(
            lambda x, y: cmp(x['priority'], y['priority']))
        # Prim�r-konto m/status=ansatt_vitenskapelig
        for row in self.account_priority:
            for aff in self.affiliations:
                if (aff['ou_id'] == row['ou_id'] and
                    aff['affiliation'] == row['affiliation'] and
                    aff['status'] == int(co.affiliation_status_ansatt_vit)):
                    return int(aff['ou_id'])
        # Annen prim�r-konto m/ansatt affiliation 
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
    for row in person.list_affiliations(source_system=co.system_lt,
                                        affiliation=co.affiliation_ansatt):
        sp = pid2person.setdefault(long(row['person_id']), SimplePerson())
        sp.affiliations.append(row)

    logger.debug("Prefetch account_type (priority)...")
    for row in ac.list_accounts_by_type(affiliation=co.affiliation_ansatt):
        sp = pid2person.get(long(row['person_id']), None)
        if sp:
            sp.account_priority.append(row)

    logger.debug("Prefetch names...")
    # Finn autoritativt navn og tittel p� personene
    for name_type, attr_name in ((co.name_first, 'name_first'),
                                 (co.name_last, 'name_last'),
                                 (co.name_work_title, 'work_title')):
        for row in person.list_persons_name(source_system=co.system_lt,
                                            name_type=name_type):
            sp = pid2person.get(long(row['person_id']), None)
            if sp:
                setattr(sp, attr_name, row['name'])

    logger.debug("Prefetch f�dselsnummer...")
    # Finn alle personenes f�dselsnummer
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
    # Finn telefon-nr og fax-nr p� personene
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
    # Finn alle personenes prim�re e-post adresse
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
    if not fs.get_person(pdata.fnr, pdata.pnr):
        logger.debug("...add person")
        fs.add_person(pdata.fnr, pdata.pnr, pdata.name_first,
                      pdata.name_last, pdata.email, pdata.gender,
                      "%4i-%02i-%02i" % pdata.birth_date)
        fs.db.commit()

    if not pdata.is_vitenskapelig_ansatt():
        return

    # Fra sted: $adr1, $adr2, $postnr, $adr3, $arbsted, $instinr,
    #           $fak, $inst, $gruppe
    # Fra uio_info: $tlf, $title, $fax
    # Statisk: $status

    stedkode = pdata.get_primary_sted()
    if not fs_stedinfo.has_key(stedkode):
        logger.warn("Sted %s er ukjent i FS" % stedkode)
        return
    new_data = [fs_stedinfo[stedkode][c] for c in (
        'adrlin1', 'adrlin2', 'postnr', 'adrlin3', 'stedkortnavn',
        'institusjonsnr', 'faknr', 'instituttnr', 'gruppenr')]
    new_data.extend([pdata.phone, pdata.work_title, pdata.fax, status])

    fagperson = fs.get_fagperson(pdata.fnr, pdata.pnr)
    logger.debug2("... er fp?: %s" % fagperson)
    if not fagperson:
        print "Add", pdata.fnr11, pdata.fnr
        logger.debug("...add fagperson (%s)" % (repr((pdata.fnr11, pdata.fnr, pdata.pnr, new_data))))
        fs.add_fagperson(pdata.fnr, pdata.pnr, *new_data)
        fs.db.commit()
    else:
        # Note:  column-order must be same as for new_data
        fs_data = [str(fagperson[0][c]) for c in (
            'adrlin1_arbeide', 'adrlin2_arbeide', 'postnr_arbeide',
            'adrlin3_arbeide', 'arbeidssted', 'institusjonsnr_ansatt',
            'faknr_ansatt', 'instituttnr_ansatt', 'gruppenr_ansatt',

            'telefonnr_arbeide', 'stillingstittel_norsk',
            'telefonnr_fax_arb', 'status_aktiv'
            )]
        if [str(t) for t in new_data] != fs_data:
            logger.debug("...update fagperson")
            fs.update_fagperson(pdata.fnr, pdata.pnr, *new_data)
            fs.db.commit()

    # $termin, $arstall, $instinr, $fak, $inst, $gruppe, $status,
    # $status_publ

    new_data = [fs_stedinfo[stedkode][c] for c in (
        'institusjonsnr', 'faknr', 'instituttnr', 'gruppenr')]
    new_data.extend([termin, arstall, status, status_publ])

    fagpersonundsem = fs.get_fagpersonundsem(
        pdata.fnr, pdata.pnr, *new_data[0:6])
    logger.debug2("... undsem?: %s -> %s" % (fagpersonundsem, repr((new_data))))
    if not fagpersonundsem:
        logger.debug("...add fagpersonundsem")
        fs.add_fagpersonundsem(pdata.fnr, pdata.pnr, *new_data)
        fs.db.commit()
    else:
        # Oppdatering ikke n�dvendig
        pass

def update_lt():
    global fs_stedinfo, arstall, termin
    
    fs_stedinfo = get_fs_stedkoder()
    arstall, termin = get_termin()
    for person_id, pdata in prefetch_person_info().items():
        if pdata.fnr_mismatch:
            logger.warn("Fnr-mismatch, skipping: %s" % pdata.fnr_mismatch)
            continue
        try:
            process_person(pdata)
        except fs.db.DatabaseError, msg:
            logger.warn("Error processing %s: %s" % (pdata, msg))
            fs.db.rollback()
        
def main():
    global fs
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['help', 'db-service='])
    except getopt.GetoptError:
        usage(1)

    database = "FSDEMO.uio.no"
    user = "ureg2000"
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--db-user',):
            user = val
        elif opt in ('--db-service',):
            database = val
    if not opts:
        usage(1)

    fs = FS(user=user, database=database)
    update_lt()

def usage(exitcode=0):
    print """Usage: lt2fsPerson [opsjoner]
    --db-user name: connect with given database username (FS)
    --db-service name: connect to given database (FS)
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

# arch-tag: c1c0ba3f-c8cb-44cf-99f0-1ff191793464
