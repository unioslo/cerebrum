# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.audit.record` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
import six

from Cerebrum.modules.audit import record
from Cerebrum.utils import date as date_utils


class _MockRecord(object):
    """ A DbAuditRecord comparable object. """

    def __init__(self, record_id):
        self.record_id = int(record_id)

    def __repr__(self):
        return "<MockRecord[%d]>" % (self.record_id,)


@six.python_2_unicode_compatible
class _MockChangeType(object):
    """ A Mock ChangeType code. """

    def __init__(self, category, chtype, intval):
        self.category = category
        self.type = chtype
        self.int = int(intval)

    def __repr__(self):
        return "<MockChangeType %s (%d)>" % (self, self)

    def __str__(self):
        return ":".join((self.category, self.type))

    def __int__(self):
        return self.int


EXAMPE_CHANGE = _MockChangeType("group", "test", 42)

EXAMPLE_OPERATOR = {
    'id': 1001,
    'name': "operator",
    'type': "account",
}

EXAMPLE_ENTITY = {
    'id': 1002,
    'name': "test-group",
    'type': "group",
}

EXAMPLE_TARGET = {
    'id': 1003,
    'name': "test-account",
    'type': "account",
}

EXAMPLE_TIMESTAMP = datetime.datetime(1998, 6, 28, 23, 30, 11, 987654,
                                      tzinfo=date_utils.UTC)


#
# AuditRecord tests
#


EXAMPLE_RECORD = {
    'change_type': EXAMPE_CHANGE,
    'operator': EXAMPLE_OPERATOR['id'],
    'entity': EXAMPLE_ENTITY['id'],
    'target': EXAMPLE_TARGET['id'],
    'metadata': {
        'change': six.text_type(EXAMPE_CHANGE),
        'operator_type': EXAMPLE_OPERATOR['type'],
        'operator_name': EXAMPLE_OPERATOR['name'],
        'entity_type': EXAMPLE_ENTITY['type'],
        'entity_name': EXAMPLE_ENTITY['name'],
        'target_type': EXAMPLE_TARGET['type'],
        'target_name': EXAMPLE_TARGET['name'],
        'change_program': __name__,
    },
    'params': {
        'foo': "example text",
        'bar': 3,
    },
}


@pytest.fixture
def audit_record():
    return record.AuditRecord(**EXAMPLE_RECORD)


def test_audit_record_init(audit_record):
    assert audit_record


def test_audit_record_id(audit_record):
    assert audit_record.record_id is None


def test_audit_record_timestamp(audit_record):
    assert audit_record.timestamp is None


def test_audit_record_repr(audit_record):
    expected = (
        "<AuditRecord[] change=%s for=%d>"
        % (EXAMPLE_RECORD['change_type'], EXAMPLE_ENTITY['id'])
    )
    assert repr(audit_record) == expected


def test_audit_record_to_dict(audit_record):
    result = audit_record.to_dict()
    assert result == EXAMPLE_RECORD


def test_audit_record_from_dict():
    result = record.AuditRecord.from_dict(EXAMPLE_RECORD)
    assert result.timestamp is None
    assert result.record_id is None
    assert result.change_type == EXAMPE_CHANGE
    assert result.metadata['entity_name'] == EXAMPLE_ENTITY['name']
    assert result.params['bar'] == 3


#
# DbAuditRecord tests
#


EXAMPLE_RECORD_DB = dict(EXAMPLE_RECORD)
EXAMPLE_RECORD_DB.update({
    'record_id': 123,
    'timestamp': EXAMPLE_TIMESTAMP,
})


@pytest.fixture
def db_record():
    return record.DbAuditRecord(**EXAMPLE_RECORD_DB)


def test_db_audit_record_init(db_record):
    assert db_record


def test_db_audit_record_id(db_record):
    assert db_record.record_id == 123


def test_db_audit_record_timestamp(db_record):
    assert db_record.timestamp == EXAMPLE_TIMESTAMP


def test_db_audit_record_repr(db_record):
    expected_start = (
        "<DbAuditRecord[%d] change=%s for=%d at="
        % (123, EXAMPE_CHANGE, EXAMPLE_ENTITY['id'])
    )
    text = repr(db_record)
    assert text.startswith(expected_start)
    assert EXAMPLE_TIMESTAMP.strftime("at='%Y-%m-%d") in text


def test_db_audit_record_dict():
    result = record.DbAuditRecord.from_dict(EXAMPLE_RECORD_DB).to_dict()
    assert result == EXAMPLE_RECORD_DB


def test_db_record_eq(db_record):
    other = _MockRecord(db_record.record_id)
    assert db_record == other


def test_db_record_ne(db_record):
    other = _MockRecord(db_record.record_id + 1)

    assert not (db_record == other)
    assert db_record != other


def test_db_record_lt_le(db_record):
    other = _MockRecord(db_record.record_id + 1)

    assert db_record < other
    assert not db_record > other


def test_db_record_gt_ge(db_record):
    other = _MockRecord(db_record.record_id - 1)

    assert db_record > other
    assert not db_record < other
