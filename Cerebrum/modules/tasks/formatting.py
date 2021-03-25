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
