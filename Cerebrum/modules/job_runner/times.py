# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
""" Job Runner time utils. """
import time

import six

from Cerebrum.utils.date import to_seconds


def fmt_time(timestamp, local=True):
    to_time = time.localtime if local else time.gmtime
    return six.text_type(time.strftime('%H:%M:%S', to_time(timestamp)))


def fmt_asc(timestamp, local=True):
    to_time = time.localtime if local else time.gmtime
    return six.text_type(time.asctime(to_time(timestamp)))


def fmt_date(timestamp, local=True):
    to_time = time.localtime if local else time.gmtime
    return six.text_type(time.strftime('%Y-%m-%d', to_time(timestamp)))


def format_datetime(timestamp, local=True):
    to_time = time.localtime if local else time.gmtime
    return six.text_type(time.strftime('%Y-%m-%d %H:%M:%S',
                                       to_time(timestamp)))


@six.python_2_unicode_compatible
class When(object):

    def __init__(self, freq=None, time=None):
        """ Run job at specific times.

        This object can be used to indicate that a job should be ran either
        with a specified frequency, or at a specified time.
        """
        assert freq is not None or time is not None
        assert not (freq is not None and time is not None)
        self.freq = freq
        self.time = time

        # TODO: support not-run interval to prevent running jobs when
        # FS is down etc.

    def next_delta(self, last_time, current_time):
        """Returns # seconds til the next time this job should run
        """
        if self.freq is not None:
            return last_time + self.freq - current_time
        else:
            times = []
            for t in self.time:
                d = t.next_time(last_time)
                times.append(d + last_time - current_time)
            return min(times)

    def __str__(self):
        if self.time:
            return six.text_type("time=(%s)" % ",".join([six.text_type(t) for t
                                                         in self.time]))
        return six.text_type("freq=%s" % fmt_time(self.freq, local=False))


@six.python_2_unicode_compatible
class Time(object):

    def __init__(self, min=None, hour=None, wday=None, max_freq=None):
        """Emulate time part of crontab(5), None=*

        When using Action.max_freq of X hours and a Time object for a
        specific time each day, the Action.max_freq setting may delay
        a job so that a job that should be ran at night is ran during
        daytime (provided that something has made the job ran at an
        unusual hour earlier).

        To avoid this, set Time.max_freq.  This prevents next_time
        from checking wheter the job should have started until
        last_time+max_freq has passed.  I.e. if max_freq=1 hour the
        job is set to run at 12:30, but was ran at 12:00, the job will
        not run until the next matching time after 13:00.  If the
        Action.max_freq had been used, the job would have ran at
        13:00.
        """
        # TBD: what mechanisms should be provided to prevent new jobs
        # from being ran immeadeately when the time is not currently
        # within the correct range?
        self.min = min
        if min is not None:
            self.min.sort()
        self.hour = hour
        if hour is not None:
            self.hour.sort()
        self.wday = wday
        if wday is not None:
            self.wday.sort()
        self.max_freq = max_freq or 0

    def _next_list_value(self, val, list, size):
        for n in list:
            if n > val:
                return n, 0
        return min(list), 1

    def delta_to_leave(self, t):
        """Return a very rough estimate of the number of seconds until
        we leave the time-period covered by this Time object"""

        hour, min, sec, wday = (time.localtime(t))[3:7]
        if self.wday is not None and wday in self.wday:
            return to_seconds(days=1) - to_seconds(hours=hour,
                                                   minutes=min,
                                                   seconds=sec)
        if self.hour is not None and hour in self.hour:
            return to_seconds(minutes=60 - min)
        if self.min is not None and min in self.min:
            return to_seconds(seconds=60 - sec)

    def next_time(self, prev_time):
        """Return the number of seconds until next time after num"""
        hour, min, sec, wday = (time.localtime(prev_time + self.max_freq))[3:7]

        add_week = 0
        for i in range(10):
            if self.wday is not None and wday not in self.wday:
                # finn midnatt neste ukedag
                hour = min = 0
                t, wrap = self._next_list_value(wday, self.wday, 6)
                wday = t
                if wrap:
                    add_week = 1

            if self.hour is not None and hour not in self.hour:
                # finn neste time, evt neste ukedag
                min = 0
                t, wrap = self._next_list_value(hour, self.hour, 23)
                hour = t
                if wrap:
                    wday += 1
                    continue

            if self.min is not None and min not in self.min:
                # finn neste minutt, evt neste ukedag
                t, wrap = self._next_list_value(min, self.min, 59)
                min = t
                if wrap:
                    hour += 1
                    continue

            # Now calculate the diff
            old_hour, old_min, old_sec, old_wday = (
                time.localtime(prev_time))[3:7]
            week_start_delta = to_seconds(days=old_wday,
                                          hours=old_hour,
                                          minutes=old_min,
                                          seconds=old_sec)

            ret = to_seconds(weeks=add_week,
                             days=wday,
                             hours=hour,
                             minutes=min) - week_start_delta

            # Assert that the time we find is after the previous time
            if ret <= 0:
                if self.min is not None:
                    min += 1
                elif self.hour is not None:
                    hour += 1
                elif self.wday is not None:
                    wday += 1
                continue
            return ret
        raise ValueError("Programming error for %i" % prev_time)

    def __str__(self):
        ret = []
        if self.wday:
            ret.append("wday=" + ":".join(["%i" % w for w in self.wday]))
        if self.hour:
            ret.append("h=" + ":".join(["%i" % w for w in self.hour]))
        if self.min:
            ret.append("m=" + ":".join(["%i" % w for w in self.min]))
        # ret should only contain ascii strings
        return six.text_type(",".join(ret))
