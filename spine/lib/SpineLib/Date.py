# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import mx.DateTime

from Builder import Builder, Attribute
import SpineExceptions

__all__ = ['Date']

class Date(Builder):
    slots = (
        Attribute('format', str, write=True),
    )

    def __init__(self, value=None, *args, **vargs):
        super(Date, self).__init__(*args, **vargs)
        if value is None:
            value = mx.DateTime.now()
        self._value = value

    def get_primary_key(self):
        return (self._value, )

    for i in ('year', 'month', 'day', 'hour', 'minute', 'second'):
        exec 'def get_%s(self):\n return self._value.%s\nget_%s.signature = int' % (i, i, i)
    def get_unix(self):
        return int(self._value.ticks())
    get_unix.signature = int

    def strftime(self, formatstr):
        return self._value.strftime(formatstr)

    strftime.signature = str
    strftime.signature_args = [str]

    def to_string(self):
        if hasattr(self, '_format'):
            return self.strftime(self._format)
        else:
            return str(self._value)

    to_string.signature = str
Date.signature_public = True

# arch-tag: 57d51c14-a6c9-4913-a011-1f7222ad79b5
