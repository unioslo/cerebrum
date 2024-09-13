# encoding: utf-8
"""
Tests for mod:`Cerebrum.modules.orgreg.client`

TODO: Add proper test requirements, and test actual client calls using
`requests-mock`?
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import json
import os
import tempfile
import shutil
import pytest

from Cerebrum.modules.orgreg import client
from Cerebrum.testutils import file_utils


#
# OrgregEndpoints tests
#


BASEURL = "http://localhost/orgreg"


@pytest.fixture
def endpoints():
    return client.OrgregEndpoints(BASEURL)


def test_endpoints_version(endpoints):
    assert endpoints.version == BASEURL + "/v3/version"


def test_endpoints_orgunits(endpoints):
    assert endpoints.orgunits == BASEURL + "/v3/ou"


@pytest.mark.parametrize(
    "orgreg_id, path",
    [
        (3, "/v3/ou/3"),
        ("a b", "/v3/ou/a+b"),
        ("3/secrets", "/v3/ou/3%2Fsecrets"),
    ],
)
def test_endpoints_get_orgunit(endpoints, orgreg_id, path):
    assert endpoints.get_org_unit(orgreg_id) == BASEURL + path


@pytest.mark.parametrize(
    "code, path",
    [
        (3, "/v3/ou/search/legacy_stedkode/3"),
        ("a b", "/v3/ou/search/legacy_stedkode/a+b"),
        ("3/secrets", "/v3/ou/search/legacy_stedkode/3%2Fsecrets"),
    ],
)
def test_search_location_code(endpoints, code, path):
    assert endpoints.search_location_code(code) == BASEURL + path


#
# OrgregClient tests
#
# TODO: We need to mock away requests and test actual calls
#

def test_client_init():
    orgreg = client.OrgregClient(
        BASEURL,
        headers={'X-Foo': "bar"},
        use_sessions=False,
    )
    assert orgreg.urls.baseurl == BASEURL
    assert orgreg.headers['Accept'] == "application/json"
    assert orgreg.headers['X-Foo'] == "bar"
    assert not orgreg.use_sessions


def test_client_repr():
    orgreg = client.OrgregClient(BASEURL)
    repr_value = repr(orgreg)
    assert repr_value == "<OrgregClient " + BASEURL + ">"


#
# OrgregClientConfig tests
#


@pytest.fixture
def config_data():
    return {
        "url": BASEURL,
        "auth": "plaintext:hunter2",
    }


@pytest.fixture
def config_obj(config_data):
    return client.OrgregClientConfig(config_data)


def _check_client_config(client):
    auth_header = "X-Gravitee-Api-Key"
    return (
        client.urls.baseurl == BASEURL
        and client.headers.get(auth_header) == "hunter2"
    )


def test_config_init(config_data):
    config = client.OrgregClientConfig(config_data)
    assert config.url == config_data['url']
    assert config.auth == config_data['auth']


def test_get_client_from_config(config_obj):
    orgreg = client.get_client(config_obj)
    assert _check_client_config(orgreg)


def test_get_client_from_dict(config_data):
    orgreg = client.get_client(config_data)
    assert _check_client_config(orgreg)


@pytest.fixture(scope='module')
def config_dir():
    with file_utils.tempdir_ctx(prefix="test-orgreg-client") as path:
        yield path


@pytest.fixture
def config_file(config_dir, config_data):
    with file_utils.tempfile_ctx(config_dir, suffix=".json") as filename:
        file_utils.write_json(filename, config_data)
        yield filename


def test_get_client_from_file(config_file):
    orgreg = client.get_client(config_file)
    assert _check_client_config(orgreg)


def test_get_client_from_invalid_value():
    with pytest.raises(ValueError):
        client.get_client(None)
