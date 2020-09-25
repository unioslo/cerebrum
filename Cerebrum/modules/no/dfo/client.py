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

import json
import logging
import os
import urlparse

import requests

from Cerebrum.config.configuration import (Configuration,
                                           ConfigDescriptor,
                                           Namespace)
from Cerebrum.config.settings import Boolean, Iterable, String


logger = logging.getLogger(__name__)


def load_json_file(name):
    here = os.path.realpath(
        os.path.join(os.getcwd(),
                     os.path.dirname(__file__).rsplit('/', 1)[0]))
    with open(os.path.join(here, '../tests/fixtures', name)) as f:
        data = json.load(f)
    return data


def get_deferred(dct):
    """ Get an url from a dict-like object.

    The dict like object should contain:

        {'__deferred': {'uri': '...'}}
    """
    return dct['__deferred']['uri']


def quote_path_arg(arg):
    return urlparse.quote_plus(str(arg))


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

    def __init__(self,
                 url,
                 employee_url='ansatte/',
                 orgenhet_url='orgenhet/',
                 stilling_url='stillinger/',
                 kursinfo_url='kursgjennomfoering/',
                 familie_url='ansattefamilie-test/'):
        self.baseurl = url
        self.employee_url = employee_url
        self.orgenhet_url = orgenhet_url
        self.stilling_url = stilling_url
        self.kursinfo_url = kursinfo_url
        self.familie_url = familie_url

    def __repr__(self):
        return '{cls.__name__}({url!r})'.format(
            cls=type(self),
            url=self.baseurl)

    @staticmethod
    def _urljoin(base, path, ident):

        # urlparse and urllib.parse behave differently.
        # Hack to add a trailing slash if it's missing
        if path[-1] != '/':
            path = path + '/'

        return urlparse.urljoin(base, path + str(ident))

    def get_employee(self, employee_id):
        return self._urljoin(self.baseurl, self.employee_url, str(employee_id))

    def get_orgenhet(self, org_id):
        return self._urljoin(self.baseurl, self.orgenhet_url, str(org_id))

    def get_stilling(self, stilling_id):
        return self._urljoin(self.baseurl, self.stilling_url, str(stilling_id))

    def get_familie(self, familie_id):
        return self._urljoin(self.baseurl, self.familie_url, str(familie_id))

    def put_kursinfo(self):
        return urlparse.urljoin(self.baseurl, self.kursinfo_url)


class SapClient(object):
    default_headers = {
        'Accept': 'application/json',
    }

    def __init__(self,
                 url,
                 employee_url=None,
                 orgenhet_url=None,
                 stilling_url=None,
                 kursinfo_url=None,
                 familie_url=None,
                 tokens={},
                 mock=False,
                 headers=None,
                 use_sessions=True):
        """
        SAP API client.

        :param str url: Base API URL
        :param str employee_url: Relative URL to employee API
        :param str orgenhet_url: Relative URL to organisational API
        :param str stilling_url: Relative URL to stillings API
        :param str kursinfo_url: Relative URL to kursinfo API
        :param str familie_url: Relative URL to familie API
        :params dict tokens: Tokens for the different APIs
        :param bool mock: Mock the API or not
        :param dict headers: Append extra headers to all requests
        :param bool use_sessions: Keep HTTP connections alive (default True)
        """
        self.urls = SapEndpoints(url,
                                 employee_url,
                                 orgenhet_url,
                                 stilling_url,
                                 kursinfo_url,
                                 familie_url)
        self.tokens = tokens
        self.mock = mock
        self.headers = merge_dicts(self.default_headers, headers)
        if use_sessions:
            self.session = requests.Session()
        else:
            self.session = requests

    def _build_request_headers(self, headers):
        request_headers = {}
        for h in self.headers:
            request_headers[h] = self.headers[h]
        for h in (headers or ()):
            request_headers[h] = headers[h]
        return request_headers

    def call(self,
             method_name,
             url,
             headers=None,
             params=None,
             return_response=True,
             **kwargs):
        headers = self._build_request_headers(headers)
        if params is None:
            params = {}
        logger.debug('Calling %s %s with params=%r',
                     method_name,
                     urlparse.urlparse(url).path,
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

    # def object_or_data(self, cls, data) -> [object, dict]:
    def object_or_data(self, cls, data):
        if not self.return_objects:
            return data
        return cls.from_dict(data)

    # def get_employee(self, employee_id: str) -> [None, dict]:
    def get_employee(self, employee_id):
        url = self.urls.get_employee(employee_id)
        if self.mock:
            return load_json_file('employee_00101223.json')
        response = self.get(url,
                            headers=self.tokens.get('employee_api',
                                                    None))
        if response.status_code == 404:
            return None
        if response.status_code == 200:
            data = response.json()
            return data.get('ansatt', None)
        response.raise_for_status()

    # def get_orgenhet(self, org_id: str) -> [None, dict]:
    def get_orgenhet(self, org_id):
        if self.mock:
            return load_json_file('org_5001234.json')
        url = self.urls.get_orgenhet(org_id)
        response = self.get(url,
                            headers=self.tokens.get('orgenhet_api',
                                                    None))
        if response.status_code == 404:
            return None
        if response.status_code == 200:
            data = response.json()
            return data.get('organisasjon', None)
        response.raise_for_status()

    # def get_stilling(self, stilling_id: str) -> [None, dict]:
    def get_stilling(self, stilling_id):
        if self.mock:
            return load_json_file('stilling_30045705.json')
        url = self.urls.get_stilling(stilling_id)
        response = self.get(url,
                            headers=self.tokens.get(
                                'stilling_api',
                                None))
        if response.status_code == 404:
            return None
        if response.status_code == 200:
            data = response.json()
            return data.get('stilling', None)
        response.raise_for_status()

    # def get_familie(self, employee_id: str) -> [None, dict]:
    def get_familie(self, employee_id):
        if self.mock:
            return load_json_file('familie_00101223.json')
        url = self.urls.get_familie(employee_id)
        response = self.get(url,
                            headers=self.tokens.get(
                                'familie_api',
                                None))
        if response.status_code == 404:
            return None
        if response.status_code == 200:
            data = self.transform_familie(response.json())
            return data.get('AnsattFamilie', None)
        response.raise_for_status()

    def transform_familie(self, data):
        if 'kontaktpersICE' in data['AnsattFamilie']:
            if data['AnsattFamilie']['kontaktpersICE'] is not None:
                if data['AnsattFamilie']['kontaktpersICE'].lower() == "ja":
                    data['AnsattFamilie']['kontaktpersICE'] = True
                else:
                    data['AnsattFamilie']['kontaktpersICE'] = False
        else:
            # If value is missing from json set it to None
            data['AnsattFamilie']['kontaktpersICE'] = None

        if 'narmesteFamilie' in data['AnsattFamilie']:
            if data['AnsattFamilie']['narmesteFamilie'] is not None:
                if data['AnsattFamilie']['narmesteFamilie'].lower() == "ja":
                    data['AnsattFamilie']['narmesteFamilie'] = True
                else:
                    data['AnsattFamilie']['narmesteFamilie'] = False
        else:
            # If value is missing from json set it to None
            data['AnsattFamilie']['narmesteFamilie'] = None
        return data

    # def put_kursinformasjon(self, kursinfo: Kursinformasjon) -:
    def put_kursinformasjon(self, kursinfo):
        """PUT kursinfo to the appropriate API endpoint"""

        data = kursinfo.json(by_alias=True)
        url = self.urls.put_kursinfo()
        token = self.tokens.get('kursinfo_api', None)
        headers = {'Content-Type': 'application/json',
                   "accept": "application/json"}
        headers.update(token)

        if self.mock:
            return "MOCK - PUT: {} to {} with headers {}".format(
                data,
                url,
                headers
            )
        response = self.put(url,
                            data=data,
                            headers=headers)
        if response.status_code == 404:
            return None
        if response.status_code == 200:
            return "Modified successfully"
        if response.status_code == 201:
            return "Created successfully"
        response.raise_for_status()


class DictEntry(Configuration):
    """Represents a key-value element"""
    key = ConfigDescriptor(String, doc='key')
    value = ConfigDescriptor(String, doc='value')


class SapClientConfig(Configuration):
    """The configuration for the dfo module"""
    url = ConfigDescriptor(String, default='http://localhost')
    employee_url = ConfigDescriptor(String, default='http://localhost')
    orgenhet_url = ConfigDescriptor(String, default='http://localhost')
    stilling_url = ConfigDescriptor(String, default='http://localhost')
    kursinfo_url = ConfigDescriptor(String, default='http://localhost')
    familie_url = ConfigDescriptor(String, default='http://localhost')
    tokens = ConfigDescriptor(Iterable,
                              default=[],
                              template=Namespace(config=DictEntry))
    mock = ConfigDescriptor(Boolean,
                            default=False)
    headers = ConfigDescriptor(Iterable,
                               default=[],
                               template=Namespace(config=DictEntry))
    use_sessions = ConfigDescriptor(Boolean,
                                    default=True)


def get_client(config):
    """Get a SapClient from configuration"""
    return SapClient(**config.dump_dict())
