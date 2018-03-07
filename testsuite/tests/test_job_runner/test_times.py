#!/usr/bin/env python
# encoding: utf-8
""" Unit tests for Cerebrum.config.parsers. """

import time
import pytest

from Cerebrum.modules.job_runner.times import to_seconds, When, Time
from Cerebrum.modules.job_runner.job_actions import Action
# , System


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
#       June 2004
# Mo Tu We Th Fr Sa Su
#             11 12 13
# 14 15 16 17 18 19
#
@pytest.mark.parametrize('when,prev,now,expect', [
    (
        # Run: Saturdays, 5:30 AM
        When(time=[Time(wday=[5], hour=[5], min=[30])]),
        '2004-06-11 17:00',  # Last ran: Fri 17:00
        '2004-06-14 20:00',  # Now: Mon 20:00
        '2004-06-12 05:30',  # Should have ran 2d ago!
    ),

    # Test max freq
    # Same as above, but now do not run if ran in last 24 hrs
    (
        When(time=[Time(wday=[5], hour=[5], min=[30],
                        max_freq=to_seconds(days=1))]),
        '2004-06-10 17:00',  # Last ran: Thu 17:00
        '2004-06-14 20:00',  # Now: Mon 20:00
        '2004-06-12 05:30',  # Should have ran at last scheduled time
     ),
    (
        # Run: Saturdays, 5:30 AM, unless ran in last 24 hrs
        When(time=[Time(wday=[5], hour=[5], min=[30],
                        max_freq=to_seconds(days=1))]),
        '2004-06-11 17:00',  # Last ran: Fri 17:00
        '2004-06-14 20:00',  # Now: Mon 20:00
        '2004-06-19 05:30',  # Already ran close to last scheduled time
     ),

    (
        # Every day, 4:05 AM
        When(time=[Time(hour=[4], min=[5])]),
        '2004-06-01 03:00',
        '2004-06-01 04:00',
        '2004-06-01 04:05',
    ),
    (
        When(time=[Time(hour=[4], min=[5])]),
        '2004-06-01 03:00',
        '2004-06-01 04:10',
        '2004-06-01 04:05',
    ),
])
def test_when_next_delta(when, prev, now, expect):
    prev, now, expect = (time.mktime(time.strptime(t, '%Y-%m-%d %H:%M'))
                         for t in (prev, now, expect))

    delta = when.next_delta(prev, now)
    assert now + delta == expect


@pytest.mark.parametrize('action,prev,now,expect', [
    # - Trigger every 5 mins
    # - Wait at least 5 mins from last run
    # - Do not consider running at 04:00-04:59 AM
    (
        Action(max_freq=to_seconds(minutes=5),
               when=When(freq=to_seconds(minutes=5)),
               notwhen=When(time=Time(hour=[4]))),
        '2004-06-01 03:58',  # Last run
        '2004-06-01 03:58',  # Now
        '2004-06-01 04:03',  # Should run at
    ),
    (
        Action(max_freq=to_seconds(minutes=5),
               when=When(freq=to_seconds(minutes=5)),
               notwhen=When(time=Time(hour=[4]))),
        '2004-06-01 03:58',  # Last run
        '2004-06-01 04:06',  # Now
        '2004-06-01 05:00',  # Should run at
    ),
    (
        Action(max_freq=to_seconds(minutes=5),
               when=When(freq=to_seconds(minutes=5)),
               notwhen=When(time=Time(hour=[4]))),
        '2004-06-01 03:58',  # Last run
        '2004-06-01 04:58',  # Now
        '2004-06-01 05:00',  # Should run at
    ),
    (
        Action(max_freq=to_seconds(minutes=5),
               when=When(freq=to_seconds(minutes=5)),
               notwhen=When(time=Time(hour=[4]))),
        '2004-06-01 03:58',  # Last run
        '2004-06-01 05:06',  # Now
        '2004-06-01 04:03',  # Should have run at
    ),
])
def test_action_notwhen(action, prev, now, expect):
    prev, now, expect = (time.mktime(time.strptime(t, '%Y-%m-%d %H:%M'))
                         for t in (prev, now, expect))

    delta = action.next_delta(prev, now)
    assert now + delta == expect
