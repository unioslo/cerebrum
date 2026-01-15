# coding: utf-8
"""
Unit tests for :mod:`Cerebrum.modules.xmlutils.fsxml2object`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import textwrap

import pytest

from Cerebrum.modules.xmlutils import fsxml2object
from Cerebrum.modules.xmlutils import xml2object


#
# FSOU
#


def test_data_ou_init():
    assert fsxml2object.FSOU()


def test_data_ou_id():
    """ test DataEntity ids (with ou id types). """
    ou_ids = {
        xml2object.DataOU.NO_SKO: "123456",
        xml2object.DataOU.NO_DFO: "12345678",
        fsxml2object.FSOU.NO_SAP_ID: "321",
    }

    ent = fsxml2object.FSOU()
    for kind, value in ou_ids.items():
        ent.add_id(kind, value)

    assert ent.get_id(fsxml2object.FSOU.NO_SAP_ID) == "321"


#
# XMLOU2Object + FSXMLDataGetter
#


OU_XML = textwrap.dedent(
    """
    <?xml version="1.0" encoding="utf-8"?>
    <data>
      <sted
          akronym="FOO"
          forkstednavn="E-FOO"
          stednavn="Example Foo"

          fakultetnr_for_org_sted="10"
          instituttnr_for_org_sted="01"
          gruppenr_for_org_sted="02"

          fakultetnr="10"
          instituttnr="01"
          gruppenr="03"

          stedkode_konv="10002001-0304"

          poststednr_intern_adr="123"
          adresselinje2_intern_adr="P.B. 1 Oslo"

          poststednr_besok_adr="120"
          adresselinje1_besok_adr="Gatevei 24"
          adresselinje2_besok_adr="Oslo"
          >
        <komm kommtypekode="EMAIL" kommnrverdi=""/>
        <komm kommtypekode="FAX" kommnrverdi="01234568"/>
        <komm kommtypekode="TLF" kommnrverdi="01234567"/>
        <komm kommtypekode="URL" kommnrverdi="https://example.org"/>
      </sted>
    </data>
    """
).lstrip()


@pytest.fixture
def ou_xml_file(write_xml_file):
    """ xml file for test_get_xml_file_encoding. """
    return write_xml_file(OU_XML)


def test_parse_ou_xml(logger, ou_xml_file):
    parser = fsxml2object.FSXMLDataGetter(ou_xml_file, logger, fetchall=False)
    org_units = list(parser.iter_ou())
    assert len(org_units) == 1


@pytest.fixture
def org_unit(logger, ou_xml_file):
    parser = fsxml2object.FSXMLDataGetter(ou_xml_file, logger, fetchall=False)
    return list(parser.iter_ou())[0]


def test_parse_ou_ids(org_unit):
    all_ids = list(org_unit.iterids())
    assert len(all_ids) == 2
    sko = org_unit.get_id(xml2object.DataOU.NO_SKO)
    assert sko == (10, 1, 3)
    sap_ou = org_unit.get_id(fsxml2object.FSOU.NO_SAP_ID)
    assert sap_ou == "10002001-0304"


def test_parse_ou_parent(org_unit):
    assert org_unit.parent == (xml2object.DataOU.NO_SKO, (10, 1, 2))


def test_parse_ou_contacts(org_unit):
    all_contacts = list(org_unit.itercontacts())
    assert len(all_contacts) == 2

    tlf = org_unit.get_contact(xml2object.DataContact.CONTACT_PHONE)
    assert len(tlf) == 1
    assert tlf[0].value == "01234567"
    assert tlf[0] in all_contacts

    fax = org_unit.get_contact(xml2object.DataContact.CONTACT_FAX)
    assert len(fax) == 1
    assert fax[0].value == "01234568"
    assert fax[0] in all_contacts


def test_parse_ou_addresses(org_unit):
    addr = org_unit.get_address(xml2object.DataAddress.ADDRESS_BESOK)
    assert addr.zip == "0120"
    assert addr.street == "Gatevei 24\nOslo"


def test_parse_ou_names(org_unit):
    all_names = list(org_unit.iternames())
    assert len(all_names) == 3

    acronym = org_unit.get_name(org_unit.NAME_ACRONYM)
    assert len(acronym) == 1
    assert acronym[0].language == "nb"
    assert acronym[0].value == "FOO"

    short = org_unit.get_name(org_unit.NAME_SHORT)
    assert len(short) == 1
    assert short[0].language == "nb"
    assert short[0].value == "E-FOO"

    long = org_unit.get_name(org_unit.NAME_LONG)
    assert len(long) == 1
    assert long[0].language == "nb"
    assert long[0].value == "Example Foo"


#
# EduKind2Object + EduDataGetter
#


STUDPROG_XML = textwrap.dedent(
    """
    <?xml version="1.0" encoding="utf-8"?>
    <data>
      <studprog
        studieprognavn="Studieprogram Foo"
        studieprogramkode="FOO"
        studienivakode="60"

        institusjonsnr_studieansv="185"
        faknr_studieansv="12"
        instituttnr_studieansv="34"
        gruppenr_studieansv="56"

        status_utgatt="N"
        status_utdplan="N"
        />
      <studprog
        studieprognavn="Studieprogram Bar"
        studieprogramkode="BAR"

        institusjonsnr_studieansv="185"
        faknr_studieansv="12"
        instituttnr_studieansv="34"
        gruppenr_studieansv="57"

        status_utgatt="N"
        status_utdplan="J"
        status_eksport_lms="J"
        />
    </data>
    """
).lstrip()


def test_parse_studprog_xml(logger, write_xml_file):
    filename = write_xml_file(STUDPROG_XML)
    parser = fsxml2object.EduDataGetter(filename, logger, fetchall=False)

    # EduDataGetter ignores any keys not defined in each iterator, and sets
    # empty (None) defaults for any known key missing from the xml
    programs = list(parser.iter_stprog())
    assert len(programs) == 2
    assert programs[0] == {
        'studieprognavn': "Studieprogram Foo",
        'studieprogramkode': "FOO",
        'institusjonsnr_studieansv': "185",
        'faknr_studieansv': "12",
        'instituttnr_studieansv': "34",
        'gruppenr_studieansv': "56",
        'status_utgatt': "N",
        'status_utdplan': "N",
        'status_eksport_lms': None,
    }


def test_edu_generic_iterator(logger, write_xml_file):
    filename = write_xml_file(STUDPROG_XML)
    iterator = fsxml2object.EduGenericIterator(filename, "studprog")

    # EduGenericIterator simply returns a attributes-dict for each matching
    # element.
    programs = list(iterator)
    assert len(programs) == 2
    assert programs[1] == {
        'studieprognavn': "Studieprogram Bar",
        'studieprogramkode': "BAR",
        'institusjonsnr_studieansv': "185",
        'faknr_studieansv': "12",
        'instituttnr_studieansv': "34",
        'gruppenr_studieansv': "57",
        'status_utgatt': "N",
        'status_utdplan': "J",
        'status_eksport_lms': "J",
    }


UE_UA_XML = textwrap.dedent(
    """
    <?xml version="1.0" encoding="utf-8"?>
    <data>

      <enhet
        institusjonsnr="185"
        emnekode="CRB1000"
        emnenavn_bokmal="Innføring i Cerebrum"
        emnenavnfork="Cerebrum 1"
        versjonskode="1"
        terminkode="VÅR"
        arstall="2026"
        terminnr="1"
        institusjonsnr_kontroll="185"
        faknr_kontroll="37"
        instituttnr_kontroll="30"
        gruppenr_kontroll="22"
        lmsrommalkode="EGET-ROM"
        status_eksport_lms="J"
        />

      <aktivitet
        institusjonsnr="185"
        emnekode="CRB1000A"
        aktivitetsnavn="Cerebrum-seminar"
        versjonskode="1"
        terminkode="VÅR"
        arstall="2026"
        terminnr="1"
        aktivitetkode="1-1"
        undpartilopenr="101"
        institusjonsnr_kontroll="185"
        faknr_kontroll="37"
        instituttnr_kontroll="30"
        gruppenr_kontroll="22"
        disiplinkode="TEORI"
        undformkode="SEM"
        lmsrommalkode="EGET-ROM"
        status_eksport_lms="N"
        />

    </data>
    """
).lstrip()


def test_parse_ue_xml(logger, write_xml_file):
    filename = write_xml_file(UE_UA_XML)
    parser = fsxml2object.EduDataGetter(filename, logger, fetchall=False)
    edu_units = list(parser.iter_undenh())
    assert len(edu_units) == 1

    assert edu_units[0] == {
        'institusjonsnr': "185",
        'emnekode': "CRB1000",
        'emnenavn_bokmal': "Innføring i Cerebrum",
        'emnenavnfork': "Cerebrum 1",
        'versjonskode': "1",
        'terminkode': "VÅR",
        'arstall': "2026",
        'terminnr': "1",
        'institusjonsnr_kontroll': "185",
        'faknr_kontroll': "37",
        'instituttnr_kontroll': "30",
        'gruppenr_kontroll': "22",
        'status_eksport_lms': "J",
        'lmsrommalkode': "EGET-ROM",
    }


def test_parse_ua_xml(logger, write_xml_file):
    filename = write_xml_file(UE_UA_XML)
    parser = fsxml2object.EduDataGetter(filename, logger, fetchall=False)
    edu_activities = list(parser.iter_undakt())
    assert len(edu_activities) == 1

    assert edu_activities[0] == {
        'institusjonsnr': "185",
        'emnekode': "CRB1000A",
        'aktivitetsnavn': "Cerebrum-seminar",
        'versjonskode': "1",
        'terminkode': "VÅR",
        'arstall': "2026",
        'terminnr': "1",
        'aktivitetkode': "1-1",
        'institusjonsnr_kontroll': "185",
        'faknr_kontroll': "37",
        'instituttnr_kontroll': "30",
        'gruppenr_kontroll': "22",
        'lmsrommalkode': "EGET-ROM",
        'status_eksport_lms': "N",
    }
