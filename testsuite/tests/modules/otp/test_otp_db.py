# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.otp.otp_db` """
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


#
# sql_set tests
#


def test_set_otp_initial(database, person):
    otp_type = "foo"
    otp_payload = "bar"
    row = otp_db.sql_set(database, person.entity_id, otp_type, otp_payload)

    assert row['person_id'] == person.entity_id
    assert row['otp_type'] == otp_type
    assert row['otp_payload'] == otp_payload
    assert row['updated_at'].tzinfo


def test_set_otp_update(database, person):
    otp_type = "foo"
    otp_payload_old = "bar"
    otp_payload = "baz"
    otp_db.sql_set(database, person.entity_id, otp_type, otp_payload_old)
    row = otp_db.sql_set(database, person.entity_id, otp_type, otp_payload)
    assert row['otp_payload'] == otp_payload


def test_set_otp_update_noop(database, person):
    otp_type = "foo"
    otp_data = "bar"
    # set initial otp value
    otp_db.sql_set(database, person.entity_id, otp_type, otp_data)

    # update with same values does not do anything
    assert not otp_db.sql_set(database, person.entity_id, otp_type, otp_data)


#
# sql_get tests
#


def test_get_otp(database, person):
    otp_type = "foo"
    otp_payload = "bar"
    otp_db.sql_set(database, person.entity_id, otp_type, otp_payload)
    row = otp_db.sql_get(database, person.entity_id, otp_type)

    assert row['person_id'] == person.entity_id
    assert row['otp_type'] == otp_type
    assert row['otp_payload'] == otp_payload
    assert row['updated_at'].tzinfo


def test_get_otp_missing(database, person):
    with pytest.raises(Errors.NotFoundError):
        otp_db.sql_get(database, person.entity_id, "foo")


#
# sql_clear tests
#


def test_clear_otp(database, person):
    otp_type = "foo"
    otp_payload = "bar"
    otp_db.sql_set(database, person.entity_id, otp_type, otp_payload)

    # Clear anc check return value is the removed row
    row = otp_db.sql_clear(database, person.entity_id, otp_type)
    assert row['person_id'] == person.entity_id
    assert row['otp_type'] == otp_type
    assert row['otp_payload'] == otp_payload
    assert row['updated_at'].tzinfo

    # Check that the row was actually cleared
    with pytest.raises(Errors.NotFoundError):
        otp_db.sql_get(database, person.entity_id, otp_type)


def test_clear_otp_missing(database, person):
    with pytest.raises(Errors.NotFoundError):
        otp_db.sql_clear(database, person.entity_id, "foo")


#
# sql_search tests
#


def test_search_otp_date_range(database, person):
    row = otp_db.sql_set(database, person.entity_id, "foo", "bar")
    after = row['updated_at'].date() - datetime.timedelta(days=2)
    before = row['updated_at'].date() + datetime.timedelta(days=2)
    rows = list(
        otp_db.sql_search(
            database,
            person_id=person.entity_id,
            updated_after=after,
            updated_before=before,
        )
    )
    assert len(rows) == 1


def test_search_otp_date_range_miss(database, person):
    row = otp_db.sql_set(database, person.entity_id, "foo", "bar")
    before = row['updated_at'].date() - datetime.timedelta(days=2)
    rows = list(
        otp_db.sql_search(
            database,
            person_id=person.entity_id,
            updated_before=before,
        )
    )
    assert len(rows) == 0


def test_search_otp_invalid_date_range(database, person):
    with pytest.raises(ValueError) as exc_info:
        otp_db.sql_search(database, person_id=person.entity_id,
                          updated_before=datetime.date(2024, 9, 2),
                          updated_after=datetime.date(2024, 9, 3))

    error = six.text_type(exc_info.value)
    assert error.startswith("updated_after: cannot be after updated_before")


def test_search_otp_limit(database, person):
    otp_db.sql_set(database, person.entity_id, "otp-1", "bar")
    otp_db.sql_set(database, person.entity_id, "otp-2", "bar")

    all_rows = list(otp_db.sql_search(database, person_id=person.entity_id))
    assert len(all_rows) == 2

    limit_rows = list(otp_db.sql_search(database, person_id=person.entity_id,
                                        limit=1))
    assert len(limit_rows) == 1


#
# sql_get_otp_type_count tests
#


def test_get_otp_type_count(database, person):
    types = ["tests-otp-1", "tests-otp-2"]
    for otp_type in types:
        otp_db.sql_set(database, person.entity_id, otp_type, "payload")

    stats = dict(otp_db.sql_get_otp_type_count(database, otp_type=types))
    assert set(stats.keys()) == set(types)
    assert all(v == 1 for v in stats.values())
