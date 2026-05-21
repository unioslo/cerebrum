# encoding: utf-8
"""
Tests for mod:`Cerebrum.modules.greg.client`

TODO: Add proper test requirements, and test actual client calls using
`requests-mock`?
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import pytest

from Cerebrum.modules.greg import client
from Cerebrum.testutils import file_utils


#
# GregEndpoints tests
#


BASEURL = "http://localhost/greg"


@pytest.fixture
def endpoints():
    return client.GregEndpoints(BASEURL)


def test_endpoints_health(endpoints):
    assert endpoints.health == BASEURL + "/health/"


def test_endpoints_orgunits(endpoints):
    assert endpoints.orgunits == BASEURL + "/v1/orgunits"


def test_endpoints_persons(endpoints):
    assert endpoints.persons == BASEURL + "/v1/persons"


@pytest.mark.parametrize(
    "greg_id, path",
    [
        (3, "/v1/orgunits/3"),
        ("a b", "/v1/orgunits/a+b"),
        ("3/secrets", "/v1/orgunits/3%2Fsecrets"),
    ],
)
def test_endpoints_get_orgunit(endpoints, greg_id, path):
    assert endpoints.get_orgunit(greg_id) == BASEURL + path


@pytest.mark.parametrize(
    "greg_id, path",
    [
        (3, "/v1/persons/3"),
        ("a b", "/v1/persons/a+b"),
        ("3/secrets", "/v1/persons/3%2Fsecrets"),
    ],
)
def test_endpoints_get_person(endpoints, greg_id, path):
    assert endpoints.get_person(greg_id) == BASEURL + path


#
# GregClient tests
#
# TODO: We need to mock away requests and test actual calls
#

def test_client_init():
    greg = client.GregClient(
        BASEURL,
        headers={'X-Foo': "bar"},
        use_sessions=False,
    )
    assert greg.urls.baseurl == BASEURL
    assert greg.headers['Accept'] == "application/json"
    assert greg.headers['X-Foo'] == "bar"
    assert not greg.use_sessions


def test_client_repr():
    greg = client.GregClient(BASEURL)
    repr_value = repr(greg)
    assert repr_value == "<GregClient " + BASEURL + ">"


#
# GregClientConfig tests
#


@pytest.fixture
def config_data():
    return {
        "url": BASEURL,
        "auth": "plaintext:hunter2",
        "auth_header": "X-Token",
    }


@pytest.fixture
def config_obj(config_data):
    return client.GregClientConfig(config_data)


def _check_client_config(client):
    auth_header = "X-Token"
    return (
        client.urls.baseurl == BASEURL
        and client.headers.get(auth_header) == "hunter2"
    )


def test_config_init(config_data):
    config = client.GregClientConfig(config_data)
    assert config.url == config_data['url']
    assert config.auth == config_data['auth']
    assert config.auth_header == config_data['auth_header']


def test_get_client_from_config(config_obj):
    greg = client.get_client(config_obj)
    assert _check_client_config(greg)


def test_get_client_from_dict(config_data):
    greg = client.get_client(config_data)
    assert _check_client_config(greg)


@pytest.fixture(scope='module')
def config_dir():
    with file_utils.tempdir_ctx(prefix="test-greg-client") as path:
        yield path


@pytest.fixture
def config_file(config_dir, config_data):
    with file_utils.tempfile_ctx(config_dir, suffix=".json") as filename:
        file_utils.write_json(filename, config_data)
        yield filename


def test_get_client_from_file(config_file):
    greg = client.get_client(config_file)
    assert _check_client_config(greg)


def test_get_client_from_invalid_value():
    with pytest.raises(ValueError):
        client.get_client(None)
