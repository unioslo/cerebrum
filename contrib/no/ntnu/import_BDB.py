#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import config
import sys
sys.path.append(config.conf.get('spine', 'client_sys_path'))
import Spine
import SpineIDL
import SpineClient
from Cerebrum.modules.no import fodselsnr
import util

import getopt
import cx_Oracle
import logging
import time
import os
"""
OUer fra BDB blir synkronisert på følgende måte:
    1. Fakulteter og institutter hentes ut fra BDB.
    2. Hvert fakultet blir forsøkt matchet mot Cerebrum på navn
        2.1 Hvert institutt blir forsøkt matchet på navn
        2.2 Hvis det fins institutter i BDB som ikke ligger i Cerebrum, og alle
            institutter i Cerebrum er matchet, har BDB ekstra institutter i forhold
            til kjernen for det aktuelle fakultetet. Hvis dette er tilfelle
            synkroniseres dataene rett inn fra BDB.
    3. Fakulteter fra BDB som ikke ble matchet blir ikke synkronisert inn i Cerebrum.
    4. Alle matchede fakulteter og institutter får sjekket sin BDB-id og
       oppdatert denne hvis den ikke stemmer.
 
"""

# Set the client encoding for the Oracle client libraries
os.environ['NLS_LANG'] = config.conf.get('bdb', 'encoding')

class BDB:
    def __init__(self):
        dsn = cx_Oracle.makedsn(config.conf.get('bdb', 'host'), int(config.conf.get('bdb', 'port')),
                config.conf.get('bdb', 'sid'))
        try:
            self.db = cx_Oracle.connect(dsn=dsn, user=config.conf.get('bdb', 'user'),
                password=config.conf.get('bdb', 'password'))
        except Exception,e:
            print "Error connecting to remote Oracle RDBMS. Reason: %s" % str(e)
            sys.exit()

    def get_persons(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT id, to_char(fodselsdato,'YYYY-MM-DD'), personnr, personnavn, fornavn, \
        etternavn, sperret FROM person" )
        bdb_persons = cursor.fetchall()
        persons = []
        # Convert to a dict
        for bp in bdb_persons:
            p = {}
            if bp[0]:
                p['id'] = bp[0]
            if bp[1]:
                p['birth_date'] = bp[1]
            if bp[2]:
                p['person_number'] = bp[2]
            #if bp[3]:
            #    p['full_name'] = bp[3]
            if bp[4] and bp[5]:
                    p['full_name'] = bp[4] + ' ' + bp[5]
            if bp[4]:
                p['first_name'] = bp[4]
            if bp[5]:
                p['last_name'] = bp[5]
            if bp[6]:
                p['sperret'] = bp[6]
            cursor.execute('SELECT p.phone_number, c.name FROM phone p, phone_categories c WHERE p.person=%s AND p.categorie=c.id' % p['id'])
            numbers = cursor.fetchall()
            for n in numbers:
                p[n[1]] = n[0]
            persons.append(p)
        cursor.close()
        return persons

    def get_accounts(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT passord_type, gruppe, person, brukernavn, siden, utloper, unix_uid, skall, standard_passord, id FROM bruker WHERE user_domain=1") # user_domain=1 is NTNU
        bdb_accounts = cursor.fetchall()
        accounts = []
        for ba in bdb_accounts:
            if not ba:
                break
            a = {}
            if ba[0]:
                a["password_type"] = ba[0]
            if ba[1]:
                a["group"] = ba[1]
            if ba[2]:
                a["person"] = ba[2]
            if ba[3]:
                a["name"] = ba[3]
            if ba[4]:
                a["creation_date"] = ba[4]
            if ba[5]:
                a["expire_date"] = ba[5]
            else:
                a['expire_date'] = None
            if ba[6]:
                a["unix_uid"] = ba[6]
            if ba[7]:
                a["shell"] = ba[7]
            if ba[8]:
                a["password"] = ba[8]
            if ba[9]:
                a["id"] = ba[9]

            accounts.append(a)
        cursor.close()
        return accounts

    def get_groups(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT id, navn, beskrivelse, unix_gid FROM gruppe")
        bdb_groups = cursor.fetchall()
        groups = []
        for bg in bdb_groups:
            g = {}
            g['id'] = bg[0]
            if bg[1]:
                g['name'] = bg[1]
            if bg[2]:
                g['description'] = bg[2]
            if bg[3]:
                g['gid'] = bg[3]
            groups.append(g)
        cursor.close()
        return groups

    def _get_ous(self, query, type):
        cursor = self.db.cursor()
        cursor.execute(query)
        bdb_ous = cursor.fetchall()
        ous = []
        for bo in bdb_ous:
            ou = {}
            ou['id'] = bo[0]
            ou['name'] = bo[1]
            ou['acronym'] = bo[2]
            ou['postal_address'] = bo[3]
            ou['postal_code'] = bo[4]
            ou['postal_city'] = bo[5]
            ou['stedkode'] = '194' + str(bo[6])
            if type == 'f':
                ou['stedkode'] = ou['stedkode'][:5] + '0000'
            elif type == 'i':
                ou['stedkode'] = ou['stedkode'][:7] + '00'
            ous.append(ou)
        cursor.close()
        return ous

    def get_ous(self):
        cursor = self.db.cursor()
        cursor.execute('SELECT UNIQUE f.id, f.navn, f.fork, f.postadresse, f.postnummer, f.poststed FROM fakultet f WHERE f.org_enhet=%s' % config.conf.get('bdb-sync', 'bdb_ntnu_ou'))
        bdb_ous = cursor.fetchall()
        ous = []
        for bdb_fak in bdb_ous:
            fak = {}
            fak['id'] = bdb_fak[0]
            fak['name'] = bdb_fak[1]
            fak['acronym'] = bdb_fak[2]
            fak['postal_address'] = bdb_fak[3]
            fak['postal_code'] = bdb_fak[4]
            fak['postal_city'] = bdb_fak[5]
            cursor.execute('SELECT UNIQUE k.kode FROM ksted k WHERE k.fakultet=%s' % fak['id'])
            try:
                stedkode = cursor.fetchall()[0][0]
                fak['stedkode'] = '194' + str(stedkode)[:2] + '0000'
            except IndexError:
                pass

            # Fetch all institutes
            cursor.execute('SELECT UNIQUE i.id, i.navn, i.fork, i.postadresse, i.postnummer, i.poststed FROM institutt i, fakultet f WHERE i.fakultet=%s' % fak['id'])
            bdb_insts = cursor.fetchall()
            insts = []
            for bdb_inst in bdb_insts:
                inst = {}
                inst['id'] = bdb_inst[0]
                inst['name'] = bdb_inst[1]
                inst['acronym'] = bdb_inst[2]
                inst['postal_address'] = bdb_inst[3]
                inst['postal_code'] = bdb_inst[4]
                inst['postal_city'] = bdb_inst[5]
                cursor.execute('SELECT UNIQUE k.kode FROM ksted k WHERE k.institutt=%s AND k.fakultet=%s' % (inst['id'], fak['id']))
                try:
                    stedkode = cursor.fetchall()[0][0]
                    inst['stedkode'] = '194' + str(stedkode)[:4] + '00'
                except IndexError:
                    pass

                insts.append(inst)
            fak['institutes'] = insts
            ous.append(fak)
        cursor.close()
        return ous

class BDBSync:
    def __init__(self):
        self.bdb = BDB()
        self.log = logging.getLogger('bdb-sync')
        try:
            self.spine = SpineClient.SpineClient(config=config.conf)
            self.connection = self.spine.connect() 
        except Exception,e:
            self.log.exception('Error trying to connect to Spine. Reason: %s' % str(e))
            print "Error trying to connect to Spine. Reason: %s" % str(e)
            sys.exit()

    def open_session(self):
        session = self.connection.login(config.conf.get('spine','login'),
                                   config.conf.get('spine','password'))
        self.transaction = session.new_transaction()
        self.session = session

    def close_session(self):
        self.transaction.commit()
        self.session.logout()

    def sync_vacation(self):
        """Not implemented yet"""
        pass

    def sync_forward(self):
        """Not implemented yet"""
        pass

    def sync_persons(self):
        self.log.debug("Getting persons from BDB...")
        persons = self.bdb.get_persons()
        self.open_session()
        # Get required types
        self.bdb_person_id_t = self.transaction.get_entity_external_id_type(config.conf.get('bdb-sync', 'ext_id_type_person'))
        self.birthno_t = self.transaction.get_entity_external_id_type('NO_BIRTHNO')
        self.first_name_t = self.transaction.get_name_type('FIRST')
        self.last_name_t = self.transaction.get_name_type('LAST')
        self.quarantine_t = self.transaction.get_quarantine_type(config.conf.get('bdb-sync', 'quarantine_type'))
        self.source_t = self.transaction.get_source_system(config.conf.get('bdb-sync', 'source_system'))
        self.ct_phone = self.transaction.get_contact_info_type(config.conf.get('bdb-sync', 'contact_info_type_phone'))
        # For the time being, we let phone and cellphone use the same info_type
        self.ct_cellphone = self.transaction.get_contact_info_type(config.conf.get('bdb-sync', 'contact_info_type_phone'))
        #self.ct_cellphone = self.transaction.get_contact_info_type(config.conf.get('bdb-sync', 'contact_info_type_cellphone'))
        self.ct_privphone = self.transaction.get_contact_info_type(config.conf.get('bdb-sync', 'contact_info_type_privphone'))
        self.ct_fax = self.transaction.get_contact_info_type(config.conf.get('bdb-sync', 'contact_info_type_fax'))
        self.log.debug("Syncing persons into Cerebrum...")
        for person in persons:
            self._sync_person(person)
        # Commit and close session
        self.close_session() 

    def _sync_person(self, person):
        commands = self.transaction.get_commands()
        self.log.debug('Synchronizing person %s...' % person)
        try:
            spine_person = commands.get_entity_with_external_id(str(person['id']), self.bdb_person_id_t, self.source_t)
            self.log.debug('Person %s matched on BDB ID.' % person)
        except SpineIDL.Errors.NotFoundError:
            # Check if the person has the minimum required data
            if not 'birth_date' in person or not 'person_number' in person:
                self.log.error('Person %s lacks birth date and/or person number, skipping.' % person)
                return

            date = time.strptime(str(person['birth_date']), '%Y-%m-%d')
            try:
                person['birth_number'] = '%s%s' % (time.strftime('%d%m%y', date), person['person_number'])
            except ValueError, e:
                self.log.error('Invalid birth date for person %s; cannot synchronize!')
                return

            # Check this birth number for validity and determine gender
            # from it. We use unknown gender if the check for valid
            # birth number fails.
            try:
                if fodselsnr.er_mann(person['birth_number']):
                    self.log.debug('Birth number %s indicates male gender.' % person['birth_number'])
                    gender = self.transaction.get_gender_type('M')
                else:
                    self.log.debug('Birth number %s indicates female gender.' % person['birth_number'])
                gender = self.transaction.get_gender_type('F')
            except fodselsnr.InvalidFnrError, e:
                self.log.error('Person %s has invalid birth number! Birth number check said: "%s". Trying to synchronize anyway.' % (person, e))
                gender = self.transaction.get_gender_type('X')

            spine_date = commands.get_date(date.tm_year, date.tm_mon, date.tm_mday)

            try:
                searcher = self.transaction.get_entity_external_id_searcher()
                searcher.set_external_id(person['birth_number'])
                searcher.set_id_type(self.birthno_t)
                result = searcher.search()
            except ValueError: # Date parsing errors occur
                self.log.warning('Cannot search for person %s: Birth date %s seems like an invalid date. Person will be tried added as if he/she was not already in Cerebrum.' % (person, date))
                result = None
            
            # Loop through the results and try to find the person we're syncing
            if result:
                assert len(result) == 1 # There can only be one person with this birth number
                spine_person = result[0].get_entity()
                self.log.debug('Person %s found in Cerebrum (match on birth date).' % person)
            else:
                # Create the person
                self.log.debug('Person %s %s not found in Cerebrum, adding.' % (person['birth_date'], person['birth_number']))
                try:
                    spine_person = commands.create_person(spine_date, gender, person['first_name'],person['last_name'], self.source_t)
                except:
                    self.log.error('Person %s could not be created, probably due to a bad birth date.' % person)
                    return

        # Set external ID from BDB, names etc.
        try:
            ext_id = spine_person.get_external_id(self.bdb_person_id_t, self.source_t)
            if ext_id != str(person['id']):
                spine_person.set_external_id(str(person['id']), self.bdb_person_id_t, self.source_t)
        except SpineIDL.Errors.NotFoundError:
            spine_person.set_external_id(str(person['id']), self.bdb_person_id_t, self.source_t)

        if 'first_name' in person:
            spine_person.set_name(person['first_name'], self.first_name_t, self.source_t)
        if 'last_name' in person:
            spine_person.set_name(person['last_name'], self.last_name_t, self.source_t)
        
        # Add a quarantine if necesseary (assumes there's a BDB quarantine)
        # BDB is authoritative for this part
        # TODO: ADD MORE PROPER DATES
        if 'sperret' in person:
            try:
                quarantine = spine_person.get_quarantine(self.quarantine_t)
                quarantine.set_description('Sperret i BDB')
                # TODO: SET PROPER DATES
            except SpineIDL.Errors.NotFoundError:
                self.log.debug('Person is quarantined in BDB, adding quarantine in Cerebrum.')
                spine_person.add_quarantine(self.quarantine_t, 'Sperret i BDB', None, None, None)
        else:
            # Remove any existing BDB quarantine
            try:
                spine_person.get_quarantine(self.quarantine_t)
                self.log.debug('Person has BDB quarantine in Cerebrum, but not in BDB. Removing quarantine.')
                spine_person.remove_quarantine(self.quarantine_t)
            except SpineIDL.Errors.NotFoundError:
                pass

        """
        # FIXME - phones
        if 'kontor' in person:
            self.log.debug('Adding office phone number from BDB.')
            self.__add_contact_info(spine_person, person['kontor'], 'Office phone number from BDB', 99, self.ct_phone)
        if 'mobil' in person:
            self.log.debug('Adding cell phone number from BDB.')
            self.__add_contact_info(spine_person, person['mobil'], 'Cell phone number from BDB', 90, self.ct_cellphone)
        if 'privat' in person:
            self.log.debug('Adding private phone number from BDB.')
            self.__add_contact_info(spine_person, person['privat'], 'Private phone number from BDB', 10, self.ct_privphone)
        if 'telefax' in person:
            self.log.debug('Adding fax number from BDB.')
            self.__add_contact_info(spine_person, person['telefax'], 'Fax number from BDB', 50, self.ct_fax)
        """
        # TODO: Studieprogram -> aff/gruppe

        self.log.debug('Person %s synchronized.' % person)

    def __add_contact_info(self, spine_person, info, desc, priority, type):
        try:
            ci = spine_person.get_contact_info(priority, type, self.source_t)
            ci.set_value(info)
            ci.set_description(desc)
        except SpineIDL.Errors.NotFoundError:
            spine_person.add_contact_info(info, desc, priority, type, self.source_t)

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
    #usage()

    try:
        sync = BDBSync()
    except Exception,e:
        print "Error while connecting to BDB. Reason: %s" % str(e)
        sys.exit()
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

if __name__ == '__main__':
    main()
