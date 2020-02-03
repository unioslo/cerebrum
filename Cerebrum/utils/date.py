# coding: utf-8
#
# Copyright 2017-2019 University of Oslo, Norway
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
This module contains utilities for dates, times and timezones in Cerebrum.

Utilities include converting between datetime and mx.DateTime, parsing iso8601
dates, as well as applying timezone, and converting between timezones.


Datetime in Cerebrum
--------------------
We use py:mod:`mx.DateTime` in Cerebrum mainly for database communication, and
for legacy resons.
The py:class:`mx.DateTime.DateTypeType` objects doesn't integrate well with
ISO-8601 parsers (including its own py:mod:`mx.DateTime.Parser`).

The `Cerebrum.database.Database` object is set up to accept
mx.DateTime objects, and convert back to mx.DateTime objects when using
execute/query. In addition, our database schema or queries does *not* use tz
aware timestamp fields.

The bottom line is; For the time being, all db-communication happens with
naive mx.DateTime objects, and we cannot use/trust the tz info in mx.DateTime
objects when communicating with the database.


Rationale
---------
Naive datetimes are used within Cerebrum, but all I/O with users and systems
*should* use UTC or timezone-aware formats.

To achieve this, we need to be able to serialize and deserialize datetimes
*with* timezone info, and convert between the local timezone and UTC.


cereconf
--------

TIMEZONE
    Default timezone.

    Most methods acting on datetime objects take an optional ``tz`` argument,
    to specify which timezone to use. This cereconf-value sets the default
    timezone for these functions.

"""
import datetime

import aniso8601
import mx.DateTime
import pytz

import cereconf

TIMEZONE = pytz.timezone(cereconf.TIMEZONE)

# TODO: Use tzlocal for default TIMEZONE?
# try:
#     import cereconf
#     TIMEZONE = pytz.timezone(cereconf.TIMEZONE)
# except ImportError:
#     from tzlocal import get_localzone
#     TIMEZONE = get_localzone()


SECONDS_PER_MIN = 60
SECONDS_PER_HOUR = SECONDS_PER_MIN * 60
SECONDS_PER_DAY = SECONDS_PER_HOUR * 24
SECONDS_PER_WEEK = SECONDS_PER_DAY * 7


def to_seconds(weeks=0, days=0, hours=0, minutes=0, seconds=0):
    """ Sum number of weeks, days, hours, etc.. to seconds. """
    return sum((
        weeks * SECONDS_PER_WEEK,
        days * SECONDS_PER_DAY,
        hours * SECONDS_PER_HOUR,
        minutes * SECONDS_PER_MIN,
        seconds,
    ))


def utcnow():
    """ `datetime.utcnow()` with tzinfo=UTC.

    :return datetime:
        Returns a timezone-aware datetime object, with the current time in UTC.
    """
    return apply_timezone(datetime.datetime.utcnow(), tz=pytz.UTC)


def now(tz=TIMEZONE):
    """ timezone-aware `now()`.

    :param tzinfo tz:
        An optional timezone to get time for.

    :return datetime:
        Returns a timezone-aware datetime object with the current time.
    """
    if not isinstance(tz, datetime.tzinfo):
        tz = pytz.timezone(tz)
    return datetime.datetime.now(tz=TIMEZONE)


def to_timezone(aware, tz=TIMEZONE):
    """
    Convert datetime to another timezone.

    :param datetime aware:
        A timezone-aware datetime object.

    :param tzinfo tz:
        The target timezone

    :return datetime:
        A timezone-aware datetime
    """
    # Accept strings (e.g. 'UTC' or 'Europe/Oslo'):
    if not isinstance(tz, datetime.tzinfo):
        tz = pytz.timezone(tz)

    if not aware.tzinfo:
        raise ValueError("datetime does not have tzinfo")

    return aware.astimezone(tz)


def apply_timezone(naive, tz=TIMEZONE):
    """ Attach tzinfo to a naive datetime object. """
    if naive.tzinfo:
        raise ValueError("datetime already has tzinfo")
    if not isinstance(tz, datetime.tzinfo):
        tz = pytz.timezone(tz)

    # TODO: this isn't entirely right -- localize() is a pytz.tzinfo method
    return tz.localize(naive)


def strip_timezone(aware):
    """ Remove tzinfo, turning a datetime naive. """
    if not aware.tzinfo:
        raise ValueError("datetime does not have tzinfo")
    return aware.replace(tzinfo=None)


def datetime2mx(src, tz=TIMEZONE):
    """ Convert (localized) datetime to naive mx.DateTime. """
    if not src.tzinfo:
        src = apply_timezone(src, tz=tz)
    src = to_timezone(src, tz=tz)
    return mx.DateTime.DateTimeFrom(strip_timezone(src))


def mx2datetime(src, tz=TIMEZONE):
    """ Convert naive mx.DateTime into a timezone-aware datetime. """
    dt = src.pydatetime()
    return apply_timezone(dt, tz=tz)


def parse_datetime_tz(dtstr):
    """
    Parse an ISO8601 datetime string, and require timezone.

    The datetime may be delimited by ' ' or 'T'.

    :param dtstr: An ISO8601 formatted datetime string with timezone.

    :rtype: datetime.datetime
    :return: A timezone-aware datetime objet.
    """
    # Allow use of space as separator
    try:
        if 'T' not in dtstr:
            date = aniso8601.parse_datetime(dtstr, delimiter=' ')
        else:
            date = aniso8601.parse_datetime(dtstr)
    except ValueError as e:
        # The aniso8601 errors are not always great
        raise ValueError("invalid iso8601 datetime (%s)" % (e,))

    if not date.tzinfo:
        raise ValueError("invalid iso8601 datetime (missing timezone)")
    return date


def parse_datetime(dtstr, default_timezone=TIMEZONE):
    """
    Parse an ISO8601 datetime string.

    The datetime may be delimited by ' ' or 'T'.
    If no timezone is included, the ``default_timezone`` will be applied

    :param dtstr: An ISO8601 formatted datetime string
    :param default_timezone: A default timezone to apply if missing.

    :rtype: datetime.datetime
    :return: A timezone-aware datetime objet.
    """
    # Allow use of space as separator
    try:
        if 'T' not in dtstr:
            date = aniso8601.parse_datetime(dtstr, delimiter=' ')
        else:
            date = aniso8601.parse_datetime(dtstr)
    except ValueError as e:
        # The aniso8601 errors are not always great
        raise ValueError("invalid iso8601 date (%s)" % (e,))

    if not date.tzinfo:
        # No timezone given, assume default_timezone
        date = apply_timezone(date, tz=default_timezone)
    return date


def parse_date(dtstr):
    """
    Parse an ISO8601 date string.

    :param dtstr: An ISO8601 formatted date string

    :rtype: datetime.date
    :return: A date object.
    """
    return aniso8601.parse_date(dtstr)


def parse(dtstr):
    """ Utility method, get a naive mx.DateTime. """
    return datetime2mx(parse_datetime(dtstr))


# python -m Cerebrum.utils.date

def main(inargs=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="parse dates using utils in this module")
    parser.add_argument(
        '-t', '--timezone',
        default=TIMEZONE,
        type=pytz.timezone,
        help="use custom timezone (default: cereconf.TIMEZONE=%(default)s)")
    parser.add_argument(
        'datetime',
        nargs='*',
        default=[],
        help="iso8601 date to parse")
    args = parser.parse_args(inargs)

    print("timezone:    {0!s}".format(args.timezone))
    print("now:         {0!s}".format(now(tz=args.timezone)))
    print("utcnow:      {0!s}".format(utcnow()))

    for num, d in enumerate(args.datetime, 1):
        print("\ndate #{0:d}: {1!r}".format(num, d))

        p = parse_datetime(d)
        print("  parse_datetime: {0!s}".format(p))
        print("                  {0!r}".format(p))

        l = to_timezone(p, tz=args.timezone)
        print("  to_timezone:    {0!s}".format(l))
        print("                  {0!r}".format(l))

        m = datetime2mx(p, tz=args.timezone)
        print("  datetime2mx:    {0!s}".format(m))
        print("                  {0!r}".format(m))

        n = mx2datetime(m, tz=args.timezone)
        print("  mx2datetime:    {0!s}".format(n))
        print("                  {0!r}".format(n))


if __name__ == '__main__':
    raise SystemExit(main())
