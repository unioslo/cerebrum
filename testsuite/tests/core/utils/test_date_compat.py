# encoding: utf-8
""" Tests for mod:`Cerebrum.utils.date_compat` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
import pytz

from Cerebrum.utils import date
from Cerebrum.utils import date_compat


LOCAL_TZ = date.TIMEZONE


class _MockDateTime(object):
    """ a mock mx-like datetime object with pydate() and pydatetime() """

    def __init__(self, ts):
        """
        :param datetime.datetime ts: a naive datetime object
        """
        self.ts = ts

    @property
    def hour(self):
        # needed for is_mx_date/is_mx_datetime
        return self.ts.hour

    @property
    def minute(self):
        # needed for is_mx_date/is_mx_datetime
        return self.ts.minute

    @property
    def second(self):
        # needed for is_mx_date/is_mx_datetime
        return self.ts.second

    def pytime(self):
        # needed for is_mx_date/is_mx_datetime
        return self.ts.time()

    def pydate(self):
        return self.ts.date()

    def pydatetime(self):
        return self.ts


class _MockDelta(object):
    """ a mock mx-like timedelta object with pytimedelta() """

    def __init__(self, delta):
        """
        :param datetime.timedelta delta: a timedelta object
        """
        self.delta = delta

    def pytimedelta(self):
        return self.delta


#
# Fixtures
#
# The fixtures returns an objet that represents roughly the same *time*:
# `utc_dt`.  The other fixtures represent that date/time, but localized to
# `LOCAL_TZ`.


@pytest.fixture
def utc_dt():
    """
    timezone-aware datetime object @ utc.

    This fixture is the basis of all the other date/datetime fixtures.
    """
    return date.apply_timezone(
        datetime.datetime(1998, 6, 28, 23, 30, 11, 987654),
        pytz.UTC)


@pytest.fixture
def local_dt(utc_dt):
    """ timezone-aware datetime object @ local time. """
    return date.to_timezone(utc_dt, LOCAL_TZ)


@pytest.fixture
def naive_dt(local_dt):
    """ naive (no tzinfo) datetime object representing `local_dt`. """
    return date.strip_timezone(local_dt)


@pytest.fixture
def mxlike_dt(naive_dt):
    """ mx-like datetime object representing `local_dt`. """
    return _MockDateTime(naive_dt)


@pytest.fixture
def local_date(local_dt):
    """ datetime.date part of `local_dt`. """
    return local_dt.date()


@pytest.fixture
def mxlike_date(local_date):
    """ mx-like date object representing `local_date`. """
    ts = datetime.datetime.combine(local_date, datetime.time(0))
    return _MockDateTime(ts)


@pytest.fixture
def delta():
    """ timedelta. """
    return datetime.timedelta(days=3, hours=2, minutes=1, seconds=30)


@pytest.fixture
def mxlike_delta(delta):
    """ mx-like timedelta object representing `delta`. """
    return _MockDelta(delta)


@pytest.fixture
def mxlike_format(local_dt):
    """ mx-like strval from the `local_dt` """
    return ".".join((
        local_dt.strftime("%Y-%m-%d %H:%M:%S"),
        local_dt.strftime('%f')[:2],
    ))


# identify mx datetime like objects

def test_is_mx_datetime_hit(mxlike_dt):
    assert date_compat.is_mx_datetime(mxlike_dt)


def test_is_mx_datetime_miss(naive_dt):
    assert not date_compat.is_mx_datetime(naive_dt)


def test_is_mx_date_hit(mxlike_date):
    assert date_compat.is_mx_date(mxlike_date)


def test_is_mx_date_miss(mxlike_dt):
    assert not date_compat.is_mx_date(mxlike_dt)
    assert not date_compat.is_mx_date(object())


def test_is_mx_delta_hit(mxlike_delta):
    assert date_compat.is_mx_delta(mxlike_delta)


def test_is_mx_delta_miss(delta):
    assert not date_compat.is_mx_delta(delta)


# get_date tests


def test_get_date_from_none():
    assert date_compat.get_date(None) is None


def test_get_date_disallow_none():
    with pytest.raises(ValueError):
        date_compat.get_date(None, allow_none=False)


def test_get_date_from_naive(naive_dt, local_date):
    assert date_compat.get_date(naive_dt) == local_date


def test_get_date_from_aware(local_dt, local_date):
    assert date_compat.get_date(local_dt) == local_date


def test_get_date_from_date(local_date):
    assert date_compat.get_date(local_date) == local_date


def test_get_date_from_mx(mxlike_dt, local_date):
    assert date_compat.get_date(mxlike_dt) == local_date


def test_get_date_from_nondate(delta):
    with pytest.raises(ValueError):
        date_compat.get_date(delta)


# get_datetime_naive tests
#
# None, date, naive datetime, tz-aware datetime, mx-like datetime
# should all result in a sane naive datetime object.
#
# If tzinfo is present, we convert the datetime it to the given tz before
# stripping tzinfo (defaults to cereconf.TIMEZONE)


def test_get_datetime_naive_from_none():
    assert date_compat.get_datetime_naive(None, tz=LOCAL_TZ) is None


def test_get_datetime_naive_disallow_none():
    with pytest.raises(ValueError):
        date_compat.get_datetime_naive(None, allow_none=False, tz=LOCAL_TZ)


def test_get_datetime_naive_from_naive(naive_dt):
    # naive datetime -> no change
    assert date_compat.get_datetime_naive(naive_dt, tz=LOCAL_TZ) == naive_dt


def test_get_datetime_naive_from_aware(local_dt, naive_dt):
    # aware datetime -> naive datetime
    assert date_compat.get_datetime_naive(local_dt, tz=LOCAL_TZ) == naive_dt


def test_get_datetime_naive_from_date(local_date):
    # date -> naive <local_date + time(0)>
    naive = datetime.datetime.combine(local_date, datetime.time(0))
    assert date_compat.get_datetime_naive(local_date, tz=LOCAL_TZ) == naive


def test_get_datetime_naive_from_mx(mxlike_dt, naive_dt):
    # mx-like -> naive datetime
    assert date_compat.get_datetime_naive(mxlike_dt, tz=LOCAL_TZ) == naive_dt


# get_datetime_tz tests
#
# None, date, naive datetime, tz-aware datetime, mx-like datetime
# should all result in a sane tz-aware datetime object.
#
# If tzinfo is missing from the input, we assume the *naive* date/datetime is
# already in the given tz (defaults to cereconf.TIMEZONE)


def test_get_datetime_tz_from_none():
    assert date_compat.get_datetime_tz(None, tz=LOCAL_TZ) is None


def test_get_datetime_tz_disallow_none():
    with pytest.raises(ValueError):
        date_compat.get_datetime_tz(None, allow_none=False, tz=LOCAL_TZ)


def test_get_datetime_tz_from_naive(naive_dt, local_dt):
    # naive datetime -> tz-aware datetime in LOCAL_TZ
    assert date_compat.get_datetime_tz(naive_dt, tz=LOCAL_TZ) == local_dt


def test_get_datetime_tz_from_aware(local_dt):
    # tz-aware datetime -> no change
    assert date_compat.get_datetime_tz(local_dt, tz=LOCAL_TZ) == local_dt


def test_get_datetime_tz_from_date(local_date):
    # date -> tz-aware <local_date + time(0)> in LOCAL_TZ
    naive = datetime.datetime.combine(local_date, datetime.time(0))
    aware = date.apply_timezone(naive, tz=LOCAL_TZ)
    assert date_compat.get_datetime_tz(local_date, tz=LOCAL_TZ) == aware


def test_get_datetime_tz_from_mx(mxlike_dt, local_dt):
    assert date_compat.get_datetime_tz(mxlike_dt, tz=LOCAL_TZ) == local_dt


# get_timedelta tests


def test_get_timedelta_from_none():
    assert date_compat.get_timedelta(None) is None


def test_get_timedelta_disallow_none():
    with pytest.raises(ValueError):
        date_compat.get_timedelta(None, allow_none=False)


def test_get_timedelta_from_timedelta(delta):
    # timedelta -> no change
    assert date_compat.get_timedelta(delta) == delta


def test_get_timedelta_from_mx(mxlike_delta, delta):
    assert date_compat.get_timedelta(mxlike_delta) == delta


def test_get_timedelta_from_days():
    # int <n> -> delta of <n> days
    days = 3
    delta = datetime.timedelta(days=days)
    assert date_compat.get_timedelta(days) == delta


# mx-datetime compatibility helper tests


def test_to_mx_format(mxlike_dt, mxlike_format):
    assert date_compat.to_mx_format(mxlike_dt, tz=LOCAL_TZ) == mxlike_format


def test_parse_fs_xml_date(mxlike_format, local_date):
    assert date_compat.parse_fs_xml_date(mxlike_format) == local_date


def test_parse_fs_xml_date_allow_empty():
    assert date_compat.parse_fs_xml_date("", allow_empty=True) is None


def test_parse_fs_xml_date_disallow_empty():
    with pytest.raises(ValueError):
        date_compat.parse_fs_xml_date("", allow_empty=False)
