# encoding: utf-8
"""
Tests for mod:`Cerebrum.utils.json`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import io

import pytest
import pytz
import six

from Cerebrum.utils import date as date_utils
from Cerebrum.utils import json


class MxLike(object):
    """
    A minimal mock mx-like datetime object.

    This object is recognized as a mx-like datetime object by
    ``is_mx_datetime``, and has all the methods and attributes used by our
    other mx-like compatibility functions.
    """

    def __init__(self, year, month=1, day=1, hour=0, minute=0, second=0.0):
        self._dt = datetime.datetime(int(year), int(month), int(day),
                                     int(hour), int(minute), int(second),
                                     int((second - int(second)) * 1000000))

    @property
    def year(self):
        return self._dt.year

    @property
    def month(self):
        return self._dt.month

    @property
    def day(self):
        return self._dt.day

    @property
    def hour(self):
        return self._dt.hour

    @property
    def minute(self):
        return self._dt.minute

    @property
    def second(self):
        return self._dt.second + self._dt.microsecond / 1000000

    def pydate(self):
        return self._dt.date()

    def pydatetime(self):
        return self._dt.replace()

    def pytime(self):
        return self._dt.time()


def test_dump_mx_datetime():
    mx_dt = MxLike(2018, 1, 1, 12, 0, 0)
    mx_repr = '"2018-01-01T12:00:00+01:00"'
    assert json.dumps(mx_dt) == mx_repr


def test_dump_mx_date():
    mx_dt = MxLike(2018, 1, 1, 0, 0, 0)
    mx_repr = '"2018-01-01"'
    assert json.dumps(mx_dt) == mx_repr


def test_dump_datetime_naive():
    dt = datetime.datetime(1998, 6, 28, 23, 30, 11, 987654)
    iso_repr = '"1998-06-28T23:30:11.987654+02:00"'
    assert json.dumps(dt) == iso_repr


def test_dump_datetime_tz():
    dt = date_utils.apply_timezone(
        datetime.datetime(1998, 6, 28, 23, 30, 11, 987654),
        pytz.UTC)
    iso_repr = '"1998-06-28T23:30:11.987654+00:00"'
    assert json.dumps(dt) == iso_repr


def test_dump_date():
    dt = datetime.date(1998, 6, 28)
    iso_repr = '"1998-06-28"'
    assert json.dumps(dt) == iso_repr


def test_dump_entity(const, initial_account):
    output = json.dumps(initial_account, sort_keys=True)

    assert output == (
        '{{"__cerebrum_object__": "entity", '
        '"entity_id": {}, '
        '"entity_type": {}, '
        '"str": "{}"}}'
    ).format(
        initial_account.entity_id,
        json.dumps(const.entity_account),
        six.text_type(initial_account),
    )


def test_load_entity(database, const, initial_account):
    text = """
      {{
        "__cerebrum_object__": "entity",
        "entity_id": {},
        "entity_type": {},
        "str": {}
      }}
    """.format(
        json.dumps(initial_account.entity_id),
        json.dumps(const.entity_account),
        json.dumps(six.text_type(initial_account)),
    )
    # Note: This is a bit ugly, as loads() initializes and uses a global db
    # connection, bypassing all our fixtures.
    assert json.loads(text) == initial_account


def test_dump_constant(const):
    output = json.dumps(const.entity_account, sort_keys=True)
    assert output == (
        '{{"__cerebrum_object__": "code", '
        '"code": {d}, '
        '"str": "{c}", '
        '"table": "{t}"}}'
    ).format(
        c=const.entity_account,
        d=int(const.entity_account),
        t=const.EntityType._lookup_table,
    )


def test_load_constant(const):
    text = """
      {{
        "__cerebrum_object__": "code",
        "code": {d},
        "str": "{c}",
        "table": "{t}"
      }}
    """.format(
        c=const.entity_account,
        d=int(const.entity_account),
        t=const.EntityType._lookup_table,
    )
    # Note: This is a bit ugly, as loads() initializes and uses a global db
    # connection, bypassing all our fixtures.
    assert json.loads(text) == const.entity_account


def test_load_invalid_constant(const):
    text = '{"__cerebrum_object__": "code"}'
    with pytest.raises(ValueError):
        json.loads(text)


def test_dump_set():
    assert json.dumps(set((4, 1, 8))) == "[1, 4, 8]"


def test_dump_tuple():
    assert json.dumps((4, 1, 8)) == "[4, 1, 8]"


def test_dump_unsupported():
    with pytest.raises(TypeError):
        assert json.dumps(object())


def test_load_unsupported():
    text = '{"__cerebrum_object__": "unsupported-object-type"}'
    with pytest.raises(ValueError) as exc_info:
        json.loads(text)
    err = six.text_type(exc_info.value)
    assert err.startswith("No handler for decoding")


def test_dump_text():
    txt = "blåbærøl"
    txt_repr = '"%s"' % (txt,)
    assert json.dumps(txt) == txt_repr


def test_dump_to_file():
    obj = {"hello": "world", "lst": [1, 2, 3]}
    expected = '{"hello": "world", "lst": [1, 2, 3]}'
    with io.StringIO() as fd:
        json.dump(obj, fd, sort_keys=True)
        output = fd.getvalue()
    assert output == expected


def test_load_from_file():
    text = '{"hello": "world", "lst": [1, 2, 3]}'
    expected = {"hello": "world", "lst": [1, 2, 3]}
    with io.StringIO(text) as fd:
        obj = json.load(fd)
    assert obj == expected
