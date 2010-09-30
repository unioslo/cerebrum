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

    # def test_get_person_data_2(self):
    #     "get_person_data must handle persons without (active) accounts"
    #     res = self.client.service.get_usernames("externalid_studentnr",
    #                                               "12345")

    # TBD: se om vi kan sette opp feilsituasjoner som logges på en
    # fornuftig måte.

