""" Tests for :mod:`Cerebrum.entity.contact_info` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
import six

import Cerebrum.Person
import Cerebrum.Entity
import Cerebrum.Errors
from Cerebrum.entity import contact_info as ci_db
from Cerebrum.testutils.log_utils import StrictNullHandler
from Cerebrum.utils import date as date_utils


#
# Some common fixtures
#


@pytest.fixture(scope='module', autouse=True)
def _patch_logging():
    """ catch badly formatted log records in reguser.logger """
    # consider mistakes in log formatting to be a test failure
    ci_db.logger.addHandler(StrictNullHandler())
    ci_db.logger.setLevel(-100)


@pytest.fixture
def ct_foo(constant_module, constant_creator):
    return constant_creator(
        constant_module._ContactInfoCode,
        "ct-foo-dcd46eac",
    )


@pytest.fixture
def ct_bar(constant_module, constant_creator):
    return constant_creator(
        constant_module._ContactInfoCode,
        "ct-bar-dcd46ead",
    )


@pytest.fixture
def entity(database, entity_type):
    entity_obj = Cerebrum.Entity.EntityContactInfo(database)
    entity_obj.populate(entity_type)
    entity_obj.write_db()
    return entity_obj


#
# add_contact_info tests
#
# This is the legacy method for adding contact info to Cerebrum.  It allows for
# duplicate entries, with different contact_pref values, but doesn't support
# updates
#


def test_add_contact_info__minimal(database, entity, system_a, ct_foo):
    row = ci_db.add_contact_info(database, entity.entity_id,
                                 system_a, ct_foo, 1, "value", None, None)
    assert dict(row) == {
        'entity_id': int(entity.entity_id),
        'source_system': int(system_a),
        'contact_type': int(ct_foo),
        'contact_pref': 1,
        'contact_value': "value",
        'description': None,
        'contact_alias': None,
        'last_modified': row['last_modified'],  # don't care about exact value
    }
    assert row['last_modified']


def test_add_contact_info__full(database, entity, system_a, ct_foo):
    row = ci_db.add_contact_info(database, entity.entity_id,
                                 system_a, ct_foo, 50, "value",
                                 "a description", "an alias")
    assert dict(row) == {
        'entity_id': int(entity.entity_id),
        'source_system': int(system_a),
        'contact_type': int(ct_foo),
        'contact_pref': 50,
        'contact_value': "value",
        'description': "a description",
        'contact_alias': "an alias",
        'last_modified': row['last_modified'],  # don't care about exact value
    }
    assert row['last_modified']


def test_add_contact_info__duplicate(database, entity, system_a, ct_foo):
    row = ci_db.add_contact_info(database, entity.entity_id,
                                 system_a, ct_foo, 1, "value",
                                 "a description", "an alias")
    assert (row['contact_pref'], row['contact_value']) == (1, "value")

    row = ci_db.add_contact_info(database, entity.entity_id,
                                 system_a, ct_foo, 2, "value",
                                 "a description", "an alias")
    assert (row['contact_pref'], row['contact_value']) == (2, "value")

    rows = ci_db.search_contact_info(database, entity_id=int(entity.entity_id),
                                     limit=10, fetchall=True)
    assert len(rows) == 2
    assert set(r['contact_pref'] for r in rows) == set((1, 2))


#
# set_contact tests
#
# This is a new method for setting contact info in Cerebrum.  It doesn't allow
# for duplicate entries, and:
#
#  1. Removes duplicate entries on update
#  2. Only sets/updates contact_pref when adding or updating an existing value
#


def test_set_contact__insert_minimal(database, entity, system_a, ct_foo):
    """ insert new contact without description or alias. """
    row = ci_db.set_contact(database, entity.entity_id, system_a,
                            ct_foo, "value")
    assert dict(row) == {
        'entity_id': int(entity.entity_id),
        'source_system': int(system_a),
        'contact_type': int(ct_foo),
        'contact_pref': ci_db._DEFAULT_PREF,
        'contact_value': "value",
        'description': None,
        'contact_alias': None,
        'last_modified': row['last_modified'],
    }


def test_set_contact__insert_full(database, entity, system_a, ct_foo):
    """ insert new contact with description and alias. """
    row = ci_db.set_contact(database, entity.entity_id,
                            source_system=system_a,
                            contact_type=ct_foo,
                            contact_value="value",
                            description="a description",
                            contact_alias="an alias")
    assert dict(row) == {
        'entity_id': int(entity.entity_id),
        'source_system': int(system_a),
        'contact_type': int(ct_foo),
        'contact_pref': ci_db._DEFAULT_PREF,
        'contact_value': "value",
        'description': "a description",
        'contact_alias': "an alias",
        'last_modified': row['last_modified'],
    }


def test_set_contact__noop(database, entity, system_a, ct_foo):
    """ ignore contact update if nothing changed. """
    pref = 73
    value = "value"
    last_modified = date_utils.now() - datetime.timedelta(days=1)
    orig = ci_db.add_contact_info(database, entity.entity_id, system_a, ct_foo,
                                  pref, value, None, None,
                                  _last_modified=last_modified)

    # Update with same set of values
    row = ci_db.set_contact(database, entity.entity_id,
                            source_system=system_a,
                            contact_type=ct_foo,
                            contact_value=value)
    assert dict(row) == {
        'entity_id': int(entity.entity_id),
        'source_system': int(system_a),
        'contact_type': int(ct_foo),
        'contact_pref': pref,  # shouldn't have changed
        'contact_value': value,
        'description': None,
        'contact_alias': None,
        'last_modified': orig['last_modified'],  # shouldn't have changed
    }


def test_set_contact__update(database, entity, system_a, ct_foo):
    """ update contact if e.g value changed. """
    last_modified = date_utils.now() - datetime.timedelta(days=1)
    orig = ci_db.add_contact_info(database, entity.entity_id, system_a, ct_foo,
                                  73, "original value", None, None,
                                  _last_modified=last_modified)

    # Update with same set of values
    row = ci_db.set_contact(database, entity.entity_id,
                            source_system=system_a,
                            contact_type=ct_foo,
                            contact_value="new value")
    assert dict(row) == {
        'entity_id': int(entity.entity_id),
        'source_system': int(system_a),
        'contact_type': int(ct_foo),
        'contact_pref': ci_db._DEFAULT_PREF,  # on update, pref is reset
        'contact_value': "new value",
        'description': None,
        'contact_alias': None,
        'last_modified': row['last_modified'],
    }
    # last_modified should be updated to a current timestamp
    assert orig['last_modified'] < row['last_modified']


def test_set_contact__clear_duplicate(database, entity, system_a, ct_foo):
    """ clear duplicate when updating a contact with no change. """
    value = "original value"
    pref = 73
    last_modified = date_utils.now() - datetime.timedelta(days=1)
    orig = ci_db.add_contact_info(database, entity.entity_id, system_a, ct_foo,
                                  pref, value, None, None,
                                  _last_modified=last_modified)
    ci_db.add_contact_info(database, entity.entity_id, system_a, ct_foo,
                           pref + 1, "other " + value, None, None,
                           _last_modified=last_modified)
    # sanity check that we have two contact entries
    assert len(ci_db.search_contact_info(database,
                                         entity_id=int(entity.entity_id),
                                         fetchall=True)) == 2

    # when updating with an existing set of values, the original should not
    # change ...
    row = ci_db.set_contact(database, entity.entity_id,
                            source_system=system_a,
                            contact_type=ct_foo,
                            contact_value=value)
    assert dict(row) == dict(orig)

    # ... but the duplicate should be removed
    assert len(ci_db.search_contact_info(database,
                                         entity_id=int(entity.entity_id),
                                         fetchall=True)) == 1


def test_set_contact__update_duplicate(database, entity, system_a, ct_foo):
    """ clear duplicates when updating a contact with e.g. a value change. """
    value = "original value"
    pref = 73
    last_modified = date_utils.now() - datetime.timedelta(days=1)
    orig = ci_db.add_contact_info(database, entity.entity_id, system_a, ct_foo,
                                  pref, value, None, None,
                                  _last_modified=last_modified)
    ci_db.add_contact_info(database, entity.entity_id, system_a, ct_foo,
                           pref + 1, "other " + value, None, None,
                           _last_modified=last_modified)
    # sanity check that we have two contact entries
    assert len(ci_db.search_contact_info(database,
                                         entity_id=int(entity.entity_id),
                                         fetchall=True)) == 2

    # when updating with a new values, all duplicates should be replaced by a
    # single, new entry
    row = ci_db.set_contact(database, entity.entity_id,
                            source_system=system_a,
                            contact_type=ct_foo,
                            contact_value="new value")
    assert dict(row) == {
        'entity_id': int(entity.entity_id),
        'source_system': int(system_a),
        'contact_type': int(ct_foo),
        'contact_pref': ci_db._DEFAULT_PREF,  # reset pref
        'contact_value': "new value",  # new value
        'description': None,
        'contact_alias': None,
        'last_modified': row['last_modified'],
    }
    assert orig['last_modified'] < row['last_modified']
    assert len(ci_db.search_contact_info(database,
                                         entity_id=int(entity.entity_id),
                                         fetchall=True)) == 1

#
# search_contact_info tests
#


def test_search_contact_info__no_prefix(database, entity):
    with pytest.raises(TypeError) as exc_info:
        ci_db.search_contact_info(database, entity_id=int(entity.entity_id),
                                  _prefix="foo")

    msg = six.text_type(exc_info.value)
    assert msg.startswith("invalid argument")


@pytest.fixture
def other_entity(database, entity_type):
    """ Another entity. """
    entity_obj = Cerebrum.Entity.EntityExternalId(database)
    entity_obj.populate(entity_type)
    entity_obj.write_db()
    return entity_obj


COMMON_ID = "0uLKKXlv6ZltOavYko"
A_FOO_1 = "a-foo-1-{}-49".format(COMMON_ID)
B_BAR_1 = "b-foo-1-{}-52".format(COMMON_ID)
A_BAR_2 = "a-bar-2-{}-54".format(COMMON_ID)
B_FOO_2 = "b-foo-2-{}-55".format(COMMON_ID)


BASE_DATETIME = date_utils.apply_timezone(
    datetime.datetime(2026, 5, 3, 14, 0, 0))


@pytest.fixture
def values(database, entity, other_entity, system_a, system_b, ct_foo, ct_bar):
    to_set = [
        {
            'entity_id': entity.entity_id,
            'source_system': system_a,
            'contact_type': ct_foo,
            'contact_pref': 1,
            'contact_value': A_FOO_1,
            'description': "a-foo-1",
            'contact_alias': '49',
            '_last_modified': BASE_DATETIME,
        },
        {
            'entity_id': entity.entity_id,
            'source_system': system_b,
            'contact_type': ct_bar,
            'contact_pref': 2,
            'contact_value': B_BAR_1,
            'description': None,
            'contact_alias': '52',
            '_last_modified': BASE_DATETIME + datetime.timedelta(hours=1),
        },
        {
            'entity_id': other_entity.entity_id,
            'source_system': system_a,
            'contact_type': ct_bar,
            'contact_pref': 3,
            'contact_value': A_BAR_2,
            'description': "a-bar-2",
            'contact_alias': None,
            '_last_modified': BASE_DATETIME + datetime.timedelta(days=2),
        },
        {
            'entity_id': other_entity.entity_id,
            'source_system': system_b,
            'contact_type': ct_foo,
            'contact_pref': 4,
            'contact_value': B_FOO_2,
            'description': None,
            'contact_alias': None,
            '_last_modified': BASE_DATETIME + datetime.timedelta(days=7),
        },
    ]
    results = {}
    for kwargs in to_set:
        row = dict(ci_db.add_contact_info(database, **kwargs))
        results[row['contact_value']] = row
    return results


def test_search_contact_info__limit(database, values, system_a, system_b):
    systems = (system_a, system_b)
    rows = ci_db.search_contact_info(database, source_system=systems,
                                     fetchall=True)
    assert len(rows) == 4

    rows = ci_db.search_contact_info(database, source_system=systems,
                                     limit=2, fetchall=True)
    assert len(rows) == 2


def test_search_contact_info__exact(database, values):
    target = values[A_FOO_1]

    rows = ci_db.search_contact_info(database,
                                     entity_id=target['entity_id'],
                                     source_system=target['source_system'],
                                     contact_type=target['contact_type'],
                                     limit=10,
                                     fetchall=True)
    assert len(rows) == 1
    assert dict(rows[0]) == values[A_FOO_1]


def test_search_contact_info__by_entity_id(database, values, entity):
    rows = ci_db.search_contact_info(database, entity_id=int(entity.entity_id),
                                     limit=10, fetchall=True)
    assert len(rows) == 2
    assert all(row['entity_id'] == entity.entity_id for row in rows)


def test_search_contact_info__by_entity_type(database, values, entity_type):
    rows = ci_db.search_contact_info(database, entity_type=entity_type,
                                     limit=10, fetchall=True)
    assert len(rows) == 4


def test_search_contact_info__by_system(database, values, system_a):
    rows = ci_db.search_contact_info(database, source_system=system_a,
                                     limit=10, fetchall=True)
    assert len(rows) == 2
    assert all(row['source_system'] == system_a for row in rows)


def test_search_contact_info__by_contact_type(database, values, ct_foo):
    rows = ci_db.search_contact_info(database, contact_type=ct_foo,
                                     limit=10, fetchall=True)
    assert len(rows) == 2
    assert all(row['contact_type'] == ct_foo for row in rows)


def test_search_contact_info__by_value(database, values):
    target = values[A_FOO_1]
    rows = ci_db.search_contact_info(database,
                                     value=target['contact_value'],
                                     limit=10, fetchall=True)
    assert len(rows) == 1
    assert dict(rows[0]) == target


def test_search_contact_info__by_value__miss(database, values):
    target = values[A_FOO_1]
    wrong_value = target['contact_value'] + "-doesnt-exist"
    rows = ci_db.search_contact_info(database, value=wrong_value,
                                     limit=10, fetchall=True)
    assert len(rows) == 0


def test_search_contact_info__by_value_like(database, values):
    pattern = "*" + COMMON_ID + "-??"
    rows = ci_db.search_contact_info(database, value_like=pattern,
                                     limit=10, fetchall=True)
    assert len(rows) == 4

    pattern = "*" + COMMON_ID + "-4?"
    rows = ci_db.search_contact_info(database, value_like=pattern,
                                     limit=10, fetchall=True)
    assert len(rows) == 1


def test_search_contact_info__by_value_like__miss(database, values):
    pattern = ("*" + COMMON_ID + "-??").lower()
    rows = ci_db.search_contact_info(database, value_like=pattern,
                                     limit=10, fetchall=True)
    assert len(rows) == 0


def test_search_contact_info__by_id_value_ilike(database, values):
    pattern = ("*" + COMMON_ID + "-5?").lower()
    rows = ci_db.search_contact_info(database, value_ilike=pattern,
                                     limit=10, fetchall=True)
    assert len(rows) == 3


@pytest.fixture
def source_systems(system_a, system_b):
    """ additional filter to use in very generic searches. """
    # This additional filter is typically used to avoid getting pre-existing
    # results included in our tests for generic searches (e.g. by contact_pref
    # or last_modified).
    return (system_a, system_b)


def test_search_contact_info__by_contact_pref(database, values,
                                              source_systems):
    target = values[A_BAR_2]
    rows = ci_db.search_contact_info(database,
                                     pref=target['contact_pref'],
                                     # we need an additional filter to avoid
                                     # getting pre-existing results
                                     source_system=source_systems,
                                     limit=10, fetchall=True)
    assert len(rows) == 1
    assert dict(rows[0]) == target


def test_search_contact_info__by_contact_pref_range(database, values,
                                                    source_systems):
    rows = ci_db.search_contact_info(database, pref_min=2, pref_max=3,
                                     source_system=source_systems,
                                     limit=10, fetchall=True)
    assert len(rows) == 2
    assert set(row['contact_pref'] for row in rows) == set((2, 3))


def test_search_contact_info__by_alias(database, values, source_systems):
    target = values[A_FOO_1]
    assert target['contact_alias'] == "49"  # sanity check

    rows = ci_db.search_contact_info(database,
                                     alias_like=target['contact_alias'],
                                     source_system=source_systems,
                                     limit=10, fetchall=True)
    assert len(rows) == 1
    assert dict(rows[0]) == target


def test_search_contact_info__by_alias_like(database, values, source_systems):
    # pattern - match A_FOO_1
    target = values[A_FOO_1]
    assert target['contact_alias'] == "49"  # sanity check

    rows = ci_db.search_contact_info(database,
                                     alias_like="4?",
                                     source_system=source_systems,
                                     limit=10, fetchall=True)
    assert len(rows) == 1
    assert dict(rows[0]) == target


def test_search_contact_info__by_alias_empty(database, values, source_systems):
    rows = ci_db.search_contact_info(database,
                                     alias=None,
                                     source_system=source_systems,
                                     limit=10, fetchall=True)
    assert len(rows) == 2
    assert set(r['contact_value'] for r in rows) == set((A_BAR_2, B_FOO_2))


def test_search_contact_info__by_modified_at(database, values, source_systems):
    target = values[A_FOO_1]
    rows = ci_db.search_contact_info(database,
                                     modified_at=target['last_modified'],
                                     source_system=source_systems,
                                     limit=10, fetchall=True)
    assert len(rows) == 1
    assert dict(rows[0]) == target


def test_search_contact_info__by_modified_range(database, values,
                                                source_systems):
    after = BASE_DATETIME + datetime.timedelta(minutes=30)
    before = BASE_DATETIME + datetime.timedelta(days=5)
    # Should match two values - B_BAR_1 and A_BAR_2
    rows = ci_db.search_contact_info(database,
                                     modified_after=after,
                                     modified_before=before,
                                     source_system=source_systems,
                                     limit=10, fetchall=True)
    assert len(rows) == 2
    assert set(r['contact_value'] for r in rows) == set((B_BAR_1, A_BAR_2))


def test_search_contact_info__by_modified_combined(database, values,
                                                   source_systems):
    # Should match two values - A_FOO_1 and B_FOO_2
    rows = ci_db.search_contact_info(
        database,
        modified_at=BASE_DATETIME,
        modified_after=BASE_DATETIME + datetime.timedelta(days=5),
        source_system=source_systems,
        limit=10, fetchall=True)
    assert len(rows) == 2
    assert set(r['contact_value'] for r in rows) == set((A_FOO_1, B_FOO_2))


#
# delete_contact_info tests
#


def test_delete_contact_info__by_entity_id(database, values, entity,
                                           other_entity):
    deleted_rows = ci_db.delete_contact_info(database,
                                             entity_id=entity.entity_id)
    assert len(deleted_rows) == 2
    assert all(row['entity_id'] == entity.entity_id for row in deleted_rows)

    remaining_rows = ci_db.search_contact_info(
        database,
        entity_id=(entity.entity_id, other_entity.entity_id),
        limit=10,
        fetchall=True,
    )
    assert len(remaining_rows) == 2
    assert all(row['entity_id'] == other_entity.entity_id
               for row in remaining_rows)
