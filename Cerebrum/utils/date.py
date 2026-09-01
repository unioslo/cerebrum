# coding: utf-8
#
# Copyright 2017-2026 University of Oslo, Norway
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
# Copyright 2002-2015 University of Oslo, Norway
"""
Date, time and timezone utilities.

Provides ISO-8601 parsing, timezone conversions, and timestamp handling.

While naive datetimes are sometimes used within Cerebrum, all I/O with users
and systems *should* use UTC or timezone-aware formats.


cereconf
=========
``TIMEZONE``
    The default local timezone.  Used as the default ``tz`` argument for most
    functions, and for interpreting naive datetime objects.


Legacy datetime
================
Cerebrum historically used ``mx.DateTime`` from *egenix-mx-base*.  See
:mod:`Cerebrum.utils.date_compat` for tools to convert between mx-like objects
and :mod:`datetime`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import calendar
import datetime

import aniso8601
import pytz

import cereconf

# Read-only tzinfo copy of ``cereconf.TIMEZONE``
TIMEZONE = pytz.timezone(cereconf.TIMEZONE)
""" ``cereconf.TIMEZONE`` as a :class:`datetime.tzinfo` object. """

# This is just for convenience - other modules should generally not need to
# deal with pytz directly.
UTC = pytz.UTC
""" UTC as a :class:`datetime.tzinfo` object. """


SECONDS_PER_MIN = 60
SECONDS_PER_HOUR = SECONDS_PER_MIN * 60
SECONDS_PER_DAY = SECONDS_PER_HOUR * 24
SECONDS_PER_WEEK = SECONDS_PER_DAY * 7


def to_seconds(weeks=0, days=0, hours=0, minutes=0, seconds=0):
    """ Convert weeks, days, hours, etc. to total seconds. """
    return sum((
        weeks * SECONDS_PER_WEEK,
        days * SECONDS_PER_DAY,
        hours * SECONDS_PER_HOUR,
        minutes * SECONDS_PER_MIN,
        seconds,
    ))


def utcnow():
    """
    Get the current UTC time as a tz-aware datetime.

    This is the same as :func:`datetime.datetime.utcnow`, but with
    :class:`datetime.tzinfo`.

    :rtype: datetime.datetime
    """
    return apply_timezone(datetime.datetime.utcnow(), tz=UTC)


def now(tz=TIMEZONE):
    """
    Get the current time as a tz-aware datetime.

    This is similar to :func:`datetime.datetime.now`, but always includes
    :class:`datetime.tzinfo`.

    :param tz: Target timezone (default: :data:`.TIMEZONE`)
    :rtype: datetime.datetime
    """
    if not isinstance(tz, datetime.tzinfo):
        tz = pytz.timezone(tz)
    return datetime.datetime.now(tz=tz)


def to_timezone(aware, tz=TIMEZONE):
    """
    Convert a timezone-aware datetime to another timezone.

    :param datetime.datetime aware: A timezone-aware datetime object.
    :param tz: Target timezone (default: :data:`.TIMEZONE`).

    :return datetime.datetime: A timezone-aware datetime.
    """
    # Accept strings (e.g. 'UTC' or 'Europe/Oslo'):
    if not isinstance(tz, datetime.tzinfo):
        tz = pytz.timezone(tz)

    if not aware.tzinfo:
        raise ValueError("datetime does not have tzinfo")

    return aware.astimezone(tz)


def apply_timezone(naive, tz=TIMEZONE):
    """
    Add tzinfo to a naive datetime (no time conversion).

    :param datetime.datetime naive: A naive datetime object
    :param tz: Timezone to apply (default: :data:`.TIMEZONE`).
    :returns datetime.datetime: A timezone-aware copy of *naive*
    """
    if naive.tzinfo:
        raise ValueError("datetime already has tzinfo")
    if not isinstance(tz, datetime.tzinfo):
        tz = pytz.timezone(tz)

    # TODO: this isn't entirely right -- localize() is a pytz.tzinfo method
    return tz.localize(naive)


def strip_timezone(aware):
    """
    Remove tzinfo from a tz-aware datetime (no time conversion).

    :param datetime.datetime aware: A timezone-aware datetime object
    :returns datetime.datetime: A naive copy of *aware*
    """
    if not aware.tzinfo:
        raise ValueError("datetime does not have tzinfo")
    return aware.replace(tzinfo=None)


#
# Strict ISO-8601 parsers
#


def _parse_datetime(rawstr):
    """ helper for *parse_datetime* and *parse_datetime_tz*. """
    dtstr = str(rawstr)
    # Allow use of space as separator
    try:
        if 'T' not in dtstr:
            date = aniso8601.parse_datetime(dtstr, delimiter=' ')
        else:
            date = aniso8601.parse_datetime(dtstr)
    except NotImplementedError as e:
        raise ValueError("unsupported iso8601 format (%s)" % (e,))
    except ValueError as e:
        # The aniso8601 errors are not always great
        raise ValueError("invalid iso8601 datetime (%s)" % (e,))
    return date


def parse_datetime_tz(rawstr):
    """
    Parse an ISO-8601 datetime string (timezone required).

    :param str rawstr: ISO-8601 datetime with timezone (delimiter: 'T' or ' ')
    :returns datetime.datetime: A timezone-aware datetime object.
    """
    date = _parse_datetime(rawstr)
    if not date.tzinfo:
        raise ValueError("invalid iso8601 datetime (missing timezone)")
    return date


def parse_datetime(rawstr, default_timezone=TIMEZONE):
    """
    Parse an ISO-8601 datetime string (timezone optional).

    :param str rawstr: ISO-8601 datetime (delimiter: 'T' or ' ')
    :param datetime.tzinfo default_timezone:
        Timezone to assume for naive datetime strings (default:
        :data:`.TIMEZONE`).
    :returns datetime.datetime: A timezone-aware datetime object.
    """
    date = _parse_datetime(rawstr)
    if not date.tzinfo:
        # No timezone given, assume default_timezone
        date = apply_timezone(date, tz=default_timezone)
    return date


def parse_date(dtstr):
    """
    Parse an ISO-8601 date string.

    :param str dtstr: ISO-8601 formatted date string
    :rtype: datetime.date
    """
    try:
        return aniso8601.parse_date(str(dtstr))
    except NotImplementedError as e:
        raise ValueError("unsupported iso8601 format (%s)" % (e,))
    except ValueError as e:
        # The aniso8601 errors are not always great
        raise ValueError("invalid iso8601 date (%s)" % (e,))


def parse_time(dtstr):
    """
    Parse an ISO-8601 time string.

    :param str dtstr: ISO-8601 formatted time string
    :rtype: datetime.time
    """
    try:
        return aniso8601.parse_time(str(dtstr))
    except ValueError as e:
        # The aniso8601 errors are not always great
        raise ValueError("invalid iso8601 time (%s)" % (e,))


#
# tz-aware timestamp utils
#

def from_timestamp(timestamp, tz=TIMEZONE):
    """
    Convert a Unix timestamp to a tz-aware datetime.

    :param float timestamp: Unix timestamp
    :param datetime.tzinfo tz: Target timezone (default: :data:`.TIMEZONE`).
    :returns datetime.datetime: A timezone-aware datetime object.
    """
    utc_dt = datetime.datetime.fromtimestamp(float(timestamp), UTC)
    return to_timezone(utc_dt, tz=tz)


def to_timestamp(dt, default_timezone=TIMEZONE):
    """
    Convert a datetime to a Unix timestamp.

    :param datetime.datetime dt: datetime object (naive or tz-aware)
    :param datetime.tzinfo default_timezone:
        Timezone to assume for naive datetimes (default: :data:`.TIMEZONE`).
    :rtype: float
    """
    if not dt.tzinfo:
        # Naive datetime, assume in default_timezone
        dt = apply_timezone(dt, tz=default_timezone)

    # Workaround for missing (tz-aware) timestamp functions in PY2
    # (most timestamp related functions in the standard library are bound to
    # local time in some way)
    #
    # 1. Convert datetime to utc timetuple:
    utc_dt = to_timezone(dt, UTC)
    gm_tuple = utc_dt.timetuple()
    # 2. Use `calendar.timegm` to convert utc timetuple to utc timestamp
    ss = float(calendar.timegm(gm_tuple))
    # 3. Extract microseconds, which are missing from the timetuple struct:
    us = float(utc_dt.microsecond / 1000000)
    return ss + us


# python -m Cerebrum.utils.date


def main(inargs=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="parse dates using utils in this module",
    )
    parser.add_argument(
        '-t', '--timezone',
        default=TIMEZONE,
        type=pytz.timezone,
        help="use custom timezone (default: cereconf.TIMEZONE=%(default)s)",
    )
    parser.add_argument(
        'datetime',
        nargs='*',
        default=[],
        help="timestamp or iso8601 date to parse",
    )
    args = parser.parse_args(inargs)

    print("timezone:    {0!s}".format(args.timezone))
    print("now:         {0!s}".format(now(tz=args.timezone)))
    print("utcnow:      {0!s}".format(utcnow()))
    print("timestamp:   {0!s}".format(to_timestamp(utcnow())))

    def print_datetime(dt, prefix="    "):
        print(prefix, "iso:  {}".format(dt.isoformat()), sep="")
        print(prefix, "ts:   {}".format(to_timestamp(dt)), sep="")
        print(prefix, "repr: {}".format(repr(dt)), sep="")

    for num, d in enumerate(args.datetime, 1):
        try:
            d = float(d)
            parse = from_timestamp
        except ValueError:
            parse = parse_datetime

        print("\ndate #{0:d}: {1!r}".format(num, d))

        name = parse.__name__
        foo = parse(d)
        print("  {}: {}".format(name, repr(d)))
        print_datetime(foo)

        bar = to_timezone(foo, tz=args.timezone)
        print("  to_timezone: {}".format(args.timezone))
        print_datetime(bar)


if __name__ == '__main__':
    raise SystemExit(main())
