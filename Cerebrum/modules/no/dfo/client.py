# -*- coding: utf-8 -*-
#
# Copyright 2020-2023 University of Oslo, Norway
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


Example config
--------------
The basic config layout.  At least the ``url`` and the APIs that are to be used
must be configured.

.. code-block:: yaml

    url: "http://localhost:8080/api"
    employee_api:
      path: "employees/"
      auth: "plaintext:super-secret-key"
    orgenhet_api:
      path: "orgunits/"
      auth: "plaintext:super-secret-key"
    stilling_api:
      path: "assignments/"
      auth: "plaintext:super-secret-key"
    headers:
      "X-Foo": "Bar"
      "User-Agent": "cerebrum"
    use_sessions: true

Example use
-----------
To use the client:
::

    client = get_client("client.yml")
    employee = client.get_employee(employee_id)

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import requests
import six

from Cerebrum.config import loader
from Cerebrum.config.configuration import (Configuration,
                                           ConfigDescriptor,
                                           Namespace)
from Cerebrum.config.secrets import Secret, get_secret_from_string
from Cerebrum.config.settings import Boolean, Iterable, String
from Cerebrum.utils import http as http_utils
from Cerebrum.utils import reprutils

logger = logging.getLogger(__name__)


class SapEndpoints(reprutils.ReprEvalMixin):
    """Get endpoints relative to the SAP API URL."""

    repr_id = False
    repr_module = False
    repr_args = ('baseurl',)
    repr_kwargs = ('employee_path', 'orgunit_path', 'assignment_path')

    default_employee_path = 'ansatte/v2'
    default_orgunit_path = 'orgenhet/v2'
    default_assignment_path = 'stillinger/v2'

    def __init__(self,
                 url,
                 employee_path=None,
                 orgunit_path=None,
                 assignment_path=None):
        self.baseurl = url
        self.employee_path = employee_path or self.default_employee_path
        self.orgunit_path = orgunit_path or self.default_orgunit_path
        self.assignment_path = assignment_path or self.default_assignment_path

    @property
    def employees_url(self):
        return http_utils.urljoin(self.baseurl, self.employee_path)

    def get_employee_url(self, employee_id):
        return http_utils.urljoin(
            self.employees_url,
            http_utils.safe_path(int(employee_id)))

    def get_orgunit_url(self, org_id):
        return http_utils.urljoin(
            self.baseurl,
            self.orgunit_path,
            http_utils.safe_path(int(org_id)))

    @property
    def assignments_url(self):
        return http_utils.urljoin(self.baseurl, self.assignment_path)

    def get_assignment_url(self, stilling_id):
        return http_utils.urljoin(
            self.assignments_url,
            http_utils.safe_path(int(stilling_id)))


class SapClient(reprutils.ReprFieldMixin):

    repr_id = False
    repr_module = False
    repr_fields = ('urls',)

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
            orgunit_path=orgenhet_path,
            assignment_path=stilling_path,
        )
        self.headers = http_utils.merge_headers(self.default_headers, headers)
        self.api_headers = {
            'employee': employee_headers,
            'orgunit': orgenhet_headers,
            'assignment': stilling_headers,
        }
        if use_sessions:
            self.session = requests.Session()
        else:
            self.session = requests

    def _is_api_response(self, response):
        """
        Check if response is actually from the DFØ API, and not a proxy.

        This is typically needed for non-2xx responses that carry special
        meaning in the API.
        """
        return "SAP" in response.headers.get('server', '')

    def _prepare_headers(self, api, date=None):
        api_headers = dict(self.api_headers[api])
        extra_headers = {}
        if date:
            extra_headers['dato'] = date.isoformat()
        return http_utils.merge_headers(api_headers, extra_headers)

    def call(self,
             method_name,
             url,
             headers=None,
             params=None,
             return_response=True,
             **kwargs):
        headers = http_utils.merge_headers(self.headers, headers)
        params = params or {}
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

    def get_employee(self, employee_id, date=None):
        url = self.urls.get_employee_url(employee_id)
        headers = self._prepare_headers('employee', date=date)
        response = self.get(url, headers=headers)
        if not self._is_api_response(response):
            response.raise_for_status()
        if response.status_code == 404:
            return None
        if response.status_code == 200:
            data = response.json()
            return data.get('ansatt', None)
        response.raise_for_status()

    def list_employees(self, date=None):
        url = self.urls.employees_url
        headers = self._prepare_headers('employee', date=date)
        response = self.get(url, headers=headers)
        if not self._is_api_response(response):
            response.raise_for_status()
        response.raise_for_status()
        data = response.json()
        return data.get('ansatt') or []

    # TODO rename to get_orgunit
    def get_orgenhet(self, org_id, date=None):
        url = self.urls.get_orgunit_url(org_id)
        headers = self._prepare_headers('orgunit', date=date)
        response = self.get(url, headers=headers)
        if response.status_code == 404:
            return None
        if response.status_code == 200:
            data = response.json()
            return data.get('organisasjon', None)
        response.raise_for_status()

    # TODO: rename to get_assignment
    def get_stilling(self, stilling_id, date=None):
        url = self.urls.get_assignment_url(stilling_id)
        headers = self._prepare_headers('assignment', date=date)
        response = self.get(url, headers=headers)
        if response.status_code == 404:
            return None
        if response.status_code == 200:
            data = response.json()
            return data.get('stilling', None)
        response.raise_for_status()

    def list_assignments(self, date=None):
        url = self.urls.assignments_url
        headers = self._prepare_headers('assignment', date=date)
        response = self.get(url, headers=headers)
        if not self._is_api_response(response):
            response.raise_for_status()
        response.raise_for_status()
        data = response.json()
        return data.get('stilling') or []


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
        Secret,
        doc='Auth token for this API',
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
    if isinstance(config, dict):
        config = SapClientConfig(config)
    elif isinstance(config, six.string_types):
        config = SapClientConfig(loader.read_config(config))

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
                api_key_header: get_secret_from_string(api_config.auth),
            })

    return SapClient(**kwargs)
