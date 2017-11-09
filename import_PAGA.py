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

import cerebrum_path
import cereconf
from Cerebrum.modules.no.uit.PagaDataParser import PagaDataParserClass
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
default_employee_file = 'paga_persons_%s.xml' % (TODAY)

def conv_name(fullname):
    fullname = fullname.strip()
    return fullname.split(None, 1)

ou_cache = {}
def get_sted(fakultet, institutt, gruppe):
    fakultet, institutt, gruppe = int(fakultet), int(institutt), int(gruppe)
    stedkode = (fakultet, institutt, gruppe)
    
    if not ou_cache.has_key(stedkode):
        ou = Factory.get('OU')(db)
        try:
            ou.find_stedkode(fakultet, institutt, gruppe,
                             institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
            addr_street = ou.get_entity_address(source=const.system_paga,
                                                type=const.address_street)
            if len(addr_street) > 0:
                addr_street = addr_street[0]
                address_text = addr_street['address_text']
                if not addr_street['country']:
                    short_name = ou.get_name_with_language(
                        name_variant=const.ou_name_short,
                        name_language=const.language_nb,
                        default=None)
                    address_text = "\n".join(x
                                             for x in (short_name, address_text)
                                             if x)
                addr_street = {'address_text': address_text,
                               'p_o_box': addr_street['p_o_box'],
                               'postal_number': addr_street['postal_number'],
                               'city': addr_street['city'],
                               'country': addr_street['country']}
            else:
                addr_street = None
            addr_post = ou.get_entity_address(source=const.system_paga,
                                                type=const.address_post)
            if len(addr_post) > 0:
                addr_post = addr_post[0]
                addr_post = {'address_text': addr_post['address_text'],
                             'p_o_box': addr_post['p_o_box'],
                             'postal_number': addr_post['postal_number'],
                             'city': addr_post['city'],
                             'country': addr_post['country']}
            else:
                addr_post = None
            fax = ou.get_contact_info(source=const.system_paga,
                                      type=const.contact_fax)
            if len(fax) > 0:
                fax = fax[0]['contact_value']
            else:
                fax = None
            ou_cache[stedkode] = {'id': int(ou.entity_id),
                                  'fax': fax,
                                  'addr_street': addr_street,
                                  'addr_post': addr_post}
            ou_cache[int(ou.entity_id)] = ou_cache[stedkode]
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
        if not type_is_active(t):
            logger.warn("Not active: %s" % person)
            continue
        #logger.debug("Andel %s" % t['stillingsandel'])
        #logger.debug("Dato-fra '%s'" % t['dato_fra'])
        
        pros = float(t['stillingsandel'])
        if t['tittel'] == 'professor II':
            pros = pros / 5.0
        if prosent_tilsetting < pros:
            prosent_tilsetting = pros
            tittel = t['tittel']
        if (t['tjenesteforhold'] == 'T') and (pros == 0.0):
            aff_stat = const.affiliation_status_timelonnet_midlertidig
        elif t['hovedkategori'] == 'TEKN':
            aff_stat = const.affiliation_status_ansatt_tekadm
        elif t['hovedkategori'] == 'ADM':
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
        new_person.add_name_with_language(name_variant=const.work_title,
                                          name_language=const.language_nb,
                                          name=tittel)

    for g in person.get('gjest', ()):
        if not type_is_active(g):
            logger.warn("Not active")
            continue
        logger.error("Gjest item not implemented for persons!")
    return ret

def determine_contact(person):
    # TODO: Check if this is being used or may be used
    ret = []
    for t in person.get('arbtlf', ()):
        if int(t['telefonnr']):
            ret.append((const.contact_phone, t['telefonnr']))
        if int(t['linjenr']):
            ret.append((const.contact_phone,
                        "%i%05i" % (int(t['innvalgnr']), int(t['linjenr']))))
    for k in person.get('komm', ()):
        if k['kommtypekode'] in ('ARBTLF', 'EKSTRA TLF', 'JOBBTLFUTL'):
            if k.has_key('kommnrverdi'):
                val = k['kommnrverdi']
            elif k.has_key('telefonnr'):
                val = int(k['telefonnr'])
            else:
                continue
            ret.append((const.contact_phone, val))
        if k['kommtypekode'] in ('FAX', 'FAXUTLAND'):
            if k.has_key('kommnrverdi'):
                val = k['kommnrverdi']
            elif k.has_key('telefonnr'):
                val = int(k['telefonnr'])
            else:
                continue
            ret.append((const.contact_fax, val))
    return ret


def person_has_active(person, entry_type):
    """
    Determine if the person represented by PERSON has active ENTRY_TYPE
    entries.  'active' is defined as: dato_fra <= now <= dato_til.
    ENTRY_TYPE can be either 'tils' or 'gjest'
    """
    data = person.get(entry_type, list())
    for entry in data:
        if type_is_active(entry):
            return True
    return False


def type_is_active(entry_type):
    """
    Check whether given TYPE is active. TYPE is a dictionary
    representing either a 'tils' record or a 'gjest' record.
    """

    earliest = mx.DateTime.DateFrom(entry_type.get("dato_fra")) - \
               mx.DateTime.DateTimeDelta(cereconf.PAGA_EARLYDAYS)

    dato_fra = mx.DateTime.DateFrom(entry_type.get("dato_fra"))
    dato_til = mx.DateTime.DateFrom(entry_type.get("dato_til"))

    if (mx.DateTime.today() >= earliest) and \
       ((not dato_til) or (mx.DateTime.today() <= dato_til)):
        return True

    logger.warn("Not active, earliest: %s, dato_fra: %s, dato_til:%s" % \
                (earliest, dato_fra,dato_til))
    return False

def get_stillingsandel(person):
    prosent_tilsetting = 0
    for tils in person.get('tils', ()):
        if not type_is_active(tils):
            continue

        if not tils['hovedkategori'] in ('TEKN', 'ADM', 'VIT'):
            # this tils has unknown hovedkat, ignore it
            continue

        pros = float(tils['stillingsandel'])
        prosent_tilsetting += pros
    return prosent_tilsetting

def set_person_spreads(person, new_person):
    # Add ansatt spreads if person has ANSATT affiliation and 
    # has a stillingsandel higher than cereconf.EMPLOYEE_PERSON_SPREADS_PERCENTAGE.
    # Spreads to add are listed in cereconf.EMPLOYEE_PERSON_SPREADS
    employee_person_spreads = [int(const.Spread(x)) for x in cereconf.EMPLOYEE_PERSON_SPREADS]

    affs = new_person.get_affiliations()
    is_ansatt = False
    for i in range(0, len(affs)):
        if affs[i]['affiliation'] == int(const.affiliation_ansatt):
            percentage = get_stillingsandel(person)
            if percentage > cereconf.EMPLOYEE_PERSON_SPREADS_PERCENTAGE:
                is_ansatt = True
                break
    
    if is_ansatt:
        spreads_to_add = employee_person_spreads

        # only add spreads this person doesn't already have
        curr_spreads = new_person.get_spread()
        for s in curr_spreads:
            if s['spread'] in spreads_to_add:
                spreads_to_add.remove(s['spread'])

        for spread in spreads_to_add:
            new_person.add_spread(spread)
    else:
        # remove employee spreads for those with is_ansatt == False
        spreads_to_remove = employee_person_spreads
    
        # only remove employee spreads this person already has
        curr_spreads = new_person.get_spread()
        for s in curr_spreads:
            if s['spread'] in spreads_to_remove:
                new_person.delete_spread(s['spread'])

def is_y2k_problem(year_chk, year):
    y2k_problem = False
    curr_year = datetime.datetime.now().year

    # If the difference between year_chk and year is exactly 100, 
    # and year_chk is 100 years or more in the past,
    # it is highly likely that there is a y2k problem with year_chk.
    if (abs(year_chk - year) == 100) and (year_chk <= (curr_year - 100)):
        y2k_problem = True

    return y2k_problem

def process_person(person):
    fnr = person['fnr']
    try:
        location = person['lokasjon']
    except:
        logger.warn("Person has no location.")

    try:
       paga_nr = int(person['ansattnr'])
    except:
       logger.error("Invalid ansattnr %s. Person not processed." % person['ansattnr'])
       return
    gender = person['kjonn']
    fodselsdato = person['fodselsdato']
    try:
        year = int(fodselsdato[0:4])
        mon = int(fodselsdato[5:7])
        day = int(fodselsdato[8:10])
    except ValueError,m:
        logger.warning("%s - Is not a valid ssn. skipping" %(m))
        return

    logger.info("Process %d" % (paga_nr))

    if gender == 'M':
        gender = const.gender_male
    else:
        gender = const.gender_female

    # If a FNR is given, do a check of the values presented
    if(person['fnr'][6:11] == "00000"):
        logger.warn("Person with fnr:%s does not have valid fnr. Do not process fnr gender check. it will fail" % person['fnr'])
    elif((person.get('fnr','') and (person['fnr'][6:11]!='00000'))):
        try:
            fodselsnr.personnr_ok(fnr)
        except:
            logger.error("FNR invalid (%s) for PAGA person %s" % (fnr, paga_nr))
            return
    
        gender_chk = const.gender_male
        if(fodselsnr.er_kvinne(fnr)):
            gender_chk = const.gender_female

        if gender_chk != gender:
            logger.error("Gender inconsistent between XML (%s) and FNR (%s) for PAGA person %s" % (gender, gender_chk, paga_nr))
            return
    
        (year_chk, mon_chk, day_chk) = fodselsnr.fodt_dato(fnr)

        if year_chk != year:
            # check if the year difference is because of the y2k problem in the fodselsnr module
            # ignore if it is.
            if not is_y2k_problem(year_chk, year):
                logger.error("Year inconsistent between XML (%s) and FNR (%s) for PAGA person %s" % (year, year_chk, paga_nr))
                return
        if mon_chk != mon:
            logger.error("Month inconsistent between XML (%s) and FNR (%s) for PAGA person %s" % (mon, mon_chk, paga_nr))
            return
        if day_chk != day:
            logger.error("Day inconsistent between XML (%s) and FNR (%s) for PAGA person %s" % (day, day_chk, paga_nr))
            return

        

    # # If a FNR is given, do a check of the values presented
    # if person.get('fnr',''):
    #     try:
    #         fodselsnr.personnr_ok(fnr)
    #     except:
    #         logger.error("FNR invalid (%s) for PAGA person %s" % (fnr, paga_nr))
#         # fodselsnr.personnr_ok() will return Invaliderror for
    #         #  fodselsnr on the form DDMMYY00000. DDMMYY00000 is a
    #         #  valid number for foreign persons. if a fodselsnr on
    #         #  this form is found, continue processing it to avoid
    #         #  changes in modules.no/fodselsnr.py, create an
    #         #  additional check here

    #         temp_pnr = fnr[6:11]
    #         if(temp_pnr != '00000'):
    #             return
    #         else:
    #             logger.error("FNR (%s) is for a foreign person and valid for PAGA person %s" % (fnr, paga_nr))
    
    #     gender_chk = const.gender_male
    #     if(fodselsnr.er_kvinne(fnr)):
    #         gender_chk = const.gender_female

    #     if gender_chk != gender:
    #         logger.error("Gender inconsistent between XML (%s) and FNR (%s) for PAGA person %s" % (gender, gender_chk, paga_nr))
    #         return
    
    #     (year_chk, mon_chk, day_chk) = fodselsnr.fodt_dato(fnr)

    #     if year_chk != year:
    #         logger.error("Year inconsistent between XML (%s) and FNR (%s) for PAGA person %s" % (year, year_chk, paga_nr))
    #         return
    #     if mon_chk != mon:
    #         logger.error("Month inconsistent between XML (%s) and FNR (%s) for PAGA person %s" % (mon, mon_chk, paga_nr))
    #         return
    #     if day_chk != day:
    #         logger.error("Day inconsistent between XML (%s) and FNR (%s) for PAGA person %s" % (day, day_chk, paga_nr))
    #         return


    new_person.clear()

    try:
        new_person.find_by_external_id(const.externalid_paga_ansattnr, str(paga_nr)) 
    except Errors.NotFoundError:
        if person.get('fnr',''):
            try:
                new_person.find_by_external_id(const.externalid_fodselsnr, fnr)
            except Errors.NotFoundError:
                pass
    if (person.get('fornavn', ' ').isspace() or person.get('etternavn', ' ').isspace()):
        logger.warn("Ikke noe navn for paga_nr %s" % paga_nr)
        return

    try:
        new_person.populate(mx.DateTime.Date(year, mon, day), gender)
    except Errors.CerebrumError,m:
        logger.error("Person %s populate failed: %s" % (fnr or paga_nr,m))
        return

    new_person.affect_names(const.system_paga, const.name_first, const.name_last)
    new_person.affect_external_id(const.system_paga, const.externalid_fodselsnr, const.externalid_paga_ansattnr)
    new_person.populate_name(const.name_first, person['fornavn'])
    new_person.populate_name(const.name_last, person['etternavn'])

    if fnr != '':
       new_person.populate_external_id(const.system_paga, const.externalid_fodselsnr, fnr)
    new_person.populate_external_id(const.system_paga, const.externalid_paga_ansattnr, paga_nr)

    # If it's a new person, we need to call write_db() to have an entity_id
    # assigned to it.
    op = new_person.write_db()

    if person.get('tittel_personlig', ''):
        new_person.add_name_with_language(name_variant=const.personal_title,
                                          name_language=const.language_nb,
                                          name=person['tittel_personlig'])

    # work_title is set by determine_affiliations
    affiliations = determine_affiliations(person)
    new_person.populate_affiliation(const.system_paga)
    contact = determine_contact(person)
    if person.has_key('fakultetnr_for_lonnsslip'):
        sted = get_sted(person['fakultetnr_for_lonnsslip'],
                        person['instituttnr_for_lonnsslip'],
                        person['gruppenr_for_lonnsslip'])
        if sted is not None:
            if sted['addr_street'] is not None:
                new_person.populate_address(
                    const.system_paga, type=const.address_street,
                    **sted['addr_street'])
            if sted['addr_post'] is not None:
                new_person.populate_address(
                    const.system_paga, type=const.address_post,
                    **sted['addr_post'])
            if not got_fax and sted['fax'] is not None:
                # Add fax number for work place with a non-NULL fax
                # to person's contact info.
                contact.append((const.contact_fax, sted['fax']))
                got_fax = True
    if person.has_key('lokasjon'):

        #
        # Populate person address with:
        # source_system = const.system_paga
        # type = const.address_location
        # address_text = person['location']
        # 
        #
        logger.warn('populating person address with:source:%s, type:%s, text:%s' % (const.system_paga,const.address_location,person['lokasjon']))
        new_person.populate_address(source_system=const.system_paga, type=const.address_location,address_text=person['lokasjon'])

            
    for k,v in affiliations.items():
        ou_id, aff, aff_stat = v
        new_person.populate_affiliation(const.system_paga, ou_id,\
                            int(aff), int(aff_stat))
        if include_del:
            if cere_list.has_key(k):
                cere_list[k] = False
    c_prefs = {}
    new_person.populate_contact_info(const.system_paga)
    for c_type, value in contact:
        c_type = int(c_type)
        pref = c_prefs.get(c_type, 0)
        new_person.populate_contact_info(const.system_paga, c_type, value, pref)
        c_prefs[c_type] = pref + 1

    #
    # Also add personal/home street address if it exists in the import file
    #
    private_address = False
    address_text = None
    p_o_box = None
    postal_number = None
    city = None
    country = None
    if (person.has_key('adresse')) and (len(person['adresse'])):
        address_text = person['adresse']
        private_address = True
    if (person.has_key('postnr')) and (len(person['postnr'])):
        postal_number = person['postnr']
        private_address = True
    if (person.has_key('poststed')) and (len(person['poststed'])):
        city = person['poststed']
        private_address = True
    if(private_address == True):
        logger.info("Setting additional home address:%s %s %s" % (address_text,postal_number,city))
        new_person.populate_address(const.system_paga,const.address_post_private,address_text,p_o_box,postal_number, city, country)

    op2 = new_person.write_db()

    # UIT: Update last_date field
    # must be done after write_db() to ensure that affiliation table entry exist
    # in database
    for k,v in affiliations.items():
        ou_id, aff, aff_stat = v
        new_person.set_affiliation_last_date(const.system_paga, ou_id,\
                                         int(aff), int(aff_stat))

    set_person_spreads(person, new_person)

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
    for row in new_person.list_affiliations(source_system=const.system_paga):
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
            affs=new_person.list_affiliations(ent_id,affiliation=affi,ou_id=ou,source_system=const.system_paga)
            for aff in affs:
                last_date = datetime.datetime.fromtimestamp(aff['last_date'])
                end_grace_period = last_date +\
                    datetime.timedelta(days=cereconf.GRACEPERIOD_EMPLOYEE)
                if datetime.datetime.today() > end_grace_period:
                    logger.warn("Deleting system_paga affiliation for " \
                    "person_id=%s,ou=%s,affi=%s last_date=%s,grace=%s" % \
                        (ent_id,ou,affi,last_date,cereconf.GRACEPERIOD_EMPLOYEE))
                    new_person.delete_affiliation(ou, affi, const.system_paga)

                # if datetime.datetime.today() > last_date:
                #     # person is no longer an employee, delete employee spreads for this person.
                #     # Spreads to delete are listed in cereconf.EMPLOYEE_PERSON_SPREADS
                #     employee_person_spreads = [int(const.Spread(x)) for x in cereconf.EMPLOYEE_PERSON_SPREADS]
                #     for s in employee_person_spreads:
                #         new_person.delete_spread(s)

                #     # TODO 1: need to test this
                #     # TODO 2: check if this will be ok for a person that "returns" before affil is deleted


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


