#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2008 University of Oslo, Norway
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

# This file is a Giske-specific extension of Cerebrum and is used to
# import data about guardians for pupils attending Giske's primary
# schools. As the questions related to registration of guardians in
# general are not properly answered this code is to be considered as
# a highly temporary and hackish solution to the registration of
# guardians.
#
# The script is a clean import, and the data registered are fetched in
# form of a text file from Giske's webportal.
#
# This script will only ever be run manually, and is not expected to
# be used after 2009. Files that the script will read should be places
# in: /cerebrum/dumps/Foresatte/
#
# File format:
# 
# <fnr><lastname><firstname><SKULE\child_uid1
# SKULE\child_uid2...><group1 group2...><url>
#
# Example:
#
# 110165xxxxx;Alnes;Eivind Johan;SKULE\magnuswa;"GOD foresatte"
# "GOD_7_foresatt";"https://portal.skule.giske.no/skule/GOD/foresatte"
#
# In addition to adding an import-script changes must be made to the
# existing AD-synchronization script and constants defined to
# represent guardian affiliation and traits needed to register which
# pupils a guardian is connected to. These are:
#
#   Affiliation: FORESATT
#   Affiliation status: aktiv
#
#   Trait: trait_guardian_of
#   Trait: trait_guardian_urls
#
# This trait should be replaced by guardian roles, but as we do not
# support roles yet we need to live with this for now.
#
# jazz, 2008-08-17
#
# Installation of this script i done in the usual way and the only
# know prerequisits are the affiliation and trait codes mentioned
# above.
#
# Run cmd:
#
# python import_foresatte.py -f /cerebrum/dumps/Foresatte/filename
#        --people --accounts [--dryrun]

import cerebrum_path
import cereconf

import getopt
import sys
import re
import time

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr

def attempt_commit():
    if dryrun:
        db.rollback()
        logger.info("Rolled back all changes")
    else:
        db.commit()
        logger.info("Committed all changes")

def usage(exitcode):
    print   "Exit code: %d" % exitcode
    print """Usage: import_foresatte.py -f filename [-p|-a]
             -d, --dryrun  : Run a fake import. Rollback after run.
             -f, --file    : File to parse - mandatory
             -p, --people  : Import person data and create person objects
             -a, --accounts: Create accounts in Cerebrum for defined guardians
             -h, --help    : Print this text
             At least one of -p, -a must be present
          """
    sys.exit(exitcode)

def check_line(l):
    tmp = []
    count_entries = 0
    tmp = l.split(';')
    count_entries = len(tmp)
    if count_entries == 0:
        logger.error("Cannot process an empty line")
        return False
    elif count_entries > 0 and count_entries != 6:
        logger.error("Cannot process a faulty line %s", l)
        return False
    return True

def p_create(fnr, lname, fname):
    gender = constants.gender_female
    try:
        fodselsnr.personnr_ok(fnr)
    except fodselsnr.InvalidFnrError:
        logger.error("Cannot create person, bad no_ssn |%s|", fnr)
        return None
    if not (lname and fname):
        logger.error("Cannot create person %s, missing name")
        return None
    if fodselsnr.er_mann(fnr):
        gender = constants.gender_female
    # this is very wrong, but as we do not have any birth days
    # registered we need to try producing them.
    year, mon, day = fodselsnr.fodt_dato(fnr)
    # in order to be a guardian you need to be over 18 years old which
    # excludes anyone born in after 1990 so this will work for now :-)
    birth_date = db.Date(year, mon, day)
    person.clear()
    # Create person
    person.populate(birth_date, gender)
    person.affect_external_id(constants.system_manual,
                              constants.externalid_fodselsnr)
    person.populate_external_id(constants.system_manual,
                                constants.externalid_fodselsnr, fnr)
    person.write_db()
    logger.info("Created new person with fnr %s", fnr)
    # Add person_name
    person.affect_names(constants.system_manual,
                        constants.name_first,
                        constants.name_last)
    person.populate_name(constants.name_first, fname)
    person.populate_name(constants.name_last, lname)
    person.write_db()
    logger.debug("Added name %s %s to fnr %s", fname, lname, fnr)
    return person.entity_id

def register_person_affs(person_id, ous):
    # Add person affiliations
    #
    # onlys following affiliations wil be processed:
    affiliation = constants.affiliation_foresatt
    affiliation_status = constants.affiliation_status_foresatt_aktiv
    # In order to make this as easy as possible we just hardcode
    # OU-acronyms and ou_id in cerebrum
    ou_mapping = {'ALN': 1558,
                  'GIS': 1559,
                  'GOD': 1560,
                  'SKJ': 1562,
                  'VBS': 1563,
                  'VUS': 1564,
                  'VIG': 1565,
                  'KONG': 1561}
    for o in ous:
        ou_id = ou_mapping[o]
        ou.clear()
        try:
            ou.find(ou_id)
        except Errors.NotFoundError:
            logger.error("Could not register affiliation to %s for %s", o, fnr)
            return None
        person.populate_affiliation(constants.system_manual,
                                    ou_id=ou_id,
                                    affiliation=affiliation,
                                    status=affiliation_status)
        person.write_db()
    
def find_aff_ous(oul):
    # line format: "https://portal.skule.giske.no/skule/VUS/foresatte"
    ou_acronyms = []
    tmp = []
    tmp1 = []
    tmp = oul.split('$')
    for i in tmp:
        tmp1 = i.split('/')
        ou_acronyms.append(tmp1[4])
    return ou_acronyms

def register_traits(person_id, guardian_of, urls):
    person.clear()
    person.find(person_id)
    ret1 = person.populate_trait(constants.trait_guardian_of, strval=guardian_of)
    if ret1:
        logger.debug("Populated guardianship trait with %s", guardian_of)
    strval_url = ""
    tmp = urls.split('$')
    for u in tmp:
        strval_url = strval_url + ' ' + u
    ret = person.populate_trait(constants.trait_guardian_urls, strval=strval_url)
    if ret:
        logger.debug("Populated guardianship urls trait with %s", urls)

def a_create(fname, lname, owner_id):
    owner_type = constants.entity_person
    account.clear()
    if not (lname and fname):
        logger.error("Cannot create account, missing name")
        return None
    tmp = account.suggest_unames(constants.account_namespace, fname, lname)
    uname = tmp[0]
    account.populate(uname, owner_type, owner_id, None, default_creator_id, None)
    account.write_db()
    passwd = account.make_passwd(uname)
    account.set_password(passwd)
    account.add_spread(constants.spread_ad_acc)
    account.write_db()
    return account.entity_id
        
def register_group_memberships(acc_id, grpl):
    tmp = grpl.split('$')
    for i in tmp:
        group.clear()
        try:
            group.find_by_name(i)
        except Errors.NotFoundError:
            logger.debug("Could not find group %s, will try to create", i)
            group.clear()
            group.populate(default_creator_id, constants.group_visibility_all,
                           i, description='Gruppe for foresatte')
            group.write_db()
            group.add_spread(constants.spread_ad_grp)
            logger.info("Created new group %s", i)
        if not group.has_member(acc_id):
            group.add_member(acc_id)
            logger.debug("Added %s to group %s", acc_id, group.group_name)
    group.write_db()
        
def process_line(l, p_type='people'):
    ous = []
    values = []
    person_id = None
    if p_type == 'people':
        person_id = None
        values = l.split(';')
        fnr = values[0]
        lname = values[1]
        fname = values[2]
        ous = find_aff_ous(values[5])        
        try:
            person.clear()
            person.find_by_external_id(constants.externalid_fodselsnr, fnr)
            logger.info("Found person %s (person creation)", fnr)
            person_id = person.entity_id
        except Errors.NotFoundError:
            logger.debug('Could not find person %s, will try to create', fnr)
            person_id = p_create(fnr, lname, fname)
        if person_id:
            register_traits(person_id, values[3], values[5])
            register_person_affs(person_id, ous)
    elif p_type == 'accounts':
        primary_acc_id = None
        accs = []
        values = l.split(';')
        fnr = values[0]
        person_id = None
        try:
            person.clear()
            person.find_by_external_id(constants.externalid_fodselsnr, fnr)
            logger.info("Found person %s (account create)", fnr)
            person_id = person.entity_id
        except Errors.NotFoundError:
            logger.error('Could not find person %s, create first', fnr)
            return
        lname = values[1]
        fname = values[2]        
        foresatt_aff = person.list_affiliations(person_id=person.entity_id,
                                                source_system=constants.system_manual,
                                                affiliation=constants.affiliation_foresatt,
                                                status=constants.affiliation_status_foresatt_aktiv)
        accs = account.list_accounts_by_owner_id(person.entity_id,
                                                 filter_expired=False)
        grpl = values[4]
        if len(accs) > 0:
            # in theory, no one has more than 1 account so this should
            # work fine
            primary_acc_id = accs[0]['account_id']
            account.clear()
            account.find(primary_acc_id)
            if account.is_deleted():
                logger.warn("A deleted account already exists for %s, restoring", fnr)
                account.add_spread(constants.spread_ad_acc)
                account.expire_date = None
        else:
            primary_acc_id = a_create(fname, lname, person_id)
        if primary_acc_id:
            if foresatt_aff:
                account.clear()
                account.find(primary_acc_id)
                for r in foresatt_aff:
                    account.set_account_type(foresatt_aff[0][1],
                                             foresatt_aff[0][2])
                account.write_db()
            register_group_memberships(primary_acc_id, grpl)

def create_objects(infile, object_type='person'):
    line = ""
    stream = open(infile, 'r')
    for l in stream:
        line = l.strip()
        if check_line(line):
            if object_type == 'people':
                process_line(line, p_type='people')
            elif object_type == 'accounts':
                process_line(line, p_type='accounts')
            else:
                logger.error("Undefined object type %s, cannot create",
                             object_type)
def main():    
    global db, constants, account, person, ou, group
    global default_creator_id
    global dryrun, logger

    logger = Factory.get_logger("cronjob")
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:hpad',
                                   ['file=',
                                    'dryrun',
                                    'help',
                                    'people',
                                    'accounts'])
    except getopt.GetoptError:
        usage(4)

    dryrun = False
    import_persons = False
    create_accs = False
    infile = ""

    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-f', '--file'):
            infile = val
        elif opt in ('-p', '--people'):
            import_persons = True
        elif opt in('-a', '--accounts'):
            create_accs = True
        elif opt in ('-h', '--help'):
            usage(0)
        else:
            usage(1)

    if infile is None:
        usage(2)

    if not (import_persons or create_accs):
        usage(3)
        
    db = Factory.get('Database')()
    db.cl_init(change_program='import_guard')
    constants = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    group = Factory.get('Group')(db)
    person = Factory.get('Person')(db)
    ou = Factory.get("OU")(db)

    account.clear()
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id

    if import_persons:
        create_objects(infile, object_type='people')

    if create_accs:
        create_objects(infile, object_type='accounts')
        
    attempt_commit()

if __name__ == '__main__':
    main()
