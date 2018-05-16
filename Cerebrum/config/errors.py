#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Configuration errors."""

from __future__ import unicode_literals


class ConfigurationError(Exception):
    """An exception that groups multiple exceptions in a _Configuration."""

    def __init__(self, errormap=dict()):
        """A new exception.

        :param dict errormap:
            Initialize with exceptions.
            An error map is a dict that maps:
                `config_key` -> `exception instance`
        """
        self._errors = dict()
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
                       for k, v in self.errors.iteritems())))

    def __repr__(self):
        return "{}({!r})".format(
            self.__class__.__name__,
            self.errors)

    def __len__(self):
        return len(self.errors)

    def __nonzero__(self):
        return bool(len(self))
