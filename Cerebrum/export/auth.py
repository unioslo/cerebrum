# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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
Fetch and process account passwords.

This module provides abstractions for fetching, selecting and formatting
account authentication data.

The general flow for exports should look something like:

1. Fetch and validate configuration (e.g. which authentication types to use)
2. Build cache of all relevant authentication types and data
3. Fetch and format authentication data as needed.

"""
import logging
import string

from Cerebrum.Constants import _AuthenticationCode
from Cerebrum.Errors import NotFoundError
from Cerebrum.Utils import Factory

from . import base


logger = logging.getLogger(__name__)


def _get_auth_type(co, value):
    """ Look up a single _AuthenticationCode value. """
    if isinstance(value, _AuthenticationCode):
        const = value
    else:
        const = co.human2constant(value, _AuthenticationCode)
    if const is None:
        raise LookupError("AuthenticationCode %r not defined" % (value, ))
    try:
        int(const)
    except NotFoundError:
        raise LookupError("AuthenticationCode %r (%r) not in db" %
                          (value, const))
    return const


def get_auth_types(co, values):
    """ Look up a sequence of _AuthenticationCode values. """
    for value in values:
        yield _get_auth_type(co, value)


def _check_auth_types(auth_types, unique=True, allow_empty=False):
    """ Check a sequence of _AuthenticationCode values """
    auth_types = tuple(auth_types)
    for auth_type in auth_types:
        if not isinstance(auth_type, _AuthenticationCode):
            raise ValueError("Invalid auth_type %s" % repr(auth_type))
    if not (allow_empty or auth_types):
        raise ValueError("No auth_types given")
    if unique and len(auth_types) != len(set(auth_types)):
        raise ValueError("Duplicate auth_types given: %s" % repr(auth_types))
    return auth_types


class _AuthFetcher(base.EntityFetcher):
    """ Fetch authentication data for accounts. """

    def __init__(self, db, auth_types, filter_expired=True):
        self.auth_types = _check_auth_types(auth_types)
        self.filter_expired = filter_expired
        self._ac = Factory.get('Account')(db)

    def _get_results(self, **extra):
        auth_type_map = dict((int(m), m) for m in self.auth_types)
        for row in self._ac.list_account_authentication(
                auth_type=self.auth_types,
                filter_expired=self.filter_expired,
                **extra):
            if not row['auth_data']:
                continue
            auth_type = auth_type_map[int(row['method'])]
            yield row['account_id'], auth_type, row['auth_data']

    def get_one(self, entity_id):
        """ Fetch authentication data for one account. """
        account_auth = {}
        for _, auth_type, auth_data in self._get_results(
                account_id=int(entity_id)):
            account_auth[auth_type] = auth_data
        return account_auth or base.MISSING

    def get_all(self):
        """ Fetch authentication data for all accounts. """
        results = {}
        for entity_id, auth_type, auth_data in self._get_results():
            account_auth = results.setdefault(int(entity_id), {})
            account_auth[auth_type] = auth_data
        return results


class _AuthSelector(object):
    """ Select and sort authentication type by priority. """

    def __init__(self, auth_types):
        auth_types = _check_auth_types(auth_types)
        self.priority = dict(
            (auth_type, order)
            for order, auth_type in enumerate(auth_types, 0))
        self.default = len(self.priority)

    def _get_sort_key(self, tup):
        auth_type, _ = tup
        return self.priority.get(auth_type, self.default)

    def __call__(self, tuples):
        for auth_type, auth_data in sorted(tuples, key=self._get_sort_key):
            yield auth_type, auth_data


class AuthCache(base.EntityCache):
    """
    A cache of account authentication methods.

    Usage:

        # List preferred authentication methods
        auth_types = get_auth_types(const, ('SHA-256-crypt', 'MD5-crypt'))
        account_auth = AuthCache(db, auth_types)

        # Optionally, cache the relevant auth_types of all accounts up front.
        account_auth.update_all()

        # Get preferred auth method and data for a given account
        auth_type, auth_data = account_auth.get_authentication(<account_id>)
    """

    def __init__(self, db, auth_types):
        """
        :param auth_types:
            An ordered sequence of preferred authentication codes
        """
        self.auth_types = _check_auth_types(auth_types)
        super(AuthCache, self).__init__(_AuthFetcher(db, auth_types))
        self.selector = _AuthSelector(auth_types)

    def get_authentication(self, account_id):
        """
        Get preferred authentication method and data a given account

        .. note::
            The cache must be populated first (see build_cache())

        :param account_id:
            The account to look up

        :rtype: tuple
        :return: A tuple with the authentication code and data
        """
        account_auth = self.get(account_id, {})
        for method, value in self.selector(account_auth.items()):
            return method, value
        raise LookupError('No auth data available for account_id=%r' %
                          (account_id, ))


def _to_template(tpl_string):
    """
    Make a template string that takes a single $value variable.

    :rtype: string.Template
    """
    template = string.Template(tpl_string)
    template.substitute(value='test')
    return template


def get_format_mapping(co, pairs):
    """
    Validate and transform a sequence of (auth_type, value_template) tuples.

    :param co:
        A constants container object (Factory.get('Constants')())
    :param pairs:
        A sequence of (auth_type, template) tuples.


    :rtype: generator
    :returns:
        A generator that yields a tuple pair for each input tuple pair.

        In the return data, the constant string is replaced with a constant
        object, and the template string is replaced with a string.Template()
        object.
    """
    for method, tpl in pairs:
        yield _get_auth_type(co, method), _to_template(tpl)


class AuthFormatter(object):
    """
    Format authentication codes.

    Usage:

        # List authentication methods and formatting template
        methods = get_format_mapping(
            const,
            (('SHA-256-crypt', '{CRYPT}$value'),
             ('SSHA', '{SSHA}$value'),
             ('MD5-crypt', '{CRYPT}$value')))

        # Make formatter
        formatter = AuthFormatter(methods)

        # Format authentication value
        formatter.format(
            _get_auth_type('SHA-256-crypt'),
            '$5$rounds=535000$B6UQYgg/nbAumqPk$2.qHiKsfXeTr97dWxaUY0ylI2UUhG5aOzFsiIt2aor/')
    """

    def __init__(self, *args, **kwargs):
        mapping = dict(*args, **kwargs)
        _check_auth_types(mapping.keys())
        for k in mapping:
            if not isinstance(mapping[k], string.Template):
                raise ValueError("Invalid template string for %s: %r" %
                                 (k, mapping[k]))
        self.mapping = mapping

    def format(self, method, value):
        return self.mapping[method].substitute(value=value)


class AuthExporter(object):
    """
    Authentication cache and lookup utility.
    """

    def __init__(self, cache, formatter, default=None):
        """
        """
        self.cache = cache
        self.formatter = formatter
        self.default = default

    @classmethod
    def make_exporter(cls, db, format_mapping):
        co = Factory.get('Constants')(db)
        pairs = tuple(get_format_mapping(co, format_mapping))
        cache = AuthCache(db, tuple(m for m, _ in pairs))
        formatter = AuthFormatter(pairs)
        return cls(cache, formatter)

    def get(self, account_id):
        method, data = self.cache.get_authentication(account_id)
        return self.formatter.format(method, data)
