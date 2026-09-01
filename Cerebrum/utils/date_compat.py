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
Date and time compatibility functions.

Functions for converting between :class:`datetime.datetime`,
:class:`datetime.date`, and the deprecated ``mx.DateTime.DateTimeType`` from
*egenix-mx-base*.


Common parameters
==================
``allow_none`` / ``allow_empty``
    Most functions accept this parameter (default: ``True``).  If ``True``,
    empty input returns ``None``.  If ``False``, empty input raises
    :class:`ValueError`.

``tz``
    Timezone for conversions (default: :data:`Cerebrum.utils.date.TIMEZONE`).
    Used when converting between naive and tz-aware datetimes.

    Note that mx-like objects are always treated as naive.


Date to datetime
=================
When converting a date to datetime, the time is set to midnight at the start of
the provided date.  For tz-aware results, this means midnight *in the given
timezone*.  Converting to another timezone (e.g. UTC) may change the date.
"""

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

from . import date


# TODO: Refactor/remove is_mx_* when egenix-mx-base is gone
_MX_ATTRS = ('pydate', 'pydatetime', 'pytime', 'hour', 'minute', 'second')


def is_mx_datetime(obj):
    """ Check if object is an mx-like (egenix-mx-base) datetime object. """
    return (obj and isinstance(obj, object)
            and all(hasattr(obj, attr) for attr in _MX_ATTRS))


def is_mx_date(obj):
    """ Check if object is an mx-like datetime with date-like precision. """
    if is_mx_datetime(obj):
        return obj.hour == obj.minute == 0 and obj.second == 0.0
    else:
        return False


def is_mx_delta(obj):
    """ Check if object is an mx-like timedelta object. """
    return (obj and isinstance(obj, object)
            and hasattr(obj, 'pytimedelta'))


def get_date(dtobj, allow_none=True):
    """
    Get a date from a datetime-like object.

    :type dtobj: datetime.datetime | datetime.date | mx.DateTime.DateTimeType
    :param dtobj: The datetime-like object to convert
    :param bool allow_none: Allow empty *dtobj* value.

    :rtype: datetime.date
    :returns: A naive datetime object.
    """
    if not dtobj and allow_none:
        return None
    if isinstance(dtobj, datetime.datetime):
        return dtobj.date()
    if isinstance(dtobj, datetime.date):
        return dtobj
    if is_mx_datetime(dtobj):
        return dtobj.pydate()
    raise ValueError('Non-date value: %r' % (dtobj,))


def get_datetime_naive(dtobj, allow_none=True, tz=date.TIMEZONE):
    """
    Get a naive datetime from a datetime-like object.

    :type dtobj: datetime.datetime | datetime.date | mx.DateTime.DateTimeType
    :param dtobj: The datetime-like object to convert
    :param bool allow_none: Allow empty *dtobj* value.
    :type tz: datetime.tzinfo
    :param tz: Tz-aware inputs are converted to *tz* before stripping tzinfo.

    :rtype: datetime.datetime
    :returns: A naive datetime object.
    """
    if not dtobj and allow_none:
        return None
    if isinstance(dtobj, datetime.datetime):
        if dtobj.tzinfo is None:
            return dtobj
        else:
            return date.strip_timezone(date.to_timezone(dtobj, tz))
    if isinstance(dtobj, datetime.date):
        return datetime.datetime.combine(dtobj, datetime.time(0))
    if is_mx_datetime(dtobj):
        return dtobj.pydatetime()
    raise ValueError('Non-datetime value: %r' % (dtobj,))


def get_datetime_tz(dtobj, allow_none=True, tz=date.TIMEZONE):
    """
    Get a tz-aware datetime from a datetime-like object.

    :type dtobj: datetime.datetime | datetime.date | mx.DateTime.DateTimeType
    :param dtobj: The datetime-like object to convert
    :param bool allow_none: Allow empty *dtobj* value.

    :type tz: datetime.tzinfo
    :param tz:
        Tz-aware inputs are converted to *tz*.  Naive inputs are assumed to
        already be in *tz*.

    :rtype: datetime.datetime
    :returns: A tz-aware datetime object.
    """
    if not dtobj and allow_none:
        return None
    if isinstance(dtobj, datetime.datetime):
        if dtobj.tzinfo is None:
            return date.apply_timezone(dtobj, tz)
        else:
            return date.to_timezone(dtobj, tz)
    if isinstance(dtobj, datetime.date):
        return date.apply_timezone(
            datetime.datetime.combine(dtobj, datetime.time(0)),
            tz)
    if is_mx_datetime(dtobj):
        # mx.DateTime
        return date.apply_timezone(dtobj.pydatetime(), tz)
    raise ValueError('Non-datetime value: %r' % (dtobj,))


def to_mx_format(dtobj, tz=date.TIMEZONE):
    """
    Get an mx-like string from a datetime-like object.

    Formats a datetime-like object as ``YYYY-MM-DD HH:mm:ss.SS``, just like
    ``str(<mx.DateTime.DateTimeType>)`` would.

    :returns: datetime string
    """
    dt = get_datetime_naive(dtobj, allow_none=False, tz=tz)
    # datetime.datetime.strftime doesn't like dates < 1900.  The following is
    # basically:
    #   dt.strftime('%Y-%m-%d %H:%M:%S') + '.' + dt.strftime('%f')[:2]
    # but with dt.isoformat(), which accepts a wider year range
    iso = dt.isoformat(sep=str(" "))
    base, _, micros = iso.partition(".")
    return ".".join((base, (micros + "00")[:2]))


def parse_fs_xml_date(dtstr, allow_empty=True):
    """
    Parse a date from an FS XML date field.

    Accepts a basic ISO-8601 date (which we should expect in the future), as
    well as the legacy mx-like datetime string.

    :param str dtstr: An ISO-8601 formatted date or datetime
    :param bool allow_empty: Allow empty *dtstr* value.

    :rtype: datetime.date
    """
    if allow_empty and not dtstr:
        return None
    elif not dtstr:
        raise ValueError("Empty datetime string")
    try:
        return date.parse_date(dtstr)
    except ValueError:
        pass
    return date.parse_datetime(dtstr).date()
