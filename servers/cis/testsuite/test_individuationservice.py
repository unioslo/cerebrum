#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test SAP service using a simple suds client.

"""
import suds
from suds.cache import Cache
import logging



class TestIndividuationService:
    def setUp(self):
        url = "http://localhost:8959/SOAP/?wsdl"
        logging.basicConfig(level=logging.INFO)
        logging.getLogger('suds').setLevel(logging.INFO)
        self.client = suds.client.Client(url)
        self.client.set_options(cache=None)
    

    def test_get_usernames(self):
        "Get person data for person with active account(s)"
        res = self.client.service.get_usernames("externalid_sap_ansattnr",
                                                "10001626")

    def test_generate_token(self):
        "Generate and store password token for a user"
        res = self.client.service.generate_token("externalid_sap_ansattnr",
                                                 "10001626",
                                                 "rogerha",
                                                 "98765432",
                                                 "123qwe")
        

    # These tests should fail
    # TBD: se om vi kan sette opp feilsituasjoner som logges på en
    # fornuftig måte.
    def test_get_person_data_2(self):
        "get_person_data must handle wrong parameters"
        res = self.client.service.get_usernames("externalid_studentnr",
                                                  "12345")

    def test_get_person_data_3(self):
        "get_person_data must handle wrong parameters"
        res = self.client.service.get_usernames("sdexternalid_studentnr",
                                                "12345")

