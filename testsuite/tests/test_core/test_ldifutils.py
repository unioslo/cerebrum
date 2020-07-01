# -*- coding: utf-8 -*-
"""tests for Cerebrum.modules.LDIFutils"""
from __future__ import unicode_literals

import re

import pytest

from Cerebrum.modules import LDIFutils


def test_hex_escape_match_bytes():
    match = re.match('...', b'123')
    assert LDIFutils.hex_escape_match(match) == r'\313233'


def test_hex_escape_match_unicode():
    match = re.match('...', u'123')
    assert LDIFutils.hex_escape_match(match) == r'\313233'


def test_config_hit():
    a = LDIFutils.LdapConfig('a', {'foo': 'bar'})
    assert a.get('foo') == 'bar'


def test_config_miss():
    a = LDIFutils.LdapConfig('a', {'foo': 'bar'})
    with pytest.raises(LookupError):
        a.get('bar')


def test_config_default():
    a = LDIFutils.LdapConfig('a', {'foo': 'bar'})
    assert a.get('bar', default='baz') == 'baz'


def test_config_inherit_hit():
    a = LDIFutils.LdapConfig('a', {'foo': 'bar'})
    b = LDIFutils.LdapConfig('b', {}, parent=a)
    assert b.get('foo', inherit=True) == 'bar'


def test_config_inherit_miss():
    # Check that we don't fetch values from parent when inherit=False
    a = LDIFutils.LdapConfig('a', {'foo': 'bar'})
    b = LDIFutils.LdapConfig('b', {}, parent=a)
    with pytest.raises(LookupError):
        b.get('foo', inherit=False)


cycles = [('a',), ('a', 'b',), ('a', 'b', 'c')]
cycle_ids = ['->'.join(t + (t[0],)) for t in cycles]


@pytest.mark.parametrize('nodes', cycles, ids=cycle_ids)
def test_config_catch_cycle(nodes):
    configs = [
        LDIFutils.LdapConfig(n, {})
        for n in nodes]

    # Set nth.parent = (n-1)th, ..., first.parent = second
    # The last config in 'configs' is the root, i.e. no parent
    parent = None
    for config in reversed(configs):
        config.parent = parent
        parent = config

    # form a cycle by pointing the nth.parent to the first node
    with pytest.raises(AttributeError):
        configs[-1].parent = configs[0]


@pytest.mark.parametrize(
    'attr,attrs', [
        ('LDAP', ('LDAP',)),
        ('LDAP_FOO', ('LDAP', 'LDAP_FOO')),
        ('LDAP_FOO_BAR', ('LDAP', 'LDAP_FOO', 'LDAP_FOO_BAR')),
    ],
    ids=('LDAP', 'LDAP_FOO', 'LDAP_FOO_BAR')
)
def test_ldap_attrs(attr, attrs):
    assert LDIFutils.expand_ldap_attrs(attr) == attrs
