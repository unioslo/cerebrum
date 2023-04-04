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


UTC_TZ = pytz.UTC
LOCAL_TZ = pytz.timezone("Europe/Oslo")

epoch_naive = datetime.datetime(1970, 1, 1, 0)
epoch_aware_utc = UTC_TZ.localize(epoch_naive)
epoch_aware_local = epoch_aware_utc.astimezone(LOCAL_TZ)


def test_to_timestamp_naive():
    # Naive datetime values are assumed to be in the ``default_timezone``,
    # which is usually what you want.  This means that e.g.
    # ``to_timestamp(datetime.datetime.now())`` gives a correct timestamp.
    assert date.to_timestamp(epoch_naive, default_timezone=UTC_TZ) == 0.0

    # our chosen LOCAL_TZ was at epoch one hour behind:
    assert date.to_timestamp(epoch_naive, default_timezone=LOCAL_TZ) == -3600.0


@pytest.mark.parametrize("aware", (epoch_aware_utc, epoch_aware_local))
def test_to_timestamp_aware(aware):
    # The ``default_timezone`` is ignored for tz-aware datetime objects.
    assert date.to_timestamp(aware, default_timezone=LOCAL_TZ) == 0.0


@pytest.mark.parametrize("tz", (UTC_TZ, LOCAL_TZ))
def test_from_timestamp(tz):
    # Get tz-aware datetime in UTC
    aware = date.from_timestamp(0, tz=tz)

    # Should be the same time as our tz-aware epoch ...
    assert aware == epoch_aware_utc
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
