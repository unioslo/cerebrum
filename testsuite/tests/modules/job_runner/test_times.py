# encoding: utf-8
""" Unit tests for Cerebrum.modules.job_runner.times """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import time

import pytest
import six

from Cerebrum.utils.date import to_seconds
from Cerebrum.modules.job_runner import times
from Cerebrum.modules.job_runner.times import When, Time
from Cerebrum.modules.job_runner.job_actions import Action
from Cerebrum.utils import date as date_utils


UTC_TZ = date_utils.UTC
LOCAL_TZ = date_utils.TIMEZONE


@pytest.fixture
def utc_dt():
    """
    timezone-aware datetime object @ utc.

    This fixture is the basis of all the other date/datetime fixtures.
    """
    return date_utils.apply_timezone(
        datetime.datetime(1998, 6, 28, 23, 30, 11, 987654),
        UTC_TZ)


@pytest.fixture
def local_dt(utc_dt):
    """ timezone-aware datetime object @ local time. """
    return date_utils.to_timezone(utc_dt, LOCAL_TZ)


@pytest.fixture
def timestamp(utc_dt):
    return date_utils.to_timestamp(utc_dt)


#
# Test formatters
#


def test_fmt_time_local(timestamp, local_dt):
    fmt = times.fmt_time(timestamp, local=True)
    expect = local_dt.strftime("%H:%M:%S")
    assert fmt == expect


def test_fmt_time_gm(timestamp, utc_dt):
    fmt = times.fmt_time(timestamp, local=False)
    expect = utc_dt.strftime("%H:%M:%S")
    assert fmt == expect


def test_fmt_asc_local(timestamp, local_dt):
    fmt = times.fmt_asc(timestamp, local=True)
    expect = local_dt.strftime("%c")
    assert fmt == expect


def test_fmt_asc_gm(timestamp, utc_dt):
    fmt = times.fmt_asc(timestamp, local=False)
    expect = utc_dt.strftime("%c")
    assert fmt == expect


def test_fmt_date_local(timestamp, local_dt):
    fmt = times.fmt_date(timestamp, local=True)
    expect = local_dt.date().isoformat()
    assert fmt == expect


def test_fmt_date_gm(timestamp, utc_dt):
    fmt = times.fmt_date(timestamp, local=False)
    expect = utc_dt.date().isoformat()
    assert fmt == expect


def test_fmt_datetime_local(timestamp, local_dt):
    fmt = times.format_datetime(timestamp, local=True)
    expect = local_dt.strftime("%Y-%m-%d %H:%M:%S")
    assert fmt == expect


def test_fmt_datetime_gm(timestamp, utc_dt):
    fmt = times.format_datetime(timestamp, local=False)
    expect = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
    assert fmt == expect


#
# Time tests
#


def test_time_str():
    time_obj = times.Time(min=[30], hour=[3, 15], wday=[1], max_freq=60)
    time_str = six.text_type(time_obj)
    # Non-sensical format, doesn't separate the different times well...
    assert time_str == "wday=1,h=3:15,m=30"


#
# When tests
#


def test_when_time_str():
    time_obj_1 = times.Time(hour=[12, 15])
    time_obj_2 = times.Time(hour=[3], wday=[1], max_freq=60)
    when_obj = When(time=[time_obj_1, time_obj_2])
    when_str = six.text_type(when_obj)
    assert when_str == "time=(h=12:15,wday=1,h=3)"


def test_when_freq_str():
    when_obj = When(freq=60 * 5)
    when_str = six.text_type(when_obj)
    assert when_str == "freq=00:05:00"


#
# Old, migrated tests
#
# Calendar for reference (cal -m 06 2004):
#
#   Mo Tu We Th Fr Sa Su
#               11 12 13
#   14 15 16 17 18 19
#


@pytest.mark.parametrize('when,prev,now,expect', [
    # Run at a given day of the week
    (
        # Run: Sat 05:30 AM
        When(time=[Time(wday=[5], hour=[5], min=[30])]),
        '2004-06-11 17:00',  # Last ran: Fri 17:00
        '2004-06-14 20:00',  # Now: Mon 20:00
        '2004-06-12 05:30',  # Should have ran 2d ago!
    ),

    # Run at a given day of the week, but skip if already ran close enough to
    # that time.
    (
        When(time=[Time(wday=[5], hour=[5], min=[30],
                        max_freq=to_seconds(days=1))]),
        '2004-06-10 17:00',  # Last ran: Thu 17:00
        '2004-06-14 20:00',  # Now: Mon 20:00
        '2004-06-12 05:30',  # Should have ran at last scheduled time
    ),
    (
        When(time=[Time(wday=[5], hour=[5], min=[30],
                        max_freq=to_seconds(days=1))]),
        '2004-06-11 17:00',  # Last ran: Fri 17:00
        '2004-06-14 20:00',  # Now: Mon 20:00
        '2004-06-19 05:30',  # Already ran close to last scheduled time
    ),
])
def test_when_next_weekday(when, prev, now, expect):
    prev, now, expect = (time.mktime(time.strptime(t, '%Y-%m-%d %H:%M'))
                         for t in (prev, now, expect))

    delta = when.next_delta(prev, now)
    assert now + delta == expect


@pytest.fixture
def when_daily():
    """ When @ every day 04:05 AM. """
    return When(time=[Time(hour=[4], min=[5])])


@pytest.mark.parametrize('prev,now,expect', [
    # prev run, curr time, expected reschedule
    ('03:00', '04:00', '04:05',),
    ('03:00', '04:10', '04:05',),
])
def test_when_next_daily(when_daily, prev, now, expect):
    prev, now, expect = (time.mktime(time.strptime(t, '%H:%M'))
                         for t in (prev, now, expect))

    delta = when_daily.next_delta(prev, now)
    assert now + delta == expect


@pytest.fixture
def notwhen_action():
    """ An action that

    - runs every 5 minutes
    - does not re-schedule if ran in the last 5 minutes
    - does not re-shecule if current time is 04:00 - 04:59 AM
    """
    return Action(max_freq=to_seconds(minutes=5),
                  when=When(freq=to_seconds(minutes=5)),
                  notwhen=When(time=Time(hour=[4])))


@pytest.mark.parametrize('prev,now,expect', [
    # prev run, curr time, expected reschedule
    ('03:58', '03:58', '04:03'),
    ('03:58', '04:06', '05:00'),
    ('03:58', '04:58', '05:00'),
    ('03:58', '05:06', '04:03'),
])
def test_action_notwhen(notwhen_action, prev, now, expect):
    prev, now, expect = (time.mktime(time.strptime(t, '%H:%M'))
                         for t in (prev, now, expect))

    delta = notwhen_action.next_delta(prev, now)
    assert now + delta == expect
