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
        url = "http://localhost:8959/SOAP/?wsdl"
        logging.basicConfig(level=logging.INFO)
        logging.getLogger('suds').setLevel(logging.INFO)
        self.client = suds.client.Client(url)
        self.client.set_options(cache=None)
    

    def test_1_get_usernames(self):
        "Get person data for person with active account(s)"
        res = self.client.service.get_usernames("externalid_sap_ansattnr",
                                                "10001626")
        print res

    def test_2_get_usernames2(self):
        "Get person data for person2 with active account(s)"
        res = self.client.service.get_usernames("externalid_studentnr",
                                                "476611")
        print res

    def test_3_generate_token(self):
        "Generate and store password token for a user"
        res = self.client.service.generate_token("externalid_sap_ansattnr",
                                                 "10001626",
                                                 "rogertst",
                                                 "91726078",
                                                 "123qwe")
        
    def test_4_check_token(self):
        "check token for a user"
        res = self.client.service.check_token("rogertst",
                                              get_token("rogertst"),
                                              "123qwe")
            
    def test_5_validate_password(self):
        pwd = ''.join(random.sample(map(chr, range(33,126)), 8))
        res = self.client.service.validate_password(pwd)

    def test_6_set_password(self):
        pwd = ''.join(random.sample(map(chr, range(33,126)), 8))
        res = self.client.service.set_password("externalid_sap_ansattnr",
                                               "10001626",
                                               "rogertst",
                                               "91726078",
                                               "123qwe",
                                               get_token("rogertst"),
                                               pwd)
        
    def test_7_abort_token(self):
        "Delete token for a user"
        res = self.client.service.abort_token("rogertst")

    def test_8_generate_token(self):
        "Generate and store password token for a user"
        res = self.client.service.generate_token("externalid_studentnr",
                                                 "476611",
                                                 "joakiho",
                                                 "22840195",
                                                 "")
    
    def test_9_check_token(self):
        "check token for a user"
        res = self.client.service.check_token("joakiho",
                                              get_token("joakiho"),
                                              "")
        

def get_token(uname):
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    ac.find_by_name(uname)
    return ac.get_trait(co.trait_password_token)['strval']
    
    
