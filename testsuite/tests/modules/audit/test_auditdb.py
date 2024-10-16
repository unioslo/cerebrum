# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.audit.auditdb` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
import six

from Cerebrum.modules.audit import auditdb
from Cerebrum.utils import date as date_utils


@pytest.fixture
def operator(initial_account):
    return initial_account


@pytest.fixture
def operator_id(operator):
    return operator.entity_id


@pytest.fixture
def group(group_creator):
    group, _ = next(group_creator(1))
    return group


@pytest.fixture
def record_id(database, const, clconst, operator, group):
    """ a simulated group type update. """
    change_type = clconst.group_mod
    return auditdb.sql_insert(
        database,
        change_type=change_type,
        operator_id=operator.entity_id,
        entity_id=group.entity_id,
        metadata={
            'change': six.text_type(change_type),
            'operator_type': six.text_type(const.entity_account),
            'operator_name': operator.account_name,
            'entity_type': six.text_type(const.entity_group),
            'entity_name': group.group_name,
            'target_type': None,
            'target_name': None,
            'change_program': __name__,
        },
        params={
            'old_group_type': six.text_type(const.group_type_unknown),
        },
    )


#
# test insert
#


def test_minimal_insert(database, clconst, operator_id, group):
    record_id = auditdb.sql_insert(
        database,
        clconst.group_mod,
        operator_id,
        group.entity_id,
    )
    assert record_id > 0


def test_insert(record_id):
    assert record_id > 0


#
# test get
#


def test_get_record(database, clconst, operator_id, group, record_id):
    record = auditdb.sql_get_record(database, record_id)
    assert record['record_id'] == record_id
    assert record['change_type'] == clconst.group_mod
    assert record['operator'] == operator_id
    assert record['entity'] == group.entity_id
    assert 'change' in record['metadata']
    assert 'old_group_type' in record['params']


#
# search and delete tests
#


CHANGE_PROGRAM_A = "test-prog-fd33b3a2803bd417"
CHANGE_PROGRAM_B = "test-prog-2faedf53f0efb73b"


@pytest.fixture
def now():
    return date_utils.now()


@pytest.fixture
def records(database, const, clconst, operator, group, now):
    """ a series of changes for *group* by *operator*. """

    def add_record(change_type, meta=None, params=None, timestamp=None):
        metadata = {
            'change': six.text_type(change_type),
            'change_program': CHANGE_PROGRAM_A,
            'entity_name': group.group_name,
            'entity_type': six.text_type(const.entity_group),
            'operator_name': operator.account_name,
            'operator_type': six.text_type(const.entity_account),
            'target_name': None,
            'target_type': None,
        }
        if meta:
            metadata.update(meta)

        return auditdb.sql_insert(
            database,
            change_type=change_type,
            operator_id=operator.entity_id,
            entity_id=group.entity_id,
            metadata=metadata,
            params=params,
            timestamp=timestamp,
        )

    records = []

    # entity:add
    records.append(
        add_record(
            clconst.entity_add,
            meta={'entity_name': None},  # name doesn't exist yet
            timestamp=now - datetime.timedelta(minutes=30),
        )
    )
    # group:create
    records.append(
        add_record(
            clconst.group_create,
            meta={'entity_name': None},  # name doesn't exist yet
            timestamp=now - datetime.timedelta(minutes=29, seconds=58),
        )
    )
    # entity_name:add
    records.append(
        add_record(
            clconst.entity_name_add,
            params={
                'domain': int(const.group_namespace),
                'domain_str': six.text_type(const.group_namespace),
                'name': group.group_name,
            },
            timestamp=now - datetime.timedelta(minutes=29, seconds=56),
        )
    )
    # group:mod
    records.append(
        add_record(
            clconst.group_mod,
            meta={'change_program': CHANGE_PROGRAM_B},  # another change prog
            params={
                'old_group_type': six.text_type(const.group_type_unknown),
            },
            timestamp=now - datetime.timedelta(minutes=15),
        )
    )
    return records


def test_search_entity_id(database, clconst, records, group):
    results = auditdb.sql_search(
        database,
        entities=int(group.entity_id),
        fetchall=True
    )
    assert len(results) == 4


def test_search_date_range(database, clconst, records, group, now):
    results = auditdb.sql_search(
        database,
        entities=int(group.entity_id),
        after_timestamp=now - datetime.timedelta(minutes=29, seconds=57),
        before_timestamp=now - datetime.timedelta(minutes=20),
        fetchall=True,
    )
    assert len(results) == 1
    assert results[0]['change_type'] == clconst.entity_name_add


def test_search_date_range_invalid(database, group, now):
    with pytest.raises(ValueError) as exc_info:
        auditdb.sql_search(
            database,
            entities=int(group.entity_id),
            after_timestamp=(now - datetime.timedelta(minutes=10)),
            before_timestamp=(now - datetime.timedelta(minutes=20)),
        )

    error_msg = six.text_type(exc_info.value)
    assert "invalid range" in error_msg


def test_search_record_range(database, clconst, records, group):
    results = auditdb.sql_search(
        database,
        entities=int(group.entity_id),
        after_id=min(records),
        before_id=max(records),
        fetchall=True,
    )
    assert len(results) == 2


def test_search_record_range_invalid(database, group, now):
    with pytest.raises(ValueError) as exc_info:
        auditdb.sql_search(
            database,
            entities=int(group.entity_id),
            after_id=10,
            before_id=5,
        )

    error_msg = six.text_type(exc_info.value)
    assert "invalid range" in error_msg


def test_search_change_type(database, clconst, records, group):
    results = auditdb.sql_search(
        database,
        entities=int(group.entity_id),
        change_types=[clconst.entity_name_add, clconst.group_mod],
        fetchall=True
    )
    assert len(results) == 2


def test_search_operator(database, clconst, records, operator_id, group):
    results = auditdb.sql_search(
        database,
        entities=int(group.entity_id),
        operators=operator_id,
        fetchall=True
    )
    assert len(results) == 4


def test_delete_records(database, clconst, records, operator_id, group):
    auditdb.sql_delete(
        database,
        entities=int(group.entity_id),
        after_id=min(records),
        before_id=max(records),
    )
    results = auditdb.sql_search(
        database,
        entities=int(group.entity_id),
        fetchall=True,
    )
    assert len(results) == 2
    assert results[0]['record_id'] == min(records)
    assert results[1]['record_id'] == max(records)


#
# test serialize_params
#


def test_serialize_params(now):
    params = {
        'foo': (1, 2, 3),
        'bar': now,
    }
    result = auditdb.serialize_params(params)
    assert len(result) == 2
    assert result['foo'] == list(params['foo'])
    assert result['bar'] == now.isoformat()


#
# test db_row_to_record
#


def test_db_row_to_record(database, clconst, record_id):
    row = auditdb.sql_get_record(database, record_id)
    record = auditdb.db_row_to_record(database, row)
    assert record.record_id == record_id
    assert record.change_type == clconst.group_mod


#
# test AuditLogAccessor
#


@pytest.fixture
def accessor(database):
    return auditdb.AuditLogAccessor(database)


def test_accessor_get_by_id(accessor, clconst, record_id):
    record = accessor.get_by_id(record_id)
    assert record.record_id == record_id
    assert record.change_type == clconst.group_mod


def test_accessor_search(accessor, clconst, records, group):
    results = accessor.search(entities=int(group.entity_id),
                              change_types=[clconst.group_mod])
    record = next(results)
    assert record.change_type == clconst.group_mod
    with pytest.raises(StopIteration):
        next(results)


def test_accessor_append(accessor, const, clconst, operator, group):
    change_type = clconst.group_mod
    mock_record = type(
        str("MockRecord"),
        (object,),
        {
            'change_type': change_type,
            'operator_id': operator.entity_id,
            'entity_id': group.entity_id,
            'target_id': None,
            'metadata': {
                'change': six.text_type(change_type),
                'operator_type': six.text_type(const.entity_account),
                'operator_name': operator.account_name,
                'entity_type': six.text_type(const.entity_group),
                'entity_name': group.group_name,
                'target_type': None,
                'target_name': None,
                'change_program': CHANGE_PROGRAM_A,
            },
            'params': {
                'old_group_type': six.text_type(const.group_type_unknown),
            },
            'timestamp': None,
            'record_id': None,
        },
    )()

    record_id = accessor.append(mock_record)
    assert record_id > 0
