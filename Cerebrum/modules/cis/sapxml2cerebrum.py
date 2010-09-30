# -*- coding: utf-8 -*-
# Copyright 2010 University of Oslo, Norway
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

"""
This module implements an abstraction layer for SAP-originated HR
data, as delivered from SAP Process Integration. (SAP PI)
"""

from lxml import etree
import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum.modules.xmlutils.sapxml2object import SAPPerson
from Cerebrum.modules.xmlutils.object2cerebrum import XML2Cerebrum
from Cerebrum.modules.xmlutils.xml2object import \
     HRDataPerson, DataAddress, DataEmployment, DataName
from Cerebrum.modules.no.fodselsnr import personnr_ok


# TODO: This code is not finished yet. It's just a sketch to
# illustrate how this is supposed to look like.

# FIXME: namespace issues. Hardwired for now

class SAPXMLPerson2Cerebrum(object):
    """
    parse XML
    check consistency
    write to cerebrum
    """

    # Each subelement has it's own parse method
    tag2method = { "{tns}PersonInfo" : "parse_person_info",
                   "{tns}PersonAddress"  : "parse_person_address", 
                   "{tns}PersonComm" : "parse_person_comm",
                   "{tns}PersonHovedstilling" : "parse_hovedstilling",
                   "{tns}PersonBistilling": "parse_bistilling",}

    tag2type = {"Fornavn": HRDataPerson.NAME_FIRST,
                "Etternavn": HRDataPerson.NAME_LAST,
                "Fodselsnummer": HRDataPerson.NO_SSN,
                "Mann": HRDataPerson.GENDER_MALE,
                "Kvinne": HRDataPerson.GENDER_FEMALE,
                "Ukjent": HRDataPerson.GENDER_UNKNOWN,
                "HovedStilling": DataEmployment.HOVEDSTILLING,
                "Bistilling": DataEmployment.BISTILLING,
                "Ansattnr": SAPPerson.SAP_NR,
                "Title": HRDataPerson.NAME_TITLE,}


    def __init__(self, sap_xml_person):
        self.db = Factory.get('Database')()
        # TBD: import_HR eller import_SAP? Bruker sistnevnte nå for å
        # skille fra eksisterende
        self.db.cl_init(change_program='import_SAP')
        self.const = Factory.get('Constants')(self.db)
        self.group = Factory.get("Group")(self.db)
        self.person = Factory.get("Person")(self.db)
        self.logger = Factory.get_logger("console")

        self.logger.debug("Starting")
        # Sett data-struktur vi trenger
        self.result = SAPPerson()
        # parse xmltree
        self.parse(sap_xml_person)


    def update():
        """
        Try to insert or update person in Cerebrum.
        """
        xml2db = XML2Cerebrum(self.db, self.source_system, self.logger)


    def parse(self, sap_xml_person):
        # We know the xml structure since the it's defined in the wsdl
        # file. Thus we don't need lots of checking of the xml structure
        self.logger.debug("sap_xml_person:")
        self.logger.debug(etree.tostring(sap_xml_person, pretty_print=True))
        #assert sap_xml_person.tag in ("Person", "Ansatt")
        # travers children elements
        for el in sap_xml_person:
            self.logger.debug("el.tag %s" % el.tag)
            try:
                # Run parse method for the given subelement
                tag = self.tag2method[el.tag]
                getattr(self, tag)(el)
            except KeyError:
                self.logger.warn("Unknown Element: %s" % el.tag)


    def parse_person_info(self, sub):
        self.logger.debug("Parsing %s" % sub.tag)

        for el in sub.iter():
            value = None
            if el.text:
                value = el.text.strip().encode("latin1")
    
            # TBD: få bort Mellomnavn fra sap?
            # Per baardj's request, we consider middle names as first names.
            middle = ""
            middle = el.find("PersonInfo/Mellomnavn")
            if middle is not None and middle.text:
                middle = middle.text.encode("latin1").strip()
    
            if el.tag == "Fornavn":
                if middle:
                    value += " " + middle
    
                # TBD: Skal vi fortsatt ta hensyn til '*' og'@'
                if '*' in value or '@' in value:
                    self.logger.debug("Name contains '@' or '*', ignored")
                    # Since the element is marked as void, there is no need to
                    # process further (we have no guarantee that any data
                    # would make sense and we won't have even more spurious
                    # warnings). 
                    return None
                # TODO: fix
                self.result.add_name(DataName(self.tag2type[el.tag], value))
            elif el.tag == "Etternavn":
                if '*' in value or '@' in value:
                    self.logger.debug("Name contains '@' or '*', ignored")
                    # Se <Fornavn>.
                    return None
                # TODO: fix
                self.result.add_name(DataName(self.tag2type[el.tag], value))
            elif el.tag == "Fodselsnummer":
                self.result.add_id(self.tag2type[el.tag], personnr_ok(value))
            elif el.tag == "Ansattnr":
                self.result.add_id(self.tag2type[el.tag], value)
            elif el.tag == "Fodselsdato":
                self.result.birth_date = self._make_mxdate(value)
            elif el.tag == "Kjonn":
                self.result.gender = self.tag2type[value]
            elif sub.tag == "Title":
                if value:
                    self.result.add_name(DataName(self.tag2type[sub.tag], value))


    def parse_person_address(self, sub):
        #self.logger.debug("Parsing ", sub.tag)

        zipcode = city = country = addr_kind = ""
        street = []

        for el in sub.iter():
            value = None
            if el.text:
                value = el.text.strip().encode("latin1")

            if el.tag == "AdressType":
                addr_kind = value
            elif el.tag == "CO":
                street.insert(0, value)
            elif el.tag in ("Gateadress", "Adressetillegg"):
                street.append(value)
            elif el.tag == "Postnummer":
                # TBD: 8 is the length of the field in the database.
                # Hvordan behandle dette?
                if len(zip) <= 8:                
                    zipcode = value
            elif el.tag == "Poststed":
                city = value
            elif el.tag == "Landkode":
                country = value
            elif el.tag == "Reservert":
                # TODO: hvorfor er denne her? 
                pass

        if addr_kind:
            self.result.add_address(DataAddress(kind=addr_kind,
                                                street=street,
                                                zip=zipcode,
                                                city=city,
                                                country=country))
        else:
            self.logger.debug("Couldn't add address")


    def parse_person_comm(self, sub):
        self.logger.debug("Parsing ", sub.tag)
        # TODO: implementer


    def parse_hovedstilling(self, sub):
        self.logger.debug("Parsing ", sub.tag)
        # TODO: implementer


    def parse_bistilling(self, sub):
        self.logger.debug("Parsing ", sub.tag)
        # TODO: implementer

    
