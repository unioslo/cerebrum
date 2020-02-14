# -*- coding: utf-8 -*-
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
Custom portability macro syntax for Cerebrum.

This module contains functionality to convert portability macros:

- ``[:op]``
- ``[:op key=value]``
- ``[:op key=value key2=value2]``

into valid SQL for a given database dialect.

History
-------
This module was extracted from ``Cerebrum.database.Database.sql_repr``

The refactor was done to make the portability functions available to
``Cerebrum.database.translate``.  The original macro translation can be seen in:

    commit: f8d149dbb21cdbf10724b60b6d1c613ebc951b5f
    Merge:  3e4c07061 be7c05022
    Date:   Tue Feb 11 11:42:09 2020 +0100
"""
import collections
import re

import six

from Cerebrum.Errors import NotFoundError
from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import deprecate


cereconf = object()
constants = object()


# Convert
_op_id = r'[-_a-z0-9]+'
_op_arg_key = r'[-_a-z0-9]+'
_op_arg_value = r'[-_a-z0-9]+'
_match_op = re.compile(
    r'\[:({op})((?:\s+(?:{key})\s*=\s*(?:{value}))*)\]'.format(
        op=_op_id,
        key=_op_arg_key,
        value=_op_arg_value,
    ),
    re.IGNORECASE | re.UNICODE)
_match_arg = re.compile(
    r'\s*({key})\s*=\s*({value})'.format(
        key=_op_arg_key,
        value=_op_arg_value,
    ),
    re.IGNORECASE | re.UNICODE)


def parse_macro(raw):
    match = _match_op.match(raw)
    if not match:
        raise ValueError('invalid macro string: %r', (raw,))
    name = match.group(1)
    params = parse_macro_args(match.group(2))
    return name, params


def parse_macro_args(raw):
    if not raw:
        return {}
    else:
        return dict(_match_arg.findall(raw))


class MacroTable(collections.Mapping):
    """A dict-like with macro functions."""

    def __init__(self, *args, **kwargs):
        self._ops = {}
        for k, v in dict(*args, **kwargs).items():
            self.set(k, v)

    def register(self, op):
        """get a decorator that sets a macro function."""
        def wrapper(fn):
            self.set(op, fn)
            return fn
        return wrapper

    def set(self, op, fn):
        """set function as macro handler for a given op."""
        self._ops[op] = fn

    def __len__(self):
        return len(self._ops)

    def __iter__(self):
        return iter(self._ops)

    def __getitem__(self, op):
        return self._ops[op]

    def __call__(self, op, params, context=None):
        """call macro function."""
        fn = self[op]
        assert 'context' not in params
        params = dict(params)
        params['context'] = context or {}
        return fn(**params)


common_macros = MacroTable()


@common_macros.register('table')
def op_table(schema, name, context=None):
    """
    Get a table name.

    This function inserts the appropriate name for a cerebrum table, using the
    macro [:table schema=<schema> name=<table>], where <schema> is a table
    namespace and <table> is the table name within that namespace.
    """
    return six.text_type(name)


@common_macros.register('now')
def op_now(context=None):
    """
    Get an appropriate now() function.

    This function inserts the appropriate sql statement for getting the current
    datetime, using the macro [:now].
    """
    return 'CURRENT_TIMESTAMP'


@common_macros.register('get_config')
def op_get_config(var, context=None):
    """
    Get value from config (cereconf).

    This function inserts a value from `cereconf` (or a similar config object),
    using the macro [:get_config var=<name>], where <name> is an attribute name
    from the config.

    .. note::
        Only string values can currently be fetched.

    .. note::
        Requires a 'config' object in the context.
    """
    config = (context or {}).get('config') or cereconf
    attr = six.text_type(var)
    if not hasattr(config, attr):
        raise ValueError("no config attribute %r" % (attr,))
    value = getattr(config, attr)
    if isinstance(value, six.string_types):
        return "'{}'".format(value)
    raise ValueError('invalid config value type %r' % type(value))


@common_macros.register('get_constant')
def op_get_constant(name, context=None):
    """
    Get CerebrumCode int value.

    This function inserts the int value value of a database constant, using the
    macro [:get_constant name=<name>], where <name> is the constant attribute
    in a ConstantsBase constants container.

    .. note::
        Requires a 'constant' ConstantsBase container, or a database connection
        to use with the Factory.get('Constants') ConstantsBase container.
    """
    context = context or {}
    constants = (
        context.get('constants') or
        Factory.get('Constants')(context.get('db')))
    name = six.text_type(name)
    try:
        const = getattr(constants, name)
    except AttributeError as e:
        raise ValueError('no constant %r: %s' % (name, e))
    try:
        return str(int(const))
    except (ValueError, NotFoundError) as e:
        raise ValueError('invalid constant %r (%r): %s' % (name, const, e))


@common_macros.register('boolean')
@deprecate('[:boolean] macro not implemented?')
def op_boolean(default=None, context=None):
    """
    Not implemented?
    """
    # default = params.get('default')
    return ''


@common_macros.register('from_dual')
def op_from_dual(context=None):
    """
    Dummy 'FROM DUAL' statement for non-oracle databases.
    """
    return ''


@common_macros.register('sequence')
def op_sequence(schema, name, op, context=None):
    """
    Sequence manipulation stub.
    """
    raise ValueError('Invalid sequnce operation: %r' % (op,))


@common_macros.register('sequence_start')
@deprecate('Use "START WITH <value>", not "[:sequence_start value=<value>"')
def op_sequence_start(value, context=None):
    """
    Suffix for CREATE / ALTER SEQUENCE to set start value.

    Shouldn't be used, 'START WITH' is plenty portable.
    """
    return 'START WITH {}'.format(int(value))
