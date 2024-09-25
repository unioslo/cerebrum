# encoding: utf-8
"""
Tests for :mod:`Cerebrum.modules.import_utils.matcher`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

import Cerebrum.Errors
from Cerebrum.modules.import_utils import matcher


# Test constants


SOURCE_SYSTEM_1 = "sys-1-073188eaba"
SOURCE_SYSTEM_2 = "sys-2-523c65043b"
ID_TYPE_1 = "id-1-c1c885f8d72"
ID_TYPE_2 = "id-2-6ff43825c6c"


@pytest.fixture(autouse=True)
def id_types(constant_module, constant_creator):
    return type(
        str("TestConstants"),
        (object,),
        {
            'system_1': constant_creator(
                constant_module._AuthoritativeSystemCode,
                SOURCE_SYSTEM_1,
            ),
            'system_2': constant_creator(
                constant_module._AuthoritativeSystemCode,
                SOURCE_SYSTEM_2,
            ),
            'id_1': constant_creator(
                constant_module._EntityExternalIdCode,
                ID_TYPE_1,
                constant_module.CoreConstants.entity_person,
            ),
            'id_2': constant_creator(
                constant_module._EntityExternalIdCode,
                ID_TYPE_2,
                constant_module.CoreConstants.entity_person,
            ),
        },
    )


# Fixture data


@pytest.fixture(autouse=True)
def known_persons(database, const, id_types, person_creator):
    """ Populate the database with some external ids. """
    id_data = [
        [
            (id_types.system_1, id_types.id_1, "101"),
            (id_types.system_1, id_types.id_2, "102"),
            (id_types.system_2, id_types.id_1, "101"),
        ],
        [
            (id_types.system_1, id_types.id_1, "201"),
            (id_types.system_1, id_types.id_2, "202"),
            (id_types.system_2, id_types.id_2, "202"),
        ],
        [
            (id_types.system_1, id_types.id_1, "301"),
            (id_types.system_2, id_types.id_1, "301"),
            (id_types.system_2, id_types.id_2, "302"),
        ],
    ]
    persons = []

    for person, ext_ids in zip((p for p, _ in person_creator(limit=3)),
                               id_data):
        for source, idtyp, idval in ext_ids:
            person._set_external_id(source, idtyp, idval)
        persons.append(person)
    return persons


PERSON_ID_1 = "001"
PERSON_ID_2 = "002"


@pytest.fixture
def target_person(database, person_creator, id_types):
    """ A target person with id_type_1 and id_type_2 from source_system_1. """
    person, _ = next(person_creator(limit=1))
    person.affect_external_id(id_types.system_1, id_types.id_1, id_types.id_2)
    person.populate_external_id(id_types.system_1, id_types.id_1, PERSON_ID_1)
    person.populate_external_id(id_types.system_1, id_types.id_2, PERSON_ID_2)
    person.write_db()
    return person


@pytest.fixture
def duplicate_person(database, person_creator, id_types):
    """ A duplicate person with only id_type_2 from source_system_2. """
    person, _ = next(person_creator(limit=1))
    person.affect_external_id(id_types.system_2, id_types.id_1, id_types.id_2)
    person.populate_external_id(id_types.system_2, id_types.id_2, PERSON_ID_2)
    person.write_db()
    return person


# Tests


def test_find_person_no_terms(database, const, target_person):
    """ not giving any search terms is an error """
    find_person = matcher.PersonMatcher()
    with pytest.raises(ValueError) as exc_info:
        find_person(database, [])

    error_msg = six.text_type(exc_info.value)
    assert error_msg == "No search criterias given"


def test_find_person_by_search(database, target_person):
    """ we can find person by search criterias """
    find_person = matcher.PersonMatcher()
    result = find_person(
        database,
        [(ID_TYPE_1, PERSON_ID_1), (ID_TYPE_2, PERSON_ID_2)],
    )
    assert result.entity_id == target_person.entity_id


def test_find_person_by_match(database, target_person):
    """ we can find person by match criterias """
    find_person = matcher.PersonMatcher(match_types=(ID_TYPE_1,))
    result = find_person(
        database,
        [(ID_TYPE_1, PERSON_ID_1), (ID_TYPE_2, PERSON_ID_2)],
    )
    assert result.entity_id == target_person.entity_id


def test_find_person_default_miss(database):
    """ no hit gives no result """
    find_person = matcher.PersonMatcher()
    result = find_person(
        database,
        [(ID_TYPE_1, PERSON_ID_1), (ID_TYPE_2, PERSON_ID_2)],
    )
    assert not result


def test_find_person_required_miss(database):
    """ no hit gives error, if required """
    find_person = matcher.PersonMatcher()
    with pytest.raises(Cerebrum.Errors.NotFoundError) as exc_info:
        find_person(
            database,
            [(ID_TYPE_1, PERSON_ID_1), (ID_TYPE_2, PERSON_ID_2)],
            required=True,
        )

    error_msg = six.text_type(exc_info.value)
    assert "no matching person objects" in error_msg


# Duplicate tests
#
# In all these tests, we get multiple hits from our given search terms.


def test_find_person_duplicate_search_err(database, target_person,
                                          duplicate_person):
    """ multiple hits for search criterias is an error """
    # In this scenario, we have *two* persons, both with the same ID_TYPE_2.
    # Since we have no *match_types*, we end up with no match hits, and two
    # search hits, which is an error.
    find_person = matcher.PersonMatcher()
    with pytest.raises(Cerebrum.Errors.TooManyRowsError) as exc_info:
        find_person(
            database,
            [(ID_TYPE_1, PERSON_ID_1), (ID_TYPE_2, PERSON_ID_2)],
        )

    error_msg = six.text_type(exc_info.value)
    assert "More than one entity found" in error_msg


def test_find_person_duplicate_match_ok(database, target_person,
                                        duplicate_person):
    """ multiple search hits are okay if we have a single match hit """
    # In this scenario, we have *two* persons, both with the same ID_TYPE_2.
    # However, since ID_TYPE_1 is in *match_types*, we should get a single
    # match hit.
    find_person = matcher.PersonMatcher(match_types=(ID_TYPE_1,))
    result = find_person(
        database,
        [(ID_TYPE_1, PERSON_ID_1), (ID_TYPE_2, PERSON_ID_2)],
    )
    assert result.entity_id == target_person.entity_id


def test_find_person_duplicate_match_err(database, target_person,
                                         duplicate_person):
    """ multiple match hits for search criterias is an error """
    # In this scenario, we have *two* persons, both with the same ID_TYPE_2.
    # Since ID_TYPE_2 is in *match_types* we get two different match hits,
    # which should be an error.
    find_person = matcher.PersonMatcher(match_types=(ID_TYPE_2,))
    with pytest.raises(Cerebrum.Errors.TooManyRowsError) as exc_info:
        find_person(
            database,
            [(ID_TYPE_1, PERSON_ID_1), (ID_TYPE_2, PERSON_ID_2)],
        )

    error_msg = six.text_type(exc_info.value)
    assert "More than one entity found" in error_msg
