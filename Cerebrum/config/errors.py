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
        return "Errors in {}".format(
            ', '.join(('{!r} ({}: {})'.format(k, type(v).__name__, v)
                       for k, v in self.errors.items())))

    def __repr__(self):
        name = self.__class__.__name__
        init = repr(self._errors)
        return "{}({})".format(name, init)

    def __len__(self):
        return len(self.errors)

    def __bool__(self):
        return bool(len(self))

    __nonzero__ = __bool__
