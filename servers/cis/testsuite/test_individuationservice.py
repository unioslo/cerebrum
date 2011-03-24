#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test SAP service using a simple suds client.

"""
import random
import suds
from suds.cache import Cache
import logging
from Cerebrum import Errors
from Cerebrum.Utils import Factory


class TestIndividuationService:
    def setUp(self):
        url = "https://localhost:8959/SOAP/?wsdl"
        logging.basicConfig(level=logging.INFO)
        logging.getLogger('suds').setLevel(logging.INFO)
        self.client = suds.client.Client(url)
        self.client.set_options(cache=None)
    

    def test_01_get_usernames(self):
        "Get person data for person with active account(s)"
        res = self.client.service.get_usernames("externalid_sap_ansattnr",
                                                "10001626")
        print res

    def test_02_get_usernames2(self):
        "Get person data for person2 with active account(s)"
        res = self.client.service.get_usernames("externalid_studentnr",
                                                "476611")
        print res

    def test_03_generate_token(self):
        "Generate and store password token for a user"
        res = self.client.service.generate_token("externalid_sap_ansattnr",
                                                 "10001626",
                                                 "rogertst",
                                                 "91726078",
                                                 "123qwe")
        
    def test_04_check_token(self):
        "check token for a user"
        res = self.client.service.check_token("rogertst",
                                              get_token("rogertst"),
                                              "123qwe")
            
    def test_05_validate_password(self):
        pwd = ''.join(random.sample(map(chr, range(33,126)), 8))
        res = self.client.service.validate_password(pwd)

    def test_06_set_password(self):
        pwd = ''.join(random.sample(map(chr, range(33,126)), 8))
        res = self.client.service.set_password("rogertst",
                                               pwd,
                                               "123qwe",
                                               get_token("rogertst"))
        
    def test_07_abort_token(self):
        "Delete token for a user"
        res = self.client.service.abort_token("rogertst")

    def test_08_generate_token(self):
        "Generate and store password token for a user"
        res = self.client.service.generate_token("externalid_studentnr",
                                                 "476611",
                                                 "joakiho",
                                                 "22840195",
                                                 "")
    
    def test_09_check_token(self):
        "check token for a user"
        res = self.client.service.check_token("joakiho",
                                              get_token("joakiho"),
                                              "")

    # This should fail with cerebrum error
    def test_10_get_usernames(self):
        res = self.client.service.get_usernames("externalid_fooid",
                                                "1234")

    # This should fail with client error
    def test_11_callfoo(self):
        res = self.client.service.foo()



def get_token(uname):
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    ac.find_by_name(uname)
    return ac.get_trait(co.trait_password_token)['strval']
    
    
