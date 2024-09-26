# -*- coding: utf-8 -*-
#
# Copyright 2015-2024 University of Oslo, Norway
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
"""Configuration errors."""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import six

from Cerebrum.utils import text_compat


def format_error(key, exc):
    """
    Format exception as a simple text string.

    :param key: the invalid config key
    :param exc: an exception to associate with the key
    """
    try:
        error = "{}: {}".format(
            text_compat.to_text(type(exc).__name__),
            text_compat.to_text(exc),
        )
    except Exception:
        error = text_compat.to_text(repr(exc))
    return "{key} ({error})".format(
        key=text_compat.to_text(repr(key)),
        error=error,
    )


@six.python_2_unicode_compatible
class ConfigurationError(Exception):
    """An exception that groups multiple exceptions in a _Configuration."""

    def __init__(self, errormap=None):
        """A new exception.

        :param dict errormap:
            Initialize with exceptions.
            An error map is a dict that maps:
                `config_key` -> `exception instance`
        """
        self._errors = {}
        errormap = errormap or {}
        assert isinstance(errormap, dict)
        for key in errormap:
            self.set_error(key, errormap[key])

    @property
    def errors(self):
        return self._errors

    def set_error(self, key, exc):
        """Set an error or group of errors.

        :param str key:
            The key to add the error(s) under.

        :param Exception exc:
            An exception instance to add.
        """
        if isinstance(exc, ConfigurationError):
            for sub in exc.errors:
                self.set_error('{}.{}'.format(key, sub), exc.errors[sub])
        else:
            self._errors[key] = exc

    def __str__(self):
        errors = (format_error(k, v) for k, v in self.errors.items())
        return "Errors in {}".format(', '.join(errors))

    def __repr__(self):
        name = self.__class__.__name__
        init = repr(self._errors)
        return "{}({})".format(name, init)

    def __len__(self):
        return len(self.errors)

    def __bool__(self):
        return bool(len(self))

    __nonzero__ = __bool__
