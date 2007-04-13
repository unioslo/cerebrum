#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import config
import sys
import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.ntnu import access_BDB

import mx
import util
import getopt
import logging
import time
import os

"""
Import orgunits,persons and accounts from NTNUs old UserAdministrative System.
"""

# Set the client encoding for the Oracle client libraries
os.environ['NLS_LANG'] = config.conf.get('bdb', 'encoding')
missing_personnr = 0
wrong_nss_checksum = 0
num_accounts = 0
num_persons = 0
ant_persons = 0
verbose = False
dryrun = False

class BDBSync:
    def __init__(self):
        self.bdb = access_BDB.BDB()
        self.db = Factory.get('Database')()
        self.db.cl_init(change_program='import_BDB')
        self.const = Factory.get('Constants')(self.db)
        self.ou = Factory.get('OU')(self.db)
        self.new_person = Factory.get('Person')(self.db)
        self.ac = Factory.get('Account')(self.db)
        self.group = Factory.get('Group')(self.db)
        self.logger = Factory.get_logger("console")
        self.logger.info("Starting import_BDB")


    def sync_vacation(self):
        """Not implemented yet"""
        pass

    def sync_forward(self):
        """Not implemented yet"""
        pass

    def sync_persons(self):
        self.logger.debug("Getting persons from BDB...")
        if verbose:
            print "Getting persons from BDB"
        global ant_persons
        persons = self.bdb.get_persons()
        ant_persons = len(persons)
        self.logger.debug("Done fetching persons from BDB")
        for person in persons:
            self._sync_person(person)
        global missing_personnr,wrong_nss_checksum
        if verbose:
            print "%s persons had missing personnumber" % missing_personnr
            print "%s persons had bad checksum on personnumber" % wrong_nss_checksum
            print "%s persons where added or updated" % num_persons

    def __validate_person(self, person):
        # Returns true||false if enough attributes are set
        _valid = True
        if not person.get("person_number"):
            self.logger.warn("Person with bdb-external-id %s has no person-number" % person['id'])
            _valid = False
        elif not person.get("birth_date"): 
            self.logger.warn("Person with bdb-external-id %s has no birthdate" % person['id'])
            _valid = False
        elif not self.__validate_names(person):
            _valid = False
        if not _valid:
            return False
        try:
            fnr = self.__get_fodselsnr(person)
        except fodselsnr.InvalidFnrError,e:
            _valid = False
        try:
            gender = self.__get_gender(person)
        except fodselsnr.InvalidFnrError,e:
            # Checksum-error on gender
            _valid = False
        return _valid

    def __get_gender(self,person):
        gender = self.const.gender_male
        fnr = self.__get_fodselsnr(person)
        try:
            if (fodselsnr.er_kvinne(fnr)):
                gender = self.const.gender_female
        except fodselsnr.InvalidFnrError,e:
            self.logger.error("Fnr for %s is suddenly invalid. Shouldn't happen. Reason :%s." % (person['id'],str(e)))
            raise e
        return gender

    def __get_fodselsnr(self,person):
        # We should not get a key-error since __validate_person should take care
        # of non-existing person_number
        pnr = str(person.get("person_number"))
        #pnr = str(person['person_number'])
        year,month,day = person.get("birth_date").split('-')
        #year,month,day = person['birth_date'].split('-')
        year = year[2:]
        fnr = day+month+year+pnr
        return fnr

    def __validate_names(self,person): 
        #To be called from __validate_person
        if (person.get('first_name', ' ').isspace() or
            person.get('last_name',' ').isspace()):
            self.logger.warn("Missing name for BDB-person %s " % person['id'])
            return False
        else:
            return True

    def _sync_person(self, person):
        global num_persons,ant_persons,dryrun,verbose
        self.logger.info("Process %s" % person['id'])
        const = self.const
        new_person = self.new_person

        if not self.__validate_person(person):
            return

        gender = self.__get_gender(person)
        fnr = self.__get_fodselsnr(person)

        new_person.clear()
        try:
            try:
                new_person.find_by_external_id(const.externalid_fodselsnr, fnr)
            except Errors.TooManyRowsError:
                # Person matches too many external-Ids of same value from different sources
                # Narrow down the search
                new_person.find_by_external_id(const.externalid_fodselsnr, \
                                               fnr,const.system_lt)
        except Errors.NotFoundError:
            # Search on nssn failed. Search on bdb-external-id instead
            try:
                new_person.find_by_external_id(const.externalid_bdb_person,person['id'])
                self.logger.debug("Got match on bdb-id as entity_externalid using %s" % person['id'])
            except Errors.NotFoundError:
                # Got no match on nss or bdb-id. Guess we have a new person
                pass

        # Rewrite glob to a method?
        # Populate person with names 
        fodt_dato = mx.DateTime.Date(*fodselsnr.fodt_dato(fnr))
        new_person.populate(fodt_dato, gender)
        new_person.affect_names(const.system_bdb,
                                const.name_first,
                                const.name_last,
                                const.name_personal_title)
        new_person.populate_name(const.name_first, person['first_name'])
        new_person.populate_name(const.name_last, person['last_name'])

        if person.get('tittel_personlig'):
            new_person.populate_name(const.name_personal_title,
                                     person['tittel_personlig'])
        # Populate person with external IDs 
        new_person.affect_external_id(const.system_bdb,
                                      const.externalid_fodselsnr, 
                                      const.externalid_bdb_person)
        new_person.populate_external_id(const.system_bdb,
                                        const.externalid_fodselsnr,
                                        fnr)
        new_person.populate_external_id(const.system_bdb,
                                        const.externalid_bdb_person,
                                        person['id'])

        # Write to database and commit transaction
        #try:
        new_person.write_db()
        if dryrun:
            self.db.rollback()
            if verbose:
                print "Person %s not written. Dryrun only" % person['id']
        else:
            self.db.commit()
            num_persons += 1
            self.logger.debug("Person %s written into Cerebrum." % person['id'])
            if verbose:
                print "Person %s (%s/%s )written into Cerebrum." % (person['id'],num_persons,ant_persons)
        #except Exception,e:
        #    self.db.rollback()
        #    self.logger.error("Rolling back transaction.Reason: %s" % str(e))
        #    return
        
    def sync_groups(self):
        """
        This method synchronizes all BDB groups into Cerebrum.
        """
        global verbose,dryrun
        groups = self.bdb.get_groups()

        for group in groups:
            if not 'name' in group:
                self.logger.error("Group %s has no name, skipping." % group)
                continue
            #TBD: Implement using Cerebrum-modules instead of Spine-API
        if dryrun:
            self.db.rollback()
            if verbose:
                print "Dryrun. Rolling back changes that would have been commited"
        else:
            self.db.commit()
            if verbose:
                print "Commiting synced groups."


    def _sync_account(self,account_info):
        """Callback-function. To be used from sync_accounts-method."""
        global num_accounts,verbose,dryrun
        logger = self.logger
        logger.debug("Callback for %s" % account_info['id'])

        # Sanity-checking
        if not 'name' in account_info:
            self.logger.error("Account %s has no name, skipping." % account_info)
            return

        # TODO: IMPLEMENT SYNC OF ACCOUNTS WITHOUT A PERSON
        if not 'person' in account_info:
            logger.error('Account %s has no person, skipping.' % account_info)
            return

        # At this point, we have enough to populate/update an account
        person = self.new_person
        ac = self.ac
        group = self.group

        person.clear()
        ac.clear()
        group.clear()

        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        default_creator_id = ac.entity_id
        default_expire_date = None
        const = self.const
        default_shell = const.posix_shell_bash

        bdb_account_type = const.externalid_bdb_account
        bdb_person_type = const.externalid_bdb_person
        bdb_source_type = const.system_bdb

        try:
            person.find_by_external_id(bdb_person_type,
                                       account_info['person'],bdb_source_type)
            logger.debug('Found person for account %s' % account_info['name'])
            #print 'Found person for account %s' % account_info['name']
        except Exception,e:
            logger.warning('Person with BDB-ID %s not found.' % account_info['person'])
            if verbose:
                print 'Person with BDB-ID %s not found.' % account_info['person']
                print account_info
            return
        person_entity = person.entity_id
        p_accounts = person.get_accounts()
        #print "%s has %s accounts" % (person_entity,str(len(p_accounts)))

        username_match = False
        # Find account-names and see if they match
        for account_id in p_accounts:
            ac.clear()
            if type(account_id) == tuple:
                account_id = int(account_id[0])
            try:
                account_id = int(account_id)
            except TypeError:
                logger.error('Account-id is not of type int or string. Value: %s' % account_id)
                if verbose:
                    print 'Account-id is not of type int or string. Value: %s' % account_id
                return
            ac.find(account_id)
            username = ac.get_account_name()
            if username == account_info['name']:
                username_match = True
                # Update expire_date
                if verbose:
                    print "Updating account %s on person %s" % (username,person_entity)
                logger.info('Updating account %s on person %s' % (username,person_entity))
                ac.expire_date = account_info.get('expire_date',None)
                if account_info.get('status','') == 1:
                    pass
                    #ac.set_account_type(ou_id,aff,priority=None) # need more data to use this
        if not username_match:
            first_name = person.get_name(const.system_cached, const.name_first)
            last_name = person.get_name(const.system_cached, const.name_last)
            ac.clear()
            # New account - check if the username is reserved 
            uname = None
            try:
                ac.find_by_name(account_info['name'])
            except Errors.NotFoundError:
                uname = account_info['name']
            except Errors.TooManyRowsError:
                pass
            if not uname:
                ac.clear()
                unames = ac.suggest_unames(domain=const.account_namespace, \
                                           fname=first_name, lname=last_name)
                uname = unames[0]
            np_type = None # this is a real account, not course,test,vendor etc
            if verbose:
                print "Adding new account %s on person %s" % (uname,person_entity)
            logger.info('Adding new account %s on person %s' % (uname,person_entity))
            #try:
            ac.clear()
            ac.populate(name=uname,
                        owner_type = const.entity_person,
                        owner_id = person_entity,
                        np_type = None,
                        creator_id = default_creator_id,
                        expire_date = default_expire_date)
            try:
                ac.write_db()
            except Exception,e:
                logger.error('write_db failed on user %s. Reason: %s' % (uname,str(e)))
                self.db.rollback()
                return
        #TBD: Check for primary group first
        #TBD: Add posix-info
        #TBD: Set passwords
        #grp_name = "posixgrp"
        #group.clear()
        #group.find_by_name(grp_name,domain=const.group_namespace)
        #try:
        #    ac.write_db()
        #except Exception,e:
        #    print "Exception caught while writing to db. Reason: %s" % str(e)
        #    print uname,const.entity_person,person_entity,np_type,default_creator_id,default_expire_date
        #    self.db.rollback()
        #    return
        try:
            if not dryrun:
                self.db.commit()
            if verbose:
                print "Changes on %s commited to Cerebrum" % account_info['name']
            logger.debug('Changes on %s commited to Cerebrum' % account_info['name'])
            num_accounts += 1
        except Exception,e:
            self.db.rollback()
            logger.error('Exception caught while trying to commit. Reason: %s' % str(e))
            if verbose:
                print 'Exception caught while trying to commit. Reason: %s' % str(e)
            return
            

    def sync_accounts(self):
        """
        This method synchronizes all BDB accounts into Cerebrum.
        """
        global num_accounts,verbose
        if verbose:
            print "Fetching accounts from BDB"
        accounts = self.bdb.get_accounts()

        for account in accounts:
            self.logger.debug('Syncronizing %s' % account['name'])
            self._sync_account(account)
        print "%s accounts added or updated in sync_accounts." % str(num_accounts)
        return

def usage():
    print """
    Usage: %s <options>

    Available options:

        --people    (-p)
        --group     (-g)
        --account   (-a)
        --verbose   (-v)
        --help      (-h)

    """ % sys.argv[0]
    sys.exit(0)

def main():
    global verbose,dryrun
    opts,args = getopt.getopt(sys.argv[1:],
                    'dpgavh',
                    ['dryrun','people','group','account','verbose','help'])

    sync = BDBSync()
    for opt,val in opts:
        if opt in ('-h','--help'):
            usage()
        elif opt in ('-p','--people'):
            sync.sync_persons()
        elif opt in ('-a','--account'):
            sync.sync_accounts()
        elif opt in ('-g','--group'):
            sync.sync_groups()
        elif opt in ('-v','--verbose'):
            verbose = True
        elif opt in ('-d','--dryrun'):
            dryrun = True
        else:
            usage()

if __name__ == '__main__':
    main()

