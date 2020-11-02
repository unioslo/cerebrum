# -*- coding: utf-8 -*-
#
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
Client for communicating with the DFØ-SAP HTTP-APIs.

History
-------
This client is forked from the ``dfo_sap_client.client`` module @
`https://bitbucket.usit.uio.no/scm/int/dfo-sap-client.git>`_.
"""
from __future__ import unicode_literals

import logging
from six.moves.urllib.parse import (
    quote_plus,
    urlparse,
    urljoin as _urljoin,
)

import requests

from Cerebrum.config.configuration import (Configuration,
                                           ConfigDescriptor,
                                           Namespace)
from Cerebrum.config.settings import Boolean, Iterable, String

logger = logging.getLogger(__name__)


def quote_path_arg(arg):
    return quote_plus(str(arg))


def merge_dicts(*dicts):
    """
    Combine a series of dicts without mutating any of them.

    >>> merge_dicts({'a': 1}, {'b': 2})
    {'a': 1, 'b': 2}
    >>> merge_dicts({'a': 1}, {'a': 2})
    {'a': 2}
    >>> merge_dicts(None, None, None)
    {}
    """
    combined = dict()
    for d in dicts:
        if not d:
            continue
        for k in d:
            combined[k] = d[k]
    return combined


def urljoin(base_url, *paths):
    """
    A sane urljoin.

    Note how urllib.parse.urljoin will assume 'relative to parent' when the
    base_url doesn't end with a '/':

    >>> urllib.parse.urljoin('https://localhost/foo', 'bar')
    'https://localhost/bar'

    >>> urljoin('https://localhost/foo', 'bar')
    'https://localhost/foo/bar'

    >>> urljoin('https://localhost/foo', 'bar', 'baz')
    'https://localhost/foo/bar/baz'
    """
    for path in paths:
        base_url = _urljoin(base_url.rstrip('/') + '/', path)
    return base_url


class SapEndpoints(object):
    """Get endpoints relative to the SAP API URL."""

    default_employee_path = 'ansatte/'
    default_orgenhet_path = 'orgenhet/'
    default_stilling_path = 'stillinger/'

    def __init__(self,
                 url,
                 employee_path=None,
                 orgenhet_path=None,
                 stilling_path=None):
        self.baseurl = url
        self.employee_path = employee_path or self.default_employee_path
        self.orgenhet_path = orgenhet_path or self.default_orgenhet_path
        self.stilling_path = stilling_path or self.default_stilling_path

    def __repr__(self):
        return (
            '{cls.__name__}'
            '({obj.baseurl!r},'
            ' employee_path={obj.employee_path!r},'
            ' orgenhet_path={obj.orgenhet_path!r},'
            ' stilling_path={obj.stilling_path!r})'
        ).format(cls=type(self), obj=self)

    def get_employee(self, employee_id):
        return urljoin(self.baseurl, self.employee_path,
                       quote_path_arg(employee_id))

    def get_orgenhet(self, org_id):
        return urljoin(self.baseurl, self.orgenhet_path,
                       quote_path_arg(org_id))

    def get_stilling(self, stilling_id):
        return urljoin(self.baseurl, self.stilling_path,
                       quote_path_arg(stilling_id))


class SapClient(object):

    default_headers = {
        'Accept': 'application/json',
    }

    def __init__(self,
                 url,
                 headers=None,
                 employee_path=None,
                 employee_headers=None,
                 orgenhet_path=None,
                 orgenhet_headers=None,
                 stilling_path=None,
                 stilling_headers=None,
                 use_sessions=True):
        """
        SAP API client.

        :param str url: Base API URL
        :param dict employee_api: employee API config
        :param dict orgenhet_api: organisational API config
        :param dict stilling_api: stilling API config
        :param dict headers: Append extra headers to all requests
        :param bool use_sessions: Keep HTTP connections alive (default True)
        """
        self.urls = SapEndpoints(
            url=url,
            employee_path=employee_path,
            orgenhet_path=orgenhet_path,
            stilling_path=stilling_path,
        )
        self.headers = merge_dicts(self.default_headers, headers)
        self.api_headers = {
            'employee': employee_headers,
            'orgenhet': orgenhet_headers,
            'stilling': stilling_headers,
        }
        if use_sessions:
            self.session = requests.Session()
        else:
            self.session = requests

    def call(self,
             method_name,
             url,
             headers=None,
             params=None,
             return_response=True,
             **kwargs):
        headers = merge_dicts(self.headers, headers)
        if params is None:
            params = {}
        logger.debug('Calling %s %s with params=%r',
                     method_name,
                     urlparse(url).path,
                     params)
        r = self.session.request(method_name,
                                 url,
                                 headers=headers,
                                 params=params,
                                 **kwargs)
        if r.status_code in (500, 400, 401, 404):
            logger.warning('Got HTTP %d: %r for url: %s',
                           r.status_code,
                           r.content, url)
        if return_response:
            return r
        r.raise_for_status()
        return r.json()

    def get(self, url, **kwargs):
        return self.call('GET', url, **kwargs)

    def put(self, url, **kwargs):
        return self.call('PUT', url, **kwargs)

    # def get_employee(self, employee_id: str) -> [None, dict]:
    def get_employee(self, employee_id):
        url = self.urls.get_employee(employee_id)
        headers = merge_dicts(self.headers, self.api_headers['employee'])
        response = self.get(url, headers=headers)
        if response.status_code == 404:
            return None
        if response.status_code == 200:
            data = response.json()
            return data.get('ansatt', None)
        response.raise_for_status()

    # def get_orgenhet(self, org_id: str) -> [None, dict]:
    def get_orgenhet(self, org_id):
        url = self.urls.get_orgenhet(org_id)
        headers = merge_dicts(self.headers, self.api_headers['orgenhet'])
        response = self.get(url, headers=headers)
        if response.status_code == 404:
            return None
        if response.status_code == 200:
            data = response.json()
            return data.get('organisasjon', None)
        response.raise_for_status()

    # def get_stilling(self, stilling_id: str) -> [None, dict]:
    def get_stilling(self, stilling_id):
        url = self.urls.get_stilling(stilling_id)
        headers = merge_dicts(self.headers, self.api_headers['stilling'])
        response = self.get(url, headers=headers)
        if response.status_code == 404:
            return None
        if response.status_code == 200:
            data = response.json()
            return data.get('stilling', None)
        response.raise_for_status()


class DictEntry(Configuration):
    """Represents a key-value element"""
    key = ConfigDescriptor(String, doc='key')
    value = ConfigDescriptor(String, doc='value')


class SapClientApi(Configuration):
    path = ConfigDescriptor(
        String,
        default=None,
        doc='Relative path to this API',
    )

    auth = ConfigDescriptor(
        String,
        default=None,
        doc='Auth key/token to use for this API',
    )


class SapClientConfig(Configuration):
    """The configuration for the dfo module"""
    url = ConfigDescriptor(String, default='http://localhost')
    employee_api = ConfigDescriptor(Namespace, config=SapClientApi)
    orgenhet_api = ConfigDescriptor(Namespace, config=SapClientApi)
    stilling_api = ConfigDescriptor(Namespace, config=SapClientApi)
    headers = ConfigDescriptor(Iterable,
                               default=[],
                               template=Namespace(config=DictEntry))
    use_sessions = ConfigDescriptor(Boolean,
                                    default=True)


def get_client(config):
    """Get a SapClient from configuration"""
    api_key_header = 'X-Gravitee-Api-Key'

    kwargs = {
        'url': config.url,
        'headers': config.headers or {},
        'use_sessions': config.use_sessions,
    }

    # set <name>_path and <name>_headers from api namespaces
    for name, api_config in (
            ('employee', config.employee_api),
            ('orgenhet', config.orgenhet_api),
            ('stilling', config.stilling_api),):
        if api_config.path:
            kwargs[name + '_path'] = api_config.path
        if api_config.auth:
            kwargs.setdefault(name + '_headers', {}).update({
                api_key_header: api_config.auth,
            })

    return SapClient(**kwargs)
