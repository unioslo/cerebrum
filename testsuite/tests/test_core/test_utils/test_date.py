import datetime

import pytest
import pytz

from Cerebrum.utils import date


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


def test_parse_date():
    raw = '2000-10-16'
    assert date.parse_date(raw) == datetime.date(2000, 10, 16)


def test_utcnow_has_tzinfo():
    now = date.utcnow()
    assert now.tzinfo is not None


@pytest.fixture
def datetime_utc_naive():
    return datetime.datetime.utcnow()


@pytest.fixture
def datetime_utc_aware():
    return datetime.datetime.now(tz=pytz.UTC)


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
