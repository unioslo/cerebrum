#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-


import getopt
import sys
import time
import cerebrum_path

from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.modules.no.uio.access_LT import LT
from Cerebrum.modules.no import fodselsnr

"""
==================================
Overføring av data fra FS til LT
==================================

Basert på 'LT-03-020 Gjest til Frida.doc'

Data som overføres
===========================

Aktuelle personer
-------------------

* doktorgrads-studenter: Alle ekstern finansierte
  doktorgrads-studenter som ligger i FS skal overføres (LT er
  autoritativ for stipendiater som har UiO som arbeidsgiver, og slike
  personer skal det således ikke overføres informasjon om).

Spørsmål:
  * ingen øvrige personer er av interesse? Fagperson?

Fra FS
-------
  Vi er interessert i følgende data om personene:

  * Fødselsnummer
  * Navn
  * Stedkoden(e) til dogtorgrads-studieprogramme(t/ne) der personen
    har opptak
  * tidsrom for studieretten
  * 1 adresse: primært fs.student.*_semadr, sekundært
    fs.person.*_hjemsted

  Student.list_drgrad returnerer de personer vi ønsker å overføre.
  Aktuelle kolonner:

   - dato_studierett_tildelt
   - dato_studierett_gyldig_til
   - institusjonsnr, faknr, instituttnr, gruppenr (fra *_studieansv)

Spørsmål:
  * skal fs.person.status_reserv_nettpubl benyttes til noe?
  * telefon, f.eks fs.person.telefonnr_hjemsted?
  * det må verifiseres at Student.list_drgrad ikke returnerer flere
    personer enn vi er interessert i.


Til LT
--------
  Kolonner ikke beskrevet her skal ha sine default-verdier fra
  databaseskjemaet, normalt NULL.

  LT.PERSON:
    - fodtdag, fodtmnd, fodtar, personnr
    - navn: fulltnavn på formen 'etternavn fornavn'
    - pentretypkode: 'JA'
    - opprettemerke_ka_oppforing: NULL
   
    Spørsmål:
      - *_privatadresse: fra FS
      - telefonnr_privattelefon: fra FS?
      - tittel: brukes ikke?  Kun fagpersoner har i FS?

  LT.GJEST:
    - fodtdag, fodtmnd, fodtar, personnr
    - dato_fra: FS: dato_studierett_tildelt
    - dato_til: FS: dato_studierett_gyldig_til eller 3000-01-01 hvis
      NULL i FS.
    - fakultetnr/instituttnr/gruppenr: fra studieprogram
    - gjestetypekode: 'EF-STIP'

    Spørsmål:
      - gjesteanskode: er NOT NULL.  Skal 'USPES' brukes?

  LT.ARBSTEDTELEFON:
    - fodtdag, fodtmnd, fodtar, personnr
    Spørsmål:
      - skal denne benyttes?

  LT.PERSKOMM:
    - fodtdag, fodtmnd, fodtar, personnr
    Spørsmål:
      - Skal den benyttes? LT-03-020 antyder at et telefonnummer og
        e-mail adresse skal lagres her.

  LT.RESERVASJON:
    - fodtdag, fodtmnd, fodtar, personnr
    - katalogkode: ELKAT
    - felttypekode: TOTAL
    - resnivakode: TOTAL

Oppdatering/Sletting
---------------------
  Det gjøres ingen oppdatering/sletting av eksisterende data utover
  det som er beskrevet i denne seksjonen.

  * LT.GJEST: dato_fra/dato_til oppdateres fortløpende

Spesielle merknader
--------------------
  Dersom personen i følge Cerebrum finnes i FS og LT, men har
  forskjellig fødselsnummer, skal logges en feilmelding og personen
  ignoreres.

"""

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
logger = Factory.get_logger("cronjob")

def _conv_date(d):
    if type(d) == lt.db._db_mod.dco2.OracleDateType:
        return time.strftime('%Y-%m-%d', time.localtime(long(d)))
    elif isinstance(d, str):
        if len(d) == 8:
            return '%s-%s-%s' % (d[0:4], d[4:6], d[6:8])
        logger.warn("wierd date format: %s" % (d))
    elif d:
        logger.warn("wierd date format: %s (type: %s)" % (d, type(d)))
    return None

def prefetch_person_info():
    drgrad = {}
    for row in fs.student.list_drgrad():
        key = (int(row['fodselsdato']), int(row['personnr']))
        if not drgrad.has_key(key):
            drgrad[key] = {}
        sted = (int(row['faknr']),
                int(row['instituttnr']),
                int(row['gruppenr']))
        drgrad[key][sted] = (_conv_date(row['dato_studierett_tildelt']),
                             _conv_date(row['dato_studierett_gyldig_til']))
    logger.debug("Found %i drgrad" % len(drgrad))

    # LT
    lt_persons = {}
    for row in lt.GetAllPersons():
        fdato = (int("%i%02i%02i" % (row['fodtdag'], row['fodtmnd'],
                                     row['fodtar'])))
        lt_persons[(fdato, int(row['personnr']))] = {}

    logger.debug("Found %i lt persons" % len(lt_persons))
    # lt gjester
    for row in lt.GetGjester():
        if row['gjestetypekode'] == 'EF-STIP':
            fdato = (int("%i%02i%02i" % (row['fodtdag'], row['fodtmnd'],
                                         row['fodtar'])))
            sted = (int(row['fakultetnr']),
                    int(row['instituttnr']),
                    int(row['gruppenr']))
            key = (fdato, int(row['personnr']))
            if not lt_persons.has_key(key):
                lt_persons[key] = {}
            lt_persons[key][sted] = (_conv_date(row['dato_fra']),
                                     _conv_date(row['dato_til']))
    return drgrad, lt_persons

def update_lt():
    fs_drgrad, lt_persons = prefetch_person_info()
    for fnr2, fs_pdta in fs_drgrad.items():
        if not lt_persons.has_key(fnr2):
            logger.debug("Add %s to LT.PERSON" % repr(fnr2))
            lt_persons[fnr2] = {}
        for sted, date_span in fs_pdta.items():
            lt_span = lt_persons[fnr2].get(sted, None)
            if lt_span:
                if date_span != lt_span:
                    logger.debug("Update %s@%s (%s != %s)" % (
                        repr(fnr2), repr(sted), repr(date_span), repr(lt_span)))
            else:
                logger.debug("Add lt.gjest: %s@%s %s" % (
                    repr(fnr2), repr(sted), repr(date_span)))
        
def main():
    global fs, lt
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', [
            'help', 'fs-db-service=', 'fs-db-user=', 'lt-db-service=',
            'lt-db-user=','dryrun'])        
    except getopt.GetoptError, msg:
        print "GetoptError: %s" % msg
        usage(1)

    fs_database = "FSDEMO.uio.no"
    fs_user = "ureg2000"
    lt_database = "LTTEST.uio.no"
    lt_user = "ureg2000"
    dryrun = False
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--fs-db-user',):
            fs_user = val
        elif opt in ('--fs-db-service',):
            fs_database = val
        elif opt in ('--lt-db-user',):
            lt_user = val
        elif opt in ('--lt-db-service',):
            lt_database = val
        elif opt in ('--dryrun',):
            dryrun = True
    if not opts:  # enforce atleast one argument to avoid accidential runs
        usage(1)

    fs = FS(user=fs_user, database=fs_database)
    lt_db = Database.connect(user=lt_user, service=lt_database,
                             DB_driver='Oracle')
    lt = LT(lt_db)
    if dryrun:
        fs.db.commit = fs.db.rollback
    update_lt()

def usage(exitcode=0):
    print """Usage: lt2fsPerson [opsjoner]
    --fs-db-user name: connect with given database username (FS)
    --fs-db-service name: connect to given database (FS)
    --lt-db-user name: connect with given database username (LT)
    --lt-db-service name: connect to given database (LT)
    --dryrun : rollback changes to db
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

# arch-tag: ec59cbc9-0877-4c55-8e3e-597e7a7785f4
