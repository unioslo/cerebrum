#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test SAP service using a simple suds client.

"""
import suds
import logging


class TestSapService:
    def setUp(self):
        url = "http://localhost:8899/SOAP/?wsdl"
        logging.basicConfig(level=logging.INFO)
        logging.getLogger('suds').setLevel(logging.INFO)
        self.client = suds.client.Client(url)
        self.client.set_options(cache=None)

    def test_get_person_data(self):
        "Get person data for person with active account(s)"
        self.client.service.get_person_data("externalid_sap_ansattnr",
                                            "10001626")

    def test_get_person_data_2(self):
        "get_person_data must handle persons without (active) accounts"
        self.client.service.get_person_data("externalid_sap_ansattnr",
                                            "10004159")

    # TODO: se om vi kan sette opp feilsituasjoner som logges på en
    # fornuftig måte.


class TestUpdatePerson:
    def setUp(self):
        url = "http://localhost:8899/SOAP/?wsdl"
        logging.basicConfig(level=logging.INFO)
        logging.getLogger('suds').setLevel(logging.INFO)
        self.client = suds.client.Client(url)
        self.client.set_options(cache=None)
        # Set up a person to update
        self.p = self.client.factory.create('{tns}Person')
        # info
        pi = self.client.factory.create('{tns}PersonInfo')
        pi.Ansattnr = "12345"
        pi.Fornavn = "Harry"
        pi.Etternavn = "Hansen"
        pi.Title = "Slask"
        pi.Fodselsnummer = "28067501000"
        pi.Fodselsdato = "280675"
        pi.Kjonn = "M"
        pi.Nasjonalitet = "N"
        self.p.PersonInfo.append(pi)
        # adress
        pa = self.client.factory.create('{tns}PersonAddress')
        pa.Ansattnr = "12345"
        pa.Gateadress = "Problemveien 1"
        pa.Postnummer = "0123"
        pa.Poststed = "Oslo"
        pa.Landkode = "N"
        self.p.PersonAddress.append(pa)

    def test_update_or_create_person(self):
        self.client.service.update_person(self.p)

    def test_update_name(self):
        self.p.PersonInfo[0].Etternavn = "Anker-Hansen"
        self.client.service.update_person(self.p)

    def test_update_title(self):
        self.p.PersonInfo[0].Title = "Flink IT-mann"
        self.client.service.update_person(self.p)

    def test_update_fnr(self):
        self.p.PersonInfo[0].Fodselsnummer = "28067502000"
        self.client.service.update_person(self.p)

    # def test_update_adr(self):
    #     pass
    #
    # def test_update_reservert(self):
    #     pass
    #
    # def test_update_(self):
    #     pass
    #
    # def test_update_(self):
    #     pass
    #
    # def test_update_(self):
    #     pass
    #
    # def test_update_(self):
    #     pass
    #
    # def test_update_(self):
    #     pass
    #
    # def test_update_(self):
    #     pass
    #
    # def test_update_(self):
    #     pass
    #
    # def test_update_(self):
    #     pass
    #
    # def test_update_(self):
    #     pass
    #
    # def test_update_(self):
    #     pass
    #
    # def test_create_new_person(self):
    #     pass
