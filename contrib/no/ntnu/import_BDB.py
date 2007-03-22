#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import config
import sys
sys.path.append(config.conf.get('spine', 'client_sys_path'))
import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.ntnu import access_BDB

import util
import getopt
import logging
import time
import os
"""
"""

# Set the client encoding for the Oracle client libraries
os.environ['NLS_LANG'] = config.conf.get('bdb', 'encoding')
missing_personnr = 0
wrong_nss_checksum = 0

class BDBSync:
    def __init__(self):
        self.bdb = access_BDB.BDB()
        self.log = logging.getLogger('bdb-sync')
        self.db = Factory.get('Database')()
        self.db.cl_init(change_program='import_BDB')
        self.const = Factory.get('Constants')(self.db)
        self.ou = Factory.get('OU')(self.db)
        self.new_person = Factory.get('Person')(self.db)
        self.ac = Factory.get('Account')(self.db)
        self.logger = Factory.get_logger("console")
        self.logger.info("Starting import_BDB")

    def sync_vacation(self):
        """Not implemented yet"""
        pass

    def sync_forward(self):
        """Not implemented yet"""
        pass

    def sync_persons(self):
        self.log.debug("Getting persons from BDB...")
        print "Getting persons from BDB"
        persons = self.bdb.get_persons()
        self.log.debug("Done fetching persons from BDB")
        print "Done fetching persons from BDB"
        for person in persons:
            self._sync_person(person)
        # Commit and close session
        print "Done syncronizing persons"
        global missing_personnr,wrong_nss_checksum
        print "%s persons had missing personnumber" % missing_personnr
        print "%s persons had bad checksum on personnumber" % wrong_nss_checksum

    def _sync_person(self, person):
        global missing_personnr
        global wrong_nss_checksum
        logger = self.logger
        logger.info("Process %s" % person['id'])
        new_person = self.new_person
        new_person.clear()
        if not person.get("person_number",""):
            logger.warn("Ikke noe personnr for %s" % person['id'])
            missing_personnr += 1
            return
        pnr = str(person['person_number'])
        year,month,day = person['birth_date'].split('-')
        year = year[2:]
        fnr = day+month+year+pnr
        const = self.const
        gender = const.gender_male
        try:
            if(fodselsnr.er_kvinne(fnr)):
                gender = const.gender_female
        except: 
            #except InvalidFnrError,ifn:
            logger.warn("Person %s has wrong checksum in their nssn" % person['id'])
            wrong_nss_checksum += 1
            return
        (year,month,day) = fodselsnr.fodt_dato(fnr)
        try:
            new_person.find_by_external_id(const.externalid_fodselsnr, fnr)
        except Errors.NotFoundError:
            pass
        except Errors.TooManyRowsError:
            try:
                new_person.find_by_external_id(const.externalid_fodselsnr,fnr,const.system_slp)
            except Errors.NotFoundError:
                pass
        if (person.get('fornavn', ' ').isspace() or
            person.get('etternavn',' ').isspace()):
            logger.warn("Ikke noe navn for %s" % fnr)
            return

        new_person.populate(mx.DateTime.Date(year,month,day), gender)
        new_person.affect_names(const.system_slp,const.name_fist,const.name_last,
                                const.name_personal_title)
        new_person.affect_external_id(const.system_slp,const.external_id_fodselsnr)
        new_person.populate_name(const.name_first, person['fornavn'])
        new_person.populate_name(const.name_last, person['etternavn'])
        if person.get('tittel_personlig',''):
            new_person.populate_name(const.name_personal_title,\
                                     person['tittel_personlig'])
        new_person.populate_external_id(
                const.system_slp,const.externalid_fodselsnr,fnr)

        # If it's a new person, we need to call write_db()( to have an entity_id
        # assigned to it
        op = new_person.write_db()
        print "Skreiv person %s til Cerebrum." % person['id']
        logger.debug("Skreiv person %s til Cerebrum." % person['id'])

        
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
            self.log.error('Fatal: Unable to get NTNU OU from Cerebrum, aborting.')
            raise SystemExit
        elif len(result) > 1:
            self.log.error('Fatal: Multiple OUs in Cerebrum with the same stedkode, aborting.')
            raise SystemExit
        self.ntnu_ou = result[0]
        self.persp_t = self.transaction.get_ou_perspective_type(config.conf.get('bdb-sync', 'ou_perspective'))
        self.id_t = self.transaction.get_entity_external_id_type(config.conf.get('bdb-sync', 'ext_id_type_fakultet'))
        self.source_t = self.transaction.get_source_system(config.conf.get('bdb-sync', 'source_system'))
        self.at_post = self.transaction.get_address_type('POST')

        # Run the recursive OU synchronization
        self._sync_ous(self.ntnu_ou, ous)
        self.close_session()
        self.log.info('OUs synchronized in %s seconds.' % (time.time() - start))

    def _sync_ous(self, spine_parent, ous):
        for ou in ous:
            if 'stedkode' in ou:
                spine_ous = util.find_ou_by_stedkode(ou['stedkode'], self.transaction)
                if len(spine_ous) > 1:
                    self.log.error('Multiple OUs in Spine with the same stedkode, aborting synchronization!')
                    raise SystemExit
                elif len(spine_ous) == 1:
                    spine_ou = spine_ous[0]
                    self.log.debug('OU %s found as %s in Cerebrum (stedkode %s == %s)' % (ou['name'], spine_ou.get_name(), ou['stedkode'], spine_ou.get_stedkode()))
                else:
                    # This OU was not in Cerebrum, so we add it
                    self.log.info('%s (stedkode %s) is not in Cerebrum, adding it.' % (ou['name'], ou['stedkode']))
                    args = [ou['name']] + list(util.stedkode_string_to_tuple(ou['stedkode'])[1:])
                    try:
                        spine_ou = self.transaction.get_commands().create_ou(*args)
                        spine_ou.set_acronym(ou['acronym'])
                    except SpineIDL.Errors.AlreadyExistsError:
                        self.log.error('An OU in Spine already has the stedkode %s; %s not synchronized!' % (ou['stedkode'], ou['name']))
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
                self.log.error('%s has no stedkode in BDB, unable to synchronize.' % (ou['name']))

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
                self.log.error("Group %s has no name, skipping." % group)
                continue
            try:
                spine_group = commands.get_entity_with_external_id(str(group['id']), self.bdb_group_id_t, self.source_t)
                self.log.debug('Group %s matched on BDB ID.' % group)
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

    def sync_accounts(self):
        """
        This method synchronizes all BDB accounts into Cerebrum.
        """
        accounts = self.bdb.get_accounts()

        self.open_session()

        # Get necesseary objects from Spine
        commands = self.transaction.get_commands()
        self.source_t = self.transaction.get_source_system(config.conf.get('bdb-sync', 'source_system'))
        self.bdb_account_id_t = self.transaction.get_entity_external_id_type(config.conf.get('bdb-sync', 'ext_id_type_account'))
        self.bdb_person_id_t = self.transaction.get_entity_external_id_type(config.conf.get('bdb-sync', 'ext_id_type_person'))
        self.bdb_group_id_t = self.transaction.get_entity_external_id_type(config.conf.get('bdb-sync', 'ext_id_type_group'))
        self.bdb_pw_type_crypt = config.conf.get('bdb-sync', 'bdb_pw_type_crypt')
        self.bdb_pw_type_blowfish = config.conf.get('bdb-sync', 'bdb_pw_type_blowfish')
        self.pw_type_crypt_t = self.transaction.get_authentication_type(config.conf.get('bdb-sync', 'pw_type_crypt'))
        self.pw_type_blowfish_t = self.transaction.get_authentication_type(config.conf.get('bdb-sync', 'pw_type_blowfish'))

        # TODO: THIS IS A TEMPORARY HACK TO MAKE POSIX PROMOTES WORK. WE NEED TO GET THE SHELL FROM THE 'bruker' TABLE
        # IN BDB AND SET IT ACCORDINGLY, BUT THERE ARE ONLY 200ISH ENTRIES WITH SHELL != NULL...
        spine_shell = self.transaction.get_posix_shell(config.conf.get('bdb-sync', 'default_posix_shell'))

        for account in accounts:
            if not 'name' in account:
                self.log.error("Account %s has no name, skipping." % account)
                continue
            if not 'person' in account:
                # TODO: IMPLEMENT SYNC OF ACCOUNTS WITHOUT A PERSON
                self.log.error('Account %s has no person, skipping.' % account)
                continue
            if account['expire_date'] is None:
                expire_date = commands.get_date_none()
            else:
                try:
                    date = time.strptime(str(account['expire_date']), '%Y-%m-%d %H:%M:%S')
                    expire_date = commands.get_date(date.tm_year, date.tm_mon, date.tm_mday)
                except ValueError:
                    self.log.error('Cannot convert expire date %s, skipping account.' % account['expire_date'])
                    continue

            try:
                spine_account = commands.get_entity_with_external_id(str(account['id']), self.bdb_account_id_t, self.source_t)
                self.log.debug('Account %s matched on BDB ID.' % account)
                spine_account.set_expire_date(expire_date)
                spine_account.set_name(account['name'])
            except SpineIDL.Errors.NotFoundError:
                try:
                    spine_person = commands.get_entity_with_external_id(str(account['person']), self.bdb_person_id_t, self.source_t)
                except SpineIDL.Errors.NotFoundError:
                    self.log.error('Account owner with BDB ID %s not found in Cerebrum, skipping the account.' % account['person'])
                    continue
                spine_account = commands.create_account(account['name'], spine_person, expire_date)
                if 'creation_date' in account:
                    spine_account.set_description("Imported from BDB - Created " + str(account['creation_date']))
                else:
                    spine_account.set_description("Imported from BDB - Creation date unknown")
            # Set external ID from BDB
            try:
                ext_id = spine_account.get_external_id(self.bdb_account_id_t, self.source_t)
            except SpineIDL.Errors.NotFoundError:
                spine_account.set_external_id(str(account['id']), self.bdb_account_id_t, self.source_t)

            # Set UID
            if 'unix_uid' in account:
                if account['unix_uid'] == 0:
                    self.log.warning('Account %s has unix UID 0, not creating POSIX account!' % account)
                elif not spine_account.is_posix():
                    try:
                        if 'group' in account:
                            spine_group = commands.get_entity_with_external_id(str(account['group']), self.bdb_group_id_t, self.source_t)
                            spine_account.promote_posix(account['unix_uid'], spine_group, spine_shell)
                        else:
                            self.log.error('Primary group for account %s not set in BDB, although it has a UNIX uid.' % account)
                    except SpineIDL.Errors.NotFoundError:
                        self.log.error('Primary group or shell for account %s not found, cannot promote to POSIX account.' % account)
                else:
                    spine_account.set_posix_uid(account['unix_uid'])
            else:
                self.log.debug('Account %s has no UNIX uid, not promoting to POSIX.' % account)

            # Set password
            if 'password' in account:
                if not 'password_type' in account:
                    self.log.error('Account %s has a password, but not a password type. Password not set.' % account)
                elif str(account['password_type']) == self.bdb_pw_type_crypt:
                    spine_account.set_authentication(self.pw_type_crypt_t, account['password'])
                elif str(account['password_type']) == self.bdb_pw_type_blowfish:
                    spine_account.set_authentication(self.pw_type_blowfish_t, account['password'])
                else:
                    self.log.error('Account %s has unknown password type. Password not set.' % account)
            else:
                self.log.error('Account %s has no authentication data.' % account)

            # TODO: We need to add a shell, but this must be taken from the 'konto' table in BDB

        self.close_session()

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

