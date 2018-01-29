#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getopt
import sys
import cerebrum_path
import cereconf

from sets import Set
from Cerebrum import Utils
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules.no.uio.Ephorte import EphorteRole


""" This script will fetch all persons assigned
    'spread_ephorte_person' and check whether they have an ePhorte
    standard role assigned. If no standard role is found a random
    'SB'-role is registered as standard. If more than one role is
    flagged as the standard role, the flagg is removed on the last
    standard role found.
    In the test environment this script returned over 9 000 persons
    without a standard_role. This number seems very large, but it
    also seems to be correct (the number corresponds to the number
    of people with ephorte-spread and without a standard_role
    registered in Cerebrum-db).
    After the script was run in the test envir the error messages
    'WARNING Person A has X roles, but no standard role' dissaperad
    from gen_eph_exporte as was expected.
    I would suggest that prior to running this in production another
    check is done in the test environment and that one should try to
    make sure that no unfortunate consequences for ePhorte will occur
    with this initial change. After the initial run th script should
    be ok to run peiodically.
    Running the script with the other option in test environment did
    not return any hits. This seems to be consistent with the
    database content, which means that this check may be run. """

def usage(exitcode=0):
    print """python set_standard_eph_roles.py [-h|-d] (help, dryryn)
             --set: flagg SB-roles as standard for people not assigned a standard role
             --remove: check all persons with ephorte roles and remove standard role
                       flagg if a doouble is found"""
    sys.exit(exitcode)

def set_standard_role():
    for row in person.list_all_with_spread(constants.spread_ephorte_person):
        standard_role = False
        tmp_role_type = None
        tmp_adm_enhet = None
        tmp_arkivdel = None
        tmp_journalenhet = None
        for role in ephorte_role.list_roles(person_id=int(row['entity_id'])):
            # register last seen SB-role that is not a standard role
            if int(role['role_type']) == int(constants.ephorte_role_sb):
                if role['standard_role'] == 'F':
                    tmp_role_type = role['role_type']
                    tmp_adm_enhet = role['adm_enhet']
                    tmp_arkivdel = role['arkivdel']
                    tmp_journalenhet = role['journalenhet']
            # check if the current role is flagged as standard role
            logger.debug("standard role flagg: %s", role['standard_role'])
            if ephorte_role.is_standard_role(role['person_id'], role['role_type'], 
                                             role['adm_enhet'], role['arkivdel'], role['journalenhet']):
                standard_role = True
                logger.debug("Found standard role for %s", int(row['entity_id']))
                break
        if not standard_role:
            if tmp_role_type and tmp_adm_enhet and tmp_arkivdel and tmp_journalenhet:
                # some people have the necessary spread, but have no
                # active roles. the test above allows us to skip
                # trying to assign an empty role as standard
                ephorte_role.set_standard_role_val(int(row['entity_id']), 
                                                   tmp_role_type,  tmp_adm_enhet, 
                                                   tmp_arkivdel, tmp_journalenhet, 'T')
                logger.debug("Added role: %s, %s, %s, %s as standard_role for %s", tmp_role_type, 
                             tmp_adm_enhet, tmp_arkivdel, tmp_journalenhet, row['entity_id'])            

def remove_double_std_roles():
    for row in person.list_all_with_spread(constants.spread_ephorte_person):
        cnt_std_roles = 0
        tmp_role_type = None
        tmp_adm_enhet = None
        tmp_arkivdel = None
        tmp_journalenhet = None
        for role in ephorte_role.list_roles(person_id=int(row['entity_id'])):
            # register last seen SB-role that is flagged as a standard role
            if int(role['role_type']) == int(constants.ephorte_role_sb):
                if role['standard_role'] == 'T':
                    tmp_role_type = role['role_type']
                    tmp_adm_enhet = role['adm_enhet']
                    tmp_arkivdel = role['arkivdel']
                    tmp_journalenhet = role['journalenhet']
            # check if the current role is flagged as standard role
            logger.debug("standard role flagg: %s", role['standard_role'])
            if ephorte_role.is_standard_role(role['person_id'], role['role_type'], 
                                             role['adm_enhet'], role['arkivdel'], role['journalenhet']):
                cnt_std_roles = cnt_std_roles + 1
                logger.debug("Found standard role for %s", int(row['entity_id']))
        if cnt_std_roles > 1:
            # the point here is that we just need to remove one ekstra
            # standard_role per run. eventually all the extra roles
            # will be removed
            ephorte_role.set_standard_role_val(int(row['entity_id']), tmp_role_type,  tmp_adm_enhet, tmp_arkivdel, tmp_journalenhet, 'F')
            logger.debug("Found %s roles flagged as standard role for %s, removing the last (%s, %s, %s, %s)", cnt_std_roles,
                         int(row['entity_id']), tmp_role_type,  tmp_adm_enhet, tmp_arkivdel, tmp_journalenhet)
def main():
    global dryrun, constants, person, ephorte_role, logger
    
    dryrun = False
    db = Factory.get('Database')()
    db.cl_init(change_program="set_eph_std")
    constants = Factory.get('Constants')(db)
    person = Factory.get('Person')(db)
    ephorte_role = EphorteRole(db)
    logger = Factory.get_logger("console")

    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                   ['dryrun',
                                    'set',
                                    'remove',
                                    'help'])
    except getopt.GetoptError:
        usage()
    for opt, val in opts:
        if opt in ('--dryrun',):
            logger.info("assuming dryrun-mode")
            dryrun = True
        elif opt in ('--help',):
            logger.debug("printing help text")
            usage()
        elif opt in ('--set',):
            set_standard_role()
        elif opt in ('--remove',):
            remove_double_std_roles()
    
    if dryrun:
        db.rollback()
        logger.info("DRYRUN: Roll back changes")
    else:
        db.commit()
        logger.info("Committing changes")

if __name__ == '__main__':
    main()
