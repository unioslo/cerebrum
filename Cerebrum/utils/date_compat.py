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
