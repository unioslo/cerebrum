# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.greg.datasource` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
# import six

import Cerebrum.Person
from Cerebrum.modules.greg import importer
from Cerebrum.testutils import datasource
# from Cerebrum.utils import date as date_utils


@pytest.fixture
def person_cls():
    return Cerebrum.Person.Person


@pytest.fixture
def person_creator(database, const, person_cls):
    """
    A helper fixture to create person objects.
    """
    person_ds = datasource.BasicPersonSource()

    def _create_persons(limit=1):
        for person_dict in person_ds(limit=limit):
            person = person_cls(database)
            gender = person_dict.get('gender')
            if gender:
                gender = const.human2constant(gender, const.Gender)
            gender = gender or const.gender_unknown
            person.populate(
                person_dict['birth_date'],
                gender,
                person_dict.get('description'),
            )
            person.write_db()
            person_dict['entity_id'] = person.entity_id
            yield person, person_dict

    return _create_persons


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(1))
    return person


@pytest.fixture
def today():
    return datetime.date.today()


@pytest.fixture
def tomorrow(today):
    return today + datetime.timedelta(days=1)


@pytest.fixture
def yesterday(today):
    return today - datetime.timedelta(days=1)


def test_is_deceased(person, today, yesterday):
    person.deceased_date = yesterday
    assert importer._is_deceased(person, _today=today)


def test_is_deceased_not_set(person):
    assert not importer._is_deceased(person)


def test_is_deceased_not_yet(person, today, tomorrow):
    person.deceased_date = tomorrow
    assert not importer._is_deceased(person, _today=today)
