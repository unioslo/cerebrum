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
This module contains mx.DateTime compatibility functions for Cerebrum.

This module is temporary, and is only in place to aid the transition from
mx.DateTime to the datetime standard library module.
"""
import datetime

from . import date


def get_date(dtobj, allow_none=True):
    """
    Get a datetime.date object from a datetime-like object.

    Typical usecase for this method is to convert database mx.DateTime objects
    to native date objects:

        if get_date(pe.birth_date) != new_date:
            pe.birth_date = new_date

    :type dtobj: datetime.datetime, datetime.date, mx.DateTime, NoneType
    :param dtobj: A datetime-like object.

    :type allow_none: bool
    :param allow_none:
        Returns None if the input value is empty (this is the default).

    :rtype: datetime.date
    :return: A date object.
    """
    if not dtobj and allow_none:
        return None
    if isinstance(dtobj, datetime.datetime):
        return dtobj.date()
    if isinstance(dtobj, datetime.date):
        return dtobj
    if hasattr(dtobj, 'pydate'):
        # mx.DateTime
        return dtobj.pydate()
    raise ValueError('Non-date value: %r' % (dtobj,))


def get_datetime_naive(dtobj, allow_none=True, tz=date.TIMEZONE):
    """
    Get a naive datetime.datetime object from a datetime-like object.

    Typical usecase for this method is to convert database mx.DateTime objects
    to naive datetime objects:

        if get_datetime_naive(row['tstamp']) > cutoff_dt:
            do_something()

    :type dtobj: datetime.datetime, datetime.date, mx.DateTime, NoneType
    :param dtobj:
        A datetime-like object.
        Note that ``datetime.date`` gets ``datetime.time(0)``

    :type allow_none: bool
    :param allow_none:
        Returns None if the input value is empty (this is the default).

    :type tz: tzinfo or NoneType
    :param tz:
        Converts tz-aware datetime objects to the given tz before stripping
        tzinfo.  If set to ``None``, the tzinfo is stripped without conversion.
        Defaults to the ``TIMEZONE`` setting.

    :rtype: datetime.datetime
    :return: A naive datetime object.
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
    if hasattr(dtobj, 'pydatetime'):
        # mx.DateTime
        return dtobj.pydatetime()
    raise ValueError('Non-datetime value: %r' % (dtobj,))


def get_datetime_tz(dtobj, allow_none=True, tz=date.TIMEZONE):
    """
    Get a tz-aware datetime.datetime object from a datetime-like object.

    Typical usecase for this method is to convert database mx.DateTime objects
    to tz-aware datetime objects:

        if get_datetime_tz(row['tstamp']) > cutoff_dt:
            do_something()

    :type dtobj: datetime.datetime, datetime.date, mx.DateTime, NoneType
    :param dtobj:
        A datetime-like object.
        Note that ``datetime.date`` gets ``datetime.time(0)``

    :type allow_none: bool
    :param allow_none:
        Returns None if the input value is empty (this is the default).

    :type tz: tzinfo or NoneType
    :param tz:
        Converts tz-aware datetime objects to the given tz, assumes other
        values are *in* the given timezone.

    :rtype: datetime.datetime
    :return: A tz-aware datetime object.
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

    if hasattr(dtobj, 'pydatetime'):
        # mx.DateTime
        return date.apply_timezone(dtobj.pydatetime(), tz)
    raise ValueError('Non-datetime value: %r' % (dtobj,))


def get_timedelta(value, allow_none=True):
    """
    Get a datetime.timedelta object from a timedelta-like value.

    This is typically needed where DateTimeDelta values are used in config
    modules.  This only seems to be done in WebID (virthome).

    :type value: datetime.timedelta, mx.DateTime.DateTimeDelta, int, NoneType
    :param value:
        A timedelta-like value.
        If an integer value is given, it is assumed to be days.

    :type allow_none: bool
    :param allow_none:
        Returns None if the input value is empty (this is the default).

    :rtype: datetime.timedelta, NoneType
    """
    if not value and allow_none:
        return None
    if isinstance(value, datetime.timedelta):
        return value
    if hasattr(value, 'pytimedelta'):
        return value.pytimedelta()
    if isinstance(value, int):
        return datetime.timedelta(days=value)
    raise ValueError('Non-timedelta value: %r' % (value,))


def to_mx_format(dtobj, tz=date.TIMEZONE):
    """
    Get the equivalent of str(mx.DateTime).

    :type dtobj: datetime.datetime, datetime.date, mx.DateTime, NoneType
    :param dtobj: A datetime-like object.

    :type tz: tzinfo
    :param tz:
        Converts tz-aware datetime objects to the given tz before formatting.

    :rtype: str
    :return:
        A datetime string with format "%Y-%m-%d %H:%M:%S.%f", but with only two
        digit precision for the %f component.
    """
    dt = get_datetime_naive(dtobj, allow_none=False, tz=tz)
    return dt.strftime('%Y-%m-%d %H:%M:%S') + '.' + dt.strftime('%f')[:2]


def parse_fs_xml_date(dtstr, allow_empty=True):
    """
    Get a date object from an FS date field.

    Currently, FS datetime objects are formatted by str(mx.DateTime) in
    various `import_from_FS` scripts.  The code for this is in
    `Cerebrum.modules.xmlutils.xml_helper`.

    In the future, we expect these date fields to be formatted as proper
    ISO8601 date values (and parsed by ``Cerebrum.utils.date.parse_date``)

    :param str dtstr:
        an ISO-formatted date or datetime

    :param bool allow_empty:
        Allow the dtstr value to be empty (return `None`)

    :rtype: datetime.date
    """
    if allow_empty and not dtstr:
        return None
    try:
        return date.parse_date(dtstr)
    except ValueError:
        pass
    return date.parse_datetime(dtstr).date()
