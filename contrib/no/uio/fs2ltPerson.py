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

Data som overføres
===========================

Personer
--------

Alle doktorgrads-studenter som ligger i FS skal overføres.

Personen skal kun registreres i LT.PERSON dersom vedkommende ikke
finnes der fra før.  Det gjøres ingen oppdatering/sletting.  Personen
registreres også i LT.GJEST med gjestetypekode EF-STIP.

Fra FS:
  Student.list_drgrad returnerer relevante personer.  Aktuelle kolonner:
   - dato_studierett_tildelt
   - dato_studierett_gyldig_til
   - institusjonsnr, faknr, instituttnr, gruppenr

Til LT:
  LT.PERSON:

   - fodtdag, fodtmnd, fodtar, personnr
   - navn : fulltnavn 'etternavn fornavn'
   - pentretypkode : ??
   

  LT.GJEST:
   - DATO_FRA
   - DATO_TIL
   - FAKULTETNR/INSTITUTTNR/GRUPPENR
  
TBD: Oppdatering/sletting i lt.gjest?  Hva med øvrige tabeller?


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

def _conv_date(d):
    if type(d) == lt.db._db_mod.dco2.OracleDateType:
        return time.strftime('%Y-%m-%d', time.localtime(long(d)))
    elif type(d) == 'str':
        if len(d) == 8:
            return '%s-%s-%s' % (d[0:4], d[4:6], d[6:8])
        logger.warn("wierd date format: %s" % (d))
    elif d:
        logger.warn("wierd date format: %s" % (d))
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
