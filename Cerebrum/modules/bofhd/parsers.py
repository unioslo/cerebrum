# -*- coding: utf-8 -*-
#
# Copyright 2022-2023 University of Oslo, Norway
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
This module contains generic utils for parsing user input in bofhd.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import six

from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import date_compat


class ParamsParser(object):
    """ Parse a sequence of <field>:<value> strings from user input.

    This class can convert a sequence of input strings like:

        ("my-str:foo", "my-str:bar", "my-int:20", "expire:2022-01-21")

    Into a dict:

        {
            "values": ["foo", "bar"],
            "limit": 20,
            "expire": datetime.datetime(2022, 1, 21, 0, 0, tzinfo=...),
        }
    """

    # A map of all implemented field types {<field>: <description>}
    #
    # Example:
    #
    #   fields =  {
    #     "my-int": "Set limit to some number <n>",
    #     "my-str": "A value (can be repeated)",
    #     "expire": "An expire <datetime> value",
    #   }
    #
    fields = {}

    # Field-to-param mapping for some or all of the supported fields.  Unmapped
    # fields will keep their name as given in `fields`.
    #
    # Example:
    #
    #   fields =  {
    #     "my-int": "limit",
    #     "my-str": "value",
    #   }
    #
    params = {}

    # Value mappers for some or all of the supported fields.  Fields without
    # parsers will remain as strings in the output.
    #
    # Example:
    #
    #   parsers =  {
    #     "my-int": int,
    #     "expire": parse_datetime,
    #   }
    #
    parsers = {}

    # A set of multivalued field names
    #
    # These fields can be given multiple times, and the resulting param will be
    # a list of all given values (in parse_items())
    #
    # Example:
    #
    #   multivalued = set(('my-str',))
    #
    multivalued = set()

    def __init__(self, allow=None):
        """
        :param allow: optional list of fields to allow
        """
        if allow is None:
            self.allow = set(self.fields)
        elif all(a in self.fields for a in allow):
            self.allow = set(allow)
        else:
            raise ValueError('invalid fields: '
                             + repr(set(allow) - set(self.fields)))

    def get_help(self):
        """ Return a sequence of (field, description) help text pairs. """
        return ((key, self.fields[key])
                for key in sorted(self.allow))

    def _parse(self, inputstr):
        try:
            field, raw_value = inputstr.split(':', 1)
            field = field.strip()
        except ValueError:
            raise CerebrumError('invalid input: %s (expected "field:value")'
                                % repr(inputstr))

        if field not in self.allow:
            raise CerebrumError('invalid field: ' + repr(field))

        parse = self.parsers.get(field, six.text_type)
        try:
            value = parse(raw_value)
        except ValueError as e:
            raise CerebrumError("invalid %s value: %s (%s)"
                                % (field, repr(raw_value), six.text_type(e)))

        return field, value

    def parse_item(self, item):
        """ Parse a single 'field:value' string.

        :param inputstr: A single "field:value" pair
        :returns tuple: (<param>, <value>) result tuple
        :raises CerebrumError: if the item is invalid
        """
        field, value = self._parse(item)
        return self.params.get(field, field), value

    def parse_items(self, items):
        """
        Parse and validate a set of 'field:value' strings.

        :param items: A sequence of "field:value" strings
        :returns dict: {<param>: <value>, ...} result
        :raises CerebrumError: if any of the items are invalid
        """
        params = {}
        for inputstr in items:
            field, value = self._parse(inputstr)
            param = self.params.get(field, field)
            repeat = field in self.multivalued

            if not repeat and param in params:
                raise CerebrumError('Cannot repeat field: ' + field)

            if repeat and param not in params:
                params[param] = [value]
            elif repeat:
                params[param].append(value)
            else:
                params[param] = value
        return params


def parse_datetime(raw_value, optional=False):
    """ Parse localized datetime from user input """
    if not raw_value or not raw_value.strip():
        if optional:
            return None
        raise CerebrumError('missing mandatory date/time')

    if raw_value.strip().lower() == 'now':
        return date_utils.now()
    if raw_value.strip().lower() == 'today':
        return date_compat.get_datetime_tz(datetime.date.today())
    parsers = (
        lambda v: date_utils.parse_datetime(v),
        lambda v: date_utils.parse_date(v),
        lambda v: datetime.datetime.combine(
            datetime.datetime.today(),
            date_utils.parse_time(v)),
    )

    for parse_value in parsers:
        try:
            return date_compat.get_datetime_tz(parse_value(raw_value))
        except ValueError:
            pass
    raise CerebrumError('invalid date/time: ' + repr(raw_value))


# A text blurb that can be used in help_refs for arguments that allow this
parse_datetime_help_blurb = """
"today"
    The literal text "today", selects current date @ midnight *

"now"
    The literal text "now", selects current date @ current time *

datetime
    An ISO-8601 datetime (T-separator optional).

    E.g. "2020-02-26 13:37" *, "2020-02-26T10:37:01.000Z",
         "2022-W04-2T12+0200"

date
    An ISO-8601 date @ midnight *,

    E.g. "2020-02-26", "2020-057", "2020-W09-3"

time
    An ISO-8601 time, selects current date @ time *

    Time must be provided in extended legacy format, e.g.:
    "14:37" or "23:15:00.000" (not "1437", "T1437", "T14:37")

*  All times are in local server time ({tz}), unless specified using ISO-8601
   format.
""".lstrip().format(tz=date_utils.TIMEZONE)


def parse_date(raw_value, optional=False):
    """ Parse date from user input """
    if not raw_value or not raw_value.strip():
        if optional:
            return None
        raise CerebrumError('missing mandatory date')

    if raw_value.strip().lower() == 'today':
        return datetime.date.today()
    try:
        return date_utils.parse_date(raw_value.strip())
    except ValueError:
        raise CerebrumError('invalid date: ' + repr(raw_value))


# A text blurb that can be used in help_refs for arguments that uses
# parse_date()
parse_date_help_blurb = """
"today"
    The literal text "today", selects current date,
    according to server time

date
    An ISO-8601 date

    E.g. "2020-02-26", "2020-057", "2020-W09-3"
""".lstrip().format(tz=date_utils.TIMEZONE)


def parse_legacy_date_range(raw_value):
    """
    Parse two dates from string, separated by '--'.

    - If only one date is given, it is assumed to be the end date.
    - If no start date is given, the start date will be "today"
    """
    # TODO: These should probably be replaced with ISO8601 interval parsers
    # (i.e.  implement date/datetime interval parsers in Cerebrum.utils.date,
    # based on aniso8601.parse_interval)
    date_start = datetime.date.today()
    date_end = None

    if raw_value and raw_value.strip():
        parts = raw_value.split("--")
        if len(parts) == 2:
            if parts[0]:
                date_start = parse_date(parts[0], optional=True)
            date_end = parse_date(parts[1], optional=True)
        elif len(parts) == 1:
            # no separator - assume date is end date, if given
            date_end = parse_date(parts[0], optional=True)

    # The method we're replacing *could* end up returing a None-value, but
    # let's try to be just a little more strict
    if date_start and date_end:
        return (date_start, date_end)
    raise CerebrumError("invalid date range: " + repr(raw_value))


parse_legacy_date_range_help_blurb = """
An end date, or a start and end date separated by '--'.  Start date defaults to
"today".

Examples:

 - 2020-02-26
 - 1998-06-28--
 - --2020-02-26
 - 1998-06-28--2020-02-26
 - 1998-06-28--today

Date format:

{}
""".lstrip().format(parse_date_help_blurb)


_cerebrum_glob_blurb = r"""
The Cerebrum pattern is a simple glob-like pattern, with the
following special characters:

- '*' matches zero or more characters
- '?' matches a single character
- '\*' matches a literal '*'
- '\?' matches a literal '?'
- '\\' matches a literal '\'
""".strip()


def parse_pattern(raw_value):
    """
    Parse a case sensitive cerebrum pattern.

    Note: This is a stub, as actual parsing is done in the sql mapper - we may
    want to add some checks here later.  See
    :mod:`Cerebrum.database.query_helpers` for details on pattern matching.
    """
    return raw_value


parse_pattern_help_blurb = """
A case sensitive glob-like pattern.

{}
""".lstrip().format(_cerebrum_glob_blurb)


def parse_ipattern(raw_value):
    """
    Parse a case insensitive Cerebrum pattern.

    Note: This is a stub, as actual parsing is done in the sql mapper - we may
    want to add some checks here later.  See
    :mod:`Cerebrum.database.query_helpers` for details on pattern matching.
    """
    return raw_value


parse_ipattern_help_blurb = """
A case insensitive glob-like pattern.

{}
""".lstrip().format(_cerebrum_glob_blurb)
