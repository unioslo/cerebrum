# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.modules.audit.auditlog`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import pytest
import six

from Cerebrum.modules.audit import auditdb
from Cerebrum.modules.audit import auditlog


class StandaloneAuditLog(auditlog.AuditLog):

    def __init__(self, db):
        self.__db = db

    @property
    def _audit_log_db(self):
        return self.__db


@pytest.fixture
def group(group_creator):
    group, _ = next(group_creator(1))
    return group


@pytest.fixture
def log(database):
    changelog = StandaloneAuditLog(database)
    changelog.cl_init(change_program=__name__)
    return changelog


#
# AuditRecordBuilder tests
#


@pytest.fixture
def builder(database, const, clconst):
    record_builder = auditlog.AuditRecordBuilder(database)
    record_builder._const = const
    record_builder._clconst = clconst
    return record_builder


def test_builder_get_change_type(builder):
    code = builder.clconst.group_add
    assert builder.get_change_type(int(code)) == code
    assert builder.get_change_type(code) == code


def test_builder_build_meta(builder, group, initial_account):
    change_type = builder.clconst.group_add
    operator = initial_account
    entity = group
    target = initial_account
    change_program = __name__

    metadata = builder.build_meta(change_type, operator.entity_id,
                                  entity.entity_id, target.entity_id,
                                  change_program)

    assert metadata == {
        'change': six.text_type(change_type),
        'operator_type': six.text_type(builder.const.entity_account),
        'operator_name': operator.account_name,
        'entity_type': six.text_type(builder.const.entity_group),
        'entity_name': group.group_name,
        'target_type': six.text_type(builder.const.entity_account),
        'target_name': operator.account_name,
        'change_program': change_program,
    }


def test_build_params_account_create(builder, initial_account):
    params = {
        'np_type': int(builder.const.account_program),
        'owner_type': int(builder.const.entity_group),
    }

    result = builder.build_params(
        change_type=builder.clconst.account_create,
        subject_entity=initial_account,
        destination_entity=None,
        change_params=params,
    )
    assert 'np_type_str' in result
    assert 'owner_type_str' in result


def test_build_params_account_password(builder, initial_account):
    params = {
        'password': "hunter2",
    }

    result = builder.build_params(
        change_type=builder.clconst.account_password,
        subject_entity=initial_account,
        destination_entity=None,
        change_params=params,
    )
    assert 'password' not in result


#
# AuditLog tests
#


@pytest.fixture
def test_auditlog_initial_account_id(log, initial_account):
    expected_id = initial_account.entity_id
    assert log.initial_account_id == expected_id


def test_auditlog_log_change(log, clconst, group, initial_account):
    params = {
        'foo': "test",
    }
    log.log_change(
        subject_entity=group.entity_id,
        change_type_id=clconst.group_add,
        destination_entity=initial_account.entity_id,
        change_params=params,
    )

    assert len(log.records) == 1
    record = log.records[0]
    assert record.entity_id == group.entity_id
    assert record.params == params


def test_auditlog_clear_log(log, clconst, group, initial_account):
    # Set up a single record in the auditlog queue
    log.log_change(
        subject_entity=group.entity_id,
        change_type_id=clconst.group_add,
        destination_entity=initial_account.entity_id,
    )
    assert len(log.records) == 1

    # Check that the queue can be cleared
    log.clear_log()
    assert len(log.records) == 0


def test_auditlog_write_log(database, log, clconst, group, initial_account):
    # Set up a single record in the auditlog queue
    log.log_change(
        subject_entity=group.entity_id,
        change_type_id=clconst.group_add,
        destination_entity=initial_account.entity_id,
    )
    assert len(log.records) == 1

    # Check that the queue is cleared after writing
    log.write_log()
    assert len(log.records) == 0

    # Check that the record is written
    results = auditdb.sql_search(database,
                                 change_types=clconst.group_add,
                                 entities=int(group.entity_id),
                                 targets=int(initial_account.entity_id),
                                 fetchall=True)
    assert len(results) == 1
