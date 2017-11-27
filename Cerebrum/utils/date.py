# coding: utf-8
#
# Copyright 2017 University of Oslo, Norway
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
""" This module contains utilities for dates, times and timezones in Cerebrum.

Utilities include converting between datetime and mx.DateTime, parsing iso8601
dates, as well as setting timezone, and converting between timezones.  This
should be enough to:

- parse iso8601 strings, with or without timezone data, into mx.DateTime
  objects in localtime.
- fetch mx.DateTime objects from the database, and output as iso8601 strings
  in any timezone.


Datetimes in Cererbum
---------------------
We use mx.DateTime in Cerebrum mainly for database communication, and for
legacy resons.  The mx.DateTime object *does* have basic timezone support, but
it does not integrate well with iso8601 parsers (including its own
mx.DateTime.Parser), or datetime objects.

The `Cerebrum.Database` object is set up to accept mx.DateTime objects, and
convert back to mx.DateTime objects when using execute/query.  In addition, our
database schema or queries does *not* use tz aware timestamp fields.

The bottom line is; For the time being, all db-communication happens with
naive mx.DateTime objects, and we cannot use/trust the tz info in mx.DateTime
object when communicating with the database.


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
import aniso8601
import datetime
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


def localize(aware, tz=TIMEZONE):
    """ Convert datetime to another timezone.

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
    src = localize(src, tz=tz)
    return mx.DateTime.DateTimeFrom(strip_timezone(src))


def mx2datetime(src, tz=TIMEZONE):
    """ Convert naive mx.DateTime into a timezone-aware datetime. """
    dt = src.pydatetime()
    return apply_timezone(dt, tz=tz)


def parse_date(dtstr):
    # Allow use of space as separator
    if 'T' not in dtstr:
        date = aniso8601.parse_datetime(dtstr, delimiter=' ')
    else:
        date = aniso8601.parse_datetime(dtstr)

    if not date.tzinfo:
        # No timezone, assume UTC?
        date = apply_timezone(date, tz=pytz.UTC)
    return date


def parse(dtstr):
    """ Utility method, get a naive mx.DateTime. """
    return datetime2mx(parse_date(dtstr))


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
        'date',
        nargs='*',
        default=[],
        help="iso8601 date to parse")
    args = parser.parse_args(inargs)

    print("timezone:    {0!s}".format(args.timezone))
    print("now:         {0!s}".format(now(tz=args.timezone)))
    print("utcnow:      {0!s}".format(utcnow()))

    for num, d in enumerate(args.date, 1):
        print("\ndate #{0:d}: {1!r}".format(num, d))

        p = parse_date(d)
        print("  parse_date:   {0!s}".format(p))
        print("                {0!r}".format(p))

        l = localize(p, tz=args.timezone)
        print("  localize:     {0!s}".format(l))
        print("                {0!r}".format(l))

        m = datetime2mx(p, tz=args.timezone)
        print("  datetime2mx:  {0!s}".format(m))
        print("                {0!r}".format(m))

        n = mx2datetime(m, tz=args.timezone)
        print("  mx2datetime:  {0!s}".format(n))
        print("                {0!r}".format(n))


if __name__ == '__main__':
    raise SystemExit(main())
