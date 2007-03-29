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
        print "Getting persons from BDB"
        global ant_persons
        persons = self.bdb.get_persons()
        ant_persons = len(persons)
        self.logger.debug("Done fetching persons from BDB")
        for person in persons:
            self._sync_person(person)
        global missing_personnr,wrong_nss_checksum
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
        self.logger.info("Process %s" % person['id'])
        const = self.const
        new_person = self.new_person
        global num_persons
        global ant_persons

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
        self.db.commit()
        num_persons += 1
        self.logger.debug("Person %s written into Cerebrum." % person['id'])
        print "Person %s (%s/%s )written into Cerebrum." % (person['id'],num_persons,ant_persons)
        #except Exception,e:
        #    self.db.rollback()
        #    self.logger.error("Rolling back transaction.Reason: %s" % str(e))
        #    return
        
    def sync_ous(self):
        """
        This method is used to synchronize OUs from BDB with Cerebrum.
        """
        ous = self.bdb.get_ous()

        self.open_session()
        # Fetch necesseary objects from Spine
        start = time.time()
        result = util.find_ou_by_stedkode(config.conf.get('bdb-sync', 'ntnu_stedkode'), self.transaction)
        if not result:
            self.logger.error('Fatal: Unable to get NTNU OU from Cerebrum, aborting.')
            raise SystemExit
        elif len(result) > 1:
            self.logger.error('Fatal: Multiple OUs in Cerebrum with the same stedkode, aborting.')
            raise SystemExit
        self.ntnu_ou = result[0]
        self.persp_t = self.transaction.get_ou_perspective_type(config.conf.get('bdb-sync', 'ou_perspective'))
        self.id_t = self.transaction.get_entity_external_id_type(config.conf.get('bdb-sync', 'ext_id_type_fakultet'))
        self.source_t = self.transaction.get_source_system(config.conf.get('bdb-sync', 'source_system'))
        self.at_post = self.transaction.get_address_type('POST')

        # Run the recursive OU synchronization
        self._sync_ous(self.ntnu_ou, ous)
        self.close_session()
        self.logger.info('OUs synchronized in %s seconds.' % (time.time() - start))

    def _sync_ous(self, spine_parent, ous):
        for ou in ous:
            if 'stedkode' in ou:
                spine_ous = util.find_ou_by_stedkode(ou['stedkode'], self.transaction)
                if len(spine_ous) > 1:
                    self.logger.error('Multiple OUs in Spine with the same stedkode, aborting synchronization!')
                    raise SystemExit
                elif len(spine_ous) == 1:
                    spine_ou = spine_ous[0]
                    self.logger.debug('OU %s found as %s in Cerebrum (stedkode %s == %s)' % (ou['name'], spine_ou.get_name(), ou['stedkode'], spine_ou.get_stedkode()))
                else:
                    # This OU was not in Cerebrum, so we add it
                    self.logger.info('%s (stedkode %s) is not in Cerebrum, adding it.' % (ou['name'], ou['stedkode']))
                    args = [ou['name']] + list(util.stedkode_string_to_tuple(ou['stedkode'])[1:])
                    try:
                        spine_ou = self.transaction.get_commands().create_ou(*args)
                        spine_ou.set_acronym(ou['acronym'])
                    except SpineIDL.Errors.AlreadyExistsError:
                        self.logger.error('An OU in Spine already has the stedkode %s; %s not synchronized!' % (ou['stedkode'], ou['name']))
                    spine_ou.set_parent(spine_parent, self.persp_t)
                    if ou['postal_address'] or ou['postal_code'] or ou['postal_city']:
                        try:
                            address = spine_ou.get_address(self.at_post, self.source_t)
                        except SpineIDL.Errors.NotFoundError:
                            address = spine_ou.create_address(self.at_post, self.source_t)
                        if ou['postal_address']:
                            address.set_address_text(ou['postal_address'])
                        if ou['postal_code']:
                            address.set_postal_number(ou['postal_code'])
                        if ou['postal_city']:
                            address.set_city(ou['postal_city'])
            else:
                self.logger.error('%s has no stedkode in BDB, unable to synchronize.' % (ou['name']))

            if 'institutes' in ou:
                # Synchronize OUs with this OU as parent
                self._sync_ous(spine_ou, ou['institutes'])

    def sync_groups(self):
        """
        This method synchronizes all BDB groups into Cerebrum.
        """
        groups = self.bdb.get_groups()
        self.open_session()
        commands = self.transaction.get_commands()
        self.bdb_group_id_t = self.transaction.get_entity_external_id_type(config.conf.get('bdb-sync', 'ext_id_type_group'))
        self.source_t = self.transaction.get_source_system(config.conf.get('bdb-sync', 'source_system'))


        for group in groups:
            if not 'name' in group:
                self.logger.error("Group %s has no name, skipping." % group)
                continue
            try:
                spine_group = commands.get_entity_with_external_id(str(group['id']), self.bdb_group_id_t, self.source_t)
                self.logger.debug('Group %s matched on BDB ID.' % group)
            except SpineIDL.Errors.NotFoundError:
                spine_group = commands.create_group(group['name'])
            spine_group.set_name(group['name'])
            spine_group.set_description(group['description'])
            if not spine_group.is_posix():
                spine_group.promote_posix()
            spine_group.set_posix_gid(group['gid'])
            # Set external ID from BDB
            try:
                ext_id = spine_group.get_external_id(self.bdb_group_id_t, self.source_t)
            except SpineIDL.Errors.NotFoundError:
                spine_group.set_external_id(str(group['id']), self.bdb_group_id_t, self.source_t)

        self.transaction.commit()

    def _sync_account(self,account_info):
        """Callback-function. To be used from sync_accounts-method."""
        global num_accounts
        logger = self.logger.er
        logger.debug("Callback for %s" % account_info['id'])

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
                print 'Account-id is not of type int or string. Value: %s' % account_id
                return
            ac.find(account_id)
            username = ac.get_account_name()
            if username == account_info['name']:
                username_match = True
                # Update expire_date
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
            self.db.commit()
            print "Changes on %s commited to Cerebrum" % account_info['name']
            logger.debug('Changes on %s commited to Cerebrum' % account_info['name'])
            num_accounts += 1
        except Exception,e:
            self.db.rollback()
            logger.error('Exception caught while trying to commit. Reason: %s' % str(e))
            print 'Exception caught while trying to commit. Reason: %s' % str(e)
            return
            

    def sync_accounts(self):
        """
        This method synchronizes all BDB accounts into Cerebrum.
        """
        global num_accounts
        print "Fetching accounts from BDB"
        accounts = self.bdb.get_accounts()
        logger = self.logger

        for account in accounts:
            if not 'name' in account:
                self.logger.error("Account %s has no name, skipping." % account)
                continue
            if not 'person' in account:
                # TODO: IMPLEMENT SYNC OF ACCOUNTS WITHOUT A PERSON
                logger.error('Account %s has no person, skipping.' % account)
            logger.debug('Syncronizing %s' % account['name'])
            self._sync_account(account)
        print "%s accounts added or updated in sync_accounts." % str(num_accounts)

def usage():
    print """
    Usage: %s <options>

    Available options:

        --ou
        --people
        --group
        --account
        --help

    """ % sys.argv[0]
    sys.exit(0)

def main():
    opts,args = getopt.getopt(sys.argv[1:],
                    'o:p:g:a:',
                    ['ou','people','group','account','help'])

    sync = BDBSync()
    for opt,val in opts:
        if opt in ('-h','--help'):
            usage()
        elif opt in ('-o','--ou'):
            sync.sync_ous()
        elif opt in ('-p','--people'):
            sync.sync_persons()
        elif opt in ('-a','--account'):
            sync.sync_accounts()
        elif opt in ('-g','--group'):
            sync.sync_groups()
        else:
            usage()

if __name__ == '__main__':
    main()

