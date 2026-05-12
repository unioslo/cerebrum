""" Tests for :mod:`Cerebrum.entity.external_id` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

import Cerebrum.Person
import Cerebrum.Entity
import Cerebrum.Errors
from Cerebrum.entity import external_id as id_db
from Cerebrum.testutils.log_utils import StrictNullHandler


#
# Some common fixtures
#


@pytest.fixture(scope='module', autouse=True)
def _patch_logging():
    """ catch badly formatted log records in reguser.logger """
    # consider mistakes in log formatting to be a test failure
    id_db.logger.addHandler(StrictNullHandler())
    id_db.logger.setLevel(-100)


@pytest.fixture
def id_foo(constant_module, constant_creator, entity_type):
    return constant_creator(
        constant_module._EntityExternalIdCode,
        "id-foo-dcd46eac",
        entity_type,
    )


@pytest.fixture
def id_bar(constant_module, constant_creator, entity_type):
    return constant_creator(
        constant_module._EntityExternalIdCode,
        "id-bar-dcd46ead",
        entity_type,
    )


@pytest.fixture
def entity(database, entity_type):
    entity_obj = Cerebrum.Entity.EntityExternalId(database)
    entity_obj.populate(entity_type)
    entity_obj.write_db()
    return entity_obj


#
# set_external_id tests
#


def test_set_external_id__insert(database, entity, system_a, id_bar):
    row = id_db.set_external_id(database, entity.entity_id, entity.entity_type,
                                system_a, id_bar, "value")
    assert dict(row) == {
        'entity_id': int(entity.entity_id),
        'entity_type': int(entity.entity_type),
        'source_system': int(system_a),
        'id_type': int(id_bar),
        'id_value': "value",
    }


def test_set_external_id__insert__no_value(database, entity, system_a, id_bar):
    with pytest.raises(ValueError):
        id_db.set_external_id(database, entity.entity_id, entity.entity_type,
                              system_a, id_bar, "")


def test_set_external_id__update(database, entity, system_a, id_bar):
    id_db.set_external_id(database, entity.entity_id, entity.entity_type,
                          system_a, id_bar, "value")
    row = id_db.set_external_id(database, entity.entity_id, entity.entity_type,
                                system_a, id_bar, "new-value")
    assert dict(row) == {
        'entity_id': int(entity.entity_id),
        'entity_type': int(entity.entity_type),
        'source_system': int(system_a),
        'id_type': int(id_bar),
        'id_value': "new-value",
    }


def test_set_external_id__update__no_value(database, entity, system_a, id_bar):
    id_db.set_external_id(database, entity.entity_id, entity.entity_type,
                          system_a, id_bar, "value")
    with pytest.raises(ValueError):
        id_db.set_external_id(database, entity.entity_id, entity.entity_type,
                              system_a, id_bar, "")


def test_set_external_id__no_change(database, entity, system_a, id_bar):
    id_db.set_external_id(database, entity.entity_id, entity.entity_type,
                          system_a, id_bar, "value")
    row = id_db.set_external_id(database, entity.entity_id, entity.entity_type,
                                system_a, id_bar, "value")
    assert dict(row) == {
        'entity_id': int(entity.entity_id),
        'entity_type': int(entity.entity_type),
        'source_system': int(system_a),
        'id_type': int(id_bar),
        'id_value': "value",
    }


#
# search_external_ids tests
#


def test_search_external_id__no_prefix(database, entity):
    with pytest.raises(TypeError) as exc_info:
        id_db.search_external_ids(database, entity_id=int(entity.entity_id),
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


@pytest.fixture
def helper(database, system_a, system_b, id_foo, id_bar):
    """ Basic test helper setup, with entities and ids. """

    class Helper(object):

        a = system_a
        b = system_b
        foo = id_foo
        bar = id_bar

        def set_id(self, entity, source_system, id_type, id_value):
            id_db.set_external_id(database, entity.entity_id,
                                  entity.entity_type, source_system, id_type,
                                  id_value)


COMMON_ID = "0uLKKXlv6ZltOavYko"
A_FOO_1 = "a-foo-1-{}-49".format(COMMON_ID)
A_BAR_1 = "a-bar-1-{}-50".format(COMMON_ID)
B_FOO_1 = "b-foo-1-{}-51".format(COMMON_ID)
B_BAR_1 = "b-foo-1-{}-52".format(COMMON_ID)
A_FOO_2 = "a-foo-2-{}-53".format(COMMON_ID)
A_BAR_2 = "a-bar-2-{}-54".format(COMMON_ID)
B_FOO_2 = "b-foo-2-{}-55".format(COMMON_ID)
B_BAR_2 = "b-foo-2-{}-56".format(COMMON_ID)


@pytest.fixture
def values(database, entity, other_entity, system_a, system_b, id_foo, id_bar):
    to_set = [
        (entity, system_a, id_foo, A_FOO_1),
        (entity, system_a, id_bar, A_BAR_1),
        (entity, system_b, id_foo, B_FOO_1),
        (entity, system_b, id_bar, B_BAR_1),
        (other_entity, system_a, id_foo, A_FOO_2),
        (other_entity, system_a, id_bar, A_BAR_2),
        (other_entity, system_b, id_foo, B_FOO_2),
        (other_entity, system_b, id_bar, B_BAR_2)
    ]
    for obj, sys, typ, val in to_set:
        id_db.set_external_id(database, obj.entity_id, obj.entity_type,
                              sys, typ, val)
    return to_set


def test_search_external_id__limit(database, values, system_a):
    rows = id_db.search_external_ids(database, source_system=system_a,
                                     fetchall=True)
    assert len(rows) == 4

    rows = id_db.search_external_ids(database, source_system=system_a,
                                     limit=2, fetchall=True)
    assert len(rows) == 2


def test_search_external_id__exact(database, values, entity, system_a, id_foo):
    rows = id_db.search_external_ids(database,
                                     entity_id=int(entity.entity_id),
                                     source_system=system_a,
                                     id_type=id_foo,
                                     limit=10,
                                     fetchall=True)
    assert len(rows) == 1
    row = rows[0]
    assert dict(row) == {
        'entity_id': int(entity.entity_id),
        'entity_type': int(entity.entity_type),
        'source_system': int(system_a),
        'id_type': int(id_foo),
        'id_value': A_FOO_1,
    }


def test_search_external_id__legacy_name(database, values, entity, system_a,
                                         id_foo):
    rows = id_db.search_external_ids(database,
                                     entity_id=int(entity.entity_id),
                                     source_system=system_a,
                                     id_type=id_foo,
                                     limit=10,
                                     _legacy_name=True,
                                     fetchall=True)
    assert len(rows) == 1
    row = rows[0]
    assert dict(row) == {
        'entity_id': int(entity.entity_id),
        'entity_type': int(entity.entity_type),
        'source_system': int(system_a),
        'id_type': int(id_foo),
        'external_id': A_FOO_1,
    }


def test_search_external_id__by_entity_id(database, values, entity):
    rows = id_db.search_external_ids(database, entity_id=int(entity.entity_id),
                                     limit=10, fetchall=True)
    assert len(rows) == 4
    assert all(row['entity_id'] == entity.entity_id for row in rows)


def test_search_external_id__by_entity_type(database, values, entity_type):
    rows = id_db.search_external_ids(database,
                                     entity_type=entity_type,
                                     limit=10, fetchall=True)
    assert len(rows) == 8
    assert all(row['entity_type'] == entity_type for row in rows)


def test_search_external_id__by_system(database, values, system_a):
    rows = id_db.search_external_ids(database, source_system=system_a,
                                     limit=10, fetchall=True)
    assert len(rows) == 4
    assert all(row['source_system'] == system_a for row in rows)


def test_search_external_id__by_id_type(database, values, id_foo):
    rows = id_db.search_external_ids(database, id_type=id_foo,
                                     limit=10, fetchall=True)
    assert len(rows) == 4
    assert all(row['id_type'] == id_foo for row in rows)


def test_search_external_id__by_id_value__hit(database, values, other_entity,
                                              system_b, id_bar):
    rows = id_db.search_external_ids(database, id_value=B_BAR_2,
                                     limit=10, fetchall=True)
    assert len(rows) == 1
    row = rows[0]
    assert dict(row) == {
        'entity_id': int(other_entity.entity_id),
        'entity_type': int(other_entity.entity_type),
        'source_system': int(system_b),
        'id_type': int(id_bar),
        'id_value': B_BAR_2,
    }


def test_search_external_id__by_id_value__miss(database, values, entity,
                                               system_a, id_foo):
    wrong_value = A_FOO_1 + "x"
    rows = id_db.search_external_ids(database, id_value=wrong_value,
                                     limit=10, fetchall=True)
    assert len(rows) == 0


def test_search_external_id__by_id_value_like(database, values):
    pattern = "*" + COMMON_ID + "-??"
    rows = id_db.search_external_ids(database, id_value_like=pattern,
                                     limit=10, fetchall=True)
    assert len(rows) == 8

    pattern = "*" + COMMON_ID + "-4?"
    rows = id_db.search_external_ids(database, id_value_like=pattern,
                                     limit=10, fetchall=True)
    assert len(rows) == 1


def test_search_external_id__by_id_value_ilike(database, values):
    pattern = ("*" + COMMON_ID + "-5?").lower()
    rows = id_db.search_external_ids(database, id_value_ilike=pattern,
                                     limit=10, fetchall=True)
    assert len(rows) == 7


#
# delete_external_ids tests
#


def test_delete_external_id__no_prefix(database, entity):
    with pytest.raises(TypeError) as exc_info:
        id_db.delete_external_ids(database, entity_id=int(entity.entity_id),
                                  _prefix="foo")

    msg = six.text_type(exc_info.value)
    assert msg.startswith("invalid argument")


def test_delete_external_id__exact(database, values, entity, system_a, id_foo):

    deleted_rows = id_db.delete_external_ids(database,
                                             entity_id=int(entity.entity_id),
                                             source_system=system_a,
                                             id_type=id_foo)
    assert len(deleted_rows) == 1
    assert dict(deleted_rows[0]) == {
        'entity_id': int(entity.entity_id),
        'entity_type': int(entity.entity_type),
        'source_system': int(system_a),
        'id_type': int(id_foo),
        'id_value': A_FOO_1,
    }


def test_delete_external_id__by_entity_id(database, values, entity,
                                          other_entity):
    deleted_rows = id_db.delete_external_ids(database,
                                             entity_id=int(entity.entity_id))
    assert len(deleted_rows) == 4
    assert all(row['entity_id'] == entity.entity_id for row in deleted_rows)

    remaining_rows = id_db.search_external_ids(
        database,
        entity_id=(entity.entity_id, other_entity.entity_id),
        limit=10,
        fetchall=True,
    )
    assert len(remaining_rows) == 4
    assert all(row['entity_id'] == other_entity.entity_id
               for row in remaining_rows)


#
# get_entity_from_ids tests
#


def test_get_entity_from_ids__miss(database, system_a, id_foo):
    identifiers = [
        (id_foo, A_FOO_1, system_a)
    ]
    # no fixture has added this value, so there shouldn't be any matches
    with pytest.raises(Cerebrum.Errors.NotFoundError) as exc_info:
        id_db.get_entity_from_ids(database, *identifiers)

    msg = six.text_type(exc_info.value)
    assert msg.startswith("Could not find")


def test_get_entity_from_ids__hit(database, values, entity, system_a, system_b,
                                  id_foo, id_bar):
    identifiers = [
        (id_foo, A_FOO_1, system_a),
        (id_bar, A_BAR_1, system_a),
        (id_foo, B_FOO_1, system_b),
        (id_bar, B_BAR_1, system_b),
    ]
    result = id_db.get_entity_from_ids(database, *identifiers)
    assert result == entity.entity_id


def test_get_entity_from_ids__multi(database, values, system_a, id_foo):
    identifiers = [
        (id_foo, A_FOO_1, system_a),
        (id_foo, A_FOO_2, system_a),
    ]
    with pytest.raises(Cerebrum.Errors.TooManyRowsError) as exc_info:
        id_db.get_entity_from_ids(database, *identifiers)

    msg = six.text_type(exc_info.value)
    assert msg.startswith("Too many rows")


def test_get_entity_from_ids__mixed_input(database, values, entity, system_a,
                                          system_b, id_foo, id_bar):
    identifiers = [
        (id_foo, A_FOO_1),
        (id_bar, A_BAR_1, None),
        {'id_type': id_foo, 'external_id': B_FOO_1, 'source_system': None},
        {'id_type': id_bar, 'id_value': B_BAR_1},
    ]
    result = id_db.get_entity_from_ids(database, *identifiers)
    assert result == entity.entity_id


#
# list_duplicate_ids tests
#


# We're already set up for miss tests with *values* - as every fixture uses a
# different id value.


def test_list_duplicate_ids__miss__id_type(database, values, id_foo):
    rows = id_db.list_duplicate_ids(database, id_type=id_foo, fetchall=True)
    assert len(rows) == 0


def test_list_duplicate_ids__miss__id_value(database, values):
    rows = id_db.list_duplicate_ids(database, id_value=A_FOO_1, fetchall=True)
    assert len(rows) == 0


@pytest.fixture
def duplicate_values(database, entity, other_entity, system_a, system_b,
                     id_foo, id_bar):
    """
    *other_entity* has the same values as *entity*, but in another system
    """
    to_set = [
        (entity, system_a, id_foo, A_FOO_1),
        (entity, system_a, id_bar, A_BAR_1),
        (other_entity, system_b, id_foo, A_FOO_1),
        (other_entity, system_b, id_bar, A_BAR_1)
    ]
    for obj, sys, typ, val in to_set:
        id_db.set_external_id(database, obj.entity_id, obj.entity_type,
                              sys, typ, val)
    return to_set


def test_list_duplicate_ids__hit__id_type(database, duplicate_values, id_foo):
    rows = id_db.list_duplicate_ids(database, id_type=id_foo, fetchall=True)
    assert len(rows) == 2
    assert all(row['id_type'] == id_foo for row in rows)
    assert all(row['id_value'] == A_FOO_1 for row in rows)


def test_list_duplicate_ids__hit__id_value(database, duplicate_values, id_foo):
    rows = id_db.list_duplicate_ids(database, id_value=A_FOO_1, fetchall=True)
    assert len(rows) == 2
    assert all(row['id_type'] == id_foo for row in rows)
    assert all(row['id_value'] == A_FOO_1 for row in rows)


#
# list_differing_ids tests
#


# We're already set up for hit tests with *values* - usually a given entity
# will not have two *different* values for a given *id-type*, but we've given
# every (entity, source-system, id-type) combination a different value


def test_list_differing_ids__hit__id_type(database, values, id_foo):
    rows = id_db.list_differing_ids(database, id_type=id_foo, fetchall=True)
    # both entity and other_entity has two different *id_foo* values in
    # system a and system b
    assert len(rows) == 4
    assert all(row['id_type'] == id_foo for row in rows)


def test_list_differing_ids__hit__entity_id(database, values, entity):
    rows = id_db.list_differing_ids(database, entity_id=int(entity.entity_id),
                                    fetchall=True)

    # entity has a duplicate *id_foo* and *id_bar*, in two different systems.
    assert len(rows) == 4
    assert all(row['entity_id'] == entity.entity_id for row in rows)


# We're already set up for *miss* tests with *duplicate_values* - this data
# set only sets one id-value for a given (entity, id-type) combination


def test_list_differing_ids__miss__id_type(database, duplicate_values, id_foo):
    rows = id_db.list_differing_ids(database, id_type=id_foo, fetchall=True)
    assert len(rows) == 0


def test_list_differing_ids__miss__entity_id(database, duplicate_values,
                                             entity):
    rows = id_db.list_differing_ids(database, entity_id=int(entity.entity_id),
                                    fetchall=True)
    assert len(rows) == 0
