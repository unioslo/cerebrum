# encoding: utf-8
""" Unit tests for `Cerebrum.modules.event_publisher.scim`. """
import datetime

import pytest

from Cerebrum.modules.event_publisher import scim
from Cerebrum.utils import date as date_utils


class _MockObject(object):

    def __init__(self, **kwargs):
        for k in kwargs:
            setattr(self, k, kwargs[k])


#
# Config tests
#


EXAMPLE_ENTITY_MAP_CONFIG = {
    'entity': "entities",
    'person': "persons",
    'account': "accounts",
    'group': "groups",
    'ou': "ous",
}


ENTITY_TYPE_TESTS = sorted(list(EXAMPLE_ENTITY_MAP_CONFIG.items()))


def test_entity_map_config():
    config = scim.EntityTypeToApiRouteMapConfig()
    config.load_dict(EXAMPLE_ENTITY_MAP_CONFIG)
    config.validate()
    config.dump_dict() == EXAMPLE_ENTITY_MAP_CONFIG


SCIM_ISSUER = "cerebrum-unit-tests"
SCIM_KEY_PREFIX = "localhost.scim"
SCIM_URI_PREFIX = "urn:ietf:params:event:SCIM"
SCIM_URL_PREFIX = "http://localhost"
SCIM_FORMATTER_CONFIG = {
    'issuer': SCIM_ISSUER,
    'urltemplate': SCIM_URL_PREFIX + "/{entity_type}/{entity_id}",
    'keytemplate': SCIM_KEY_PREFIX + ".{entity_type}.{event}",
    'entity_type_map': EXAMPLE_ENTITY_MAP_CONFIG,
    'uri_prefix': SCIM_URI_PREFIX,
}


def test_scim_formatter_config():
    config = scim.ScimFormatterConfig()
    config.load_dict(SCIM_FORMATTER_CONFIG)
    config.validate()
    config.dump_dict() == SCIM_FORMATTER_CONFIG


#
# ScimFormatter tests
#


@pytest.fixture
def scim_formatter():
    config = scim.ScimFormatterConfig()
    config.load_dict(SCIM_FORMATTER_CONFIG)
    config.validate()
    return scim.ScimFormatter(config)


dt_aware_utc = datetime.datetime(1998, 6, 28, 23, 30, 11, 987654,
                                 tzinfo=date_utils.UTC)
dt_timestamp = 899076611


def test_make_timestamp(scim_formatter):
    ts = scim_formatter.make_timestamp(dt_aware_utc)
    assert ts == dt_timestamp


def test_make_timestamp_default(scim_formatter):
    ts = scim_formatter.make_timestamp()
    now = date_utils.to_timestamp(date_utils.utcnow())
    delta = 10  # 10 seconds is good enough for this test
    assert now - ts < delta


@pytest.mark.parametrize(
    "entity_type, slug",
    ENTITY_TYPE_TESTS,
    ids=[t[0] for t in ENTITY_TYPE_TESTS],
)
def test_get_entity_type_route(scim_formatter, entity_type, slug):
    get = scim_formatter.get_entity_type_route
    assert get("account") == "accounts"


def test_get_entity_type_route_default(scim_formatter):
    get = scim_formatter.get_entity_type_route
    assert get("foo") == "entities"


def test_get_uri(scim_formatter):
    get = scim_formatter.get_uri
    assert get("foo") == SCIM_URI_PREFIX + ":foo"


def test_get_key(scim_formatter):
    get = scim_formatter.get_key
    assert get("foo", "bar") == SCIM_KEY_PREFIX + ".foo.bar"


def test_build_url(scim_formatter):
    get = scim_formatter.build_url
    assert get("foo", "bar") == SCIM_URL_PREFIX + "/foo/bar"


#
# EventScimFormatter tests
#


class _MockEntityRef(_MockObject):
    entity_id = 123
    entity_type = "entity"
    ident = None


@pytest.fixture
def event_formatter():
    config = scim.ScimFormatterConfig()
    config.load_dict(SCIM_FORMATTER_CONFIG)
    config.validate()
    return scim.EventScimFormatter(config)


@pytest.mark.parametrize(
    "entity_type, slug",
    ENTITY_TYPE_TESTS,
    ids=[t[0] for t in ENTITY_TYPE_TESTS],
)
def test_get_entity_type(event_formatter, entity_type, slug):
    ref = _MockEntityRef(entity_type=entity_type)
    result = event_formatter.get_entity_type(ref)
    assert result == slug


def test_get_entity_id(event_formatter):
    ref = _MockEntityRef(entity_id=123)
    assert event_formatter.get_entity_id(ref) == "123"


def test_get_entity_id_ident(event_formatter):
    ref = _MockEntityRef(entity_type="account", ident="foo")
    assert event_formatter.get_entity_id(ref) == "foo"


def test_get_url_entity(event_formatter):
    ref = _MockEntityRef(entity_id=123, entity_type="entity")
    assert event_formatter.get_url(ref) == SCIM_URL_PREFIX + "/entities/123"


def test_get_url_acocunt(event_formatter):
    ref = _MockEntityRef(entity_type="account", ident="foo")
    assert event_formatter.get_url(ref) == SCIM_URL_PREFIX + "/accounts/foo"


class _MockEventType(_MockObject):
    verb = "modify"


def test_get_event_key(event_formatter):
    ref = _MockEntityRef(entity_type="account")
    ev = _MockEventType(verb="modify")
    key = event_formatter.get_key(ev, ref)
    assert key == SCIM_KEY_PREFIX + ".accounts.modify"


class _MockEvent(_MockObject):

    event_type = _MockEventType()
    subject = _MockEntityRef()
    objects = set()

    timestamp = None
    scheduled = None

    attributes = set()
    context = set()


def test_format_event_minimal(event_formatter):
    payload = event_formatter(_MockEvent())
    assert set(payload.keys()) == set((
        'aud',
        'eventUris',
        'iat',
        'iss',
        'jti',
        'resourceType',
        'sub',
    ))
    assert payload['aud'] == []
    assert payload['iat']
    assert payload['iss'] == SCIM_ISSUER
    assert payload['jti']
    assert payload['resourceType']


def test_format_event_account_modify(event_formatter):
    ev = _MockEvent(
        event_type=_MockEventType(verb="modify"),
        subject=_MockEntityRef(entity_type="account", ident="foo"),
    )
    payload = event_formatter(ev)
    assert payload['eventUris'] == [SCIM_URI_PREFIX + ":modify"]
    assert payload['sub'] == SCIM_URL_PREFIX + "/accounts/foo"


def test_format_event_with_context(event_formatter):
    spreads = set(("foo", "bar"))
    ev = _MockEvent(
        context=spreads,
    )

    payload = event_formatter(ev)
    assert set(payload['aud']) == spreads


def test_format_event_with_attrs(event_formatter):
    attrs = set(("foo", "bar"))
    ev = _MockEvent(
        event_type=_MockEventType(verb="add"),
        attributes=attrs,
    )

    uri = SCIM_URI_PREFIX + ":add"

    payload = event_formatter(ev)
    assert uri in payload
    assert 'attributes' in payload[uri]
    assert set(payload[uri]['attributes']) == attrs


def test_format_event_with_objects(event_formatter):
    ev = _MockEvent(
        event_type=_MockEventType(verb="add"),
        objects=[
            _MockEntityRef(entity_type="group", ident="foo"),
            _MockEntityRef(entity_type="group", ident="bar"),
        ],
    )

    uri = SCIM_URI_PREFIX + ":add"
    urls = set((
        SCIM_URL_PREFIX + "/groups/foo",
        SCIM_URL_PREFIX + "/groups/bar",
    ))

    payload = event_formatter(ev)
    assert uri in payload
    assert 'object' in payload[uri]
    assert set(payload[uri]['object']) == urls


def test_format_event_scheduled(event_formatter):
    ev = _MockEvent(
        scheduled=dt_aware_utc,
    )

    payload = event_formatter(ev)
    assert 'nbf' in payload
    assert payload['nbf'] == dt_timestamp
