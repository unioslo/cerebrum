# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
""" A simple table formatter for task scripts. """
from __future__ import print_function

import datetime
import logging

logger = logging.getLogger(__name__)


def to_str(value):
    if value is None:
        return ''
    if isinstance(value, datetime.date):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(value, dict):
        return repr(value)
    return str(value)


def limit_str(s, max_length):
    return s if len(s) <= max_length else s[:max_length-3] + '...'


class TaskFormatter(object):
    """ Format selected task fields as table rows. """
    # TODO: We could probably re-write this as a generic dict-like to table
    # formatter

    default_field_size = 20

    field_size = {
        'queue': 15,
        'key': 10,
        'attempts': 8,
    }

    field_sep = '  '

    def __init__(self,
                 fields,
                 default_field_size=default_field_size,
                 field_size=None):
        self.fields = tuple(fields)
        self.default_field_size = default_field_size
        self.field_size = {}
        for field, size in type(self).field_size.items():
            self.field_size[field] = size
        for field, size in (field_size or {}).items():
            self.field_size[field] = size

    def get_size(self, field):
        return self.field_size.get(field, self.default_field_size)

    def format_cell(self, field, value):
        size = self.get_size(field)
        return format(limit_str(to_str(value), size), '<' + str(size))

    def format_header(self):
        return self.field_sep.join(self.format_cell(f, f)
                                   for f in self.fields)

    def format_sep(self):
        return self.field_sep.join(self.format_cell(f, '-' * self.get_size(f))
                                   for f in self.fields)

    def format_dict(self, data):
        return self.field_sep.join(self.format_cell(f, data[f])
                                   for f in self.fields)

    def __call__(self, items, header=False):
        if header:
            yield self.format_header()
            yield self.format_sep()

        for item in items:
            yield self.format_dict(item)
