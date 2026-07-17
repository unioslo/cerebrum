# coding: utf-8
"""
Unit tests for :mod:`Cerebrum.modules.xmlutils.xml2object`
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
import six

from Cerebrum.testutils import file_utils

from Cerebrum.modules.xmlutils import xml2object


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf):
    cereconf.OU_USAGE_SPREAD = {
        "Foo Use": "foo_spread",
        "Bar Use": "bar_spread",
        "Baz Use": "baz_spread",
    }


#
# test get_xml_file_encoding
#


@pytest.fixture(params=["utf-8", "iso8859-1", "ascii"])
def xml_encoding(request):
    """ encoding params for test_get_xml_file_encoding. """
    return request.param


@pytest.fixture
def xml_file(write_dir, xml_encoding):
    """ xml file for test_get_xml_file_encoding. """
    xml_bytes = textwrap.dedent(
        """
        <?xml version="1.0" encoding="{encoding}"?>
        <data>
          <foo></foo>
        </data>
        """
    ).lstrip().format(encoding=xml_encoding).encode(xml_encoding)
    with file_utils.tempfile_ctx(write_dir, suffix=".xml") as filename:
        file_utils.write_bytes(filename, xml_bytes)
        yield filename


def test_get_xml_file_encoding(xml_file, xml_encoding):
    assert xml2object.get_xml_file_encoding(xml_file) == xml_encoding


#
# DataAddress
#


@pytest.fixture
def data_address():
    return xml2object.DataAddress(
        kind=xml2object.DataAddress.ADDRESS_BESOK,
        street="Karl Johans gt. 47",
        zip="0162",
        city="Oslo",
        country="NO",
    )


def test_data_address_init(data_address):
    assert data_address.kind == "besøk"
    assert data_address.street == "Karl Johans gt. 47"
    assert data_address.zip == "0162"
    assert data_address.city == "Oslo"
    assert data_address.country == "NO"


def test_data_address_str(data_address):
    text = six.text_type(data_address)
    assert text == ", ".join((
        data_address.kind,
        data_address.street,
        data_address.zip,
        data_address.city,
        data_address.country,
    ))


def test_data_address_zip():
    data_addr = xml2object.DataAddress(
        kind=xml2object.DataAddress.ADDRESS_POST,
        zip=123,
    )
    assert data_addr.zip == "0123"


#
# DataContact
#


@pytest.fixture
def data_contact():
    return xml2object.DataContact(
        kind=xml2object.DataContact.CONTACT_EMAIL,
        value="test@example.org",
        priority=3,
    )


def test_data_contact_init(data_contact):
    assert data_contact.kind == "e-mail"
    assert data_contact.value == "test@example.org"
    assert data_contact.priority == 3


def test_data_contact_str(data_contact):
    text = six.text_type(data_contact)
    assert text == "contact (e-mail 3): test@example.org"


#
# DataName
#


@pytest.fixture(params=["nb", None])
def data_name(request):
    lang = request.param.upper() if request.param else None
    return xml2object.DataName(
        kind="foo",
        value="Bar",
        lang=lang,
    )


def test_data_name_init(data_name):
    assert data_name.kind == "foo"
    assert data_name.value == "Bar"
    if data_name.language:
        assert data_name.language == "nb"
    else:
        assert data_name.language is None


def test_data_name_str(data_name):
    text = six.text_type(data_name)
    if data_name.language:
        assert text == "foo: Bar (nb)"
    else:
        assert text == "foo: Bar"


#
# NameContainer
#


def test_name_container_init():
    nc = xml2object.NameContainer()
    assert nc


def test_name_container_validate_name():
    nc = xml2object.NameContainer()
    assert nc.validate_name("foo")


def test_name_container_add_name(data_name):
    nc = xml2object.NameContainer()
    nc.add_name(data_name)
    assert True


def test_name_container_get_name(data_name):
    nc = xml2object.NameContainer()
    nc.add_name(data_name)

    names = nc.get_name(data_name.kind)
    assert names == [data_name]


def test_name_container_get_default(data_name):
    nc = xml2object.NameContainer()
    assert nc.get_name(data_name.kind) is None


def test_name_container_iternames():
    nc = xml2object.NameContainer()
    nc.add_name(xml2object.DataName("foo", "Foo"))
    nc.add_name(xml2object.DataName("foo", "Bar"))
    nc.add_name(xml2object.DataName("bar", "Baz"))

    it = nc.iternames()
    res_1 = next(it)
    res_2 = next(it)

    assert res_1
    assert res_2
    with pytest.raises(StopIteration):
        next(it)


def test_name_container_get_lang():
    nc = xml2object.NameContainer()
    nc.add_name(xml2object.DataName("title", "Rådgiver", lang="nb"))
    nc.add_name(xml2object.DataName("title", "Rådgivar", lang="nn"))
    nc.add_name(xml2object.DataName("title", "Advisor", lang="en"))
    nc.add_name(xml2object.DataName("short", "ABC", lang="en"))
    lookup_order = ("fi", "dk", "nn", "nb")

    # lookup should find the first available value
    assert nc.get_name_with_lang("title", *lookup_order) == "Rådgivar"

    # lookup should not give result for missing translations
    assert nc.get_name_with_lang("short", *lookup_order) is None

    # lookup should not give result for missing name types
    assert nc.get_name_with_lang("unknown", *lookup_order) is None


#
# DataEmployment
#


EMPLOYMENT_START = datetime.date(2025, 1, 1)
EMPLOYMENT_END = datetime.date(2025, 12, 31)
EMPLOYMENT_TODAY = datetime.date(2025, 3, 1)


def _create_employment(**args):
    # defaults:
    init = {
        'kind': xml2object.DataEmployment.HOVEDSTILLING,
        'percentage': 100.0,
        'code': 214,
        'start': EMPLOYMENT_START,
        'end': EMPLOYMENT_END,
        'place': ("sko", "123456"),
        'category': xml2object.DataEmployment.KATEGORI_OEVRIG,
        'leave': [],
        'mg': 1,
        'mug': 1,
    }
    init.update(args)
    return xml2object.DataEmployment(**init)


def test_data_employment_init():
    emp = _create_employment()
    assert emp.kind == "hovedstilling"
    assert emp.percentage == 100.0
    assert emp.code == 214
    assert emp.start == EMPLOYMENT_START
    assert emp.end == EMPLOYMENT_END
    assert emp.place == ("sko", "123456")
    assert emp.category == "tekadm-øvrig"
    assert emp.leave == []
    assert emp.mg == 1
    assert emp.mug == 1


@pytest.mark.parametrize("kind, is_main", [
    pytest.param(xml2object.DataEmployment.HOVEDSTILLING, True, id="true"),
    pytest.param(xml2object.DataEmployment.GJEST, False, id="false"),
])
def test_data_employment_is_main(kind, is_main):
    emp = _create_employment(kind=kind)
    assert emp.is_main() == is_main


@pytest.mark.parametrize("kind, is_guest", [
    pytest.param(xml2object.DataEmployment.GJEST, True, id="true"),
    pytest.param(xml2object.DataEmployment.HOVEDSTILLING, False, id="false"),
])
def test_data_employment_is_guest(kind, is_guest):
    emp = _create_employment(kind=kind)
    assert emp.is_guest() == is_guest


@pytest.mark.parametrize("today, is_active", [
    pytest.param(datetime.date(2025, 3, 1), True, id="active"),
    pytest.param(datetime.date(2024, 3, 1), False, id="not started"),
    pytest.param(datetime.date(2026, 3, 1), False, id="ended"),
])
def test_data_employment_is_active(today, is_active):
    emp = _create_employment()
    assert emp.is_active(today) == is_active


EMPLOYMENT_LEAVE = [
    {
        'start_date': datetime.date(2025, 2, 1),
        'end_date': datetime.date(2025, 3, 1),
    },
    {
        'start_date': datetime.date(2025, 5, 1),
        'end_date': datetime.date(2025, 6, 1),
    },
]


@pytest.mark.parametrize("leave, today, has_leave", [
    pytest.param([], datetime.date(2025, 3, 1), False,
                 id="no leave"),
    pytest.param(EMPLOYMENT_LEAVE, datetime.date(2025, 2, 15), True,
                 id="in leave"),
    pytest.param(EMPLOYMENT_LEAVE, datetime.date(2026, 3, 1), False,
                 id="out of leave"),
])
def test_data_employment_has_leave(leave, today, has_leave):
    emp = _create_employment(leave=leave)
    assert emp.has_leave(today) == has_leave


#
# DataExternalWork
#
# TODO: Absolutely no normalization - is this used for anything?
#


@pytest.fixture
def data_external_work():
    return xml2object.DataExternalWork(
        organization="Org",
        type="Type",
        extent="Extent",
        start=datetime.date(2025, 1, 1),
        end=datetime.date(2025, 12, 31),
        description="Description",
    )


def test_data_external_work_init(data_external_work):
    assert data_external_work.organization == "Org"
    assert data_external_work.type == "Type"
    assert data_external_work.extent == "Extent"
    assert data_external_work.start == datetime.date(2025, 1, 1)
    assert data_external_work.end == datetime.date(2025, 12, 31)
    assert data_external_work.description == "Description"


def test_data_external_work_str(data_external_work):
    text = six.text_type(data_external_work)
    assert text == " ".join((
        "Org: Org",
        "Type: Type",
        "Extent: Extent",
        "Start: 2025-01-01",
        "End: 2025-12-31",
    ))


#
# DataEntity
#


def test_data_entity_init():
    ent = xml2object.DataEntity()
    assert ent


def test_data_entity_contact():
    """ test setting and getting contact info """
    email_addrs = [
        xml2object.DataContact(
            xml2object.DataContact.CONTACT_EMAIL,
            value="test-1@example.org", priority=1,
        ),
        xml2object.DataContact(
            xml2object.DataContact.CONTACT_EMAIL,
            value="test-3@example.org", priority=3,
        ),
    ]
    urls = [
        xml2object.DataContact(
            xml2object.DataContact.CONTACT_URL,
            value="https://test.example.org/1", priority=1,
        ),
    ]

    ent = xml2object.DataEntity()
    for obj in email_addrs + urls:
        ent.add_contact(obj)

    assert ent.get_contact(xml2object.DataContact.CONTACT_FAX) == []

    result = ent.get_contact(xml2object.DataContact.CONTACT_EMAIL)
    assert len(result) == len(email_addrs)
    assert all(addr in result for addr in email_addrs)

    result = list(ent.itercontacts())
    assert len(result) == len(email_addrs) + len(urls)
    assert all(addr in result for addr in (email_addrs + urls))


#
# DataOU
#


def test_data_ou_init():
    assert xml2object.DataOU()


def test_data_ou_id():
    """ test DataEntity ids (with ou id types). """
    ou_ids = {
        xml2object.DataOU.NO_SKO: "123456",
        xml2object.DataOU.NO_DFO: "12345678",
    }

    ent = xml2object.DataOU()
    for kind, value in ou_ids.items():
        ent.add_id(kind, value)

    assert ent.get_id(xml2object.DataOU.NO_SKO) == "123456"
    assert ent.get_id(xml2object.DataOU.NO_NSD) is None
    assert dict(ent.iterids()) == ou_ids


def test_data_ou_usage_codes():
    valid = set(("Foo Use", "Bar Use"))
    unknown = set(("Unkonwn Use",))

    ent = xml2object.DataOU()
    for uc in (valid | unknown):
        ent.add_usage_code(uc)

    assert set(ent.iter_usage_codes()) == valid


def test_data_ou_str():
    ent = xml2object.DataOU()
    ent.start_date = datetime.date(1998, 6, 28)
    text = six.text_type(ent)
    assert text == textwrap.dedent(
        """
        DataOU (valid: 1998-06-28-None): []
        | []
        | []
        | []
        __[]
        """
    ).lstrip()


#
# DataPerson
#


def test_data_person_init():
    ent = xml2object.DataPerson()
    assert ent


def test_data_person_str():
    ent = xml2object.DataPerson()
    text = six.text_type(ent)
    assert text == textwrap.dedent(
        """
        DataPerson: []
        """
    ).lstrip()


#
# HRDataPerson
#


def test_data_hr_person_init():
    ent = xml2object.HRDataPerson()
    assert ent


def test_data_hr_person_str():
    ent = xml2object.HRDataPerson()
    text = six.text_type(ent)
    assert text == textwrap.dedent(
        """
        HRDataPerson: []
        | gender: None
        | birth: None
        | address: []
        | employment: []
        """
    ).lstrip()


#
# Test XML Parser
#
# These tests are a bit messy, the goal is just to run as much of the code here
# as possible.
#


class _AbstractDataGetter(xml2object.AbstractDataGetter):

    def __init__(self, *args, **kwargs):
        # prevent calling fetch in __init__
        pass


@pytest.mark.parametrize("method", ("fetch", "iter_person", "iter_ou"))
def test_abstract_data_getter(method):
    func = getattr(_AbstractDataGetter(), method)
    msg = "{} not implemented".format(method)
    with pytest.raises(NotImplementedError) as exc_info:
        func()
    assert six.text_type(exc_info.value) == msg


EXAMPLE_XML = textwrap.dedent(
    """
    <?xml version="1.0" encoding="utf-8"?>
    <data>
      <org>
        <orgunit>
          <ouid>101</ouid>
          <parent></parent>
          <date>19980628</date>
        </orgunit>
        <orgunit></orgunit>
        <orgunit>
          <ouid>102</ouid>
          <parent>101</parent>
          <date/>
          <unknown_tag/>
        </orgunit>
      </org>
    </data>
    """
).lstrip().encode("utf-8")


class XmlGetter(xml2object.XMLDataGetter):
    """ An XML parser that iterates over <orgunit> tags using XmlToOrgUnit. """

    def iter_ou(self, **kwargs):
        return iter(self._make_iterator("orgunit", XmlToOrgUnit, **kwargs))


class MockLogger(object):
    def __init__(self):
        self.items = []

    def warn(self, *args, **kwargs):
        self.items.append((args, kwargs))

    def clear(self):
        self.items.clear()


class XmlToOrgUnit(xml2object.XMLEntity2Object):
    """ An element2object mapper that maps <orgunit> to a dict. """

    # Include any <date> tags in the ou dict.  This tests:
    #  1. passing args through XMLDataGetter._make_iterator to XMLEntity2Object
    #  2. the XMLEntity2Object._make_date method
    include_date = False

    def _validate_object(self, obj):
        is_valid = obj['ouid'] is not None

        return is_valid

    def next_object(self, element):
        """ build a single ou-dict from an <orgunit> tag. """
        if element.tag != "orgunit":
            raise Exception("invalid org element: " + repr(element))

        obj = {
            'ouid': None,
            'parent': None,
        }

        # Iterate over *all* subelements
        for sub in xml2object.iter_element(element):
            if sub.tag == element.tag:
                continue
            if sub.tag == "ouid":
                obj['ouid'] = int(sub.text)
            if sub.tag == "parent" and sub.text and sub.text.strip():
                obj['parent'] = int(sub.text)
            if sub.tag == "date" and self.include_date:
                obj['date'] = self._make_date(sub.text)

        if not self._validate_object(obj):
            return None

        return obj


@pytest.fixture
def example_xml_file(write_dir):
    """ xml file for test_get_xml_file_encoding. """
    with file_utils.tempfile_ctx(write_dir, suffix=".xml") as filename:
        file_utils.write_bytes(filename, EXAMPLE_XML)
        yield filename


def test_parse_xml_file(example_xml_file, logger):
    parser = XmlGetter(example_xml_file, logger, fetchall=True)
    org_units = parser.iter_ou(include_date=True)

    # Check that we get our org units in xml-order
    assert next(org_units) == {'ouid': 101, 'parent': None,
                               'date': datetime.date(1998, 6, 28)}
    assert next(org_units) == {'ouid': 102, 'parent': 101,
                               'date': None}

    with pytest.raises(StopIteration):
        next(org_units)


def test_parse_xml_file_iter(example_xml_file, logger):
    parser = XmlGetter(example_xml_file, logger, fetchall=False)
    org_units = parser.iter_ou()

    # Check that we get our org units in xml-order
    assert next(org_units) == {'ouid': 101, 'parent': None}
    assert next(org_units) == {'ouid': 102, 'parent': 101}

    with pytest.raises(StopIteration):
        next(org_units)


class XmlFormatter(xml2object.XMLDataGetter):

    def iter_formatted(self, **kwargs):
        return self._make_iterator("orgunit", XmlToFormatted, **kwargs)


class XmlToFormatted(xml2object.XMLEntity2Object):

    def next_object(self, element):
        if element.tag != "orgunit":
            raise Exception("invalid org element: " + repr(element))
        return self.format_xml_element(element)


def test_parse_xml_file_format_element(example_xml_file, logger):
    parser = XmlFormatter(example_xml_file, logger, fetchall=False)
    org_units = parser.iter_formatted()

    # Not sure why this format is so weird?
    assert next(org_units).strip() == textwrap.dedent(
        """
        <orgunit>
              <ouid>101</ouid>
              <parent />
              <date>19980628</date>
            </orgunit>
        """
    ).strip().encode("ascii")
