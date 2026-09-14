# -*- coding: utf-8 -*-
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
"""
Cerebrum log filters.

This module provides some filters for manipulating log records.  They are
typically applied to specific loggers in configuration.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
)
import logging
import re
import sys


class SubstituteFilter(logging.Filter):
    """
    Log message substitution filter.

    This filter cleans log messages for a given pattern.  This can be useful
    for censoring sensitive log messages that are otherwise hard to deal with
    in a clean manner.

    It looks through the rendered LogRecord message and replaces occurances of
    the *pattern* with the *replacement* string.  Substution is applied to the
    *rendered* message from :meth:`logging.LogRecord.getMessage`, and done
    using :func:`re.sub`.

    .. note::
       If a replacement occurs, the log record is manipulated:

       - ``msg`` is replaced by a pre-rendered, substituted message
       - ``args`` is emptied
    """

    def __init__(self, pattern='^$', replacement=r''):
        """
        :param str pattern:
            A pattern to look for. May contain capture groups that can be used
            in the replacement string.

        :param str replacement:
            A string to replace the pattern with. May contain references to
            capture groups.
        """
        self.pattern = re.compile(pattern)
        self.replacement = replacement

    def filter(self, record):
        """ Determine if the specified record is to be logged.

        We will always return `True` (i.e. keep this log record), but modify
        its contents (alter the message).
        """
        message = record.getMessage()
        if message:
            msg = self.pattern.sub(self.replacement, message)
            if msg != message:
                # censord message and args
                record.args = []
                record.msg = msg

        return True


class AddCommandField(logging.Filter):
    """
    Add a command log field.

    This filter adds an extra :class:`logging.LogRecord` field that includes
    a re-constructed command that would be used to invoke this process.

    .. note::
       This is really only something you'd want if the formatter outputs
       structured log records, e.g. by using a json formatter.
    """

    DEFAULT_FIELD_NAME = 'command'
    """ Default LogRecord attribute/field name. """

    def __init__(self, field_name=DEFAULT_FIELD_NAME):
        """
        :param str field_name: LogRecord attribute/field name to use
        """
        # TODO: Should we include options to sys.executable?
        #       Most of them can be found in `sys`... Can we get the raw,
        #       unaltered command?
        if sys.argv:
            command = '{0} {1}'.format(sys.executable, ' '.join(sys.argv))
        else:
            command = '{0}'.format(sys.executable)
        self.field_name = field_name
        self.field_value = command

    def filter(self, record):
        setattr(record, self.field_name, self.field_value)
        return True
