# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway
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
""" Utilities for use with argparse. """
import argparse
import codecs
import locale
import sys

import six

from Cerebrum.Utils import Factory

#
# types
#
# These objects and functions can be used as the ``type`` value of
# most argparse.Action (add_argument) types.
#


class UnicodeType(object):
    """ Argparse transform for non-unicode input. """

    def __init__(self, encoding=None):
        if encoding is None:
            self.encoding = self.get_default_encoding()
        else:
            self.encoding = encoding

    def get_default_encoding(self):
        """ guess encoding for arguments. """
        return filter(None, [locale.getdefaultlocale()[1],
                             sys.getfilesystemencoding(),
                             sys.getdefaultencoding()]).pop(0)

    def __call__(self, value):
        if isinstance(value, bytes):
            try:
                value = value.decode(self.encoding)
            except UnicodeError as e:
                raise ValueError(e)
        return six.text_type(value)

    def __repr__(self):
        return 'UnicodeType(encoding={0})'.format(repr(self.encoding))


class IntegerType(object):
    """ Argparse transform for integers, with optional limits. """

    def __init__(self, minval=None, maxval=None):
        self.minval = int(minval) if minval is not None else None
        self.maxval = int(maxval) if maxval is not None else None

    def __call__(self, value):
        value = int(value)
        if self.minval is not None and value < self.minval:
            raise ValueError("value is too small")
        if self.maxval is not None and value > self.maxval:
            raise ValueError("value is too large")
        return value

    def __repr__(self):
        return 'IntegerType(minval={0}, maxval={1})'.format(repr(self.minval),
                                                            repr(self.maxval))


def attr_type(obj, type_func=None, attr_func=None):
    """ Get value as an attribute from `obj`.

    :param object obj: An object to fetch the attribute value from
    :param callable type_func: An additional transform for the attribute value
    :param callable attr_func: A tranform for the attribute before fetching

    Example:

    >>> o = type('example', (object, ), {'FOO': '1'})()
    >>> argparse.ArgumentParser().add_argument(
    ...     type=attr_type(o, type_func=int, attr_func=lambda x: x.upper()))

    This function is mainly useful for fetching values from `cereconf`,
    `eventconf`, etc...

    """
    def get(value):
        try:
            attr = (attr_func or (lambda x: x))(value)
            real = getattr(obj, attr)
        except (TypeError, ValueError, AttributeError):
            raise argparse.ArgumentTypeError(
                "invalid %r value: %r" % (obj, value))
        try:
            return (type_func or (lambda x: x))(real)
        except (TypeError, ValueError):
            raise argparse.ArgumentTypeError(
                "invalid value in %r.%s: %r" % (obj, attr, real))
    return get


def codec_type(encoding):
    """ Argparse transform for encoding.

    >>> argparse.ArgumentParser().add_argument(
    ...    '--encoding', type=codec_type, default='utf-8'))

    """
    try:
        return codecs.lookup(encoding)
    except LookupError as e:
        raise ValueError(str(e))


#
# errors and validation
#
# These objects and functions can be used to ensure similar behaviour when
# doing argument validation.
#


class ParserContext(object):
    """ Perform argument validation on the context of an argument parser.

    If an exception is raised in the ParserContext, the script will exit with
    a parser error.

    Typical usage:

        parser = argparse.ArgumentParser()
        foo_arg = parser.add_argument('--foo')
        args = parser.parse_args()

        with ParserContext(parser, foo_arg):
            # validate args.foo here
            if args.foo in ('foo', 'bar', 'baz'):
                raise ValueError("should not be %r" % (args.foo, ))

    """

    def __init__(self, parser, argument=None):
        self.parser = parser
        self.argument = argument

    def make_error(self, message):
        if self.argument:
            return argparse.ArgumentError(self.argument, message)
        else:
            return argparse.ArgumentTypeError(message)

    def cause_error(self, message):
        self.parser.error(str(self.make_error(message)))

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            self.cause_error(str(exc_value))


def get_constant(db, parser, const_types, value, argument=None):
    """ Get an exising constant.

    NOTE: This function triggers the argparse error handler (exists by default)
          if the constant does not exist.

    :type db: Cerebrum.database.Database
    :type parser: argparse.ArgumentParser
    :param const_types: The expected constant class(es)
    :param value: The value to look up
    :type argument: argparse.Action
    """
    # TODO: We really should have a way to look up constants attrs/strvals from
    # Factory.get('Constants') without needing a db-connection
    co = Factory.get('Constants')
    with ParserContext(parser, argument):
        const_value = co.resolve_constant(db, value, const_types)
        if const_value is None:
            raise ValueError(
                "invalid constant value: %r" % (value, ))
    return const_value


#
# actions
#
# These objects and functions can be used as the ``action`` value of
# most add_argument, and provide alternate behaviour in options parsing.
#


class ExtendAction(argparse.Action):
    """ Like the 'append'-action, but uses `list.extend`.

    This means that the `type` argument should be set to something that returns
    a sequence of items to add to the namespace value.
    """

    def __init__(self, option_strings, dest, default=None, type=None,
                 required=False, help=None, metavar=None):
        super(ExtendAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=None,
            const=None,
            default=default,
            type=type or (lambda x: x),
            choices=None,
            required=required,
            help=help,
            metavar=metavar)

    def __call__(self, parser, namespace, values, option_string=None):
        items = list(getattr(namespace, self.dest, None) or ())
        items.extend(values)
        setattr(namespace, self.dest, self.type(items))


class ExtendConstAction(argparse.Action):
    """ Like ExtendAction, but adds constants to the list.

    Typical usage is to collect a sequence of things to do using switches.

    Example:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            '--preset-a',
            dest='items',
            action=ExtendConstAction,
            const=['foo', 'bar', 'baz'])
        parser.add_argument(
            '--preset-b',
            dest='items',
            action=ExtendConstAction,
            const=['bar', 'baz'])
    """

    def __init__(self, option_strings, dest, const, default=None,
                 type=None, required=False, help=None, metavar=None):
        # Ensure iterable item:
        const = tuple(c for c in const)
        super(ExtendConstAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            const=const,
            default=default or [],
            type=type or (lambda x: x),
            choices=None,
            required=required,
            help=help,
            metavar=metavar)

    def __call__(self, parser, namespace, values, option_string=None):
        items = list(getattr(namespace, self.dest, None) or ())
        items.extend(self.const)
        setattr(namespace, self.dest, self.type(items))


def add_commit_args(parser, default=False, commit_desc=None):
    """ Add --commit and --dryrun arguments to parser.

    :param parser: argument parser or argument group
    :param default: commit by default if True
    :param commit_desc: use a custom description for commit argument
    :type commit_desc: unicode
    """

    commit_mutex = parser.add_mutually_exclusive_group()
    commit_mutex.add_argument(
        '--dryrun',
        dest='commit',
        action='store_false',
        help='Run in dryrun mode' + ('' if default else ' (default)'))
    commit_mutex.add_argument(
        '--commit',
        dest='commit',
        action='store_true',
        help=(commit_desc or 'Commit changes to the database') + (
            '' if not default else ' (default)'))
    commit_mutex.set_defaults(commit=default)
    return parser
