# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
"""
Utilities for communicating with SAP @ DFØ.
"""
from __future__ import unicode_literals
import datetime


def assert_list(value):
    """
    Assert that value is a list.

    Usage: ``some_key = assert_list(dfo_object.get('someKey'))``
    """
    # This is a hacky way to fix the broken DFØ API
    # Some items in the API are specified to be a list, but lists of length 1
    # are unwrapped, and empty lists are simply not present.
    if not value:
        return []
    if not isinstance(value, list):
        return [value]
    return value


def parse_date(value, fmt='%Y-%m-%d', allow_empty=True):
    if value:
        return datetime.datetime.strptime(value, fmt).date()
    elif allow_empty:
        return None
    else:
        raise ValueError('No date: %r' % (value,))
