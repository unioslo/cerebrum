#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010-2024 University of Oslo, Norway
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
Fetch org units from Orgreg as a "sap2bas.xml"-compatible file.

This script is a drop-in replacement for the legacy SAP file used by
``contrib/no/import_ou.py``.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import json
import logging
import xml.dom.minidom
import xml.etree.ElementTree as ET  # noqa: N817

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.config import loader
from Cerebrum.modules.orgreg import datasource
from Cerebrum.modules.orgreg.client import get_client, OrgregClientConfig
from Cerebrum.modules.orgreg.mapper import get_external_key
from Cerebrum.utils import file_stream
from Cerebrum.utils import reprutils
from Cerebrum.utils import text_compat

logger = logging.getLogger(__name__)


class XmlObject(reprutils.ReprFieldMixin):
    """ A simple xml element with preset sub-element values. """

    repr_id = False
    repr_module = False
    name = "BaseObject"
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
            return super(XmlObject, self).__getattr__(attr)
        except AttributeError:
            if attr not in self._values:
                raise
            return self._values[attr]

    def __iter__(self):
        for f in self.fields:
            yield f, self._values[f]

    def to_xml(self):
        """ Create an ElementTree.Element from this object. """
        elem = ET.Element(self.name)
        for field, value in self:
            field_elem = ET.SubElement(elem, field)
            field_elem.text = text_compat.to_text("" if value is None
                                                  else value)
        return elem


class XmlSted(XmlObject):
    repr_fields = ("OrgRegOuId", "Stedkode", "Overordnetstedkode")
    name = "Sted"
    fields = (
        "Overordnetstedkode",
        "DfoOrgId",
        "Stedkode",
        "Startdato",
        "Sluttdato",
        "OrgRegOuId",
    )

    def set_parent(self, value):
        self._values["Overordnetstedkode"] = value


class XmlKomm(XmlObject):
    repr_fields = ("Type",)
    name = "Kommunikasjon"
    fields = (
        "Type",
        "Verdi",
        "Prioritet",
    )


class XmlBruk(XmlObject):
    repr_fields = ("Type",)
    name = "Bruksomrade"
    fields = (
        "Type",
        "Verdi",
        "Niva",
    )


class XmlAdr(XmlObject):
    repr_fields = ("Type",)
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


class XmlNavn(XmlObject):
    repr_fields = ("Sprak", "Akronym")
    name = "Navn"
    fields = (
        "Sprak",
        "Akronym",
        "Navn20",
        "Navn40",
        "Navn120",
    )


class XmlCollection(reprutils.ReprFieldMixin):
    """ A simple XML container element. """

    repr_fields = ("size",)
    name = "BaseCollection"

    def __init__(self, *items):
        self.items = list(items)

    def __iter__(self):
        return iter(self.items)

    @property
    def size(self):
        return len(self.items)

    def append(self, elem):
        self.items.append(elem)

    def to_xml(self):
        elem = ET.Element(self.name)
        for node in self:
            elem.append(node.to_xml())
        return elem


class XmlRoot(XmlCollection):
    name = "sap2bas_data"


class XmlOrgUnit(XmlCollection):
    """
    sap2bas_sted XML element.

    This element is a collection of other XmlObject elements that together
    represents a single org unit.
    """
    repr_fields = ("orgreg_id", "location_code", "size")
    name = "sap2bas_sted"

    def __init__(self, parent_id, xml_sted, *xml_objects):
        self.parent_id = parent_id
        self.xml_sted = xml_sted
        super(XmlOrgUnit, self).__init__(*xml_objects)

    def __iter__(self):
        return iter([self.xml_sted] + self.items)

    @property
    def orgreg_id(self):
        return self.xml_sted.OrgRegOuId

    @property
    def location_code(self):
        return self.xml_sted.Stedkode


class OrgregMapper(object):
    """ Build XmlObject elements from sanitized Orgreg data. """

    contact_type_mapper = {
        "phone": {"type": "Telefon1", "pri": "1"},
        "fax": {"type": "Telefax", "pri": "0"},
        "email": {"type": "E-post adresse", "pri": "0"},
    }

    @classmethod
    def map_contact(cls, contact_type, contact_value):
        return XmlKomm(
            cls.contact_type_mapper[contact_type]['type'],
            contact_value,
            cls.contact_type_mapper[contact_type]['pri'],
        )

    @classmethod
    def iter_contacts(cls, data):
        for orgreg_field in sorted(cls.contact_type_mapper.keys(),
                                   reverse=True):
            if data[orgreg_field]:
                yield cls.map_contact(orgreg_field, data[orgreg_field])

    tags_to_usage = {
        "arkivsted": {"type": "Arkivsted", "level": 1},
        "tillatt_organisasjon": {"type": "Tillatt Organisasjon", "level": 1},
        "tillatt_koststed": {"type": "Tillatt koststed", "level": 1},
        "elektronisk_katalog": {"type": "Elektronisk katalog", "level": 1},
        # "reply": {}  # TODO ??
    }

    @classmethod
    def map_tag(cls, tag):
        return XmlBruk(
            cls.tags_to_usage[tag]['type'],
            None,
            cls.tags_to_usage[tag]['level'],
        )

    @classmethod
    def iter_tags(cls, data):
        tags = set(data['tags'])
        for tag in sorted(cls.tags_to_usage.keys()):
            if tag in tags:
                yield cls.map_tag(tag)

    address_type_mapper = {
        "postalAddress": "Postadresse",
        "visitAddress": "Besøksadresse",
    }

    @classmethod
    def map_address(cls, addr_type, addr_data):
        return XmlAdr(
            cls.address_type_mapper[addr_type],
            "INTERN",  # Everything is aparently INTERN
            None,  # CO attr is no more, unless they just forgot
            addr_data['street'],
            addr_data['extended'],
            addr_data['postalCode'],
            addr_data['city'],
            addr_data['country'],
        )

    @classmethod
    def iter_addresses(cls, data):
        for addr_type in sorted(cls.address_type_mapper.keys()):
            if data[addr_type]:
                yield cls.map_address(addr_type, data[addr_type])

    languages = ["nb", "en"]

    @classmethod
    def map_name(cls, data, lang):
        name = data["name"][lang]  # This is required to be present
        long_name = data['longName'].get(lang) or name
        short_name = data['shortName'].get(lang) or name
        acronym = data['acronym'].get(lang) or ""
        return XmlNavn(
            lang.upper(),
            acronym,
            short_name,
            name,
            long_name
        )

    @classmethod
    def iter_names(cls, data):
        for lang in cls.languages:
            yield cls.map_name(data, lang)


def parse_ou(raw_ou_data, dfo_system):
    """ Parse raw orgreg ou data into a XmlOrgUnit object. """
    raw_id = None
    try:
        raw_id = raw_ou_data.get("ouId")
        sanitized = datasource.parse_org_unit(raw_ou_data)
    except Exception as e:
        logger.error("invalid ou data for ouId=%s", repr(raw_id))
        raise

    # identifiers
    orgreg_id = sanitized["ouId"]
    try:
        stedkode = get_external_key(sanitized, "sapuio", "legacy_stedkode")
        dfo_sap_id = get_external_key(sanitized, dfo_system, "dfo_org_id")
    except ValueError as e:
        logger.debug("Skipping orgreg_id=%r: %s", orgreg_id, e)
        return None

    parent_id = sanitized['parent']
    valid_from = sanitized['validFrom'].isoformat()
    if sanitized['validTo']:
        valid_to = sanitized['validTo'].isoformat()
    else:
        valid_to = "9999-12-31"

    # <Sted>
    xml_ou = XmlOrgUnit(
        parent_id,
        XmlSted(
            None,  # we'll fill in parent once we've mapped all location codes
            dfo_sap_id,
            stedkode,
            valid_from,
            valid_to,
            orgreg_id,
        ),
    )

    # <Kommunikasjon>
    for xml_komm in OrgregMapper.iter_contacts(sanitized):
        xml_ou.append(xml_komm)

    # <Bruksomrade>
    for xml_bruk in OrgregMapper.iter_tags(sanitized):
        xml_ou.append(xml_bruk)

    # <Kommunikasjon>
    for xml_addr in OrgregMapper.iter_addresses(sanitized):
        xml_ou.append(xml_addr)

    # <Navn>
    for xml_navn in OrgregMapper.iter_names(sanitized):
        xml_ou.append(xml_navn)

    return xml_ou


def parse_api_data(data, dfo_system):
    include = 0
    skip = 0
    nodes = []
    stedkode_map = {
        # The root ou (orgreg-id 0) has no location code
        0: "",
    }
    for _ou in data:
        org_unit = parse_ou(_ou, dfo_system)
        if org_unit is not None:
            nodes.append(org_unit)
            include += 1
            stedkode_map[org_unit.orgreg_id] = org_unit.location_code
        else:
            skip += 1
    logger.info("org units: %d included, %d skipped", include, skip)

    root = XmlRoot()

    # update parent fields with location code
    for item in nodes:
        if item.parent_id and item.parent_id in stedkode_map:
            item.xml_sted.set_parent(stedkode_map[item.parent_id])
        else:
            logger.warning(
                "Parent id=%s of %s has no location code (stedkode)",
                repr(item.parent_id), repr(item))
        root.append(item)
    return root


def write_xml(org_units, filename):
    root_elem = org_units.to_xml()

    encoding = "UTF-8"
    # ElementTree.tostring()/ElementTree.Element.write() is kind of insane:
    # If the *encoding* argument itself is a unicode object, then the
    # xml-declaration will *also* be in unicode, but the remaining elements
    # will be bytestrings encoded in whatever encoding is given.  If any xml
    # element data contains non-ascii text, this causes issues in the final
    # `b"".join()` in ElementTree.tostring()
    xml_text = ET.tostring(root_elem,
                           encoding=(encoding.encode(encoding)
                                     if str is bytes
                                     else encoding))
    dom = xml.dom.minidom.parseString(xml_text)
    xml_bytes = dom.toprettyxml(encoding=encoding)

    with file_stream.get_output_context(filename, encoding=None) as f:
        f.write(xml_bytes)
    logger.info("Wrote org units to %s", f.name)


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


def read_from_api(config):
    client = get_client(config)
    logger.info("Loading orgreg data from %s", repr(client.urls))
    return client.list_org_units()


def read_from_file(filename):
    logger.info("Loading orgreg cache from %s", repr(filename))
    with file_stream.get_input_context(filename, encoding="utf-8") as f:
        return json.loads(f.read())


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description=(
            "Fetch and write all org units from orgreg to a sap2bas xml file"
        ),
    )
    source_group = parser.add_argument_group(
        "Source",
        """
        Fetch orgreg data from the API (default), or use a previously cached
        result.
        """.strip(),
    )
    source_mutex = source_group.add_mutually_exclusive_group()
    source_mutex.add_argument(
        '-c', '--config',
        help="Read orgreg client config from %(metavar)s",
        metavar="<filename>",
    )
    source_mutex.add_argument(
        '--cache',
        help="Use cached orgreg data from %(metavar)s",
        metavar="<filename>",
    )

    parser.add_argument(
        '-t', '--test',
        action='store_true',
        help='for development, use dfo_sap-9902 instead of production dfo_sap',
    )

    parser.add_argument(
        "output",
        help="output XML file to write (required)",
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('tee', args)
    logger.info("start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    dfo_system = "dfo_sap-9902" if args.test else "dfo_sap"
    if args.cache:
        raw_data = read_from_file(args.cache)
    else:
        raw_data = read_from_api(args.config or autoload_config())

    org_units = parse_api_data(raw_data, dfo_system)
    write_xml(org_units, args.output)

    logger.info("done %s", parser.prog)


if __name__ == '__main__':
    main()
