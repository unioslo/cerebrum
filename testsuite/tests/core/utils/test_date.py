# encoding: utf-8
""" Tests for mod:`Cerebrum.utils.date` """
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


# Some known datetime objects


UTC_TZ = pytz.UTC
LOCAL_TZ = pytz.timezone("Europe/Oslo")
EPOCH_NAIVE = datetime.datetime(1970, 1, 1, 0)
EPOCH_AWARE_UTC = UTC_TZ.localize(EPOCH_NAIVE)
EPOCH_AWARE_LOCAL = EPOCH_AWARE_UTC.astimezone(LOCAL_TZ)


@pytest.fixture
def datetime_utc_aware():
    return datetime.datetime.now(tz=pytz.UTC)


#
# test to_seconds
#


@pytest.mark.parametrize(
    "result,args",
    [
        (8, {'seconds': 8}),
        (129, {'minutes': 2, 'seconds': 9}),
        (2017920, {'days': 23, 'minutes': 512}),
        (1242000, {'weeks': 2, 'hours': 9}),
    ]
)
def test_to_seconds(args, result):
    assert date.to_seconds(**args) == result


#
# test utcnow/now
#


def test_utcnow_has_tzinfo():
    now = date.utcnow()
    assert now.tzinfo is not None


def test_now_is_localized():
    # A bit of a hacky test, but it ensures date.now() creates a localized dt
    assert str(date.now().tzinfo) == str(date.TIMEZONE)


def test_now_is_correct(datetime_utc_aware):
    # A bit of a hacky test, but it ensures date.now() creates a correct dt
    assert (date.now() - datetime_utc_aware) < datetime.timedelta(seconds=10)


def test_now_custom_tz(datetime_utc_aware):
    # A bit of a hacky test, but it ensures date.now() accepts a tz-argument,
    # and that the argument may be a string
    diff = abs(date.now("UTC") - datetime_utc_aware)
    assert date.now("UTC").tzinfo == UTC_TZ
    assert diff < datetime.timedelta(seconds=10)


#
# test timezone operations
#


def test_to_timezone():
    converted = date.to_timezone(EPOCH_AWARE_LOCAL, tz="UTC")
    assert converted == EPOCH_AWARE_UTC
    assert converted.tzinfo == EPOCH_AWARE_UTC.tzinfo


def test_apply_timezone_without_tzinfo():
    with pytest.raises(ValueError):
        date.to_timezone(EPOCH_NAIVE, tz="UTC")


def test_apply_timezone():
    converted = date.apply_timezone(EPOCH_NAIVE, tz="UTC")
    assert converted == EPOCH_AWARE_UTC
    assert converted.tzinfo == EPOCH_AWARE_UTC.tzinfo


def test_apply_timezone_with_tzinfo():
    with pytest.raises(ValueError):
        date.apply_timezone(EPOCH_AWARE_UTC, tz="UTC")


def test_strip_timezone():
    converted = date.strip_timezone(EPOCH_AWARE_UTC)
    assert converted.tzinfo is None
    assert converted == EPOCH_NAIVE


def test_strip_timezone_without_tzinfo():
    with pytest.raises(ValueError):
        date.strip_timezone(EPOCH_NAIVE)


#
# test parsers
#


def test_parse_datetime_tz_with_offset(datetime_utc_aware):
    fmt = '%Y-%m-%dT%H:%M:%S.%f%z'
    raw = datetime_utc_aware.strftime(fmt)
    tz = datetime_utc_aware.tzinfo
    dt = date.parse_datetime_tz(raw)
    assert dt.date() == datetime_utc_aware.date()
    assert dt.time() == datetime_utc_aware.time()
    assert dt.tzinfo.utcoffset(dt) == tz.utcoffset(datetime_utc_aware)


def test_parse_datetime_tz_without_offset():
    raw = '2000-10-16T12:15:01'
    with pytest.raises(ValueError):
        date.parse_datetime_tz(raw)


@pytest.mark.parametrize(
    "value",
    [
        '2000-10-16T12:15:01+0200',
        '2000-10-16T12:15:01',
        '2000-10-16 12:15:01',
        '2000-10-16T12',
    ]
)
def test_parse_datetime(value):
    default_timezone = pytz.UTC
    dt = date.parse_datetime(value, default_timezone=default_timezone)
    assert dt.tzinfo is not None


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not a date",
        '2000-10-16',  # a valid date w/o time
        "T",  # just a delimiter
        "+1-10-16T12",  # "extended" or relative year - NotImplementedError
        "2000-10-16T12:15:60",  # leap second
    ]
)
def test_parse_datetime_error(value):
    default_timezone = pytz.UTC
    with pytest.raises(ValueError):
        date.parse_datetime(value, default_timezone=default_timezone)


def test_parse_date():
    raw = '2000-10-16'
    assert date.parse_date(raw) == datetime.date(2000, 10, 16)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not a date",
        "-10-16",  # "extended" or relative year - NotImplementedError
    ]
)
def test_parse_date_error(value):
    with pytest.raises(ValueError):
        date.parse_date(value)


def test_parse_time():
    raw = '12:21'
    assert date.parse_time(raw) == datetime.time(12, 21, 0)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not a date",
        ":10:16",  # "extended" or relative year - NotImplementedError
    ]
)
def test_parse_time_error(value):
    with pytest.raises(ValueError):
        date.parse_time(value)


#
# test timestamp
#


def test_to_timestamp_naive():
    # Naive datetime values are assumed to be in the ``default_timezone``,
    # which is usually what you want.  This means that e.g.
    # ``to_timestamp(datetime.datetime.now())`` gives a correct timestamp.
    assert date.to_timestamp(EPOCH_NAIVE, default_timezone=UTC_TZ) == 0.0

    # our chosen LOCAL_TZ was at epoch one hour behind:
    assert date.to_timestamp(EPOCH_NAIVE, default_timezone=LOCAL_TZ) == -3600.0


@pytest.mark.parametrize("aware", (EPOCH_AWARE_UTC, EPOCH_AWARE_LOCAL))
def test_to_timestamp_aware(aware):
    # The ``default_timezone`` is ignored for tz-aware datetime objects.
    assert date.to_timestamp(aware, default_timezone=LOCAL_TZ) == 0.0


@pytest.mark.parametrize("tz", (UTC_TZ, LOCAL_TZ))
def test_from_timestamp(tz):
    # Get tz-aware datetime in UTC
    aware = date.from_timestamp(0, tz=tz)

    # Should be the same time as our tz-aware epoch ...
    assert aware == EPOCH_AWARE_UTC
    # .. and in our chosen time zone
    assert aware.tzinfo.zone == tz.zone


def test_timestamp_cycle():
    utc = date.utcnow()
    utc_ts = date.to_timestamp(utc)
    assert date.from_timestamp(utc_ts) == utc

    # in local tz from cereconf!
    aware = date.now()
    aware_ts = date.to_timestamp(aware)
    assert date.from_timestamp(aware_ts) == aware
