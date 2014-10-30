#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2013 University of Tromsø, Norway
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

# Global imports

import sys
import os
import getopt
import datetime
import pprint
import mx.DateTime
pp = pprint.PrettyPrinter(indent=4)

# Cerebrum imports
import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum import Database
from Cerebrum.modules.no import fodselsnr

# Global variables
db = Factory.get('Database')()
const = Factory.get('Constants')(db)
ou = Factory.get('OU')(db)
db_person = Factory.get('Person')(db)
e = Factory.get('Entity')(db)
#sko = Factory.get('Stedkode')(db)
sko = ou
dryrun = False
include_del = False
#stedkode = Factory.get('Stedkode')(db)
logger = Factory.get_logger(cereconf.DEFAULT_LOGGER_TARGET)
progname = __file__.split("/")[-1]
db.cl_init(change_program=progname)


__doc__ = """ Usage: %s [-p personfile] [-h | --help ][--logger-name]
-h | --help        :   this text
-p | --person_file :   Path to person file from generate_flyt.py
-a | --all_nodes   :   persons and accounts get all affiliations received from Feide. Default
                       is to only set affiliations for the highest affiliation in any single path.
                       see: https://www.feide.no/attribute/edupersonaffiliation
-l | --logger-name :
""" % (progname)


def usage(exitcode = 0, msg = None):
    if msg:
        print msg
    print __doc__
    sys.exit(exitcode)




#
# generates person affiliations for all flyt persons already in Cerebrum
#
def load_all_affi_entry():
    affi_list = {}
    for row in db_person.list_affiliations(source_system=const.system_flyt):
        key_l = "%s:%s:%s" % (row['person_id'],row['ou_id'],row['affiliation'])
        affi_list[key_l] = True
    #print "returning;%s" % affi_list
    return(affi_list)


#
# deletes expired person affiliations
#
def clean_affi_s_list():
    for k,v in cere_list.items():
        #logger.info("clean_affi_s_list: k=%s,v=%s" % (k,v))
    
        if v:
            print "V is set"
            [ent_id,ou,affi] = [int(x) for x in k.split(':')]
            db_person.clear()
            db_person.entity_id = int(ent_id)
            affs=db_person.list_affiliations(ent_id,affiliation=affi,ou_id=ou,source_system=const.system_flyt)
            for aff in affs:
                print "HAS AFFS"
                last_date = datetime.datetime.fromtimestamp(aff['last_date'])
                end_grace_period = last_date +\
                    datetime.timedelta(days=cereconf.FLYT_GRACEPERIOD)
                

                if datetime.datetime.today() > end_grace_period:
                    logger.warn("Deleting system_flyt affiliation for " \
                    "person_id=%s,ou=%s,affi=%s last_date=%s,grace=%s" % \
                        (ent_id,ou,affi,last_date,cereconf.GRACEPERIOD_EMPLOYEE))
                    db_person.delete_affiliation(ou, affi, const.system_flyt)


#
# Set correct encoding
#
def decode_text(text):
    #print "original text:%s" % text
    new_text = unicode(text,'utf-8').encode('iso-8859-1')
    #print "decoded text:%s" % new_text
    return new_text

#####################################################################
# process persons. person_list contains the following information.
#
#
# [0] = ' norEduPersonNIN'
# [1] = 'givenname'
# [2] = 'sn'
# [3] = 'norEduOrgNiN'
# [4] = 'orgName'
# [5] = 'eduPersonPrincipalName'
# [6] = 'eduPersonAffiliation'
# [7] = 'eduPersonOrgUnitDN'
# [8] = 'auththentication_type'
# [9] = 'authentication_value'
# [10] = 'mail'
# [11] = 'eduPersonEntitlement'
# [12] = 'groups'
# [13] = 'mobile'
# [14] = 'last_seen'
# [15] = 'expire_date'
# [16] = 'password'
# [17] = 'agreement_expire_date' (only used by process_flyt.py)
#
#######################################################################
def import_person(persons,all_nodes):
    print "import person"
    global dryrun
    global cere_list
    global include_del
    logger.info("database:%s" % cereconf.CEREBRUM_DATABASE_CONNECT_DATA['host'])
    for person in persons:

        ssn_is_missing = False
        ssn_not_valid = False
        valid_birthday = True
        person_to_be_processed = {}

        person = person.rstrip()
        person_list = person.split(";")

        logger.debug("--- Processing new person ---")

        try:
            #print "fnr:'%s'" % person_list[1]
            person_to_be_processed['noreduorgnin'] = person_list[3]
            person_to_be_processed['birth_day'] = person_list[0][0:2]
            person_to_be_processed['birth_month'] = person_list[0][2:4]
            person_to_be_processed['birth_year'] = person_list[0][4:6]

            # Make sure year contains 4 digits.
            if(person_to_be_processed['birth_year'] < 20 ):
                birth_year = "20%s" % (person_to_be_processed['birth_year'])
            else:
                birth_year = "19%s" % (person_to_be_processed['birth_year'])
            person_to_be_processed['birth_year'] = birth_year
            #print "birth_day:'%s'" % person_to_be_processed['birth_day']
            #print "birth_month:'%s'" % person_to_be_processed['birth_month']
            #print "birth_year:'%s'" % person_to_be_processed['birth_year']
        except ValueError:
            logger.warning("Empty Birthdate for person named:%s %s. Continue with next person" % (person_list[1],person_list[2]))
            continue
        except IndexError:
            logger.warning("empty person file?")
            continue
        # Check if SSN is valid
        #print "current fnr:%s" % person_list[0]
        try:
            fodselsnr.personnr_ok(person_list[0])
            person_to_be_processed['ssn'] = person_list[0]
        except fodselsnr.InvalidFnrError:
            logger.warning("Empty or non-valid ssn %s for person:%s %s from :%s. Continue with next person" % (person_list[0],person_list[1],person_list[2],person_list[4]))
            #ssn_not_valid = True
            #person_to_be_processed['ssn'] = ''
            continue

        # set person gender
        #gender = const.gender_male
        gender = const.gender_male
        if(ssn_not_valid == False):
            if(fodselsnr.er_kvinne(person_to_be_processed['ssn'])):
                gender = const.gender_female
        else:
            # Impossible to set gender. Return error message and set gender to unknown
            logger.warning("Impossible to set gender for person:%s %s. Using Unknown"% (person_list[1],person_list[2]))
            gender = const.gender_unknown

        # set gender
        person_to_be_processed['gender'] = gender
        # get person firstname
        person_to_be_processed['firstname'] = person_list[1]
        #print "firstname:%s" % person_to_be_processed['firstname']
        # get person lastname
        person_to_be_processed['lastname'] = person_list[2]
        #print "lastname:%s" % person_to_be_processed['lastname']

        if((person_to_be_processed['firstname'].isspace() == True )or (person_to_be_processed['lastname'].isspace() == True)):
            # Firstname and/or lastname is made of whitespace ONLY.
            # generate error message and continue with NEXT person
            logger.warn("missing first and/or lastname for person:%s. Person NOT imported" % person)
            continue

        # set correct encoding
        person_to_be_processed['firstname'] = decode_text(person_to_be_processed['firstname'])
        person_to_be_processed['lastname'] = decode_text(person_to_be_processed['lastname'])


        #
        # Finished building person_to_be_processed dict.
        #pp.pprint(person_to_be_processed)
        #
        # create person object
        db_person.clear()
        try:
            db_person.find_by_external_id(const.externalid_fodselsnr,person_to_be_processed['ssn'])
            logger.info("Ssn already in database. update person object")
            #existing_person = True
        except Errors.NotFoundError:
            logger.warning("Unknown ssn:%s, create new person object" % person_to_be_processed['ssn'])
            # Unable to find person with ssn in the database.
            pass


        #
        # Populate person object
        #
        try:
            db_person.populate(mx.DateTime.Date(int(person_to_be_processed['birth_year'])
                                                ,int(person_to_be_processed['birth_month'])
                                                ,int(person_to_be_processed['birth_day']))
                               ,int(person_to_be_processed['gender']))
        except Errors.CerebrumError,m:
            # unable to populate person object. Return error message and continue with next person
            logger.error("Person:%s population failed" % (person_to_be_processed['ssn'],m))
            continue

        # affect name and external id
        db_person.affect_names(const.system_flyt, const.name_first, const.name_last)
        # populate firstname, lastname and external id
        db_person.populate_name(const.name_first, person_to_be_processed['firstname'])
        db_person.populate_name(const.name_last, person_to_be_processed['lastname'])

        db_person.affect_external_id(const.system_flyt, const.externalid_fodselsnr)
        db_person.populate_external_id(const.system_flyt, const.externalid_fodselsnr, person_to_be_processed['ssn'])

        # In case this is a new person, we will need to write to DB before we can continue.
        try:
            op = db_person.write_db()
        except db.IntegrityError,e:            
            db_person.clear()
            db.rollback()
            logger.info("Error:%s - person not imported to BAS" % (e))
            continue

        #op = db_person.write_db()

        
        # Determine person affiliation and affiliation_status
        det_ou,det_affiliation = determine_affiliation(person_list,all_nodes)
        
        #logger.debug(" --- from determine affiliation, the following is calculated ---")
        #pp.pprint(det_affiliation)

        for single_ou in det_ou:
            for single_aff in det_affiliation:                
                new_aff = getattr(const,single_aff)
                new_aff_stat = getattr(const,det_affiliation[single_aff])
                sko.clear()
                sko.find_stedkode(single_ou[0:2],single_ou[2:4],single_ou[4:6],cereconf.DEFAULT_INSTITUSJONSNR)
                logger.debug("setting:: ou_id:%s, aff:%s, aff_stat:%s for person:%s" % (int(sko.ou_id),int(new_aff),int(new_aff_stat),db_person.entity_id))

                db_person.populate_affiliation(const.system_flyt,
                                               sko.ou_id,
                                               new_aff,
                                               new_aff_stat)
                k = "%s:%s:%s" % (db_person.entity_id,int(sko.ou_id),int(new_aff))
                if include_del:
                    if cere_list.has_key(k):
                        cere_list[k] = False
                #db_person.write_db()
                #db_person.set_affiliation_last_date(const.system_flyt,int(single_ou),int(new_aff),int(new_aff_stat))

                
        # store mobile for those that has it
        #contact = determine_contact(db_person)
        if(len(person_list[13])> 1):
            person_list[13]
            logger.debug("has mobile:%s" % person_list[13])
            number = person_list[13]
            type = 'mobile'
            c_prefs = {}
            c_type = int(const.contact_mobile_phone)
            pref = c_prefs.get(c_type,0)
            db_person.populate_contact_info(const.system_flyt,c_type,number,pref)
            pref = c_prefs[c_type] = pref = 1
        else:
            logger.debug("No mobile registered for this user")

            

        op2 = db_person.write_db()

        for single_ou in det_ou:
            for single_aff in det_affiliation:
                new_aff = getattr(const,single_aff)
                new_aff_stat = getattr(const,det_affiliation[single_aff])
                sko.clear()
                sko.find_stedkode(single_ou[0:2],single_ou[2:4],single_ou[4:6],cereconf.DEFAULT_INSTITUSJONSNR) 
                db_person.set_affiliation_last_date(const.system_flyt,sko.ou_id,new_aff,new_aff_stat)

        if op is None and op2 is None:
            logger.info("**** EQUAL ****")
        elif op == True:
            logger.info("**** NEW ****")
        else:
            logger.info("**** UPDATE  (%s:%s) ****" % (op,op2))

#
# Will return list of: <ou_id>:<affiliation>:<affiliation_type>
#
def determine_affiliation(person_list,all_nodes):
    aff_stat = []
    ou = []
    id_values = []
    calculated_aff_stat = []
    # affiliation tree contains a list of affiliation status types
    # and the affiliation types not valid when the key is encountered.
    # i.e if a Feide person has the faculty affiliation status, then
    # employee and member are non-valid affilation status and as such
    # no affiliation status will be set for these two values.
    affiliation_tree = {'member' : '',
                        'student' : 'member',
                        'employee' : 'member',
                        'faculty' : 'employee,member',
                        'staff' : 'employee,member',
                        'affiliate': '',
                        'alum': '',
                        'library-walkin' : ''
                        }
    #pp.pprint(person_list)
    affiliation_status = person_list[6].split(",")
    
    if(all_nodes == False):
        #
        # We only set affiliations with the highest value in the hierarcy of any single path.
        # Im not really happy about how its done here, but it will have to do for now.
        #
        logger.debug("only setting affiliations with the highest value in the hierachy")
        not_valid = []
        for status in affiliation_status:
            if (status in not_valid):
                # already exists. Do not append value
                #print "%s is in the not valid list. pass" % status
                pass
            else:
                # valid key. append to list
                aff_stat_list = affiliation_tree[status].split(",")
                for elem in aff_stat_list:
                    #print "single aff elem:%s" % elem
                    if elem not in not_valid:
                        not_valid.append(elem)
                        #print "adding:%s to list of not valid affiliations" % elem 
                        
                    if status not in calculated_aff_stat:
                        #print "appending:%s to final affiliation list" % status
                        calculated_aff_stat.append(status)

                    try:
                        calculated_aff_stat.remove(elem)
                        #print "removing:%s from calcualated aff list" % elem
                        #print_r(calculated_aff_stat)
                    except:
                        pass

        #logger.debug("not valid list now contains:%s" % not_valid)
        #logger.debug("valid now contains:%s" % calculated_aff_stat)
        affiliation_status = calculated_aff_stat
    

    #
    # Calculate correct affiliation and affiliation status
    #
    #print "person_list[8]['AFF']:%s" % person_list[8]
    #pp.pprint(person_list)
    aff_stat = {}
    for aff_s in affiliation_status:
        aff_list  = person_list[9].split(",")
        for aff in aff_list:
            try:
                affiliation_status = cereconf.FLYT_AFF[person_list[3]][aff_s][person_list[8]][aff]['affiliation_status']
                aff_stat[cereconf.FLYT_AFF[person_list[3]][aff_s][person_list[8]][aff]['affiliation']] = affiliation_status
                ou.append(cereconf.FLYT_AFF[person_list[3]][aff_s][person_list[8]][aff]['stedkode'])
            except KeyError,m:
                logger.error("ERROR: %s is not a valid authentication value for person:%s" % (m,person_list[0]))
    pp.pprint(aff_stat)

    if len(ou) ==0 :
        #print "person:%s has no valid ou" % person_list[1]
        return -1
    else:
        #print "ous:%s"% ou
        pass

    return ou,aff_stat

    
def get_person_data(person_file):

    print "get_person_data"
    fp = open(person_file,'r')
    content = fp.readlines()
    for person in content:
        if(person[0] == '#'):
            # Weee deleting entry inside a loop..really shouldnt do this. scary!
            del content[0]
    return content
        


def main():

    default_person_filename = "/cerebrum/var/dumps/flyt/flyt_person.txt"
    default_file = True
    default_file_path = cereconf.DUMPDIR
    all_nodes = False
    global include_del
    global dryrun
    global cere_list

    try:
        opts,args = getopt.getopt(sys.argv[1:],'ardp:',['all_nodes','include_delete','dryrun','person_file='])
    except getopt.GetoptError,m:
        usage(1,m)

    for opt,val in opts:
        if opt in('-p','--person_file'):
            default_person_filename = val
        if opt in ('-d','--dryrun'):
            dryrun = True
        if opt in ('-r','--include_delete'):
            include_del = True
        if opt in('-a','all_nodes'):
            all_nodes = True

    if (include_del == True):
        cere_list = load_all_affi_entry()
        

    person_list = get_person_data(default_person_filename)
    pp.pprint(person_list)
    import_person(person_list,all_nodes)

    if (include_del == True):
        clean_affi_s_list()


    if(dryrun == False):
        logger.info("Commiting to DB")
        db.commit()
    elif(dryrun == True):
        logger.warning("Dryrun. NOT commiting to DB")
        db.rollback()
        

if __name__ == '__main__':
    main()

