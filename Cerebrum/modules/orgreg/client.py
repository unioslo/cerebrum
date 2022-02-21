# -*- coding: utf-8 -*-
#
# Copyright 2022 University of Oslo, Norway
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
Client for communicating with the Orgreg API.

Use py:func:`.get_client` to get a client object from config:

::

    client = get_client({
        'url': 'http://localhost/api',
        'auth': 'plaintext:my-api-key',
    })
    # or
    client = get_client('my-config-file.yml')

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
from Cerebrum.config.configuration import Configuration, ConfigDescriptor
from Cerebrum.config.secrets import Secret, get_secret_from_string
from Cerebrum.config.settings import String
from Cerebrum.utils import http as http_utils

logger = logging.getLogger(__name__)


class OrgregEndpoints(object):
    """ Orgreg API endpoints.  """

    def __init__(self, url):
        """
        :param url: baseurl to the Orgreg API
        """
        self.baseurl = url

    def __repr__(self):
        return ('{cls.__name__}({obj.baseurl!r})').format(cls=type(self),
                                                          obj=self)

    @property
    def version(self):
        """ url to current orgreg version endpoint. """
        return http_utils.urljoin(self.baseurl, 'v3/version')

    @property
    def orgunits(self):
        """ url to list all org_units. """
        return http_utils.urljoin(self.baseurl, 'v3/ou')

    def get_org_unit(self, orgreg_id):
        """ url to a specific org unit"""
        return http_utils.urljoin(self.orgunits,
                                  http_utils.safe_path(orgreg_id))

    def search_location_code(self, code):
        return http_utils.urljoin(self.orgunits, 'search/legacy_stedkode',
                                  http_utils.safe_path(code))


class OrgregClient(object):
    """ Orgreg API client.  """

    default_headers = {
        'Accept': 'application/json',
    }

    def __init__(self, url, headers=None, use_sessions=True):
        """
        :param str url: baseurl to the Orgreg API
        :param dict headers: Headers to apply to all requests
        :param bool use_sessions: Keep HTTP connections alive (default True)
        """
        self.urls = OrgregEndpoints(url)
        self.headers = http_utils.merge_headers(self.default_headers, headers)
        if use_sessions:
            self._session = requests.Session()
        else:
            self._session = requests

    def __repr__(self):
        return ('<{cls.__name__} {obj.urls.baseurl}>').format(cls=type(self),
                                                              obj=self)

    @property
    def use_sessions(self):
        return self._session is not requests

    def _is_api_response(self, response):
        """
        Check if response is actually from the Orgreg API, and not a proxy.

        This is typically needed for non-2xx responses that carry special
        meaning in the API.
        """
        return 'X-OrgReg-Response-For' in response.headers

    def _req(self,
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

    def get_version(self):
        """ Get Orgreg health check. """
        url = self.urls.version
        response = self._req('GET', url)
        response.raise_for_status()
        return response.json()

    def list_org_units(self):
        """ List all org units. """
        url = self.urls.orgunits
        response = self._req('GET', url)
        response.raise_for_status()
        return response.json()

    def get_org_unit(self, orgreg_id):
        """ Look up a org unit by id. """
        url = self.urls.get_org_unit(orgreg_id)
        response = self._req('GET', url)
        from_api = self._is_api_response(response)
        if response.status_code == 404 and from_api:
            return None
        response.raise_for_status()
        return response.json()


class OrgregClientConfig(Configuration):
    """ Orgreg API client config. """

    url = ConfigDescriptor(
        String,
        default='http://localhost',
        doc='URL to an Orgreg API',
    )

    auth = ConfigDescriptor(
        Secret,
        doc='Auth token for the Orgreg API',
    )


def get_client(config):
    """
    Get an OrgregClient from config.

    :type config: str, dict, OrgregClientConfig
    :param config: Client config (filename, config dict, config object)

    :rtype: OrgregClient
    """
    if isinstance(config, six.string_types):
        config = OrgregClientConfig(loader.read_config(config))
    elif isinstance(config, dict):
        config = OrgregClientConfig(config)
    elif not isinstance(config, OrgregClientConfig):
        raise ValueError('invalid config: ' + repr(config))

    config.validate()

    api_key_header = 'X-Gravitee-Api-Key'
    api_key_value = get_secret_from_string(config.auth)

    kwargs = {
        'url': config.url,
        'headers': {
            api_key_header: api_key_value,
        },
    }

    return OrgregClient(**kwargs)


def main():
    """
    A very basic cli client.

    python -m Cerebrum.modules.orgreg.client <config>
        list all org units

    python -m Cerebrum.modules.orgreg.client <config> <orgreg-id>
        fetch one org unit
    """
    import json
    import sys

    def cli_error(*msg):
        print("Usage:",
              "python -m Cerebrum.modules.orgreg.client <config> [orgreg-id]",
              file=sys.stderr)
        print("", file=sys.stderr)
        print("Error:", *msg, file=sys.stderr)
        raise SystemExit(1)

    try:
        config_file = sys.argv[1]
    except IndexError:
        cli_error("missing mandatory argument: config")

    try:
        orgreg_id = int(sys.argv[2])
    except IndexError:
        orgreg_id = None
    except ValueError:
        cli_error("invalid orgreg-id:", repr(sys.argv[2]))

    client = get_client(config_file)
    if orgreg_id:
        result = client.get_org_unit(orgreg_id)
    else:
        result = client.list_org_units()

    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
