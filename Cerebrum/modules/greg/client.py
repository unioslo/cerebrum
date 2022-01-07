# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
Client for communicating with the Greg API.

To get a client:

::

    # from dict
    config_d = {'url': 'http://localhost/api',
               'auth': 'plaintext:my-api-key'}
    client = get_client(config_d)

    # from config object
    config = GregClientConfig(config_d)
    client = get_client(config)

    # most convenient: from file
    filename = 'greg-config.yml'
    client = get_client(filename)
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
from six.moves.urllib.parse import parse_qsl, urlsplit

from Cerebrum.config import loader
from Cerebrum.config.configuration import Configuration, ConfigDescriptor
from Cerebrum.config.secrets import Secret, get_secret_from_string
from Cerebrum.config.settings import String
from Cerebrum.utils import http as http_utils

logger = logging.getLogger(__name__)


class GregEndpoints(object):
    """ Greg API endpoints.  """

    def __init__(self, url):
        """
        :param url: baseurl to the Greg API
        """
        self.baseurl = url

    def __repr__(self):
        return ('{cls.__name__}({obj.baseurl!r})').format(cls=type(self),
                                                          obj=self)

    @property
    def health(self):
        """ url to health check endpoint. """
        return http_utils.urljoin(self.baseurl, 'health/')

    @property
    def orgunits(self):
        """ baseurl for, and url to list/search orgunits """
        return http_utils.urljoin(self.baseurl, 'v1/orgunits')

    @property
    def persons(self):
        """ baseurl for, and url to list/search persons """
        return http_utils.urljoin(self.baseurl, 'v1/persons')

    def get_orgunit(self, greg_id):
        """ url to a specific person """
        return http_utils.urljoin(self.orgunits,
                                  http_utils.safe_path(greg_id))

    def get_person(self, greg_id):
        """ url to a specific person """
        return http_utils.urljoin(self.persons,
                                  http_utils.safe_path(greg_id))


class GregClient(object):
    """ Greg API client.  """

    default_headers = {
        'Accept': 'application/json',
    }

    def __init__(self, url, headers=None, use_sessions=True):
        """
        :param str url: API URL
        :param dict headers: Headers to apply to all requests
        :param bool use_sessions: Keep HTTP connections alive (default True)
        """
        self.urls = GregEndpoints(url)
        self.headers = http_utils.merge_headers(self.default_headers, headers)
        if use_sessions:
            self._session = requests.Session()
        else:
            self._session = requests

    @property
    def use_sessions(self):
        return self._session is not requests

    def _is_api_response(self, response):
        """
        Check if response is actually from the Greg API, and not a proxy.

        This is typically needed for non-2xx responses that carry special
        meaning in the API.
        """
        return 'X-Greg-Response-For' in response.headers

    def _call(self,
              method_name,
              url,
              headers=None,
              params=None,
              **kwargs):
        """ Send an HTTP request to the API.  """
        headers = http_utils.merge_headers(self.headers, headers)
        params = {} if params is None else params
        return self._session.request(method_name,
                                     url,
                                     headers=headers,
                                     params=params,
                                     **kwargs)

    def _get_object(self, url):
        """ fetch a single object at the given greg url """
        response = self._call('GET', url, headers=self.headers)
        from_api = self._is_api_response(response)
        if response.status_code == 404 and from_api:
            return None
        if response.status_code == 200:
            return response.json()
        response.raise_for_status()

    def _list_objects(self, url, params):
        """ fetch all available objects at the given greg url """
        response = self._call('GET', url, headers=self.headers, params=params)

        while response:
            response.raise_for_status()
            data = response.json()
            results = data.pop('results')
            next_page = data.pop('next', None)

            for obj in results:
                yield obj

            if next_page:
                next_q = urlsplit(url).query
                params = dict(parse_qsl(next_q))
                response = self._call('GET', url, headers=self.headers,
                                      params=params)
            else:
                response = None

    def get_health(self):
        """ get health status """
        url = self.urls.health
        response = self._call('GET', url, headers=self.headers)
        response.raise_for_status()
        from_api = self._is_api_response(response)
        is_ok = from_api and response.text == 'OK'
        if not is_ok:
            logger.warning('greg health: %s', response.text)
        return is_ok

    def get_orgunit(self, greg_id):
        """ get orgunit by id """
        return self._get_object(self.urls.get_orgunit(greg_id))

    def get_person(self, greg_id):
        """ get person by id """
        return self._get_object(self.urls.get_person(greg_id))

    def list_orgunits(self):
        """ list orgunits """
        url = self.urls.orgunits
        return self._list_objects(url, {})

    def list_persons(self, active=None, verified=None,
                     first_name=None, last_name=None):
        """ list/search persons """
        url = self.urls.persons
        params = {
            key: value
            for key, value in (
                ('active', active),
                ('verified', verified),
                ('first_name', first_name),
                ('last_name', last_name),
            ) if value is not None
        }
        return self._list_objects(url, params)


class GregClientConfig(Configuration):
    """
    Greg API client config.

    Example YAML-config:

    ::

        url: "http://localhost/api"
        auth: "plaintext:secret"

    url
        URL to a Greg API.  If the health check endpoint is at
        https://example.org/subpath/health/, then *url* should be set to
        https://example.org/subpath

    auth
        API auth secret (api key/header value) to access Greg.  See
        py:class:`Cerebrum.config.secrets.Secrets` for details.
    """
    url = ConfigDescriptor(
        String,
        default='http://localhost',
        doc='URL to a Greg API',
    )

    auth = ConfigDescriptor(
        Secret,
        doc='Auth token for the Greg API',
    )


def get_client(config):
    """
    Get a GregClient from a GregClientConfig.

    :type config: str, dict, GregClientConfig
    :param config: Client config (filename, config dict, config object)

    :rtype: GregClient
    """
    if isinstance(config, dict):
        config = GregClientConfig(config)
    elif isinstance(config, six.string_types):
        config = GregClientConfig(loader.read_config(config))
    # else - assume already a GregClientConfig

    config.validate()

    api_key_header = 'X-Gravitee-Api-Key'
    api_key_value = get_secret_from_string(config.auth)

    kwargs = {
        'url': config.url,
        'headers': {
            api_key_header: api_key_value,
        },
    }

    return GregClient(**kwargs)
