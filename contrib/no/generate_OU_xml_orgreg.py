#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010-2023 University of Oslo, Norway
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
This script generates an XML file to replace the old file we got from SAP
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging
import operator
import os
import xml.dom.minidom
import xml.etree.ElementTree as ET  # noqa: N817

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.date
from Cerebrum.config import loader
from Cerebrum.modules.orgreg.client import get_client, OrgregClientConfig
from Cerebrum.utils.reprutils import ReprFieldMixin

logger = logging.getLogger(__name__)


orgreg_to_stedkode = {
    # The root ou (orgreg-id 0) has no stedkode
    0: "",
}


def to_text(value):
    """ ensure value is a unicode text object. """
    if isinstance(value, bytes):
        return value.decode('ascii')
    elif isinstance(value, six.text_type):
        return value
    else:
        return six.text_type(value)


class XmlBase(ReprFieldMixin):

    __repr_id__ = False
    __repr_module__ = False

    name = "Base"
    fields = tuple()

    def __init__(self, *values):
        self._values = {}
        if len(values) != len(self.fields):
            raise TypeError("%s expected %d arguments, got %d"
                            % (self.__class__.__name__, len(self.fields),
                               len(values)))
        self._values.update(zip(self.fields, values))

    def __getattr__(self, attr):
        try:
            super(XmlBase, self).__getattr__(attr)
        except AttributeError:
            if attr not in self._values:
                raise
            return self._values[attr]

    def __iter__(self):
        # Order by self.fields
        # for f in self.fields:
        #     yield f, self._values[f]
        return iter(self._values.items())

    def to_xml(self):
        elem = ET.Element(self.name)
        for field, value in self:
            # if value is None:
            #     continue
            field_elem = ET.SubElement(elem, field)
            field_elem.text = to_text(value or "")
        return elem


class XmlSted(XmlBase):

    __repr_fields__ = ("OrgRegOuId", "Stedkode", "Overordnetstedkode")

    name = "Sted"
    fields = (
        "Overordnetstedkode",
        "DfoOrgId",
        "Stedkode",
        "Startdato",
        "Sluttdato",
        "OrgRegOuId",
    )

    def update_parent(self, parent_map):
        parent_id = int(self._values['Overordnetstedkode'])
        try:
            parent_sko = parent_map[int(parent_id)]
        except KeyError:
            logger.error("Parent of %r has no location code "
                         "(stedkode)", self)
            parent_sko = None
        self._values['Overordnetstedkode'] = parent_sko


class XmlKomm(XmlBase):

    __repr_fields__ = ("Type",)

    name = "Kommunikasjon"
    fields = (
        "Type",
        "Verdi",
        "Prioritet",
    )


class XmlBruk(XmlBase):

    __repr_fields__ = ("Type",)

    name = "Bruksomrade"
    fields = (
        "Type",
        "Verdi",
        "Niva",
    )


class XmlAdr(XmlBase):

    __repr_fields__ = ("Type",)

    name = "Adresse"
    fields = (
        "Type",
        "Distribusjon",
        "CO",
        "Gateadresse",
        "Adressetillegg",
        "Postnummer",
        "Poststed",
        "Landkode",
    )


class XmlNavn(XmlBase):

    __repr_fields__ = ("Sprak", "Akronym")

    name = "Navn"
    fields = (
        "Sprak",
        "Akronym",
        "Navn20",
        "Navn40",
        "Navn120",
    )


def get_external_key(ou_data, id_source, id_type):
    """ Get OU identifier from orgreg externalKeys field """
    for x in ou_data["externalKeys"]:
        if (x["sourceSystem"] == id_source
                and x["type"] == id_type
                and x["value"]):
            return x["value"]
    raise LookupError("no externalKey with sourceSystem=%r, type=%r"
                      % (id_source, id_type))


def transform_address(ou_json, _type):
    if _type not in ou_json:
        return
    _postal = ou_json[_type]
    address_type_mapper = {
        "postalAddress": "Postadresse",
        "visitAddress": "Besøksadresse"
    }

    extended_address = _postal.get("extended", None)
    street_address = _postal.get("street", None)
    city = _postal.get("city", None)
    country = _postal.get("country", None)
    postal_code = _postal.get("postalCode", None)

    addr = XmlAdr(
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

    if long_name:  # This checks for key longName
        long_name = long_name.get(_type, "")
    if not long_name:
        long_name = name

    if short_name:  # This checks for key shortName
        short_name = short_name.get(_type, "")
    if not short_name:
        short_name = name

    if acronym:
        acronym = acronym.get(_type, "")

    name = XmlNavn(
        language_mapper[_type],
        acronym,
        short_name,
        name,
        long_name
    )
    return name


# Convert contact fields to Communication args
CONTACT_TO_COMM = {
    "phone": {"type": "Telefon1", "pri": "1"},
    "fax": {"type": "Telefax", "pri": "0"}
}


# Convert tags in Orgreg to cereconf.USAGE_TO_SPREAD data
TAGS_TO_USAGE = {
    "arkivsted": {"type": "Arkivsted", "level": 1},
    "tillatt_organisasjon": {"type": "Tillatt Organisasjon", "level": 1},
    "tillatt_koststed": {"type": "Tillatt koststed", "level": 1},
    "elektronisk_katalog": {"type": "Elektronisk katalog", "level": 1},
    # "reply": {}  # TODO ??
}


def parse_ou(ou_json, dfo_system):
    sap2bas_sted = []

    # identifiers
    orgreg_id = ou_json["ouId"]
    try:
        stedkode = get_external_key(ou_json, "sapuio", "legacy_stedkode")
        dfo_sap_id = get_external_key(ou_json, dfo_system, "dfo_org_id")
    except LookupError as e:
        logger.debug("Skipping orgreg_id=%r: %s", orgreg_id, e)
        return None

    # Keep track of ou_id:stedkode mapping for later in
    # xml serialization since data from orgReg isn't ordered
    orgreg_to_stedkode[orgreg_id] = stedkode

    parent = ou_json.get("parent", "")

    valid_from = ou_json["validFrom"]  # This is required
    try:
        Cerebrum.utils.date.parse_date(valid_from)
    except ValueError as e:
        logger.error("Skipping orgreg_id=%s, invalid validFrom=%r (%s)",
                     orgreg_id, valid_from, e)
        return None

    default_valid_to = "9999-12-31"
    valid_to = ou_json.get("validTo", default_valid_to)
    if valid_to != default_valid_to:
        try:
            Cerebrum.utils.date.parse_date(valid_to)
        except ValueError:
            logger.warning(
                "orgreg_id=%s, invalid validTo=%r, using default %r (%s)",
                orgreg_id, valid_to, default_valid_to, e)
            valid_to = default_valid_to

    # <Sted>
    _place = XmlSted(
        parent,
        dfo_sap_id,
        stedkode,
        valid_from,
        valid_to,
        orgreg_id,
    )
    sap2bas_sted.append(_place)

    _sort_by_key = operator.itemgetter(0)

    # <Kommunikasjon>
    for orgreg_field, xml_values in sorted(CONTACT_TO_COMM.items(),
                                           key=_sort_by_key,
                                           reverse=True):
        if orgreg_field in ou_json:
            _com = XmlKomm(
                xml_values["type"],
                ou_json[orgreg_field],
                xml_values["pri"]
            )
            sap2bas_sted.append(_com)

    # <Bruksomrade>
    orgreg_tags = set(ou_json.get("tags") or ())
    for tag, xml_values in sorted(TAGS_TO_USAGE.items(), key=_sort_by_key):
        if tag in orgreg_tags:
            _ua = XmlBruk(
                xml_values["type"],
                None,
                xml_values["level"]
            )
            sap2bas_sted.append(_ua)

    # <Kommunikasjon>
    for _type in ["postalAddress", "visitAddress"]:
        addr = transform_address(ou_json, _type)
        if addr is None:
            continue
        sap2bas_sted.append(addr)

    # <Navn>
    for _type in ["nob", "eng", ]:  # ["nob", "eng", "nno"]
        name = transform_name(ou_json, _type)
        if name is None:
            continue
        sap2bas_sted.append(name)
    return sap2bas_sted


def update_parent(org_units):
    for org_unit in org_units:
        for xml_obj in org_unit:
            if xml_obj.__class__ is XmlSted:
                xml_obj.update_parent(orgreg_to_stedkode)


def serialize_ou_to_xml(xml_node):
    sted_root = ET.Element('sap2bas_sted')
    for node in xml_node:
        sted_root.append(node.to_xml())
    return sted_root


def construct_xml(org_units):
    data_root = ET.Element('sap2bas_data')
    for xml_node in org_units:
        xml_sub_node = serialize_ou_to_xml(xml_node)
        data_root.append(xml_sub_node)

    # ElementTree.tostring()/ElementTree.Element.write() is kind of insane:
    # If the *encoding* argument itself is a unicode object, then the
    # xml-declaration will *also* be in unicode, but the remaining elements
    # will be bytestrings encoded in whatever encoding is given.  If any xml
    # element data contains non-ascii text, this causes issues in the final
    # `b"".join()` in ElementTree.tostring()
    xml_text = ET.tostring(data_root, encoding=b"UTF-8")
    dom = xml.dom.minidom.parseString(xml_text)
    return dom.toprettyxml(encoding="UTF-8")


def parse_data_from_api(data, dfo_system):
    include = 0
    skip = 0
    nodes = []
    for _ou in data:
        org_unit = parse_ou(_ou, dfo_system)
        if org_unit is not None:
            nodes.append(org_unit)
            include += 1
        else:
            skip += 1
    logger.info("org units: %d included, %d skipped", include, skip)
    return nodes


def write_xml(org_units, filepath):

    if len(filepath) > 0 and filepath[0] != "/":
        filepath = os.path.abspath(filepath)

    if os.path.exists(filepath):
        if os.path.isdir(filepath):
            logger.error("path a directory, not a file")
            return

    xml = construct_xml(org_units)

    with open(filepath, "wb") as f:
        f.write(xml)

    logger.info("Wrote org units to %s", filepath)


def autoload_config(name='orgreg-client'):
    """
    Autoload an OrgregClientConfig from the Cerebrum config dir.

    .. note::
        This is a temporary solution, to avoid changing the input arguments of
        this script.  Should be replaced by a mandatory --client argument.
    """
    config = OrgregClientConfig()
    loader.read(config, name)
    config.validate()
    return config


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description=(
            "Fetch and write all org units from orgreg to a sap2bas xml file"
        ),
    )

    parser.add_argument(
        '-c', '--config',
        help="Orgreg client config (see Cerebrum.modules.orgreg.client)",
    )

    parser.add_argument(
        '-t', '--test',
        action='store_true',
        help='for development, use dfo_sap-9902 instead of production dfo_sap',
    )

    parser.add_argument(
        'filepath',
        help='path to write the xml file',
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('tee', args)
    logger.info("start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    config = args.config or autoload_config()
    dfo_system = "dfo_sap-9902" if args.test else "dfo_sap"

    client = get_client(config)
    raw_data = client.list_org_units()

    org_units = parse_data_from_api(raw_data, dfo_system)
    update_parent(org_units)
    write_xml(org_units, args.filepath)

    logger.info("done %s", parser.prog)


if __name__ == '__main__':
    main()
