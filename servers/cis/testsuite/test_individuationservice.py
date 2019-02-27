#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011-2012 University of Oslo, Norway
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

"""Testing of the Individuation service. The Cerebrum database and the
Individuation server is set up by the script, so the tests should run as
automatically as possible.

To get a system ready for testing:

 - Install python, twisted, M2Crypto and nosetest. Install postgresql if you
   want it on your localhost.

 - Set the $PYTHONPATH to point to the Cerebrum directories to test and a
   cereconf file set up with testing variables.

 - Set up a postgresql database server. Put the hostname of the db in
   cereconf.CEREBRUM_DATABASE_CONNECT_DATA['host'], e.g. 'localhost'. Note that
   the cerebrum user must have the rights to create new databases.

 - The script is preferred to be run by twisted's test tool, trial::

    trial ./test_individuationservice.py

   Or nosetest could be used, which gives prettier feedback, but misses some
   functionality::

    nosetests ./test_individuationservice.py

 - Note that a database is created by each test run, but it is not dropped.  You
   therefore want to clean up the database from time to time. The databases are
   named 'nosetest_individuation_' and a random number.

TODO: If the cerebrum-specific is usable for others, move it code to a basic
class available for other test modules?

TODO: The cerebrum code can only be run once in a python session. The next run
would cause trouble. Fix this, to be able to create several databases in one go,
e.g. when testing several modules which needs a clean database.
"""

import sys
import os
import time
import random
from mx.DateTime import DateTime, DateTimeDelta, now

import suds
from twisted.web import soap, error
from twisted.internet import ssl, reactor, defer
from twisted.internet.protocol import ClientFactory, Protocol
from twisted.python import log
from twisted.trial import unittest

import OpenSSL
from M2Crypto import RSA, X509, EVP, m2, ASN1

import cereconf
from Cerebrum import Errors, Utils
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email

from Cerebrum.modules.cis import SoapListener, Individuation


log.startLogging(sys.stdout)


class IndividuationTestSetup:
    """Setup and helper methods for testing the Individuation webservice."""

    @classmethod
    def setupCerebrum(cls):
        """Sets up an empty Cerebrum database and fill it with needed data.
        Imitates makedb.py for doing this."""
        # TODO: does changing cereconf affect the different modules?

        # TODO: doesn't work correctly when several classes needs setup and
        # teardown... fix.

        cls.dbname = 'nosetest_individuation_%s' % int(random.random() *
                                                       1000000000)
        print "Database: ", cls.dbname

        cereconf.CEREBRUM_DATABASE_NAME_new = cls.dbname
        cereconf.CEREBRUM_DATABASE_NAME_original = \
            cereconf.CEREBRUM_DATABASE_NAME
        cls.dbuser = (cereconf.CEREBRUM_DATABASE_CONNECT_DATA['table_owner'] or
                      cereconf.CEREBRUM_DATABASE_CONNECT_DATA['user'])

        def read_password(user, system, host=None, *args):
            """Mockup of Util's password reader"""
            # Would prefer to overwrite only 'system' and run original function:
            # return Utils.read_password_original(user=user,
            #                    system=cereconf.CEREBRUM_DATABASE_NAME_original)

            if system == cereconf.CEREBRUM_DATABASE_NAME_new:
                system = cereconf.CEREBRUM_DATABASE_NAME_original
            filename = cls.helper_generate_password_filename(user, system, host)
            f = file(filename)
            try:
                # .rstrip() removes any trailing newline, if present.
                dbuser, dbpass = f.readline().rstrip('\n').split('\t', 1)
                assert dbuser == user
                return dbpass
            finally:
                f.close()
        Utils.read_password = read_password

        # create a password file for the new database
        os.link(cls.helper_generate_password_filename(
            cls.dbuser,
            cereconf.CEREBRUM_DATABASE_NAME_original,
            cereconf.CEREBRUM_DATABASE_CONNECT_DATA['host']),
            cls.helper_generate_password_filename(
                cls.dbuser, cls.dbname,
                cereconf.CEREBRUM_DATABASE_CONNECT_DATA['host']))

        # TODO: This requires an already existing database to first connect
        # to, for creating temporary. Could it be done without any db instead?
        # TODO: Could try to connect to a default database instead, i.e.
        # 'postgres', or maybe 'cerebrum', if the first connection attempt
        # doesn't work.
        db = Factory.get('Database')(user=cls.dbuser)
        db.execute('rollback')
        db.execute('create database %s' % cls.dbname)
        db.commit()
        db.close()
        del db

        cereconf.CEREBRUM_DATABASE_NAME = cls.dbname
        cereconf.CEREBRUM_DDL_DIR = os.path.join(os.path.dirname(__file__),
                                                 "../../../design")

        cls.db = Factory.get('Database')(user=cls.dbuser)
        cls.db.cl_init(change_program='nosetest')

        # Force all Constants-writing to use the same db-connection
        from Cerebrum.Constants import _CerebrumCode
        _CerebrumCode.sql.fset(None, cls.db)

        from Cerebrum import Metainfo
        import makedb
        # TODO: does this fix that cereconf gets updated
        # correctly for the module?
        reload(makedb)
        global meta
        meta = Metainfo.Metainfo(cls.db)
        makedb.meta = meta

        debug = 0
        extra_files = []
        # TODO: it seems a bit complex having to include all the sql files,
        #       just to avoid dependencies between them? E.g. should ephorte
        #       relevant data be referenced by mod_auth?
        for f in ('mod_changelog.sql', 'mod_entity_trait.sql',
                  'mod_password_history.sql', 'mod_posix_user.sql',
                  'mod_email.sql', 'mod_employment.sql', 'mod_sap.sql',
                  'mod_printer_quota.sql', 'mod_stedkode.sql',
                  'mod_ephorte.sql', 'mod_voip.sql',
                  'bofhd_tables.sql', 'bofhd_auth.sql',
                  'mod_hostpolicy.sql', 'mod_dns.sql',
                  ):
            extra_files.append(os.path.join(cereconf.CEREBRUM_DDL_DIR, f))

        for f in makedb.get_filelist(cls.db, extra_files=extra_files):
            makedb.runfile(f, cls.db, debug, 'code')
        cls.db.commit()
        makedb.insert_code_values(cls.db, debug=debug)
        cls.db.commit()
        # TODO: check if this loop is necessary for testing
        for f in makedb.get_filelist(cls.db, extra_files=extra_files):
            makedb.runfile(f, cls.db, debug, 'main')
        cls.db.commit()
        makedb.makeInitialUsers(cls.db)

        # Other tweaks
        cls.setupCerebrumForIndividuation()

    @classmethod
    def setupCerebrumForIndividuation(cls):
        """Local tweaks to the Cerebrum database for the Individuation
        project."""
        co = Factory.get('Constants')(cls.db)
        gr = Factory.get('Group')(cls.db)
        ac = Factory.get('Account')(cls.db)

        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        bootstrap_id = ac.entity_id

        for group in ((getattr(cereconf, 'BOFHD_SUPERUSER_GROUP', ()),) +
                      getattr(cereconf, 'INDIVIDUATION_PASW_RESERVED', ())):
            gr.clear()
            try:
                gr.find_by_name(group)
                continue
            except Errors.NotFoundError:
                pass
            gr.populate(creator_id=bootstrap_id,
                        visibility=co.group_visibility_all, name=group,
                        description='Group for individuation')
            gr.write_db()
            cls.db.commit()

        # create an ou to put affiliations on
        ou = Factory.get('OU')(cls.db)
        ou.populate(fakultet=0, institutt=0, avdeling=0, institusjon=0)
        ou.write_db()
        ou.add_name_with_language(name_variant=co.ou_name_display,
                                  name_language=co.language_en,
                                  name='Basic OU')
        ou.write_db()
        ou.commit()

    @classmethod
    def tearDownCerebrum(cls):
        """Cleans up temporary database, password files, etc."""
        if not cls.dbname.startswith('nosetest_'):
            print "Unknown dbname: '%s', don't want to drop it" % cls.dbname
        else:
            os.unlink(cls.helper_generate_password_filename(
                cls.dbuser,
                cls.dbname,
                host=cereconf.CEREBRUM_DATABASE_CONNECT_DATA['host']))

            # TODO: do not drop db if errors have occured? Might want to look
            # at it first.

            cls.db.commit()
        cereconf.CEREBRUM_DATABASE_NAME = \
            cereconf.CEREBRUM_DATABASE_NAME_original

    def createServer(self, instance, encrypt=False, server_key=None,
                     server_cert=None, client_cert=None, whitelist=None):
        """Creates a temporary Individuation webservice. Note that the reactor
        is handled by twisted.trial.unittest, so do not run() the server.

        """
        sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
        import SoapIndividuationServer
        SoapListener.interface = '127.0.0.1'
        SoapIndividuationServer.IndividuationServer.cere_class = instance

        if encrypt:
            server = SoapListener.TLSTwistedSoapStarter(
                port=0,
                applications=SoapIndividuationServer.IndividuationServer,
                private_key_file=server_key,
                certificate_file=server_cert,
                client_ca=client_cert,
                client_fingerprints=whitelist)
        else:
            server = SoapListener.TwistedSoapStarter(
                port=0,
                applications=SoapIndividuationServer.IndividuationServer)

        SoapIndividuationServer.IndividuationServer.site = server.site

        # The reactor can only be run once in a process, it can not be rerun.
        # Besides, twisted.trial takes care of all that.
        return server

    def setupServer(self, encrypt=False, server_key=None, server_cert=None,
                    client_cert=None, instance=None, whitelist=None):
        """Start up the Individuation webservice.
        """
        self.tearDownServer()  # reset if not correctly stopped by last test

        if not instance:
            # Force Individuation to use same database:
            if hasattr(self, 'db'):
                db = self.db
            elif hasattr(self.__class__, 'db'):
                db = self.db
            Individuation.db = db
            Individuation.Individuation.db = db
            instance = Individuation.Individuation
        # overwrite some functionality

        def send_token_grabber(self, phone_no, token):
            self.last_token = token
            return True
        instance.send_token = send_token_grabber

        def sendmail_grabber(toaddr, fromaddr, subject, body, cc=None,
                             charset='utf-8', debug=False):
            log.msg("email %s -> %s (%s)" % (fromaddr, toaddr, subject))
        Individuation.sendmail = sendmail_grabber

        self.server = self.createServer(instance=instance, encrypt=encrypt,
                                        server_key=server_key,
                                        server_cert=server_cert,
                                        client_cert=client_cert,
                                        whitelist=whitelist)
        return self.server

    def tearDownServer(self):
        if getattr(self, 'server', None):
            self.server.port.stopListening()
            # expire all sessions to avoid conflicts with next test:
            # TODO: should these be cleaned up the server itself?
            for s in self.server.site.sessions.copy():
                self.server.site.getSession(s).expire()

    def setupSudsClient(self, url=None):
        """Set up suds and connect to webservice."""
        if not url:
            url = ("http://cere-utv01.uio.no:%d/SOAP/?wsdl" %
                   self.server.port.getHost().port)
        # A bug in suds fetches the xml dtd, which is wrong. This caches it
        from suds.xsd import sxbasic
        sxbasic.Import.bind(
            'http://www.w3.org/2001/XMLSchema',
            'file://' + os.path.join('/tmp/', 'cache', 'suds', 'XMLSchema.xml'))
        client = suds.client.Client(url)
        client.options.cache.setduration(days=100)
        return client

    def setupClient(self, url=None, encrypt=False):
        """Sets up a simple twisted soap client. Server has to be started. If
        url is not given, encrypt can be set for connecting through https."""
        if not url:
            host = self.server.port.getHost()
            if encrypt:
                proto = 'https'
            else:
                proto = 'http'
            url = '%s://%s:%d/SOAP/?wsdl' % (proto, host.host, host.port)
        return soap.Proxy(url)

    def createPerson(self, birth=DateTime(1970, 2, 3), first_name=None,
                     last_name=None, system=None, gender=True, fnr=None,
                     ansnr=None, studnr=None):
        """Shortcut for creating a test person in the db"""
        pe = Factory.get('Person')(self.db)
        co = Factory.get('Constants')(self.db)
        if gender:
            gender = co.gender_female
        else:
            gender = co.gender_male
        pe.populate(birth, gender=gender)
        pe.write_db()
        pe_id = pe.entity_id

        if first_name or last_name:
            pe.affect_names(co.system_sap, co.name_first, co.name_last)
            pe.populate_name(co.name_first, first_name)
            pe.populate_name(co.name_last, last_name)
            pe.write_db()

        if fnr:
            pe.affect_external_id(co.system_sap, co.externalid_fodselsnr)
            pe.populate_external_id(co.system_sap, co.externalid_fodselsnr, fnr)
            pe.write_db()
            self.db.commit()
            pe.clear()
            pe.find(pe_id)
        if studnr:
            pe.affect_external_id(co.system_fs, co.externalid_studentnr)
            pe.populate_external_id(co.system_fs, co.externalid_studentnr,
                                    studnr)
            pe.write_db()
            self.db.commit()
            pe.clear()
            pe.find(pe_id)
        if ansnr:
            pe.affect_external_id(co.system_sap, co.externalid_sap_ansattnr)
            pe.populate_external_id(co.system_sap, co.externalid_sap_ansattnr,
                                    ansnr)
            pe.write_db()
            self.db.commit()
        pe.write_db()
        self.db.commit()
        return pe

    def createAccount(self, owner, uname):
        """Shortcut for creating an account in the test db"""
        ac = Factory.get('Account')(self.db)
        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        bootstrap_id = ac.entity_id
        ac.clear()
        ac.populate(name=uname, owner_type=owner.entity_type,
                    owner_id=owner.entity_id, np_type=None,
                    creator_id=bootstrap_id, expire_date=None)
        ac.write_db()
        ac.commit()
        return ac

    @staticmethod
    def helper_generate_password_filename(user, system, host=None):
        """Shortcut for generating a password filename."""
        fmt = ['passwd-%s@%s']
        var = [user.lower(), system.lower()]
        if host is not None and not host.startswith("/"):
            fmt.append('@%s')
            var.append(host.lower())
        format_str = ''.join(fmt)
        format_var = tuple(var)
        return os.path.join(cereconf.DB_AUTH_DIR,
                            format_str % format_var)

    def helper_generate_sms_token(self,
                                  username='rogertst',
                                  ext_id='externalid_sap_ansattnr',
                                  id='10001626',
                                  phone_no='91726078',
                                  browser_token='123qwe'):
        """Helper method for generating an SMS token and returning it from the
        db, so validation of it can be tested."""
        self.client.service.generate_token(ext_id, id, username, phone_no,
                                           browser_token)
        # TODO: the token is hashed before put in the database
        return get_token(username)


class TestIndividuationService(unittest.TestCase, IndividuationTestSetup):
    """Testing the Individuation webservice. A test database is created and
    filled with test data, and the webservice is setup on a port.

    """

    @classmethod
    def setUpClass(cls):
        cls.setupCerebrum()

    def setUp(self):
        # trial doesn't seem to use setUpClass()... nosetest does, however
        if not hasattr(self.__class__, 'db'):
            self.__class__.setUpClass()
        self.timeout = 60
        self.server = self.setupServer()
        self.client = self.setupClient()
        if hasattr(self, 'last_token'):
            del self.last_token
        # reset variables in cereconf that should be set to default
        cereconf.INDIVIDUATION_PHONE_TYPES = {
            'system_sap': {
                'types': {
                    'contact_mobile_phone': {},
                    'contact_private_mobile': {}},
                'priority': 1},
            'system_fs':  {
                'types': {
                    'contact_mobile_phone': {'delay': 7},
                    'contact_private_mobile': {'delay': 7}},
                'priority': 1}}

    def assertAccounts(self, data, match):
        """Check that returned accounts are as expected."""
        if type(data.Account) is not list:
            # if only one return value, twisted's soap "fixes" returned data...
            data.Account = [data.Account]
        assert len(data.Account) == len(match)
        for b in data.Account:
            assert b.uname in match
        # TODO: more we should check?

    def test_config(self):
        pass
    test_config.skip = 'TODO'

    def test_config_priorities(self):
        cereconf.INDIVIDUATION_PHONE_TYPES = {
            'system_sap': {
                'types': {
                    'contact_private_mobile': {}},
                'priority': 1},
            'system_fs':  {
                'types': {
                    'contact_mobile_phone': {'delay': 7}},
                'priority': 2},
            'system_pbx': {
                'types': {
                    'contact_mobile_phone': {}},
                'priority': 2},
        }
        pri = list(Individuation.Individuation()._get_priorities())
        self.assertEquals(len(pri), 2)
        self.assertTrue('system_sap' in pri[0])
        # order doesn't matter inside each priority
        self.assertEquals(len(pri[1]), 2)
        self.assertTrue('system_fs' in pri[1])
        self.assertTrue('system_pbx' in pri[1])

    def test_get_nonexisting_user(self):
        d = self.client.callRemote('get_usernames',
                                   id_type='externalid_sap_ansattnr',
                                   ext_id='9999999999099')
        # TODO: find out what failure message is returned
        return self.assertFailure(d, error.Error)

    def test_get_user_by_nonexisting_idtype(self):
        d = self.client.callRemote('get_usernames',
                                   id_type='externalid_foobarbaz', ext_id='123')
        # TODO: twisted's soap client doesn't seem to be able to figure out what
        #       type of failure it receives... Check server's log instead?
        return self.assertFailure(d, error.Error)

    def test_get_username(self):
        pe = self.createPerson(ansnr='1001234')
        self.createAccount(pe, 'tarnfrid')
        d = self.client.callRemote('get_usernames',
                                   id_type='externalid_sap_ansattnr',
                                   ext_id='1001234')
        d.addCallback(self.assertAccounts, ('tarnfrid',))
        return

    def test_get_usernames(self):
        pe = self.createPerson(DateTime(1984, 8, 1), "Ola", "Nordmann",
                               ansnr='12387001')
        self.createAccount(pe, 'ola')
        self.createAccount(pe, 'olano')
        self.createAccount(pe, 'norman')

        d = self.client.callRemote('get_usernames',
                                   id_type='externalid_sap_ansattnr',
                                   ext_id='12387001')
        d.addCallback(self.assertAccounts, ('ola', 'olano', 'norman'))
        return d

    def test_validate_short_password(self):
        d = self.client.callRemote('validate_password', password='1234')
        # TODO: twisted's soap client doesn't seem to be able to figure out what
        #       type of failure it receives... Check server's log instead?
        d = self.assertFailure(d, error.Error)
        return d

    def test_validate_password(self):
        d = self.client.callRemote('validate_password',
                                   password='q_i#A%U1sB4f+Q')
        d.addCallback(self.assertEquals, 'true')
        return d

    def test_correct_password_change(self):
        uname = 'mrtest'
        browser_token = '123qwe'
        new_password = 'a_4!Vbx8k#_'

        pe = self.createPerson(first_name='Mister', last_name='Test',
                               ansnr='1001235')
        co = Factory.get('Constants')(self.db)
        ou = Factory.get('OU')(self.db)
        ou.find_stedkode(0, 0, 0, 0)

        pe.populate_affiliation(
            source_system=co.system_sap, ou_id=ou.entity_id,
            affiliation=co.affiliation_ansatt,
            status=co.affiliation_status_ansatt_vitenskapelig)
        pe.populate_contact_info(source_system=co.system_sap,
                                 type=co.contact_mobile_phone,
                                 value='12345678')
        pe.write_db()
        pe.commit()
        ac = self.createAccount(pe, uname)

        pe = Factory.get('Person')(self.db)
        d = self.client.callRemote('generate_token',
                                   id_type="externalid_sap_ansattnr",
                                   ext_id='1001235', username=uname,
                                   phone_no='12345678',
                                   browser_token=browser_token)
        d.addCallback(self.assertEquals, 'true')

        def checkPassword(data):
            ac.clear()
            ac.find_by_name(uname)
            assert ac.verify_auth(new_password), "Password not set"

        def setPassword(data):
            NEW_password = None
            d = self.client.callRemote('set_password', username=uname,
                                       new_password=NEW_password,
                                       token=self.last_token,
                                       browser_token=browser_token)
            d.addCallback(self.assertEquals, 'true')
            d.addCallback(checkPassword)
            return d

        def checkToken(data):
            d = self.client.callRemote('check_token', username=uname,
                                       token=self.last_token,
                                       browser_token=browser_token)
            # the soap client doesn't seem to handle booleans correctly?
            d.addCallback(self.assertEquals, 'true')
            d.addCallback(setPassword)
            return d
        d.addCallback(checkToken)
        return d

    def test_max_user_attempts(self):
        # TODO:
        # 1. generate tokens for a given user as many times as defined in
        #    cereconf.INDIVIDUATION_ATTEMPTS
        # 2. check that you are not allowed to try more times.
        pass
    test_max_user_attempts.skip = "TODO"

    def test_max_token_fail_checks(self):
        # TODO:
        # 1. generate a token for a given user
        # 2. fail the check_token as many times as defined in
        #    cereconf.INDIVIDUATION_TOKEN_ATTEMPTS.
        # 3. check that token is invalid by checking the correct token
        # 4. check that set_password aborts the user as well
        pass
    test_max_token_fail_checks.skip = "TODO"

    def test_max_token_fail_password(self):
        # TODO:
        # 1. generate a token for a given user
        # 2. fail the set_password as many times as defined in
        #    cereconf.INDIVIDUATION_TOKEN_ATTEMPTS, by giving wrong token
        # 3. check that token is invalid by calling set_password with correct
        #    token.
        # 4. check that check_password aborts the user as well
        pass
    test_max_token_fail_password.skip = "TODO"

    def test_abort_token(self):
        d = self.client.callRemote('abort_token',
                                   username=cereconf.INITIAL_ACCOUNTNAME)
        # this should never return any error, even if account exists or not
        return d
    test_abort_token.skip = "TODO"

    def test_abort_correct_token(self):
        # TODO:
        # 1. generate a token for a user
        # 2. call abort_token
        # 3. check that neither set_password nor check_token passes
        pass
    test_abort_correct_token.skip = "TODO"

    def test_abort_token_nonexisting_user(self):
        d = self.client.callRemote('abort_token',
                                   username='test1234_username_125_nonexisting')
        # this should never return any error, even if account exists or not
        return d

    def test_phonenumberchange_delay(self):
        """Fresh phone numbers should not be used if config says so."""
        cereconf.INDIVIDUATION_PHONE_TYPES[
            'system_fs']['types']['contact_mobile_phone']['delay'] = 7
        cereconf.INDIVIDUATION_PHONE_TYPES[
            'system_fs']['types']['contact_private_mobile']['delay'] = 7

        ou = Factory.get('OU')(self.db)
        co = Factory.get('Constants')(self.db)
        ou.find_stedkode(0, 0, 0, 0)
        pe = self.createPerson(first_name='Miss', last_name='Test',
                               studnr='007')
        ac = self.createAccount(pe, 'mstest')

        pe.populate_affiliation(source_system=co.system_fs, ou_id=ou.entity_id,
                                affiliation=co.affiliation_student,
                                status=co.affiliation_status_student_aktiv)
        pe.write_db()
        pe.populate_contact_info(source_system=co.system_fs,
                                 type=co.contact_mobile_phone,
                                 value='98012345')
        pe.write_db()

        # Create e-mail address for user
        ed = Email.EmailDomain(self.db)
        ed.populate('example.com', 'For testing')
        ed.write_db()
        et = Email.EmailTarget(self.db)
        et.populate(co.email_target_account, ac.entity_id, co.entity_account)
        et.write_db()
        ea = Email.EmailAddress(self.db)
        ea.populate('test', ed.entity_id, et.entity_id)
        ea.write_db()
        epa = Email.EmailPrimaryAddressTarget(self.db)
        epa.populate(ea.entity_id, et)
        epa.write_db()

        self.db.commit()

        # hack the create_date in change_log
        self.db.execute("""
            UPDATE [:table schema=cerebrum name=change_log]
            SET tstamp = :tid
            WHERE
                subject_entity = :s_id AND
                change_type_id = :ct_id""",
                        {'s_id': pe.entity_id,
                         'ct_id': co.person_create,
                         'tid': DateTime(2009, 10, 4)})
        self.db.commit()

        d = self.client.callRemote('generate_token',
                                   id_type="externalid_studentnr", ext_id='007',
                                   username='mstest', phone_no='98012345',
                                   browser_token='a')
        d = self.assertFailure(d, error.Error)
        # TODO: test that sendmail is called with the correct to-address
        return d

    def test_phonenumberchange_fresh_person(self):
        """Fresh phone numbers should still be available for new persons"""
        cereconf.INDIVIDUATION_PHONE_TYPES[
            'system_fs']['types']['contact_mobile_phone']['delay'] = 7
        cereconf.INDIVIDUATION_PHONE_TYPES[
            'system_fs']['types']['contact_private_mobile']['delay'] = 7

        ou = Factory.get('OU')(self.db)
        co = Factory.get('Constants')(self.db)
        ou.find_stedkode(0, 0, 0, 0)
        pe = self.createPerson(first_name='Miss', last_name='Test2',
                               studnr='008')
        self.createAccount(pe, 'mstest2')

        pe.populate_affiliation(source_system=co.system_fs, ou_id=ou.entity_id,
                                affiliation=co.affiliation_student,
                                status=co.affiliation_status_student_aktiv)
        pe.write_db()
        pe.populate_contact_info(source_system=co.system_fs,
                                 type=co.contact_mobile_phone,
                                 value='98012345')
        pe.write_db()
        self.db.commit()

        # hack the create_date in change_log
        print self.db.execute("""
            UPDATE [:table schema=cerebrum name=change_log]
            SET tstamp = :tid
            WHERE
                subject_entity = :s_id AND
                change_type_id = :ct_id""",
                              {'s_id': pe.entity_id,
                               'ct_id': co.person_create,
                               'tid': now() - DateTimeDelta(5)})

        d = self.client.callRemote('generate_token',
                                   id_type="externalid_studentnr", ext_id='008',
                                   username='mstest2', phone_no='98012345',
                                   browser_token='a')
        d.addCallback(self.assertEquals, 'true')
        return d

    def test_source_order_notoverlap(self):
        """Employees should not be able to use their student phone numbers if
        config says so."""
        # TODO: make sure this affects the Individuation module
        cereconf.INDIVIDUATION_PHONE_TYPES = {
            'system_sap': {
                'types': {
                    'contact_mobile_phone': {}},
                'priority': 1, },
            'system_fs':  {
                'types': {
                    'contact_mobile_phone': {'delay': 7}},
                'priority': 2}}
        co = Factory.get('Constants')(self.db)
        ou = Factory.get('OU')(self.db)
        ou.find_stedkode(0, 0, 0, 0)
        pe = self.createPerson(first_name='Double', last_name='Registered',
                               ansnr='12345', studnr='12344')
        pe_id = pe.entity_id

        pe.populate_affiliation(
            source_system=co.system_sap, ou_id=ou.entity_id,
            affiliation=co.affiliation_ansatt,
            status=co.affiliation_status_ansatt_vitenskapelig)
        pe.populate_contact_info(source_system=co.system_sap,
                                 type=co.contact_mobile_phone,
                                 value='12345678')
        pe.write_db()
        self.db.commit()
        pe.clear()
        pe.find(pe_id)
        pe.populate_affiliation(source_system=co.system_fs, ou_id=ou.entity_id,
                                affiliation=co.affiliation_student,
                                status=co.affiliation_status_student_aktiv)
        pe.populate_contact_info(source_system=co.system_fs,
                                 type=co.contact_mobile_phone,
                                 value='87654321')
        pe.write_db()
        self.db.commit()

        self.createAccount(pe, 'mrduble')

        d = self.client.callRemote('generate_token',
                                   id_type="externalid_studentnr",
                                   ext_id='12344', username='mrduble',
                                   phone_no='87654321', browser_token='b')
        d = self.assertFailure(d, error.Error)
        return d

    def test_source_order_overlap(self):
        """Employees should be able to use their student phone numbers if config
        says so."""
        # TODO: make sure this affects the Individuation module
        cereconf.INDIVIDUATION_PHONE_TYPES = {
            'system_sap': {
                'types': {'contact_mobile_phone': {}},
                'priority': 2},
            'system_fs':  {
                'types': {
                    'contact_mobile_phone': {'delay': 7}},
                'priority': 2}}
        co = Factory.get('Constants')(self.db)
        ou = Factory.get('OU')(self.db)
        ou.find_stedkode(0, 0, 0, 0)
        pe = self.createPerson(first_name='Triple', last_name='Registered',
                               ansnr='22345', studnr='22344')
        pe_id = pe.entity_id

        pe.populate_affiliation(
            source_system=co.system_sap, ou_id=ou.entity_id,
            affiliation=co.affiliation_ansatt,
            status=co.affiliation_status_ansatt_vitenskapelig)
        pe.populate_contact_info(source_system=co.system_sap,
                                 type=co.contact_mobile_phone,
                                 value='12345678')
        pe.write_db()
        self.db.commit()
        pe.clear()
        pe.find(pe_id)
        pe.populate_affiliation(source_system=co.system_fs, ou_id=ou.entity_id,
                                affiliation=co.affiliation_student,
                                status=co.affiliation_status_student_aktiv)
        pe.populate_contact_info(source_system=co.system_fs,
                                 type=co.contact_mobile_phone,
                                 value='87654321')
        pe.write_db()
        self.db.commit()

        self.createAccount(pe, 'mrdubl2')

        d = self.client.callRemote('generate_token',
                                   id_type="externalid_studentnr",
                                   ext_id='12344', username='mrduble',
                                   phone_no='87654321', browser_token='b')
        d.addCallback(self.assertEquals, 'true')
        return d

    def tearDown(self):
        self.tearDownServer()
        del self.client

    @classmethod
    def tearDownClass(cls):
        cls.tearDownCerebrum()
        if hasattr(cls, 'server'):
            del cls.server


class EmptyIndividuation(Individuation.Individuation):
    """Empty Individuation class, to mimic webservice's behaviour without
    Cerebrum."""
    def get_person_accounts(self, id_type, ext_id):
        ret = list()
        ret.append({'uname': id_type,
                    'priority': ext_id,
                    'status': 'statt'})
        ret.append({'uname': 'new',
                    'priority': 'test',
                    'status': 'statt'})
        return ret

    def generate_token(self, id_type, ext_id, uname, phone_no, browser_token):
        return None

    def send_token(self, phone_no, token):
        return None

    def check_token(self, uname, token, browser_token):
        return None

    def delete_token(self, uname):
        """Overwriting this to an echo method, for checking data"""
        return uname

    def _check_password(self, password, account=None):
        return False

    def set_password(self, uname, new_password, token, browser_token):
        return None

    def get_person(self, id_type, ext_id):
        return None

    def get_account(self, uname):
        return None

    def validate_password(self, password):
        """Overwriting this to return data in an exception, for checking data"""
        raise Errors.CerebrumRPCException(password)


class TestIndividuationConnection(unittest.TestCase, IndividuationTestSetup):
    """Testing the connection of the Individuation webservice, independent of
    Cerebrum."""

    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        self.timeout = 5  # only testing connection, should not take long
        if hasattr(self, 'server'):
            del self.server

    def helper_generate_key(self):
        """Create a public-private key."""
        key = RSA.gen_key(1024, m2.RSA_F4)
        pkey = EVP.PKey()
        pkey.assign_rsa(key)
        return (key, pkey)

    def helper_generate_certificate_request(self, pkey):
        """Create a certificate request."""
        name = X509.X509_Name()
        name.C = 'NO'
        name.ST = 'Oslo'
        name.L = 'Oslo'
        name.O = 'University of Oslo'
        name.OU = 'Cerebrum requestor'
        name.CN = '127.0.0.1'
        name.emailAddress = 'test@example.com'

        req = X509.Request()
        # Seems to default to 0, but we can now set it as well, so just API test
        req.set_version(req.get_version())  # TODO: set to version 2 as well
        req.set_pubkey(pkey)
        req.set_subject_name(name)

        # ext1 = X509.new_extension('Comment', 'Auto Generated')
        # extstack = X509.X509_Extension_Stack()
        # extstack.push(ext1)
        # req.add_extensions(extstack)
        req.sign(pkey, 'sha1')
        return req

    def helper_generate_certificate(self, pkey):
        """Create a self-signed x509 certificate."""
        name = X509.X509_Name()
        name.C = 'NO'
        name.ST = 'Oslo'
        name.L = 'Oslo'
        name.O = 'University of Oslo'
        name.OU = 'Cerebrumtesting'
        name.CN = '127.0.0.1'
        name.emailAddress = 'test@example.com'

        cert = X509.X509()
        cert.set_version(2)
        cert.set_serial_number(1)
        cert.set_subject(name)

        t = long(time.time()) + time.timezone
        now = ASN1.ASN1_UTCTIME()
        now.set_time(t)
        end = ASN1.ASN1_UTCTIME()
        end.set_time(t + 60 * 60 * 24 * 365 * 10)
        cert.set_not_before(now)
        cert.set_not_after(end)

        cert.set_issuer(name)
        cert.set_pubkey(pkey)

        # ext = X509.new_extension('subjectAltName', 'DNS:localhost')
        # ext.set_critical(0)
        # cert.add_ext(ext)
        cert.sign(pkey, 'sha1')
        return cert

    def helper_sign_certificate(self, cakey, cacert, request):
        """Sign a certificate request by the given ca key and ca certificate."""
        cert = X509.X509()
        cert.set_version(2)
        cert.set_serial_number(1)
        cert.set_subject(request.get_subject())

        t = long(time.time()) + time.timezone
        now = ASN1.ASN1_UTCTIME()
        now.set_time(t)
        end = ASN1.ASN1_UTCTIME()
        end.set_time(t + 60 * 60 * 24 * 365 * 10)
        cert.set_not_before(now)
        cert.set_not_after(end)

        cert.set_issuer(cacert.get_subject())
        cert.set_pubkey(request.get_pubkey())

        # ext = X509.new_extension('subjectAltName', 'DNS:localhost')
        # ext.set_critical(0)
        # cert.add_ext(ext)
        cert.sign(cakey, 'sha1')
        return cert

    def helper_get_certificate(self):
        """Get a generic self-signed certificate and private key"""
        keylocation = '/tmp/nosetest_individuation.key'
        certlocation = '/tmp/nosetest_individuation.pem'

        try:
            os.stat(keylocation)
            os.stat(certlocation)
        except OSError:
            (key, pkey) = self.helper_generate_key()
            f = open(keylocation, 'w')
            f.write(key.as_pem(cipher=None))
            f.close()

            cert = self.helper_generate_certificate(pkey)
            f = open(certlocation, 'w')
            f.write(cert.as_pem())
            f.close()
        return (keylocation, certlocation)

    def helper_get_client_certificate(self):
        """Get a generic client certificate and its public-private key."""
        (cakey, cacert) = self.helper_get_certificate()
        key = RSA.load_key(cakey)
        cakey = EVP.PKey()
        cakey.assign_rsa(key)
        cacert = X509.load_cert(cacert)

        keylocation = '/tmp/nosetest_individuation.client.key'
        certlocation = '/tmp/nosetest_individuation.client.pem'

        try:
            os.stat(keylocation)
            os.stat(certlocation)
        except OSError:
            (key, pkey) = self.helper_generate_key()
            f = open(keylocation, 'w')
            f.write(key.as_pem(cipher=None))
            f.close()

            req = self.helper_generate_certificate_request(pkey)
            cert = self.helper_sign_certificate(cakey, cacert, req)
            f = open(certlocation, 'w')
            f.write(cert.as_pem())
            f.close()
        return (keylocation, certlocation)

    def test_unencrypted_connection(self):
        self.server = self.setupServer(encrypt=False,
                                       instance=EmptyIndividuation)
        client = self.setupClient()
        d = client.callRemote('get_usernames', id_type=3, ext_id=4)
        return d

    def test_bad_method(self):
        self.server = self.setupServer(encrypt=False,
                                       instance=EmptyIndividuation)
        client = self.setupClient()
        d = client.callRemote('call_nonexisting_method_14151', 3, param1=4)
        d = self.assertFailure(d, error.Error)

        def cb(err):
            self.assertEquals(int(err.status), 500)
        d.addCallback(cb)
        return d

    def test_bad_params(self):
        self.server = self.setupServer(encrypt=False,
                                       instance=EmptyIndividuation)
        client = self.setupClient()
        d = client.callRemote('get_usernames')
        d = self.assertFailure(d, error.Error)
        return d

    def test_safe_strings(self):
        string = 'test 123'
        string2 = u'99 _'
        self.server = self.setupServer(encrypt=False,
                                       instance=EmptyIndividuation)
        client = self.setupClient()
        d = client.callRemote('get_usernames', id_type=string, ext_id=string2)

        def cb(data):
            print data.Account
            self.assertEquals(len(data.Account), 2)
            account = data.Account[0]
            self.assertEquals(account.uname, string)
            self.assertEquals(account.priority, string2)
        d.addCallback(cb)
        return d

    def test_xml_data(self):
        string = u'test & 1% ¤2© ª”«»3'  # how to parse this correctly?
        string2 = u'9³ 5² 8¼'
        self.server = self.setupServer(encrypt=False,
                                       instance=EmptyIndividuation)
        client = self.setupClient()
        d = client.callRemote('get_usernames', id_type=string, ext_id=string2)

        def cb(data):
            print data.Account
            self.assertEquals(len(data.Account), 2)
            account = data.Account[0]
            self.assertEquals(account.uname, string)
            self.assertEquals(account.priority, string2)
        d.addCallback(cb)
        return d

    def test_encrypted_server_start(self):
        (key, cert) = self.helper_get_certificate()
        self.server = self.setupServer(encrypt=True, server_key=key,
                                       server_cert=cert,
                                       instance=EmptyIndividuation)
        client = self.setupClient(encrypt=True)
        d = client.callRemote('get_usernames', id_type=1, ext_id=None)
        return d

    def test_no_client_certificate(self):
        # client_cert_name = '/tmp/nosetest_individuation.client.pem'
        (key, cert) = self.helper_get_certificate()
        # (c_key, c_pkey) = self.helper_generate_key()
        # c_cert = self.helper_generate_certificate(c_pkey)
        # f = open(client_cert_name, 'w')
        # f.write(c_cert.as_pem())
        # f.close()
        self.server = self.setupServer(encrypt=True, server_key=key,
                                       server_cert=cert,
                                       client_cert=cert,
                                       instance=EmptyIndividuation)
        # TODO: create a twisted ssl connection instead, and only try to get the
        # wsdl definitions in a deferred. It should be blocked!
        client = self.setupClient(encrypt=True)
        d = client.callRemote('get_usernames')
        return self.assertFailure(d, OpenSSL.SSL.Error)

    def test_connection_with_certificate(self):
        (key, cert) = self.helper_get_certificate()
        (ckey, ccert) = self.helper_get_client_certificate()
        self.server = self.setupServer(encrypt=True, server_key=key,
                                       server_cert=cert,
                                       client_cert=cert,
                                       instance=EmptyIndividuation)
        f = ConnectionDebuggerFactory()
        ccf = ssl.DefaultOpenSSLContextFactory(ckey, ccert)
        ctx = ccf.getContext()

        def cb2(data):
            print "ssl: %s" % data
        ctx.set_info_callback(cb2)

        reactor.connectSSL('127.0.0.1', self.server.port.getHost().port, f, ccf)

        def cb(data):
            print "data: %s" % data

        def cbfail(data):
            print "fail: %s" % data
        f.d.addErrback(cbfail)
        f.d.addCallback(cb)
        # TODO: times out - probably wrong use of deferred in test code
        return f.d

    def test_connection_with_whitelisted_certificate(self):
        (key, cert) = self.helper_get_certificate()
        (ckey, ccert) = self.helper_get_client_certificate()
        client_cert = X509.load_cert(ccert)
        fingerprint = str(client_cert.get_fingerprint('sha1'))
        self.server = self.setupServer(encrypt=True, server_key=key,
                                       server_cert=cert,
                                       client_cert=cert,
                                       instance=EmptyIndividuation,
                                       whitelist=fingerprint)
        f = ConnectionDebuggerFactory()
        ccf = ssl.DefaultOpenSSLContextFactory(ckey, ccert)
        reactor.connectSSL('127.0.0.1', self.server.port.getHost().port, f, ccf)

        def cb(data):
            print "data: %s" % data

        def cbfail(data):
            print "fail: %s" % data
        f.d.addErrback(cbfail)
        f.d.addCallback(cb)
        # TODO: times out - probably wrong use of deferred in test code
        return f.d

    def test_connection_with_nonwhitelisted_certificate(self):
        (key, cert) = self.helper_get_certificate()
        (ckey, ccert) = self.helper_get_client_certificate()
        self.server = self.setupServer(encrypt=True, server_key=key,
                                       server_cert=cert,
                                       client_cert=cert,
                                       instance=EmptyIndividuation,
                                       whitelist='asdfasdf')
        f = ConnectionDebuggerFactory()
        ccf = ssl.DefaultOpenSSLContextFactory(ckey, ccert)
        reactor.connectSSL('127.0.0.1', self.server.port.getHost().port, f, ccf)
        return self.assertFailure(f.d, OpenSSL.SSL.Error)

    def test_connection_with_wrong_certificate(self):
        (key, cert) = self.helper_get_certificate()
        (ckey, ccert) = self.helper_get_client_certificate()
        self.server = self.setupServer(encrypt=True, server_key=key,
                                       server_cert=cert,
                                       client_cert=ccert,
                                       instance=EmptyIndividuation)
        f = ConnectionDebuggerFactory()
        ccf = ssl.DefaultOpenSSLContextFactory(ckey, ccert)
        reactor.connectSSL('127.0.0.1', self.server.port.getHost().port, f, ccf)
        return self.assertFailure(f.d, OpenSSL.SSL.Error)

    def test_selfsigned_client_certificate(self):
        # 1. start server with server cert as client authority as well
        # 2. generate a certificate that is self signed by the client
        # 3. connect to webservice with self signed certificate, by starting
        #    twisted's ssl connection and aim for the wsdl.
        # 4. check that connection is blocked!

        # Simply done by switching the certificates, since ca certificate is
        # self signed
        (cakey, ca) = self.helper_get_certificate()
        (key, cert) = self.helper_get_client_certificate()

        (ckey, ccert) = self.helper_get_client_certificate()
        self.server = self.setupServer(encrypt=True, server_key=key,
                                       server_cert=cert,
                                       client_cert=cert,
                                       instance=EmptyIndividuation)
        f = ConnectionDebuggerFactory()
        ccf = ssl.DefaultOpenSSLContextFactory(cakey, ca)
        reactor.connectSSL('127.0.0.1', self.server.port.getHost().port, f, ccf)
        return self.assertFailure(f.d, OpenSSL.SSL.Error)

    def tearDown(self):
        if getattr(self, 'server', None):
            self.server.port.stopListening()
            # expire all sessions to avoid conflicts with next test:
            # TODO: should these be cleaned up the server itself?
            for s in self.server.site.sessions.copy():
                self.server.site.getSession(s).expire()

    @classmethod
    def tearDownClass(cls):
        pass


class ConnectionDebuggerProtocol(Protocol):
    def connectionMade(self):
        print "connection made!"
        self.transport.write("GET /SOAP/ HTTP/1.1\nHost: localhost\n\n")

    def dataReceived(self, data):
        print "data received"

    def connectionLost(self, reason):
        print "connection lost..."


class ConnectionDebuggerFactory(ClientFactory):
    """Class which puts the activity into a deferred, as the attribute "d"."""
    # not necessary to debug the protocol when testing tls
    protocol = ConnectionDebuggerProtocol

    def __init__(self):
        self.d = defer.Deferred()

    # def startedConnecting(self, connector):
    #     print "started connecting..."

    def clientConnectionFailed(self, _, reason):
        return self.d.errback(reason)

    def clientConnectionLost(self, _, reason):
        return self.d.errback(reason)

    def gotData(self, data):
        print "data received: %s" % data
        self.d.callback(data)


def get_token(uname):
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    ac.find_by_name(uname)
    return ac.get_trait(co.trait_password_token)['strval']
