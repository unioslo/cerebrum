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
Client for communicating with the SAP HTTP-API @ UiO.

History
-------
This client is forked from the ``sap_client.client`` module @
`<https://bitbucket.usit.uio.no/projects/INT/repos/sap-client/>`_.
"""
from __future__ import unicode_literals

import logging

import requests
import six
from six.moves.urllib.parse import (
    quote_plus,
    urlparse,
    urljoin as _urljoin,
)

from Cerebrum.config.configuration import (
    Configuration,
    ConfigDescriptor,
)
from Cerebrum.config.secrets import Secret, get_secret_from_string
from Cerebrum.config.settings import String

logger = logging.getLogger(__name__)


def get_deferred(dct):
    """ Get an url from a dict-like object.

    The dict like object should contain:

        {'__deferred': {'uri': '...'}}
    """
    return dct['__deferred']['uri']


def quote_path_arg(arg):
    return quote_plus(six.text_type(arg))


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


class SapEndpoints(object):
    """Get endpoints relative to the SAP API URL."""

    def __init__(self, url):
        self.baseurl = url

    def __repr__(self):
        return '{cls.__name__}({url!r})'.format(
            cls=type(self),
            url=self.baseurl)

    def list_locations(self):
        """ Endpoint to list locations. """
        return urljoin(self.baseurl, 'locations')

    def get_location(self, location_id):
        """ Endpoint to get location data. """
        location_id = quote_path_arg(location_id)
        path = 'locations({location_id})'.format(location_id=location_id)
        return urljoin(self.baseurl, path)

    def get_parent_location(self, location_id):
        """ Endpoint to get parent location data of a location. """
        location_url = self.get_location(location_id)
        return urljoin(location_url, 'parent')

    def get_employee(self, person_id):
        """ Endpoint to get employee data. """
        person_id = quote_path_arg(person_id)
        path = 'employees({person_id})'.format(person_id=person_id)
        return urljoin(self.baseurl, path)

    def get_employee_assignments(self, person_id):
        employee_url = self.get_employee(person_id)
        return urljoin(employee_url, 'assignments')

    def get_employee_roles(self, person_id):
        employee_url = self.get_employee(person_id)
        return urljoin(employee_url, 'roles')


class SapClient(object):

    default_headers = {
        'Accept': 'application/json',
    }

    def __init__(self,
                 url,
                 headers=None,
                 use_sessions=True):
        """
        SAP API client.

        :param str url: Base API URL
        :param dict headers: Append extra headers to all requests
        :param bool use_sessions: Keep HTTP connections alive (default True)
        """
        self.urls = SapEndpoints(url)
        self.headers = merge_dicts(self.default_headers, headers)
        if use_sessions:
            self.session = requests.Session()
        else:
            self.session = requests

    def call(self,
             method_name,
             url,
             headers=None,
             params=None,
             **kwargs):
        headers = merge_dicts(self.headers, headers)
        params = params or {}
        logger.debug('Calling %s %s with params=%r',
                     method_name, urlparse(url).path, params)
        return self.session.request(method_name,
                                    url,
                                    headers=headers,
                                    params=params,
                                    **kwargs)

    def get(self, url, **kwargs):
        r = self.call('GET', url, **kwargs)
        # Verify that request hit the actual SAP server, and has not been
        # rejected at any reverse-proxy.
        if ('sap-server' not in r.headers or
                r.headers['sap-server'] != 'true'):
            logger.warning('missing sap header: %r', r.headers)
            logger.debug('response: %r', r)
            logger.debug('body: %r', r.text)
            raise RuntimeError('Invalid response from server')
        return r

    def get_location(self, location_id):
        url = self.urls.get_location(location_id)
        response = self.get(url)
        if response.status_code == 200:
            data = response.json().get('d')
            return data
        if response.status_code == 404:
            return None
        response.raise_for_status()

    def list_locations(self):
        url = self.urls.list_locations()
        response = self.get(url)
        if response.status_code == 200:
            results = response.json().get('d', {}).get('results')
            for data in results:
                yield data
        response.raise_for_status()

    def get_parent_location(self, location):
        if isinstance(location, dict):
            url = get_deferred(location['parent'])
        elif isinstance(location, six.text_type):
            url = self.urls.get_parent_location(location)
        else:
            raise TypeError('ou must be ou id or ou dict')
        if not url:
            return None
        response = self.get(url)
        if response.status_code == 200:
            data = response.json().get('d')
            return data
        if response.status_code == 404:
            return None
        response.raise_for_status()

    def get_tree_parents(self, ou):
        assert ou
        tmp = ou
        r = []
        while tmp:
            r.append(tmp)
            tmp = self.get_parent_location(tmp)
        return r

    def get_employee(self, employee_id):
        url = self.urls.get_employee(employee_id)
        response = self.get(url)
        if response.status_code == 404:
            return None
        elif response.status_code == 200:
            data = response.json().get('d')
            return data
        response.raise_for_status()

    def get_assignments(self, employee):
        if isinstance(employee, dict):
            url = get_deferred(employee['assignments'])
        elif isinstance(employee, six.text_type):
            url = self.urls.get_employee_assignments(employee)
        else:
            raise TypeError('employee must be employee id or employee dict')

        response = self.get(url)
        if response.status_code == 404:
            return None
        elif response.status_code == 200:
            data = response.json().get('d', {}).get('results')
            return data
        response.raise_for_status()

    def get_roles(self, employee):
        if isinstance(employee, dict):
            url = get_deferred(employee['roles'])
        elif isinstance(employee, six.text_type):
            url = self.urls.get_employee_roles(employee)
        else:
            raise TypeError('employee must be employee id or employee dict')

        response = self.get(url)
        if response.status_code == 404:
            return None
        elif response.status_code == 200:
            data = response.json().get('d', {}).get('results')
            return data
        response.raise_for_status()


class SapClientConfig(Configuration):

    url = ConfigDescriptor(
        String,
        default='http://localhost',
        doc='URL to a SAP API',
    )
    # TODO: Read auth token from file!
    auth = ConfigDescriptor(
        Secret,
        doc='Auth token for the SAP API',
    )


def get_client(config):
    kwargs = {
        'url': config.url,
        'headers': {
            'X-Gravitee-Api-Key': get_secret_from_string(config.auth),
        }
    }
    return SapClient(**kwargs)
