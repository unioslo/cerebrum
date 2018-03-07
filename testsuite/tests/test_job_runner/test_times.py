# encoding: utf-8
""" Unit tests for Cerebrum.modules.job_runner.times """

import time
import pytest

from Cerebrum.modules.job_runner.times import to_seconds, When, Time
from Cerebrum.modules.job_runner.job_actions import Action


@pytest.mark.parametrize("result,args", [
    (8, {'seconds': 8}),
    (129, {'minutes': 2, 'seconds': 9}),
    (2017920, {'days': 23, 'minutes': 512}),
    (1242000, {'weeks': 2, 'hours': 9}),
])
def test_to_seconds(args, result):
    assert to_seconds(**args) == result


#
# Old tests
#

# Calendar for reference (cal -m 06 2004)
#
# Mo Tu We Th Fr Sa Su
#             11 12 13
# 14 15 16 17 18 19

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


@pytest.mark.parametrize('when,prev,now,expect', [
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
