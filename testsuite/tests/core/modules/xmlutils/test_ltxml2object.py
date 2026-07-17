# coding: utf-8
"""
Unit tests for :mod:`Cerebrum.modules.xmlutils.ltxml2object`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import textwrap

import pytest

from Cerebrum.modules.xmlutils import ltxml2object
from Cerebrum.modules.xmlutils import xml2object


OU_XML = textwrap.dedent(
    """
    <?xml version="1.0" encoding="utf-8"?>
    <data>
      <sted
          fakultetnr="80" instituttnr="10" gruppenr="0"
          forkstednavn="Example Org"
          stednavn="Example Organisation"
          stedlangnavn_bokmal="Eksempelorganisasjon"
          akronym="EO"
          fakultetnr_for_org_sted="80"
          instituttnr_for_org_sted="0"
          gruppenr_for_org_sted="0"
          telefonnr="01234567"
          adrtypekode_besok_adr="EKST"
          adresselinje1_besok_adr="Gateveien 12"
          poststednr_besok_adr="0123"
          poststednavn_besok_adr="STED"

          adrtypekode_intern_adr="EKST"
          adresselinje1_intern_adr="Gateveien 13"
          poststednr_intern_adr="0321"
          poststednavn_intern_adr="STAD"
          stedpostboks="1012"
          dato_opprettet="20250115"
          dato_nedlagt=""

          nsd_kode="1237"
          opprettetmerke_for_oppf_i_kat="Y"
          >
        <komm kommtypekode="EPOST" kommnrverdi="postmaster@example.org"/>
        <komm kommtypekode="FAX" telefonnr="01234568"/>
        <komm kommtypekode="TLF" telefonnr="01234567"/>
        <komm kommtypekode="URL" kommnrverdi="https://example.org"/>
        <!-- an unknown komm type -->
        <komm kommtypekode="UNKNOWN" kommnrverdi="foo"/>
        <!-- an empty komm value -->
        <komm kommtypekode="EPOST" kommnrverdi=""/>
      </sted>
    </data>
    """
).lstrip()


@pytest.fixture
def ou_xml_file(write_xml_file):
    """ xml file for test_get_xml_file_encoding. """
    return write_xml_file(OU_XML)


def test_parse_ou_xml(logger, ou_xml_file):
    parser = ltxml2object.LTXMLDataGetter(ou_xml_file, logger, fetchall=False)
    org_units = list(parser.iter_ou())
    assert len(org_units) == 1


@pytest.fixture
def org_unit(logger, ou_xml_file):
    parser = ltxml2object.LTXMLDataGetter(ou_xml_file, logger, fetchall=False)
    return list(parser.iter_ou())[0]


def test_parse_ou_ids(org_unit):
    all_ids = list(org_unit.iterids())
    assert len(all_ids) == 2

    sko = org_unit.get_id(xml2object.DataOU.NO_SKO)
    assert sko == (80, 10, 0)

    nsd = org_unit.get_id(xml2object.DataOU.NO_NSD)
    assert nsd == "1237"


def test_parse_ou_parent(org_unit):
    assert org_unit.parent == (xml2object.DataOU.NO_SKO, (80, 0, 0))


def test_parse_ou_dates(org_unit):
    assert org_unit.start_date == datetime.date(2025, 1, 15)
    assert not org_unit.end_date


def test_parse_ou_contacts(org_unit):
    # Test ou contacts
    tlf = org_unit.get_contact(xml2object.DataContact.CONTACT_PHONE)
    assert len(tlf) == 1
    assert tlf[0].value == "01234567"

    fax = org_unit.get_contact(xml2object.DataContact.CONTACT_FAX)
    assert len(fax) == 1
    assert fax[0].value == "01234568"

    email = org_unit.get_contact(xml2object.DataContact.CONTACT_EMAIL)
    assert len(email) == 1
    assert email[0].value == "postmaster@example.org"

    url = org_unit.get_contact(xml2object.DataContact.CONTACT_URL)
    assert len(url) == 1
    assert url[0].value == "https://example.org"

    all_contacts = list(org_unit.itercontacts())
    assert len(all_contacts) == 4


def test_parse_ou_addresses(org_unit):
    # test ou address
    all_addrs = list(org_unit.iteraddress())
    assert len(all_addrs) == 2

    addr = org_unit.get_address(xml2object.DataAddress.ADDRESS_BESOK)
    assert addr.zip == "0123"
    assert addr.street == "Gateveien 12"

    addr = org_unit.get_address(xml2object.DataAddress.ADDRESS_POST)
    assert addr.zip == "0321"
    assert addr.street == "Postboks 1012 Blindern"


def test_parse_ou_names(org_unit):
    all_names = list(org_unit.iternames())
    assert len(all_names) == 3

    # test ou names
    acronym = org_unit.get_name(org_unit.NAME_ACRONYM)
    assert len(acronym) == 1
    assert acronym[0].language == "nb"
    assert acronym[0].value == "EO"

    short = org_unit.get_name(org_unit.NAME_SHORT)
    assert len(short) == 1
    assert short[0].language == "nb"
    assert short[0].value == "Example Org"

    long = org_unit.get_name(org_unit.NAME_LONG)
    assert len(long) == 1
    assert long[0].language == "nb"
    assert long[0].value == "Eksempelorganisasjon"


def test_parse_ou_publishable(org_unit):
    assert org_unit.publishable
