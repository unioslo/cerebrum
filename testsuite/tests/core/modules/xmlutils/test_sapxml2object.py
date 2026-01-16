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
import logging
import textwrap

import pytest

from Cerebrum.modules.xmlutils import sapxml2object
from Cerebrum.modules.xmlutils import xml2object


@pytest.mark.parametrize(
    "value, expected",
    [
        ("12345678", "12345678"),
        ("123 45 678", "12345678"),
        ("+47 12-34-56-78", "+4712345678"),
    ],
)
def test_deuglify_phone(value, expected):
    assert sapxml2object.deuglify_phone(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("123456", (12, 34, 56)),
        ("010203", (1, 2, 3)),

    ],
)
def test_make_sko(value, expected):
    assert sapxml2object.make_sko(value) == expected


def test_make_sko_invalid():
    assert sapxml2object.make_sko("12-34-56") is None


OU_XML = textwrap.dedent(
    """
    <?xml version="1.0" encoding="utf-8"?>
    <sap2bas_data>
      <sap2bas_sted>
        <Sted>
          <Overordnetstedkode>705000</Overordnetstedkode>
          <Stedkode>705500</Stedkode>
          <OrgRegOuId>1234</OrgRegOuId>
          <DfoOrgId>10012345</DfoOrgId>
          <Startdato>2023-06-22</Startdato>
          <Sluttdato>9999-12-31</Sluttdato>
        </Sted>
        <Navn>
          <Sprak>NB</Sprak>
          <Akronym>TEST-OU</Akronym>
          <Navn20>TEST-OU-KORT</Navn20>
          <Navn40>Org-enhet for tester</Navn40>
          <Navn120>Organisasjonsenhet for enhetstester</Navn120>
        </Navn>
        <Navn>
          <Sprak>EN</Sprak>
          <Akronym>TEST-OU</Akronym>
          <Navn20>TEST-OU-SHORT</Navn20>
          <Navn40>Org-unit for tests</Navn40>
          <Navn120>Organizational Unit for unit tests</Navn120>
        </Navn>
        <Kommunikasjon>
          <Type>E-post adresse</Type>
          <Verdi>foo@example.org</Verdi>
          <Prioritet>1</Prioritet>
        </Kommunikasjon>
        <Kommunikasjon>
          <Type>Telefon1</Type>
          <Verdi>+4712345678</Verdi>
          <Prioritet>1</Prioritet>
        </Kommunikasjon>
        <Bruksomrade>
          <Type>Elektronisk katalog</Type>
          <Verdi/>
          <Niva>1</Niva>
        </Bruksomrade>
        <Bruksomrade>
          <Type>Tillatt Organisasjon</Type>
          <Verdi/>
          <Niva>1</Niva>
        </Bruksomrade>
        <Adresse>
          <Type>Postadresse</Type>
          <Distribusjon>INTERN</Distribusjon>
          <CO/>
          <Gateadresse>Postboks 1072 Blindern</Gateadresse>
          <Adressetillegg/>
          <Postnummer>0316</Postnummer>
          <Poststed>Oslo</Poststed>
          <Landkode>NO</Landkode>
        </Adresse>
        <Adresse>
          <Type>Besøksadresse</Type>
          <Distribusjon>INTERN</Distribusjon>
          <CO/>
          <Gateadresse>Problemveien 7,Lucy Smiths hus</Gateadresse>
          <Adressetillegg/>
          <Postnummer>0313</Postnummer>
          <Poststed>Oslo</Poststed>
          <Landkode>NO</Landkode>
        </Adresse>
      </sap2bas_sted>
    </sap2bas_data>
    """
).lstrip()


@pytest.fixture
def ou_xml_file(write_xml_file):
    """ xml file for test_get_xml_file_encoding. """
    return write_xml_file(OU_XML)


def test_parse_ou_xml(logger, ou_xml_file):
    parser = sapxml2object.SAPXMLDataGetter(ou_xml_file, logger,
                                            fetchall=False)
    org_units = list(parser.iter_ou())
    assert len(org_units) == 1


@pytest.fixture
def org_unit(logger, ou_xml_file):
    parser = sapxml2object.SAPXMLDataGetter(ou_xml_file, logger,
                                            fetchall=False)
    return list(parser.iter_ou())[0]


def test_parse_ou_ids(org_unit):
    all_ids = list(org_unit.iterids())
    assert len(all_ids) == 3

    # Sted/Stedkode
    sko = org_unit.get_id(xml2object.DataOU.NO_SKO)
    assert sko == (70, 55, 0)

    # Sted/DfoOrgId
    dfo_id = org_unit.get_id(xml2object.DataOU.NO_DFO)
    assert dfo_id == "10012345"

    # Sted/OrgRegOuId
    orgreg_id = org_unit.get_id(xml2object.DataOU.NO_ORGREG)
    assert orgreg_id == "1234"


def test_parse_ou_parent(org_unit):
    # Sted/Overordnetstedkode
    assert org_unit.parent == (xml2object.DataOU.NO_SKO, (70, 50, 0))


def test_parse_ou_dates(org_unit):
    assert org_unit.start_date == datetime.date(2023, 6, 22)
    assert org_unit.end_date == datetime.date(9999, 12, 31)


def test_parse_ou_contacts(org_unit):
    # Kommunikasjon/Type[text() == "E-post adresse"] -> CONTACT_EMAIL
    email = org_unit.get_contact(xml2object.DataContact.CONTACT_EMAIL)
    assert len(email) == 1
    assert email[0].value == "foo@example.org"

    # Kommunikasjon/Type[text() == "Telefon1"] -> CONTACT_PHONE
    tlf = org_unit.get_contact(xml2object.DataContact.CONTACT_PHONE)
    assert len(tlf) == 1
    assert tlf[0].value == "+4712345678"

    all_contacts = list(org_unit.itercontacts())
    assert len(all_contacts) == 2


def test_parse_ou_names(org_unit):
    all_names = list(org_unit.iternames())
    assert len(all_names) == 3

    # Navn/Akronym -> NAME_ACRONYM
    acronyms = set((a.language, a.value)
                   for a in org_unit.get_name(org_unit.NAME_ACRONYM))
    assert acronyms == set((("nb", "TEST-OU"), ("en", "TEST-OU")))

    # Navn/Navn40 -> NAME_SHORT
    short = set((a.language, a.value)
                for a in org_unit.get_name(org_unit.NAME_SHORT))
    assert short == set((("nb", "TEST-OU-KORT"), ("en", "TEST-OU-SHORT")))

    # Navn/Navn120 -> NAME_LONG
    long = set((a.language, a.value)
               for a in org_unit.get_name(org_unit.NAME_LONG))
    assert long == set((
        ("nb", "Organisasjonsenhet for enhetstester"),
        ("en", "Organizational Unit for unit tests"),
    ))


def test_parse_ou_publishable(org_unit):
    # Bruksomrade/Type[text() == "Tillatt Organisasjon"] -> publishable
    assert org_unit.publishable


def test_parse_ou_xml_no_names(caplog, logger, write_xml_file):
    # The *only* `DataOU` requirement in sapxml2object is the presence
    # of a `DataOU.NAME_LONG`
    content = textwrap.dedent(
        """
        <?xml version="1.0" encoding="utf-8"?>
        <sap2bas_data>
          <sap2bas_sted>
            <!-- invalid sted - no names -->
            <Sted>
            </Sted>
          </sap2bas_sted>
        </sap2bas_data>
        """
    ).lstrip()
    filename = write_xml_file(content)
    parser = sapxml2object.SAPXMLDataGetter(filename, logger, fetchall=False)
    org_units = list(parser.iter_ou())
    assert len(org_units) == 0

    record = caplog.records[-1]
    assert record.levelno == logging.WARNING
    assert "no name available" in record.msg.lower()
