#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010-2021 University of Oslo, Norway
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

"""This script generates an XML file to replace the old file we got from SAP

The file exported contains information about:

- OU: All OUs from Orgreg.
"""

import argparse
import logging
import os
import xml.dom.minidom
import xml.etree.ElementTree as ET

import requests

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import read_password
logger = logging.getLogger(__name__)

url = "https://gw-uio.intark.uh-it.no/orgreg/v3/ou"


def get_ou_data():
    api_key = read_password("orgreg", "api.uio.intark")
    headers = {"X-Gravitee-Api-Key": api_key}
    x = requests.get(url, headers=headers)
    return x.json()


OUs = list()
parent_to_stedkode = {}


class Place(object):
    Overordnetstedkode = str()
    Stedkode = str()
    Startdato = str()
    Sluttdato = str()
    OrgRegOuId = str()

    def __init__(self, parent, stedkode, start_date, end_date, ou_id):
        self.Overordnetstedkode = str(parent)
        self.Stedkode = str(stedkode)
        self.Startdato = str(start_date)
        self.Sluttdato = str(end_date)
        self.OrgRegOuId = str(ou_id)

    def __iter__(self):
        for attr, value in self.__dict__.iteritems():
            yield attr, value

    def __repr__(self):
        ov = self.Overordnetstedkode
        st = self.Stedkode
        org = self.OrgRegOuId
        return "Over:{} Sted:{} OrgReg:{}".format(ov, st, org)


class ExternalKeys(object):
    source_system = str()
    _type = str()
    value = str()

    def __init__(self):
        pass

    def __iter__(self):
        for attr, value in self.__dict__.iteritems():
            yield attr, value


class Communication(object):
    Type = str()
    Verdi = str()
    Prioritet = int()

    def __init__(self, _type, value, priority):
        self.Type = _type
        self.Verdi = value
        self.Prioritet = priority

    def __iter__(self):
        for attr, value in self.__dict__.iteritems():
            yield attr, value


class UseArea(object):
    Type = str()
    Verdi = str()
    Niva = int()

    def __init__(self, _type, value, level):
        self.Type = _type
        self.Verdi = value
        self.Niva = level

    def __iter__(self):
        for attr, value in self.__dict__.iteritems():
            yield attr, value


class Adress(object):
    Type = str()
    Distribusjon = str()
    CO = str()
    Gateadresse = str()
    Adressetillegg = str()
    Postnummer = str()
    Poststed = str()
    Landkode = str()

    def __init__(self, _type, distribution, co, street_address,
                 address_line_2, post_code, city, area_code):
        self.Type = _type
        self.Distribusjon = distribution
        self.CO = co
        self.Gateadresse = street_address
        self.Adressetillegg = address_line_2
        self.Postnummer = post_code
        self.Poststed = city
        self.Landkode = area_code

    def __iter__(self):
        for attr, value in self.__dict__.iteritems():
            yield attr, value


class Name(object):
    Sprak = str()
    Akronym = str()
    Navn20 = str()
    Navn40 = str()
    Navn120 = str()

    def __init__(self, language, acronym, name_20, name_40, name_120):
        self.Sprak = language
        self.Akronym = acronym
        self.Navn20 = name_20
        self.Navn40 = name_40
        self.Navn120 = name_120

    def __iter__(self):
        for attr, value in self.__dict__.iteritems():
            yield attr, value


class OU(object):
    externalKeys = None
    place = dict()
    commmunication = dict()
    use_area = dict()
    adress = dict()
    name = dict()

    def __init__(self):
        pass

    def __iter__(self):
        for attr, value in self.__dict__.iteritems():
            yield attr, value


def get_legacy_stedkode(externalKey, ouId, ou_json):
    for x in externalKey:
        if x["sourceSystem"] == "sapuio" and x["type"] == "legacy_stedkode":
            # Keep track of ouId:stedkode mapping for later in
            # xml serialization since data from orgReg isn't ordered
            parent_to_stedkode[ouId] = x["value"]
            return x
    return False


def transform_address(ou_json, _type):
    if _type not in ou_json:
        return
    _postal = ou_json[_type]
    address_type_mapper = {
        "postalAddress": "Postadresse",
        "visitAddress": u"Besøksadresse"
    }

    extended_address = _postal.get("extended", None)
    street_address = _postal.get("street", None)
    city = _postal.get("city", None)
    country = _postal.get("country", None)
    postal_code = _postal.get("postalCode", None)

    addr = Adress(
        address_type_mapper[_type],
        "INTERN",  # Everything is aparently INTERN
        None,  # CO attr is no more, unless they just forgot
        street_address,
        extended_address,
        postal_code,
        city,
        country
    )
    return addr


def transform_name(ou_json, _type):
    # XML wants language on form ISO 639-1
    # While we get 3 letter ISO 639-2 from json
    language_mapper = {"nob": "NB", "eng": "EN", "nno": "NN"}

    name = ou_json["name"][_type]  # This is required to be present
    long_name = ou_json.get("longName", "")
    short_name = ou_json.get("shortName", "")
    acronym = ou_json.get("acronym", "")

    if long_name:
        long_name = long_name.get(_type, "")

    if short_name:
        short_name = short_name.get(_type, "")

    if acronym:
        acronym = acronym.get(_type, "")

    if not long_name or not short_name:
        return None

    name = Name(
        language_mapper[_type],
        acronym,
        short_name,
        name,
        long_name
    )
    return name


def parse_ou(ou_json):
    sap2bas_sted = []

    # Insert root parent to point to empty string
    parent_to_stedkode[0] = ""
    stedkode = get_legacy_stedkode(
        ou_json["externalKeys"], ou_json["ouId"], ou_json
    )
    if not stedkode:
        return

    parent = ou_json.get("parent", "")
    valid_to = ou_json.get("validTo", "9999-12-31")

    # <Sted>
    _place = Place(
        parent,
        stedkode["value"],
        ou_json["validFrom"],
        valid_to,
        ou_json["ouId"]
    )
    sap2bas_sted.append(_place)

    # <Kommunikasjon>
    communication_mapper = {
        "phone": {"type": "Telefon1", "pri": "1"},
        "fax": {"type": "Telefax", "pri": "0"}
    }
    for _type in ["phone", "fax"]:  # OrgReg only has 1 phone and 1 fax
        if _type in ou_json:        # as opposed to sapuios Telephone2..x
            _com = Communication(
                communication_mapper[_type]["type"],
                ou_json[_type],
                communication_mapper[_type]["pri"]
            )
            sap2bas_sted.append(_com)

    # <Bruksomrade>
    if "tags" in ou_json:  # Bruksomrade is aparently not required?
        # Names are not the same in orgreg as in sapuio
        use_area_mapper = {
            "arkivsted": {"type": "Arkivsted", "level": 1},
            "tillattorganisasjon": {"type": "Tillatt Organisasjon", "level": 1},
            "costcenter": {"type": "Tillatt koststed", "level": 1},
            "directory": {"type": "Elektronisk katalog", "level": 1},
            # "reply": {}  # TODO ??
        }
        for _type in ou_json["tags"]:
            if _type in use_area_mapper:
                _ua = UseArea(
                    use_area_mapper[_type]["type"],
                    None,
                    use_area_mapper[_type]["level"]
                )
                sap2bas_sted.append(_ua)

    # <Kommunikasjon>
    for _type in ["postalAddress", "visitAddress"]:
        addr = transform_address(ou_json, _type)
        if addr is None:
            continue
        sap2bas_sted.append(addr)

    # <Navn>
    for _type in ["nob", ]:  # ["nob", "eng", "nno"]
        name = transform_name(ou_json, _type)
        if name is None:
            continue
        sap2bas_sted.append(name)
    return sap2bas_sted


def serialize_ou_to_xml(xml_node):
    root_node = ET.Element('sap2bas_sted')
    for node in xml_node:
        cls_name = node.__class__.__name__
        if cls_name == "Place":
            place = ET.SubElement(root_node, "Sted")
            for element in node:
                element = list(element)  # A cast from tuple to list
                if element[0] == "Overordnetstedkode" and element[1]:
                    try:
                        element[1] = parent_to_stedkode[int(element[1])]
                    except KeyError as e:
                        logger.error(
                            "Could not index stedkode from parent attribute", e
                        )
                        continue
                item1 = ET.SubElement(place, str(element[0]))
                item1.text = str(element[1])

        if cls_name == "Communication":
            place = ET.SubElement(root_node, "Kommunikasjon")
            for element in node:
                item1 = ET.SubElement(place, str(element[0]))
                item1.text = str(element[1])

        if cls_name == "UseArea":
            place = ET.SubElement(root_node, "Bruksomrade")
            for element in node:
                item1 = ET.SubElement(place, str(element[0]))
                item1.text = str(element[1])

        if cls_name == "Adress":
            place = ET.SubElement(root_node, "Adresse")
            for element in node:
                item1 = ET.SubElement(place, str(element[0]))
                item1.text = element[1]

        if cls_name == "Name":
            place = ET.SubElement(root_node, "Navn")
            for element in node:
                item1 = ET.SubElement(place, str(element[0]))
                item1.text = element[1]

    return root_node


def construct_xml(OUs):
    root_root_node = ET.Element('sap2bas_data')
    for xml_node in OUs:
        xml_sub_node = serialize_ou_to_xml(xml_node)
        root_root_node.append(xml_sub_node)

    mydata = ET.tostring(root_root_node, encoding="UTF-8")
    dom = xml.dom.minidom.parseString(mydata)
    return dom.toprettyxml(encoding="UTF-8")


def get_data_from_api(OUs):
    data = get_ou_data()
    for _ou in data:
        org_unit = parse_ou(_ou)
        if org_unit is not None:
            OUs.append(org_unit)


def write_xml(OUs, filepath):

    if len(filepath) > 0 and filepath[0] != "/":
        filepath = os.path.abspath(filepath)

    if os.path.exists(filepath):
        if os.path.isdir(filepath):
            logger.error("path a directory, not a file")
            return

    xml = construct_xml(OUs)

    with open(filepath, "wb") as f:
        f.write(xml)

    logger.info("Wrote OU data to file: {}".format(filepath))


def main(OUs, inargs=None):
    parser = argparse.ArgumentParser(
        description='Run script to batch fetch all OUs from orgreg and \
        produce an xml file',
    )

    parser.add_argument(
        'filepath',
        help='path to write the xml file',
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('tee', args)

    logger.info("Starting %s", parser.prog)

    get_data_from_api(OUs)
    write_xml(OUs, args.filepath)


if __name__ == '__main__':
    main(OUs)
