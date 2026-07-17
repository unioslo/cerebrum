# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.otp.otp_ldif_utils` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
import six

from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.testutils import datasource
from Cerebrum.modules.otp import otp_db
from Cerebrum.modules.otp import otp_ldif_utils


PERSON_CLS = Person.Person


@pytest.fixture
def person_creator(database, const):
    person_ds = datasource.BasicPersonSource()

    def _create_persons(limit=1):
        for person_dict in person_ds(limit=limit):
            person = PERSON_CLS(database)
            gender = person_dict.get('gender')
            if gender:
                gender = const.human2constant(gender, const.Gender)
            gender = gender or const.gender_unknown

            person.populate(person_dict['birth_date'],
                            gender,
                            person_dict.get('description'))
            person.write_db()
            person_dict['entity_id'] = person.entity_id
            yield person, person_dict

    return _create_persons


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(limit=1))
    return person


OTP_TYPES = ("test-otp-ldif-utils-a", "test-otp-ldif-utils-b")


@pytest.fixture()
def otp_data(database, person_creator):
    """
    A set of otp data for persons
    """
    data = []
    for _, person_d in person_creator(limit=3):
        person_id = person_d['entity_id']
        for otp_type in OTP_TYPES:
            otp_value = "{}-{}".format(person_id, otp_type[-1])
            otp_db.sql_set(database, person_id, otp_type, otp_value)
            data.append((person_id, otp_type, otp_value))
    return tuple(data)


#
# _OtpFetcher tests
#


def test_otp_fetcher_all(database, otp_data):
    fetcher = otp_ldif_utils._OtpFetcher(database, OTP_TYPES)
    results = fetcher.get_all()
    person_ids = set(r[0] for r in otp_data)
    assert set(results.keys()) == person_ids
    person_id = otp_data[0][0]
    otp_values = results[person_id]
    assert set(otp_values.keys()) == set(OTP_TYPES)


def test_otp_fetcher_one(database, otp_data):
    fetcher = otp_ldif_utils._OtpFetcher(database, OTP_TYPES)
    person_id = otp_data[0][0]
    otp_values = fetcher.get_one(person_id)
    assert set(otp_values.keys()) == set(OTP_TYPES)


def test_otp_fetcher_one_miss(database, otp_data):
    fetcher = otp_ldif_utils._OtpFetcher(database, OTP_TYPES)
    assert fetcher.get_one(0) is otp_ldif_utils.MISSING


def test_otp_fetcher_filter_type(database, otp_data):
    fetcher = otp_ldif_utils._OtpFetcher(database, (OTP_TYPES[0],))
    person_id = otp_data[0][0]
    otp_values = fetcher.get_one(person_id)
    assert set(otp_values.keys()) == set((OTP_TYPES[0],))


#
# OtpCache tests
#

def test_otp_cache_hit(database, otp_data):
    person_id = otp_data[0][0]
    otp_type = OTP_TYPES[1]
    expect = {p_id_: value_
              for p_id_, type_, value_ in otp_data
              if type_ == otp_type}
    cache = otp_ldif_utils.OtpCache(database, otp_type)
    cache.get_payload(person_id) == expect[person_id]


def test_otp_cache_miss(database, otp_data):
    otp_type = OTP_TYPES[1]
    cache = otp_ldif_utils.OtpCache(database, otp_type)
    with pytest.raises(LookupError):
        cache.get_payload(0)
