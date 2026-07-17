# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.audit.formatter` """
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
from Cerebrum.modules.audit import formatter
from Cerebrum.utils import date as date_utils


@six.python_2_unicode_compatible
class _MockChangeType(object):
    """ A Mock ChangeType code. """

    def __init__(self, category, chtype, intval):
        self.category = category
        self.type = chtype
        self.int = int(intval)
        self.msg_string = None
        self.format = None

    def __repr__(self):
        return "<MockChangeType %s (%d)>" % (self, self)

    def __str__(self):
        return ":".join((self.category, self.type))

    def __int__(self):
        return self.int


EXAMPE_CHANGE = _MockChangeType("person", "test", 42)

EXAMPLE_OPERATOR = {
    'id': 1001,
    'name': "operator",
    'type': "account",
}

EXAMPLE_ENTITY = {
    'id': 1002,
    'name': None,
    'type': "person",
}


EXAMPLE_TIMESTAMP = datetime.datetime(1998, 6, 28, 23, 30, 11, 987654,
                                      tzinfo=date_utils.UTC)

EXAMPLE_PROGRAM = __name__


EXAMPLE_RECORD = {
    'record_id': 123,
    'timestamp': EXAMPLE_TIMESTAMP,
    'change_type': EXAMPE_CHANGE,
    'operator': EXAMPLE_OPERATOR['id'],
    'entity': EXAMPLE_ENTITY['id'],
    'target': None,
    'metadata': {
        'change': six.text_type(EXAMPE_CHANGE),
        'operator_type': EXAMPLE_OPERATOR['type'],
        'operator_name': EXAMPLE_OPERATOR['name'],
        'entity_type': EXAMPLE_ENTITY['type'],
        'entity_name': EXAMPLE_ENTITY['name'],
        'target_type': None,
        'target_name': None,
        'change_program': EXAMPLE_PROGRAM,
    },
    'params': {
        'foo': "example text",
        'bar': 3,
    },
}


@pytest.fixture
def record_data():
    """ a copy of EXAMPLE_RECORD. """
    data = dict(EXAMPLE_RECORD)
    data['metadata'] = dict(EXAMPLE_RECORD['metadata'])
    data['params'] = dict(EXAMPLE_RECORD['params'])
    return data


@pytest.fixture
def new_record(record_data):
    return record.AuditRecord.from_dict(record_data)


@pytest.fixture
def db_record(record_data):
    return record.DbAuditRecord.from_dict(record_data)


#
# PreparedRecord tests
#


@pytest.fixture
def prepared_record(db_record):
    return formatter.PreparedRecord(db_record)


def test_prepared_record_init(prepared_record):
    assert prepared_record
    assert prepared_record.message is None


def test_prepared_record_message(prepared_record):
    message = "Hello, world!"
    prepared_record = formatter.PreparedRecord(db_record, message)
    assert prepared_record.message == message


def test_prepared_record_repr(prepared_record):
    assert repr(prepared_record).startswith(
        "<PreparedRecord change=" + six.text_type(EXAMPE_CHANGE)
    )


def test_prepared_record_id(prepared_record, record_data):
    record_id = record_data['record_id']
    assert prepared_record.record_id == record_id


def test_prepared_record_id_missing(new_record):
    prepared_record = formatter.PreparedRecord(new_record)
    assert prepared_record.record_id is None


def test_prepared_record_timestamp(prepared_record, record_data):
    expect_start = record_data['timestamp'].date().isoformat()
    assert prepared_record.timestamp.startswith(expect_start)


def test_prepared_record_timestamp_missing(new_record):
    prepared_record = formatter.PreparedRecord(new_record)
    assert prepared_record.timestamp is None


def test_prepared_record_change_type(prepared_record, record_data):
    expected = six.text_type(record_data['change_type'])
    assert prepared_record.change_type == expected


def test_prepared_record_operator(prepared_record, record_data):
    operator_name = record_data['metadata']['operator_name']
    operator_id = record_data['operator']
    expected = "%s(%d)" % (operator_name, operator_id)
    assert prepared_record.operator == expected


def test_prepared_record_entity(prepared_record, record_data):
    entity_id = record_data['entity']
    expected = "<no name>(%d)" % (entity_id,)
    assert prepared_record.entity == expected


def test_prepared_record_target(prepared_record):
    assert prepared_record.target is None


def test_prepared_record_change_program(prepared_record, record_data):
    expected = record_data['metadata']['change_program']
    assert prepared_record.change_program == expected


def test_prepared_record_change_by_program(prepared_record):
    assert prepared_record.change_by == prepared_record.change_program


def test_prepared_record_change_by_operator(prepared_record, record_data):
    del record_data['metadata']['change_program']
    assert prepared_record.change_by == prepared_record.operator


def test_prepared_record_to_dict(prepared_record, record_data):
    result = prepared_record.to_dict()
    assert result['message'] is None
    assert result['change_type'] == prepared_record.change_type
    assert result['metadata'] == record_data['metadata']


#
# format_message tests
#
# This tests the default (fallback) AuditRecord message formatter.
#


def test_format_message(db_record):
    message = formatter.format_message(db_record)
    assert message.startswith("record=%s" % (db_record.record_id,))
    assert "params=" in message
    assert "metadata=" in message


#
# AuditRecordProcessor tests
#


@pytest.fixture
def get_prepared():
    return formatter.AuditRecordProcessor()


def test_audit_record_processor(db_record, get_prepared):
    prepared_record = get_prepared(db_record)
    result = prepared_record.message
    assert result.startswith("record=%d" % (db_record.record_id,))
    assert "params=" in result
    assert "metadata=" in result


def test_audit_record_processor_legacy(db_record, get_prepared):
    # This is a bit ugly, as we end up creating a new db connection
    change_type = _MockChangeType("foo", "bar", 1)
    change_type.msg_string = "legacy subject=%(subject)s"
    change_type.format = ["intval=%(int:bar)s"]
    db_record.change_type = change_type
    db_record.metadata['change'] = six.text_type(change_type)

    prepared_record = get_prepared(db_record)
    result = prepared_record.message
    assert result.startswith("legacy subject=")
    assert "intval=3" in result


#
# AuditRecordFormatter tests
#


def test_audit_record_formatter(prepared_record):
    prepared_record.message = "hello!"

    record_format = "record[{record_id}]: {change_type} - {message}"
    fmt_msg = formatter.AuditRecordFormatter(record_format)

    expected = record_format.format(record_id=prepared_record.record_id,
                                    change_type=prepared_record.change_type,
                                    message=prepared_record.message)

    assert fmt_msg(prepared_record) == expected
