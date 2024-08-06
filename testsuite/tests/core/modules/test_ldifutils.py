# -*- coding: utf-8 -*-
"""tests for Cerebrum.modules.LDIFutils"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import re
import textwrap

import pytest

import Cerebrum.Errors
from Cerebrum.modules import LDIFutils


def test_to_base64_text():
    assert LDIFutils.to_base64("blåbærøl") == "YmzDpWLDpnLDuGw="


def test_to_base64_bytes():
    value = "blåbærøl".encode("utf-8")
    assert LDIFutils.to_base64(value) == "YmzDpWLDpnLDuGw="


def test_ldap_hexlify_text():
    value = "foo"
    assert LDIFutils.ldap_hexlify(value) == r"\66\6f\6f"


def test_ldap_hexlify_bytes():
    value = "foo".encode("ascii")
    assert LDIFutils.ldap_hexlify(value) == r"\66\6f\6f"


def test_hex_escape_match_text():
    pattern = re.compile(".")
    escaped = pattern.sub(LDIFutils.hex_escape_match, "foo")
    assert escaped == r'\66\6f\6f'


# TODO: Figure out how to make this work on python 3
# def test_hex_unescape_match_text():
#     pattern = re.compile(r"\\([0-9a-fA-F]{2})")
#     escaped = pattern.sub(LDIFutils.unescape_match, r'\66\6f\6f')
#     assert escaped == "foo"


@pytest.fixture
def config_module():
    config = type(str('config'), (object,),
                  {'LDAP': {}, 'LDAP_FOO': {}, '__name__': "test-fixture"})
    config.LDAP.update({
        'int': 7,
        'str': "foo",
        'container_attrs': {
            'aa': "LDAP_aa",
            'bb': "LDAP_bb",
            'cc': "LDAP_cc",
        }
    })
    config.LDAP_FOO.update({
        'dn': 'ou=foo,dc=example,dc=org',
        'str': "bar",
        'empty': None,
        'attrs': {
            'aa': "LDAP_FOO_aa",  # replaces LDAP_aa
            'dd': "LDAP_FOO_dd",
            'ff': "LDAP_FOO_ff",
        },
    })
    return config()


def test_ldapconf_hit_ldap(config_module):
    value = LDIFutils.ldapconf(None, "str", module=config_module)
    assert value == "foo"


def test_ldapconf_hit_tree(config_module):
    value = LDIFutils.ldapconf("FOO", "str", module=config_module)
    assert value == "bar"


def test_ldapconf_hit_default(config_module):
    value = LDIFutils.ldapconf("FOO", "empty", default=3, module=config_module)
    assert value == 3


def test_ldapconf_miss_default(config_module):
    value = LDIFutils.ldapconf("FOO", "non-existing", default=3,
                               module=config_module)
    assert value == 3


def test_ldapconf_miss_error(config_module):
    with pytest.raises(Cerebrum.Errors.CerebrumError):
        LDIFutils.ldapconf("FOO", "non-existing", module=config_module)


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


def test_get_ldap_config(config_module):
    config = LDIFutils.get_ldap_config(["LDAP", "LDAP_FOO"],
                                       module=config_module)
    assert config.get("str") == "bar"
    assert config.get("int", inherit=True) == 7


#
# entry_string tests
#


def test_entry_string_only_dn():
    # check that the dn is included in the entry_string
    dn = "uid=foo"
    value = LDIFutils.entry_string(dn, {}, add_rdn=False)
    assert value == textwrap.dedent(
        """
        dn: uid=foo

        """
    ).lstrip()


def test_entry_string_order():
    # check that the entry_string starts with dn
    # check that other attributes are included alphabetically
    dn = "uid=foo"
    attrs = {"mail": "foo@example.org", "cn": "Ola", "sn": "Nordmann"}
    value = LDIFutils.entry_string(dn, attrs, add_rdn=False)
    assert value == textwrap.dedent(
        """
        dn: uid=foo
        cn: Ola
        mail: foo@example.org
        sn: Nordmann

        """
    ).lstrip()


def test_entry_string_full_dn():
    # check that the dn can contain multiple levels
    dn = "uid=foo,ou=bar,dc=example,dc=org"
    value = LDIFutils.entry_string(dn, {}, add_rdn=False)
    assert value == textwrap.dedent(
        """
        dn: uid=foo,ou=bar,dc=example,dc=org

        """
    ).lstrip()


def test_entry_string_rdn():
    # check that attributes from the dn is included with add_rdn
    dn = "uid=foo"
    value = LDIFutils.entry_string(dn, {}, add_rdn=True)
    assert value == textwrap.dedent(
        """
        dn: uid=foo
        uid: foo

        """
    ).lstrip()


def test_entry_string_rdn_overlap():
    # check overlapping attributes rdn attribtues -
    # values from the dn should come before values from the attributes
    dn = "uid=foo+cn=foo"
    value = LDIFutils.entry_string(dn, {'cn': "bar"}, add_rdn=True)
    assert value == textwrap.dedent(
        """
        dn: uid=foo+cn=foo
        cn: foo
        cn: bar
        uid: foo

        """
    ).lstrip()


def test_entry_string_rdn_order():
    # check that all attributes from the dn is included
    # check that attribtues are sorted
    dn = "uid=foo+mail=foo@example.org+cn=Ola,ou=baz,dc=example,dc=org"
    attrs = {"sn": "Nordmann", "title": "test-subject"}
    value = LDIFutils.entry_string(dn, attrs, add_rdn=True)
    assert value == textwrap.dedent(
        """
        dn: uid=foo+mail=foo@example.org+cn=Ola,ou=baz,dc=example,dc=org
        cn: Ola
        mail: foo@example.org
        sn: Nordmann
        title: test-subject
        uid: foo

        """
    ).lstrip()


@pytest.mark.parametrize(
    "seqtype",
    [tuple, list],
    ids=lambda t: t.__name__,
)
def test_entry_string_ordered_mv_attr(seqtype):
    # Multivalued sequences should keep their input order
    dn = "uid=foo"
    attrs = {"title": seqtype(("baz", "foo", "bar"))}
    value = LDIFutils.entry_string(dn, attrs, add_rdn=False)
    assert value == textwrap.dedent(
        """
        dn: uid=foo
        title: baz
        title: foo
        title: bar

        """
    ).lstrip()


@pytest.mark.parametrize(
    "seqtype",
    [set, frozenset],
    ids=lambda t: t.__name__,
)
def test_entry_string_unordered_mv_attr(seqtype):
    dn = "uid=foo"
    attrs = {"title": seqtype(("baz", "foo", "bar"))}
    value = LDIFutils.entry_string(dn, attrs, add_rdn=False)
    assert value == textwrap.dedent(
        """
        dn: uid=foo
        title: bar
        title: baz
        title: foo

        """
    ).lstrip()


#
# container entry string tests
#


def test_container_entry_string(config_module):
    attrs = {
        'bb': "attrs_bb",  # replaces LDAP_bb
        'dd': "attrs_dd",  # replaced by LDAP_FOO_dd
        'ee': "attrs_ee",  # new value
    }

    value = LDIFutils.container_entry_string("FOO", attrs=attrs,
                                             module=config_module)
    assert value == textwrap.dedent(
        """
        dn: ou=foo,dc=example,dc=org
        aa: LDAP_FOO_aa
        bb: attrs_bb
        cc: LDAP_cc
        dd: LDAP_FOO_dd
        ee: attrs_ee
        ff: LDAP_FOO_ff
        ou: foo

        """
    ).lstrip()
