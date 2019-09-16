#!/usr/bin/env python
# -*- coding: utf-8 -*-
u""" Tests for Cerebrum.modules.bofhd.session """

import pytest

SOURCE_IP_SHORT = '10.0.0.2'
SOURCE_IP_LONG = '10.0.0.254'
BOFHD_SHORT_TIMEOUT = 60
BOFHD_SHORT_TIMEOUT_HOSTS = ['10.10.0.0/5', '10.10.128.0']


@pytest.fixture
def cereconf(cereconf):
    u""" Patched `cereconf` with known BOFHD_ session values. """
    setattr(cereconf, 'BOFHD_SHORT_TIMEOUT', BOFHD_SHORT_TIMEOUT)
    setattr(cereconf, 'BOFHD_SHORT_TIMEOUT_HOSTS', BOFHD_SHORT_TIMEOUT_HOSTS)
    return cereconf


@pytest.fixture
def database(database):
    database.cl_init(change_program='test_bofhd_session')
    return database


@pytest.fixture
def AccountCode(constant_module):
    return constant_module._AccountCode


@pytest.fixture
def account(cereconf, factory, database, AccountCode):
    u""" Create a non-personal account for tests. """
    acc = factory.get('Account')(database)
    group = factory.get('Group')(database)

    # creator_id
    acc.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    creator_id = acc.entity_id
    acc.clear()

    # owner_id, owner_type
    group.find_by_name(cereconf.INITIAL_GROUPNAME)

    # non-personal account type
    np_type = AccountCode('6c96aa56a57d0831',
                          description='test_bofhd_session account')
    np_type.insert()

    acc.populate('fc3acf7e',
                 group.entity_type,
                 group.entity_id,
                 np_type,
                 creator_id,
                 None)
    acc.write_db()
    return acc


@pytest.fixture
def session_module(cereconf):
    # Depend on cereconf to monkey patch the cereconf values
    return pytest.importorskip('Cerebrum.modules.bofhd.session')


@pytest.fixture
def session(session_module, database, logger):
    return session_module.BofhdSession(database, logger)


def test_ip_to_long(session_module):
    """ Cerebrum.modules.bofhd.session.ip_to_long """
    assert session_module.ip_to_long('127.0.0.1') == 2130706433
    assert session_module.ip_to_long('129.240.8.200') == 2179991752


def test_ip_subnet_slash_to_range(session_module):
    """ Cerebrum.modules.bofhd.session.ip_subnet_to_slash_range. """
    test = session_module.ip_subnet_slash_to_range
    assert test('127.0.0.0/8') == (2130706432L, 2147483647L)
    assert test('127.0.0.0/31') == (2130706432L, 2130706433L)
    assert test('127.0.0.0/1') == (0L, 2147483647L)


def test_ip_subnet_slash_to_range_big(session_module):
    """ Cerebrum.modules.bofhd.session.ip_subnet_to_slash_range error. """
    with pytest.raises(ValueError):
        session_module.ip_subnet_slash_to_range('127.0.0.0/0')


def test_ip_subnet_slash_to_range_small(session_module):
    """ Cerebrum.modules.bofhd.session.ip_subnet_to_slash_range error. """
    with pytest.raises(ValueError):
        session_module.ip_subnet_slash_to_range('127.0.0.0/32')


def test_conf_short_timeout(session_module):
    assert session_module._get_short_timeout() == BOFHD_SHORT_TIMEOUT


def test_conf_short_timeout_hosts(session_module):
    hosts = session_module._get_short_timeout_hosts()
    assert len(hosts) == len(BOFHD_SHORT_TIMEOUT_HOSTS)
    # TODO: Iterate through `hosts` and check start/end values?


def test_setup_session(session, account):
    sid = session.set_authenticated_entity(account.entity_id, SOURCE_IP_LONG)
    print 'session_id', repr(sid)
    assert sid is not None
    assert len(sid) > 1


@pytest.fixture
def long_session(session, account):
    u""" Logged in session. """
    session.set_authenticated_entity(account.entity_id, SOURCE_IP_LONG)
    return session


@pytest.fixture
def short_session(session, account):
    session.set_authenticated_entity(account.entity_id, SOURCE_IP_SHORT)
    return session


def test_get_session_id(long_session):
    sid = long_session.get_session_id()
    assert sid is not None
    assert len(sid) > 1


def test_get_entity_id(long_session, account):
    eid = long_session.get_entity_id()
    assert eid == account.entity_id


@pytest.mark.skipif(True, reason="TODO: Figure out how to time out")
def test_get_entity_id_expired(short_session, expired):
    assert expired.expire_date is not None
    # TODO: Make session time out, then try get_entity_id with and without
    # include_expired.


def test_get_owner_id(long_session, account):
    oid = long_session.get_owner_id()
    assert oid == account.owner_id


def test_store_state(long_session):
    long_session.store_state('foo', 'string',
                             entity_id=long_session.get_entity_id())
    long_session.store_state('bar', 10)
    state = long_session.get_state()
    assert len(state) == 2
    for d in state:
        if d['state_type'] == 'foo':
            assert d['entity_id'] == long_session.get_entity_id()
        else:
            assert d['entity_id'] is None


@pytest.fixture
def state(long_session):
    st = {
        'test_bofhd_session a': ['foo', 3],
        'test_bofhd_session b': dict(foo=1, bar=2),
    }
    for state_type, state_data in st.items():
        long_session.store_state(state_type, state_data)
    return st


def test_get_state_all_types(long_session, state):
    data = long_session.get_state()
    assert len(data) == 2

    for row in data:
        assert row['state_data'] == state[row['state_type']]


def test_get_state_by_type(long_session, state):
    for state_type in state:
        data = long_session.get_state(state_type)
        assert len(data) == 1
        assert data[0]['state_data'] == state[state_type]


def test_clear_state_by_type(long_session, state):
    for i, state_type in enumerate(state):
        long_session.clear_state(state_types=(state_type, ))
        data = long_session.get_state()
        assert len(data) == len(state) - i - 1


def test_clear_state_all_types(long_session, state):
    long_session.clear_state()
    data = long_session.get_state()
    assert len(data) == 0


def test_multiple_states_for_type(long_session):
    state_type = 'test_bofhd_session non-unique'
    states = {1, 2}
    for state in states:
        long_session.store_state(state_type, state)
    data = long_session.get_state()
    assert len(data) == len(states)
    assert all(r['state_type'] == state_type for r in data)
    assert {r['state_data'] for r in data} == states
