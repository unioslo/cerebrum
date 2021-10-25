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
"""
from __future__ import absolute_import, division, unicode_literals

import logging

import requests

from Cerebrum.config.configuration import (Configuration,
                                           ConfigDescriptor)
from Cerebrum.config.secrets import Secret, get_secret_from_string
from Cerebrum.config.settings import String
from Cerebrum.utils import http as http_utils

logger = logging.getLogger(__name__)


class GregEndpoints(object):
    """ Greg API endpoints.  """

    def __init__(self, url):
        self.baseurl = url

    def __repr__(self):
        return ('{cls.__name__}({obj.baseurl!r})').format(cls=type(self),
                                                          obj=self)

    def get_person(self, person_id):
        return http_utils.urljoin(self.baseurl, 'v1/persons',
                                  http_utils.safe_path(person_id))


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
        # TODO: Need to implement a check (typically a header check) to verify
        # if this response is actually from the Greg-API.
        raise NotImplementedError("Check if response is from API or proxy")

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

    def get_person(self, greg_pid):
        """ Look up a person by id. """
        url = self.urls.get_person(greg_pid)
        response = self._call('GET', url, headers=self.headers)
        from_api = self._is_api_response(response)
        if response.status_code == 404 and from_api:
            return None
        if response.status_code == 200:
            data = response.json()
            return data['guest']
        response.raise_for_status()


class GregClientConfig(Configuration):
    """ Greg API client config. """

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
    """ Get a GregClient from a GregClientConfig. """
    api_key_header = 'X-Gravitee-Api-Key'
    api_key_value = get_secret_from_string(config.auth)

    kwargs = {
        'url': config.url,
        'headers': {
            api_key_header: api_key_value,
        },
    }

    return GregClient(**kwargs)
