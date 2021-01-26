import datetime

import pytest
import pytz

from Cerebrum.utils import date
from Cerebrum.utils import date_compat


LOCAL_TZ = pytz.timezone('Europe/Oslo')


class MockDateTime(object):
    """ a mock mx.DateTime object with pydate() and pydatetime() """

    def __init__(self, ts):
        self.ts = ts

    def pydate(self):
        return self.ts.date()

    def pydatetime(self):
        return date.strip_timezone(self.ts)


@pytest.fixture
def dt_utc():
    return date.apply_timezone(
        datetime.datetime(1998, 6, 28, 22, 30, 11, 987654),
        pytz.UTC)


@pytest.fixture
def dt_local(dt_utc):
    return date.to_timezone(dt_utc, LOCAL_TZ)


@pytest.fixture
def dt_mxlike(dt_local):
    return MockDateTime(dt_local)


# get_date


def test_get_date_from_none():
    assert date_compat.get_date(None) is None


def test_get_date_from_none_err():
    with pytest.raises(ValueError):
        date_compat.get_date(None, allow_none=False)


def test_get_date_from_naive(dt_local):
    src = date.strip_timezone(dt_local)
    assert date_compat.get_date(src) == src.date()


def test_get_date_from_aware(dt_local):
    src = dt_local
    assert date_compat.get_date(src) == src.date()


def test_get_date_from_date(dt_local):
    src = dt_local.date()
    assert date_compat.get_date(src) == src


def test_get_date_from_mx(dt_mxlike):
    src = dt_mxlike
    assert date_compat.get_date(src) == src.ts.date()


# get_datetime_naive
#
# None, date, naive datetime, tz-aware datetime, mx.DateTime
# should all result in a sane naive datetime object.
#
# If tzinfo is present, we convert the datetime it to the given tz before
# stripping tzinfo (defaults to cereconf.TIMEZONE)


def test_get_datetime_naive_from_none():
    assert date_compat.get_datetime_naive(None, tz=LOCAL_TZ) is None


def test_get_datetime_naive_from_none_err():
    with pytest.raises(ValueError):
        date_compat.get_datetime_naive(None, allow_none=False, tz=LOCAL_TZ)


def test_get_datetime_naive_from_naive(dt_local):
    # naive datetime -> no change
    naive = date.strip_timezone(dt_local)
    assert date_compat.get_datetime_naive(naive, tz=LOCAL_TZ) == naive


def test_get_datetime_naive_from_aware(dt_local):
    # aware datetime -> naive datetime
    aware = dt_local
    naive = date.strip_timezone(dt_local)
    assert date_compat.get_datetime_naive(aware, tz=LOCAL_TZ) == naive


def test_get_datetime_naive_from_date(dt_local):
    src = dt_local.date()
    naive = datetime.datetime.combine(src, datetime.time(0))
    assert date_compat.get_datetime_naive(src, tz=LOCAL_TZ) == naive


def test_get_datetime_naive_from_mx(dt_mxlike):
    naive = date.strip_timezone(dt_mxlike.ts)
    assert date_compat.get_datetime_naive(dt_mxlike, tz=LOCAL_TZ) == naive


# get_datetime_tz
#
# None, date, naive datetime, tz-aware datetime, mx.DateTime
# should all result in a sane tz-aware datetime object.
#
# If tzinfo is missing from the input, we assume the *naive* date/datetime is
# already in the given tz (defaults to cereconf.TIMEZONE)


def test_get_datetime_tz_from_none():
    assert date_compat.get_datetime_tz(None, tz=LOCAL_TZ) is None


def test_get_datetime_tz_from_none_err():
    with pytest.raises(ValueError):
        date_compat.get_datetime_tz(None, allow_none=False, tz=LOCAL_TZ)


def test_get_datetime_tz_from_naive(dt_local):
    # get_datetime_tz(datetime.datetime) -> datetime.date
    naive = date.strip_timezone(dt_local)
    aware = dt_local
    assert date_compat.get_datetime_tz(naive, tz=LOCAL_TZ) == aware


def test_get_datetime_tz_from_aware(dt_local):
    aware = dt_local
    assert date_compat.get_datetime_tz(aware, tz=LOCAL_TZ) == aware


def test_get_datetime_tz_from_date(dt_local):
    src = dt_local.date()
    naive = datetime.datetime.combine(src, datetime.time(0))
    aware = date.apply_timezone(naive, tz=LOCAL_TZ)
    assert date_compat.get_datetime_tz(src, tz=LOCAL_TZ) == aware


def test_get_datetime_tz_from_mx(dt_mxlike):
    aware = dt_mxlike.ts
    assert date_compat.get_datetime_tz(dt_mxlike, tz=LOCAL_TZ) == aware
