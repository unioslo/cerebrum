#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

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

progname = __file__.split("/")[-1]
__doc__="""Usage: %s -p personfile [-h|--help] [-v] [-d|--dryrun] [--logger-name] [--logger-level]

    -h | --help:    Show this
    -p              Which file to read persons from
    -r              Delete affiliations.
    -d | --dryrun   Dryrun. Do not commit changes to database.
    --logger-name   Which logger to use
    --logger-level  Which loglevel to use            
    """ % (progname,)

import re
import os
import sys
import getopt
import mx.DateTime
import datetime
import xml.sax

from Cerebrum.modules.no.uit.PagaDataParser import PagaDataParserClass
import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError


# some globals
TODAY=mx.DateTime.today().strftime("%Y-%m-%d")

db = Factory.get('Database')()
db.cl_init(change_program=progname)
const = Factory.get('Constants')(db)
ou = Factory.get('OU')(db)
new_person = Factory.get('Person')(db)

#init the logger.
logger = Factory.get_logger(cereconf.DEFAULT_LOGGER_TARGET)


# Define default file locations
dumpdir_employees = os.path.join(cereconf.DUMPDIR, "employees")
default_employee_file = 'hitos_employees.xml'


ou_cache = {}
def get_sted(fakultet, institutt, gruppe):
    fakultet, institutt, gruppe = int(fakultet), int(institutt), int(gruppe)
    stedkode = (fakultet, institutt, gruppe)
    
    if not ou_cache.has_key(stedkode):
        ou = Factory.get('OU')(db)
        try:
            ou.find_stedkode(fakultet, institutt, gruppe,
                             institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
            ou_cache[stedkode] = {'id': int(ou.ou_id)}
            ou_cache[int(ou.ou_id)] = ou_cache[stedkode]
        except Errors.NotFoundError:
            logger.error("Bad stedkode: %s" % str(stedkode))
            ou_cache[stedkode] = None
        except EntityExpiredError:
            ou_cache[stedkode] = None
            logger.error("Expired stedkode: %s" % str(stedkode))
            
    return ou_cache[stedkode]

def determine_affiliations(person):
    "Determine affiliations in order of significance"
    ret = {}
    tittel = None
    prosent_tilsetting = -1
    for t in person.get('tils', ()):
        pros = float(t['stillingsandel'])
        if t['tittel'] == 'professor II':
            pros = pros / 5.0
        if prosent_tilsetting < pros:
            prosent_tilsetting = pros
            tittel = t['tittel']
        if t['hovedkategori'] == 'TEKADM':
            aff_stat = const.affiliation_status_ansatt_tekadm
        elif t['hovedkategori'] == 'VIT':
            aff_stat = const.affiliation_status_ansatt_vitenskapelig
        else:
            logger.error("Unknown hovedkat: %s" % t['hovedkategori'])
            continue
            
        fakultet, institutt, gruppe = (t['fakultetnr_utgift'],
                                       t['instituttnr_utgift'],
                                       t['gruppenr_utgift'])
        sted = get_sted(fakultet, institutt, gruppe)
        if sted is None:
            continue
        k = "%s:%s:%s" % (new_person.entity_id,sted['id'],
                          int(const.affiliation_ansatt))
 
        if not ret.has_key(k):
            ret[k] = sted['id'],const.affiliation_ansatt, aff_stat
    
    if tittel:
        new_person.populate_name(const.name_work_title, tittel)

    return ret


def process_person(person):
    fnr = person['fnr']
    gender = person['kjonn']
    fodselsdato = person['fodselsdato']
    year = int(fodselsdato[0:4])
    mon = int(fodselsdato[5:7])
    day = int(fodselsdato[8:10])
    

    if gender == 'M':
        gender = const.gender_male
    else:
        gender = const.gender_female

    # If a FNR is given, do a check of the values presented
    if person.get('fnr',''):
        try:
            fodselsnr.personnr_ok(fnr)
        except:
            logger.error("FNR invalid (%s) for HITOS employee" % (fnr))
            return
    
        gender_chk = const.gender_male
        if(fodselsnr.er_kvinne(fnr)):
            gender_chk = const.gender_female

        if gender_chk != gender:
            logger.error("Gender inconsistent between XML (%s) and FNR (%s) for HITOS employee %s" % (gender, gender_chk, fnr))
            return
    
        (year_chk, mon_chk, day_chk) = fodselsnr.fodt_dato(fnr)

        if year_chk != year:
            logger.error("Year inconsistent between XML (%s) and FNR (%s) for HITOS employee %s" % (year, year_chk, fnr))
            return
        if mon_chk != mon:
            logger.error("Month inconsistent between XML (%s) and FNR (%s) for HITOS employee %s" % (mon, mon_chk, fnr))
            return
        if day_chk != day:
            logger.error("Day inconsistent between XML (%s) and FNR (%s) for HITOS emplyee %s" % (day, day_chk, fnr))
            return
    else:
        logger.error("No FNR given for HITOS employee")
        return


    new_person.clear()

    try:
        new_person.find_by_external_id(const.externalid_fodselsnr, fnr)
    except Errors.NotFoundError:
        pass
    if (person.get('fornavn', ' ').isspace() or person.get('etternavn', ' ').isspace()):
        logger.warn("Ikke noe navn for HITOS employee fnr %s" % fnr)
        return

    new_person.populate(mx.DateTime.Date(year, mon, day), gender)
    new_person.affect_names(const.system_hitos, const.name_first, const.name_last, const.name_personal_title)
    new_person.affect_external_id(const.system_hitos, const.externalid_fodselsnr)
    new_person.populate_name(const.name_first, person['fornavn'])
    new_person.populate_name(const.name_last, person['etternavn'])
    if person.get('tittel_personlig',''):
        new_person.populate_name(const.name_personal_title, person['tittel_personlig'])
    new_person.populate_external_id(const.system_hitos, const.externalid_fodselsnr, fnr)

    # If it's a new person, we need to call write_db() to have an entity_id
    # assigned to it.
    op = new_person.write_db()

    # work_title is set by determine_affiliations
    new_person.affect_names(const.system_hitos, const.name_work_title)
    affiliations = determine_affiliations(person)
    print affiliations
    new_person.populate_affiliation(const.system_hitos)

    for k,v in affiliations.items():
        ou_id, aff, aff_stat = v
        new_person.populate_affiliation(const.system_hitos, ou_id, int(aff), int(aff_stat))
        if include_del:
            if cere_list.has_key(k):
                cere_list[k] = False
    op2 = new_person.write_db()

    # UIT: Update last_date field
    # must be done after write_db() to ensure that affiliation table entry exist
    # in database
    for k,v in affiliations.items():
        ou_id, aff, aff_stat = v
        new_person.set_affiliation_last_date(const.system_hitos, ou_id, int(aff), int(aff_stat))

    if op is None and op2 is None:
        logger.info("**** EQUAL ****")
    elif op == True:
        logger.info("**** NEW ****")
    else:
        logger.info("**** UPDATE  (%s:%s) ****" % (op,op2))

def usage(exitcode=0,msg=None):
    if msg:
        print msg
        
    print __doc__
    sys.exit(exitcode)


def load_all_affi_entry():
    affi_list = {}
    for row in new_person.list_affiliations(source_system=const.system_hitos):
        key_l = "%s:%s:%s" % (row['person_id'],row['ou_id'],row['affiliation'])
        affi_list[key_l] = True
    return(affi_list)


def clean_affi_s_list():
    for k,v in cere_list.items():
        logger.info("clean_affi_s_list: k=%s,v=%s" % (k,v))
        if v:
            [ent_id,ou,affi] = [int(x) for x in k.split(':')]
            new_person.clear()
            new_person.entity_id = int(ent_id)
            affs=new_person.list_affiliations(ent_id,affiliation=affi,ou_id=ou,source_system=const.system_hitos)
            for aff in affs:
                last_date = datetime.datetime.fromtimestamp(aff['last_date'])
                end_grace_period = last_date +\
                    datetime.timedelta(days=cereconf.GRACEPERIOD_EMPLOYEE)
                if datetime.datetime.today() > end_grace_period:
                    logger.warn("Deleting system_hitos affiliation for " \
                    "person_id=%s,ou=%s,affi=%s last_date=%s,grace=%s" % \
                        (ent_id,ou,affi,last_date,cereconf.GRACEPERIOD_EMPLOYEE))
                    new_person.delete_affiliation(ou, affi, const.system_hitos)


def main():
    global cere_list, include_del

    logger.info("Starting %s" % (progname,))
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'p:drh',
                                   ['person-file=',
                                    'include_delete',
                                    'dryrun','help'])
    except getopt.GetoptError,m:
        usage(1,m)

    personfile = os.path.join(dumpdir_employees, default_employee_file)
    include_del = False
    dryrun = False
    
    for opt, val in opts:
        if opt in ('-p', '--person-file'):
            personfile = val
        elif opt in ('-r', '--include_delete'):
            include_del = True
        elif opt in ('-h', '--help'):
            usage()
        elif opt in ('-d','--dryrun'):
            dryrun = True

    if include_del:
        cere_list = load_all_affi_entry()

    if personfile is not None:
        PagaDataParserClass(personfile, process_person)

    if include_del:
        clean_affi_s_list()

    if dryrun:
        db.rollback()
        logger.info("All changes rolled back")
    else:
        db.commit()
        logger.info("Committed all changes")

if __name__ == '__main__':
    main()


