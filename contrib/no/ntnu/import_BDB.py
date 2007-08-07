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
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum.modules import Email

import mx
import util
import getopt
import logging
import time
import os

import locale
locale.setlocale(locale.LC_ALL,'nb_NO')

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
        self.posix_group = PosixGroup.PosixGroup(self.db)
        self.posix_user = PosixUser.PosixUser(self.db)
        self.et = Email.EmailTarget(self.db)
        self.ea = Email.EmailAddress(self.db)
        self.ed = Email.EmailDomain(self.db)
        self.ev = Email.EmailVacation(self.db)
        self.ef = Email.EmailForward(self.db)
        self.logger = Factory.get_logger("console")
        self.logger = Factory.get_logger("syslog")
        self.logger.info("Starting import_BDB")
        self.ac.find_by_name('bootstrap_account')
        self.initial_account = self.ac.entity_id
        self.ac.clear()
        self.spread_mapping = self.get_spread_mapping()
        bdb_key = config.conf.get('bdb-sync','bdb_key')

    def get_spread_mapping(self):
        # TBD: complete the spread-mappings
        co = self.const
        s = {}
        s['ansatt'] =  int(co.Spread("user@%s" % 'ansatt'))
        s['chembio'] =  int(co.Spread("user@%s" % 'chembio'))
        s['fender'] =  int(co.Spread("user@%s" % 'fender'))
        s['fysmat'] =  int(co.Spread("user@%s" % 'fysmat'))
        s['hf'] =  int(co.Spread("user@%s" % 'hf'))
        s['idi'] =  int(co.Spread("user@%s" % 'idi'))
        s['ime'] =  int(co.Spread("user@%s" % 'ime'))
        s['iptansatt'] =  int(co.Spread("user@%s" % 'iptansatt'))
        s['ivt'] = int(co.Spread("user@%s" % 'ivt'))
        s['kybernetikk'] =  int(co.Spread("user@%s" % 'kybernetikk'))
        s['math'] = int(co.Spread("user@%s" % 'math'))
        s['norgrid'] =  int(co.Spread("user@%s" % 'norgrid'))
        s['norgrid-ny'] =  int(co.Spread("user@%s" % 'norgrid'))
        s['ntnu_ad'] =  int(co.Spread("user@%s" % 'ntnu_ad'))
        s['odin'] =  int(co.Spread("user@%s" % 'odin'))
        s['petra'] =  int(co.Spread("user@%s" % 'petra'))
        s['q2s'] =  int(co.Spread("user@%s" % 'q2s'))
        s['samson'] =  int(co.Spread("user@%s" % 'samson'))
        s['sol'] =  int(co.Spread("user@%s" % 'sol'))
        s['stud'] = int(co.Spread("user@%s" % 'stud'))
        s['studmath'] =  int(co.Spread("user@%s" % 'studmath'))
        s['ubit'] =  int(co.Spread("user@%s" % 'ubit'))
        s['ansoppr'] =  int(co.Spread("user@%s" % 'ansoppr'))
        s['oppringt'] =  int(co.Spread("user@%s" % 'oppringt'))
        s['cyrus_imap'] =  int(co.Spread("user@%s" % 'cyrus_imap'))
        s['test2'] =  int(co.Spread("user@%s" % 'test2'))
        s['nav'] =  int(co.Spread("user@%s" % 'nav'))
        s['itil_cm'] =  int(co.Spread("user@%s" % 'itil_cm'))
        s['lisens'] =  int(co.Spread("user@%s" % 'lisens'))
        s['kalender'] =  int(co.Spread("user@%s" % 'kalender'))
        s['vm'] =  int(co.Spread("user@%s" % 'vm'))
        s['itea'] =  int(co.Spread("user@%s" % 'itea'))
        s['pride'] =  int(co.Spread("user@%s" % 'pride'))
        s['hflinux'] =  int(co.Spread("user@%s" % 'hflinux'))
        s['ipt_soil'] =  int(co.Spread("user@%s" % 'ipt_soil'))
        s['kerberos'] = int(co.Spread("user@%s" % 'kerberos'))
        return s

    def sync_vacation(self):
        """Not implemented yet"""
        vacations = self.bdb.get_vacations()
        for vacation in vacations:
            _sync_vacation(vacation)
        return

    def _sync_vacation(self,vac):
        global dryrun,verbose
        const = self.const
        person = self.new_person
        person.clear()
        ev = self.ev
        ev.clear()
        ac = self.ac
        ac.clear()
        try:
            person.find_by_external_id(const.externalid_bdb_person,vac['person'])
        except Errors.NotFoundError:
            return

        # For this person, we need to find an EmailTarget, but to get that, we need an account
        account = person.get_primary_account()
        if not account:
            return
            # FIXME lookup other accounts
        ac.find(account)
        try:
            ev.find_by_entity(ac.entity_id)
        except Errors.NotFoundError:
            # No EmailTarget for this Entity
            return
        except Errors.TooManyRowsError:
            # Narrow down the search.. how?
            return
        if dryrun:
            self.db.rollback()
        else:
            self.db.commit()
        return

    def _sync_forward(self,forward):
        global dryrun
        # This method to be called from sync_persons, so person.entity_id should
        # already be set.
        person = self.new_person
        account = self.ac
        const = self.const
        fwd = self.ef
        fwd.clear()
        # See if a forward is already set.
        try:
            fwd.find_by_entity(person.entity_id)
            fwd.delete()
        except Errors.NotFoundError:
            pass
        fwd.populate(type=const.email_target_forward, entity_id=person.entity_id, entity_type=const.entity_person)
        fwd.writedb()
        if dryrun:
            fwd.rollback()
        else:
            fwd.commit()
        return

    def sync_affiliations(self):
        self.logger.debug("Getting affiliations from BDB...")
        self.aff_map = {}
        self.aff_map[1] = self.const.affiliation_student
        self.aff_map[2] = self.const.affiliation_ansatt
        self.aff_map[3] = self.const.affiliation_ansatt
        self.aff_map[4] = self.const.affiliation_manuell_ekst_stip
        self.aff_map[5] = self.const.affiliation_manuell_annen
        self.aff_map[7] = self.const.affiliation_manuell_emeritus
        self.aff_map[9] = self.const.affiliation_manuell_alumni
        self.aff_map[12] = self.const.affiliation_manuell_annen
        global verbose,dryrun
        if verbose:
            print "Getting affiliations from BDB"
        affiliations = self.bdb.get_affiliations()
        for affiliation in affiliations:
            self._sync_affiliation(affiliation)
        return

    def _sync_affiliation(self,aff):
        #aff is a dict with keys. aff['person'] is the bdb-external-id which can be found
        #as an externalid on persons in Cerebrum. We use this to connect affiliations and
        #persons.
        global dryrun,verbose
        self.logger.info("Process affiliation for %s" % aff['person'])
        if verbose:
            print "Process affiliation for bdb-person: %s" % aff['person']

        const = self.const
        person = self.new_person
        person.clear()
        ou = self.ou
        ou.clear()

        try: 
            person.find_by_external_id(const.externalid_bdb_person,aff['person'])
            self.logger.debug("Got match on bdb-id as entity_externalid using %s" % aff['person'])
            if verbose:
                print "Got match on bdb-id as entity_externalid using %s" % aff['person']
        except Errors.NotFoundError:
            self.logger.error("Got no match on bdb-id as entity_externalid using %s" % aff['person'])
            if verbose:
                print "Error: Got no match on bdb-id as entity_externalid using %s" % aff['person']
            return

        # Convert codes to IDs,type and status
        _oucode =  str(aff['ou_code'])
        faknr = _oucode[:2]
        instituttnr = _oucode[2:4]
        gruppenr = _oucode[4:6]

        #Search up the entity-id for this OrgUnit
        try:
            ou.find_stedkode(faknr,instituttnr,gruppenr,cereconf.DEFAULT_INSTITUSJONSNR)
            if verbose:
                print "Got match on stedkode %s bdb-person: %s" % (_oucode,aff['person'])
        except Errors.NotFoundError:
            if verbose:
                print "Got no match on stedkode %s bdb-person: %s" % (_oucode,aff['person'])
            self.logger.error("Got no match on stedkode %s for bdb-person: %s" % (_oucode,aff['person']))
            return 

        aff_type = self.aff_map[aff['aff_type']]
        aff_status = const.affiliation_tilknyttet

        person.populate_affiliation(const.system_bdb, ou.entity_id, aff_type, aff_status) 

        if dryrun:
            self.db.rollback()
            if verbose:
                print "Dryrun set. Rolling back changes for entity %s" % person.entity_id
        else:
            self.db.commit()
            if verbose:
                print "Commiting affiliation to database for entity %s" % person.entity_id
        return

    def sync_persons(self):
        self.logger.debug("Getting persons from BDB...")
        global ant_persons,verbose,dryrun
        if verbose:
            print "Getting persons from BDB"
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
        year,month,day = person.get("birth_date").split('-')
        year = year[2:]
        # Format fnr correctly
        fnr = "%02d%02d%02d%05d" % (int(day),int(month),int(year),int(pnr))
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
            new_person.find_by_external_id(const.externalid_bdb_person,person['id'])
            self.logger.debug("Got match on bdb-id as entity_externalid using %s" % person['id'])
        except Errors.NotFoundError:
            # Search on nssn failed. Search on bdb-external-id instead
            try:
                new_person.find_by_external_id(const.externalid_fodselsnr, fnr)
            except Errors.TooManyRowsError:
                # Person matches too many external-Ids of same value from different sources
                # Narrow down the search
                new_person.find_by_external_id(const.externalid_fodselsnr, \
                                               fnr,const.system_lt)
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
        try:
            new_person.populate_name(const.name_first, person['first_name'])
            new_person.populate_name(const.name_last, person['last_name'])
        except ValueError,ve:
            fname = person['first_name'] or ''
            sname = person['last_name'] or ''
            self.logger.error("ValueError when trying to populate names for %s. Reason: %s" % (fnr,str(ve)))
            self.db.rollback()
            return

        if person.get('tittel_personlig'):
            new_person.populate_name(const.name_personal_title,
                                     person['tittel_personlig'])
        # TBD: rewrite
        np = new_person
        np.affect_external_id(const.system_bdb,
                              const.externalid_fodselsnr, 
                              const.externalid_bdb_person)
        np.populate_external_id(const.system_bdb,
                                const.externalid_bdb_person,
                                person['id'])
        np.populate_external_id(const.system_bdb,
                                const.externalid_fodselsnr,
                                fnr)
        # Write to database and commit transaction
        try:
            new_person.write_db()
        except self.db.IntegrityError,ie:
            self.logger.warning("This External-ID is already in use from this source_system. Clean up please. BDB-person: %s" % person['id'])
            self.db.rollback()
            return
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

    def _is_posix_group(self,group):
        res = False
        if 'gid' in group:
            res = True
        return res

    def _validate_group(self,group):
        res = True
        if not 'name' in group:
            self.logger.error("Group %s is invalid, has no name." % grp['id'])
            res = False
        return res
        
    def sync_groups(self):
        """
        This method synchronizes all BDB groups into Cerebrum.
        """
        global verbose,dryrun
        groups = self.bdb.get_groups()
        posix_group = self.posix_group
        group = self.group
        creator_id = self.initial_account
        const = self.const

        def _clean_name(name):
            name = name.replace('-','_')
            name = name.replace(' ','_')
            name = name.lower()
            return name

        for grp in groups:
            posix_group.clear()
            group.clear()
            if not self._validate_group(grp):
                continue
            grp['name'] = _clean_name(grp['name'])
            if self._is_posix_group(grp):
                try:
                    posix_group.find_by_name(grp['name'])
                    if verbose:
                        print "Updating group %s" % grp['name']
                    _has_changed = False
                    _gid = posix_group.posix_gid
                    if posix_group.posix_gid != grp['gid']:
                        posix_group.posix_gid = grp['gid']
                        _has_changed = True
                    if not posix_group.has_spread(const.spread_ntnu_group):
                        posix_group.add_spread(const.spread_ntnu_group)
                    if _has_changed:
                        posix_group.write_db()
                    if dryrun:
                        self.db.rollback()
                    else:
                        self.db.commit()
                    continue
                except Errors.NotFoundError:
                    posix_group.populate(creator_id, visibility=self.const.group_visibility_all,\
                                         name=grp['name'], description=grp['description'], \
                                         gid=grp['gid'])
                    if not posix_group.has_spread(const.spread_ntnu_group):
                        posix_group.add_spread(const.spread_ntnu_group)
                    try:
                        posix_group.write_db()
                    except self.db.IntegrityError,ie: 
                        self.logger.error("Integrity error catched on bdb group %s. Reason: %s" % \
                                         (grp['name'],str(ie)))
                        if verbose:
                            print "Integrity error catched on bdb group %s. Reason: %s" % \
                                    (grp['name'],str(ie))
                        continue
                    if verbose:
                        print "PosixGroup %s written to db" % grp['name']
            else:
                try:
                    group.find_by_name(grp['name'])
                    if verbose:
                        print "Group %s already exists." % grp['name']
                    continue
                except Errors.NotFoundError:
                    group.populate(creator_id,visibility=const.group_visibility_all,\
                                   name=grp['name'], description=grp['description'])
                    group.write_db()
                    if verbose:
                        print "Group %s written to db" % grp['name']
                except Errors.IntegrityError,ie:
                    self.logger.error("Integrity error catched on bdb group %s. Reason: %s" % \
                                       (grp['name'],str(ie)))
                    continue
            if dryrun:
                self.db.rollback()
                if verbose:
                    print "Dryrun. Adding group rolled back" 
            else:
                self.db.commit()
                if verbose:
                    print "Adding group commited"

    def _promote_posix(self,account_info):
        # TBD: rewrite and consolidate this method and the method of same name
        #      from process_employees.py
        global num_accounts, verbose, dryrun
        res = True
        group = self.group
        posix_user = self.posix_user
        posix_group = self.posix_group
        ac = self.ac

        ac.clear()
        posix_user.clear()
        posix_group.clear()

        try:
            ac.find(account_info['account_id'])
        except Errors.NotFoundError:
            if verbose:
                print "Account with id %s not found. Cannot promote." % account_info['account_id']
            return False

        uid = account_info.get('unix_uid',posix_user.get_free_uid())
        shell = account_info.get('shell',self.const.posix_shell_bash)

        try:
            posix_group.find_by_gid(account_info.get('unix_gid'))
        except Errors.NotFoundError:
            grp_name = account_info.get('group_name','posixgroup')
            posix_group.find_by_name(grp_name,domain=self.const.group_namespace)
            pass

        try:
            posix_user.populate(uid,posix_group.entity_id, None, shell, parent=ac)
            posix_user.write_db()
            if verbose:
                print "Account %s with posix-uid %s promoted to posix." % (account_info['username'],uid)
        except Exception,e:
            if verbose:
                print "Error during promote_posix. Error was: %s" % str(e)
            self.logger.error("Error during promote_posix. Error was: %s" % str(e))
            res = False
        return res

    def _sync_account(self,account_info,update_password_only=False):
        """Callback-function. To be used from sync_accounts-method."""
        global num_accounts,verbose,dryrun
        logger = self.logger
        logger.debug("Callback for %s" % account_info['id'])

        def _get_password(_account):
            return _account.get('password2')

        def _is_posix(_account):
            res = True
            if not 'unix_uid' in _account:
                res = False
            if not 'unix_gid' in _account:
                res = False
            return res

        def _is_primary(_account):
            if _account.get('status') == 1:
                return True
            else:
                return False

        def _validate(_account):
            res = True
            if not 'name' in account_info:
                self.logger.error("Account %s has no name, skipping." % account_info)
                res = False
            return res

        # TODO: IMPLEMENT SYNC OF ACCOUNTS WITHOUT A PERSON
        if not 'person' in account_info:
            logger.error('Account %s has no person, skipping.' % account_info)
            return

        if not _validate(account_info):
            return

        # At this point, we have enough to populate/update an account
        person = self.new_person
        ac = self.ac
        posix_user = self.posix_user
        posix_group = self.posix_group
        group = self.group

        person.clear()
        ac.clear()
        posix_user.clear()
        posix_group.clear()
        group.clear()


        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        default_creator_id = ac.entity_id
        default_expire_date = None
        const = self.const
        default_shell = const.posix_shell_bash

        bdb_account_type = const.externalid_bdb_account
        bdb_person_type = const.externalid_bdb_person
        bdb_source_type = const.system_bdb

        ac.clear()
        try:
           ac.find_by_name(account_info.get('name'))
        except Errors.NotFoundError:
           return
        _pwd = _get_password(account_info)
        if _pwd is None:
            return
        ac.set_password(_pwd)
        ac.write_db()
        if update_password_only:
            logger.debug('Updating password for %s' % account_info.get('name'))
            try:
                self.db.commit()
            except Exception,e:
                logger.warning('Error occured when updating password for user %s. Reason: %s' % (account_info.get('username'),str(e)))
            return

        try:
            person.find_by_external_id(bdb_person_type,
                                       account_info['person'],bdb_source_type)
            logger.debug('Found person for account %s' % account_info['name'])
        except Exception,e:
            logger.warning('Person with BDB-ID %s not found.' % account_info['person'])
            if verbose:
                print 'Person with BDB-ID %s not found.' % account_info['person']
            return
        person_entity = person.entity_id
        p_accounts = person.get_accounts()

        username_match = False
        # Find account-names and see if they match
        for account_id in p_accounts:
            ac.clear()
            account_id = account_id[0]

            try:
                account_id = int(account_id)
            except TypeError:
                print "id is of type: %s" % type(account_id)
                logger.error('Account-id is not of type int or string. Value: %s' % account_id)
                if verbose:
                    print 'Account-id is not of type int or string. Value: %s' % account_id
                return
            ac.find(account_id)
            username = ac.get_account_name()
            if username == account_info['name']:
                # If we got a match on username, we'll update expire-date and possibly 
                # promote the account to posix if we have enough information
                username_match = True
                logger.info('Updating account %s on person %s' % (username,person_entity))
                ac.expire_date = account_info.get('expire_date',None)
                """
                if _is_primary(account_info):
                    # Fetch the affiliations from the person-object
                    affs = person.get_affiliations()
                    # FIXME: Make a wrapper-call to auto-prioritize affiliations
                    ac.set_account_type(ou_id, affiliation, priority)
                    ac.write_db()
                """
                if _is_posix(account_info):
                    try:
                        posix_user.clear()
                        posix_user.find(account_id)
                    except Errors.NotFoundError:
                        # posix-search returned NotFound. promote to posix
                        account_info['account_id'] = ac.entity_id
                        if self._promote_posix(account_info):
                            logger.info("Account %s promoted to posix" % ac.entity_id)
                        else:
                            logger.info("Account %s not promoted to posix" % ac.entity_id)
                            self.db.rollback()
                    else:
                        if verbose:
                            print "Account %s is already posix. Updating posix-uid/gid." % account_id
                        self.logger.info("Account %s is already posix. Updating" % account_id)
                        _has_changed = False
                        _uid = posix_user.posix_uid
                        _gid = posix_user.gid_id

                        if posix_user.posix_uid != account_info['unix_uid']:
                            posix_user.posix_uid = account_info['unix_uid']
                            _has_changed = True

                        posix_group.clear()
                        try:
                            posix_group.find(posix_user.gid_id)
                        except Errors.NotFoundError:
                            posix_group.find_by_name('posixgroup')

                        if posix_group.posix_gid != account_info['unix_gid']:
                            posix_group.clear()
                            # Denne kan kaste exception hvis unix_gid ikke finnes
                            try:
                                posix_group.find_by_gid(account_info['unix_gid'])
                            except Errors.NotFoundError:
                                posix_group.find_by_name('posixgroup')
                            posix_user.gid_id = posix_group.entity_id
                            _has_changed = True

                        if _has_changed:
                            try:
                                posix_user.write_db()
                            except self.db.IntegrityError,ie:
                                uid,gid,name = account_info['unix_uid'],account_info['unix_gid'],account_info['name']
                                logger.error('Uid/gid (%s/%s) already in use for account %s' % (uid,gid,name))
                                self.db.rollback()
                                return
                            except Exception,e:
                                print "Exception caught. at line 666"
                                print str(e)
                                sys.exit()
                        else:
                            self.db.rollback()
                    #except self.db.IntegrityError,ie:
                    #    logger.error("Account %s has changes, but database threw it back. Reason: %s" % (account_id,str(ie)))
                    #    self.db.rollback()

        if not username_match:
            first_name = person.get_name(const.system_cached, const.name_first)
            last_name = person.get_name(const.system_cached, const.name_last)
            ac.clear()
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
            logger.info('Adding new account %s on person %s' % (uname,person_entity))
            if _is_posix(account_info):
                posix_user.clear()
                # Kan kaste exception
                posix_group.clear()
                try:
                    posix_group.find_by_gid(account_info['unix_gid'])
                except Errors.NotFoundError:
                    posix_group.find_by_name('posixgroup')
                posix_user.populate(posix_uid=account_info['unix_uid'],
                        gid_id=posix_group.entity_id,
                        gecos=posix_user.simplify_name(person.get_name(const.system_cached,const.name_full),as_gecos=1),
                        shell=const.posix_shell_bash,
                        name = uname,
                        owner_type = const.entity_person,
                        owner_id = person_entity,
                        creator_id = default_creator_id,
                        np_type = None,
                        expire_date=account_info['expire_date'],
                        parent=None)
                try:
                    posix_user.write_db()
                except Exception,e:
                    logger.error('write_db failed on user %s. Reason: %s' % (uname,str(e)))
                    self.db.rollback()
                    return
            else:
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
                
        try:
            if ac.entity_id:
                print "updating password on account"
                ac.set_password(_get_password(account_info))
                ac.write_db()
            elif posix_user.entity_id:
                print "updating password on account"
                posix_user.set_password(_get_password(account_info))
                posix_user.write_db()
            if dryrun:
                self.db.rollback()
                logger.debug('Rollback called. Changes omitted.')
            else:
                self.db.commit()
                logger.debug('Changes on %s commited to Cerebrum' % account_info['name'])
                num_accounts += 1
        except Exception,e:
            self.db.rollback()
            logger.error('Exception caught while trying to commit. Rolling back. Reason: %s' % str(e))
            return

    def sync_accounts(self,username=None,password_only=False):
        """
        This method synchronizes all BDB accounts into Cerebrum.
        """
        global num_accounts,verbose,dryrun
        if verbose:
            print "Fetching accounts from BDB"

        accounts = self.bdb.get_accounts(username)

        for account in accounts:
            self.logger.debug('Syncronizing %s' % account['name'])
            self._sync_account(account,password_only)
        print "%s accounts added or updated in sync_accounts." % str(num_accounts)
        return

    def _sync_spread(self,spread):
        global verbose,dryrun
        s_map = self.spread_mapping
        ac = self.ac
        ac.clear()
        if not spread.has_key('username'):
            print "Key 'username' missing from spread-dict. %s" % spread
            return
        try:
            ac.find_by_name(spread.get('username'))
        except Errors.NotFoundError,e:
            if verbose:
                print "Account with name %s not found. Continuing." % spread['username']
            self.logger.warn("Account with name %s not found. Continuing." % spread['username'])
            return

        spreads = ac.get_spread()

        # We need a match between cerebrum-spreads and bdb-spreads
        bdbspread = spread.get('spread_name')
        if not bdbspread:
            return

        c_spread = s_map.get(bdbspread)

        for spread in spreads:
            if c_spread in spread:
                # Account already has this spread
                return

        if c_spread:
            try:
                ac.add_spread(c_spread)
            except Errors.NotFoundError,nfe:
                if verbose:
                    print "Failed when adding spread. Reason: %s" % str(nfe)
                self.logger.error("Failed when adding spread. Reason: %s" % str(nfe))
                self.db.rollback()
                return
            except Errors.RequiresPosixError,rpe:
                if verbose:
                    print "Spread %s propably require posix, but %s isn't. " % (c_spread,ac.entity_id)
            except self.db.IntegrityError,ie:
                self.logger.error("Integrity-Error caught. Reason: %s" % (str(ie)))
                self.db.rollback()
                return
        else:
            print spread
            username = spread.get('username')
            s_name = spread.get('spread_name')
            if verbose:
                print "Found no matching spread %s for user %s" % (s_name,username)
            self.logger.warning("Found no matching spread %s for user %s" % (s_name,username))
        if not dryrun:
            if verbose:
                print "Commiting changes to database"
            self.db.commit()
        else:
            if verbose:
                print "Rollback changes in database"
            self.db.rollback()
        return

    def sync_spreads(self):
        """This method syncronizes all spreads on accounts from BDB into Cerebrum."""
        global verbose,dryrun
        if verbose:
            print "Fetching accounts with spreads from BDB"
        spreads = self.bdb.get_account_spreads()
        for spread in spreads:
            self._sync_spread(spread)
        return

    def sync_email_domains(self):
        print "Fetching email-domains"
        global verbose, dryrun
        domains = self.bdb.get_email_domains()
        for domain in domains:
            self._sync_email_domain(domain)
        if dryrun:
            if verbose:
                print "Email-domains rollback."
            self.db.rollback()
        else:
            if verbose:
                print "Commiting changes to email_domains"
            self.db.commit()
        return

    def _sync_email_domain(self,domain):
        global verbose, dryrun
        if verbose:
            print "Syncronizing %s" % domain.get('email_domain')
        ed=Email.EmailDomain(self.db)
        ed.clear()
        try:
            ed.find_by_domain(domain.get('email_domain'))
            if verbose:
                print "EmailDomain %s already exists." % domain.get('email_domain')
        except Errors.NotFound:
            description = "Domain handled by spread %s" % domain.get('spread_name')
            if verbose:
                print "Adding EmailDomain %s" % domain.get('email_domain')
            ed.populate(domain.get('email_domain'),description)
            ed.write_db()
        return


    def sync_email_addresses(self):
        global dryrun,verbose
        if verbose:
            print "Fetching email addresses from BDB"
        addresses = self.bdb.get_email_addresses()
        for address in addresses:
            self._sync_email_address(address)
        if dryrun:
            if verbose:
                "Rolling back changes on email addresses"
            self.db.rollback()
        else:
            if verbose:
                "Commiting changes on email addresses"
            self.db.commit()
        return

    def _sync_email_address(self,address):
        global verbose
        if verbose:
            print "Processing %s@%s" % (address.get('email_address'),address.get('email_domain_name'))

        person = self.new_person
        ac = self.ac
        et = self.et
        ea = self.ea
        ed = self.ed
        co = self.const

        person.clear()
        ac.clear()
        et.clear()
        ed.clear()
        ea.clear()

        try:
            ac.find_by_name(address.get('username'))
        except Errors.NotFoundError:
            pass

        if not hasattr(ac,'entity_id'):
            try:
                person.find_by_external_id(co.externalid_bdb_person, address.get('id'), \
                                           co.system_bdb, co.entity_person)
            except Errors.NotFoundError:
                # aye.. neither username or person matches.. 
                return
            try:
                ac.clear()
                ac.find(person.get_primary_account())
            except Errors.NotFoundError:
                # Person has no primary.. what to do?
                return

        # Does the account have an EmailTarget?
        try:
            et.find_by_entity(ac.entity_id)
        except Errors.NotFoundError:
            # Populate a new EmailTarget for this Account
            et.populate(co.email_target_account, ac.entity_id, ac.entity_type)
            # Need to write it to the db before we can use it.
            op = et.write_db()

        # Does this domain exist in Cerebrum?
        try:
            ed.find_by_domain(address.get('email_domain_name'))
        except Errors.NotFoundError:
            self.logger.error("Domain %s not found in Cerebrum." % address.get('email_domain_name'))
            return

        try:
            ea.populate(address.get('email_address'), ed.email_domain_id, et.email_target_id)
            ea.write_db()
        except self.db.IntegrityError,ie:
            if verbose:
                print "Address %s@%s already exists" % (address.get('email_address'),address.get('email_domain_name'))
            self.db.rollback()
        return

def usage():
    print """
    Usage: %s <options>

    Available options:

        --dryrun    (-d) Does not commit changes to Cerebrum
        --people    (-p) Syncronize persons
        --group     (-g) Syncronise posixGrourp
        --account   (-a) Syncronize posixAccounts
        --spread    (-s) Synronize account-spreads
        --affiliations (-t) Syncronize affiliations on persons
        --email_domains  Syncronize email-domains
        --email_address  Syncronize email-addresses
        --verbose   (-v) Prints debug-messages to STDOUT
        --help      (-h)

        --personid       the BDB-id or the nssn of the person
        --accountname    the username of the user to import from BDB
        --password-only  To be used only with syncronization of all accounts or a given accountname

    """ % sys.argv[0]
    sys.exit(0)

def main():
    global verbose,dryrun
    opts,args = getopt.getopt(sys.argv[1:],
                    'dptgasvh',
                    ['password-only','personid=','accountname=','spread','email_domains','email_address','affiliations','dryrun','people','group','account','verbose','help'])

    sync = BDBSync()
    if (('--password-only','')) in opts:
        _password_only = True
    else:
        _password_only = False
    for opt,val in opts:
        if opt in ('-h','--help'):
            usage()
        elif opt in ('-v','--verbose'):
            verbose = True
        elif opt in ('-d','--dryrun'):
            dryrun = True
        elif opt in ('--personid',):
            # Konverter val til noe saklig
            print "Syncronizing BDBPerson: %s" % val
            if len(val) == 11:
                person = sync.bdb.get_persons(fdato=val[:6],pnr=val[6:])
            else:
                person = sync.bdb.get_persons(bdbid=val) 
            # person is now a list of one element (dict)
            if len(person) == 1:
                sync._sync_person(person[0])
            else:
                print "Too many persons match criteria. Exiting.."
            sys.exit()
        elif opt in ('-p','--people'):
            sync.sync_persons()
        elif opt in ('-g','--group'):
            sync.sync_groups()
        elif opt in ('-a','--account'):
            sync.sync_accounts(password_only=_password_only)
        elif opt in ('-s','--spread'):
            sync.sync_spreads()
        elif opt in ('-t','--affiliations'):
            sync.sync_affiliations()
        elif opt in ('--email_domains',):
            sync.sync_email_domains()
        elif opt in ('--email_address',):
            sync.sync_email_addresses()
        elif opt in ('--password-only',):
            accounts = sync.bdb.get_accounts(last=30) 
            for account in accounts:
                sync._sync_account(account,update_password_only=True)
        elif opt in ('--accountname',):
            print "Syncronizing account: %s" % val
            sync.sync_accounts(username=val,password_only=_password_only)
        else:
            usage()

if __name__ == '__main__':
    main()

