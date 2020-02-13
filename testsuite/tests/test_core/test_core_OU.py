#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Basic tests for Cerebrum/OU.py."""
from __future__ import unicode_literals

import pytest
import datasource


@pytest.fixture
def database(database):
    """ A database-object, with change_program set. """
    database.cl_init(change_program='test_core_OU')
    return database


@pytest.fixture
def perspective(constant_module):
    u""" A new, unique perspective setting. """
    code = constant_module._OUPerspectiveCode
    p = code('35c9adc5de9ffff0', description='perspective')
    p.insert()
    return p


@pytest.fixture
def ou_entity_type(database):
    u""" Return the entity type for OUs from DB. """
    from Cerebrum.Constants import Constants
    return Constants(database).entity_ou


@pytest.fixture
def ou_spread(constant_module, ou_entity_type):
    u""" A new, unique OU spread. """
    code = constant_module._SpreadCode
    s = code('35c9adc5de9ffff2',
             entity_type=ou_entity_type,
             description='OU spread')
    s.insert()
    return s


@pytest.fixture
def ou_quarantine(constant_module):
    u""" A new, unique OU quarantine. """
    code = constant_module._QuarantineCode
    q = code('35c9adc5de9ffff3', 'OU quarantine')
    q.insert()
    return q


@pytest.fixture
def ou_object(database, factory):
    """ Returns instantiated Cerebrum.OU object. """
    from Cerebrum.OU import OU
    return OU(database)


def _populator(ou, limit=5):
    """ Basic populator function for OUs.

    Instantiates L{limit} OUs (default: 5)."""
    ous = list()
    for e in datasource.BasicOUSource()(limit=limit):
        try:
            ou.populate()
            ou.write_db()
            e['entity_id'] = ou.entity_id
            e['entity_type'] = ou.entity_type
            ous.append(e)
        except:
            ou._db.rollback()
            raise
        finally:
            ou.clear()
    return ous


@pytest.fixture
def basic_ous(ou_object):
    """ Returns list of pure OU objects. """
    return _populator(ou_object)


@pytest.fixture
def ou_tree(ou_object, perspective):
    """ Returns list of OU objects, in a tree structure. """
    ous = list()
    for e in _populator(ou_object):
        ou_object.find(e.get('entity_id'))
        ou_object.set_parent(perspective,
                             ous[-1].get('entity_id') if ous else None)
        ou_object.clear()
        ous.append(e)
    return ous


@pytest.fixture
def ous_with_spreads(ou_object, ou_spread):
    """ Returns a list of OUs with OU-spreads. """
    ous = list()
    for e in _populator(ou_object):
        ou_object.find(e.get('entity_id'))
        ou_object.add_spread(ou_spread)
        ou_object.clear()
        ous.append(e)
    return ous


@pytest.fixture
def ous_with_quarantines(ou_object, ou_quarantine, initial_account):
    from mx.DateTime import now
    ous = list()
    for e in _populator(ou_object):
        ou_object.find(e.get('entity_id'))
        ou_object.add_entity_quarantine(ou_quarantine,
                                        initial_account.entity_id,
                                        "Description",
                                        now())
        ou_object.clear()
        ous.append(e)
    return ous


def test_find(ou_object, basic_ous):
    if len(basic_ous) < 1:
        pytest.skip('Test needs at least one OU')
    for entry in basic_ous:
        ou_object.find(entry['entity_id'])
        ou_object.clear()


def test_find_error(ou_object):
    from Cerebrum.Errors import NotFoundError
    with pytest.raises(NotFoundError):
        ou_object.find(-1)


def test_get_parent(ou_object, ou_tree, perspective):
    if len(ou_tree) < 2:
        pytest.skip('Test needs at least two OUs')
    parent = None
    for entry in ou_tree:
        ou_object.clear()
        ou_object.find(entry['entity_id'])
        assert parent == ou_object.get_parent(perspective)
        parent = entry['entity_id']


def test_get_parent_error(ou_object, basic_ous, perspective):
    from Cerebrum.Errors import NotFoundError
    if len(basic_ous) < 1:
        pytest.skip('Test needs at least one OU')

    ou_object.find(basic_ous[-1]['entity_id'])

    with pytest.raises(NotFoundError):
        ou_object.get_parent(perspective)


def test_root(ou_object, perspective):
    def _gen():
        return ou_tree(ou_object, perspective)[0]['entity_id']

    assert filter(
        lambda x: x in map(
            lambda x: x['ou_id'], ou_object.root()),
        [_gen(), _gen()])


def test_list_children(ou_object, ou_tree, perspective):
    if len(ou_tree) < 2:
        pytest.skip('Test needs at least two OUs')

    parent_id = ou_tree[0]['entity_id']  # should have one child
    child_id = ou_tree[1]['entity_id']
    leaf_id = ou_tree[-1]['entity_id']  # should not have any children

    ou_object.find(parent_id)

    direct_children = [r['ou_id']
                       for r in ou_object.list_children(perspective)]
    assert [child_id] == direct_children

    all_children = [r['ou_id']
                    for r in ou_object.list_children(perspective,
                                                     recursive=True)]
    assert [d['entity_id'] for d in ou_tree[1:]] == all_children

    assert [] == ou_object.list_children(perspective, entity_id=leaf_id)


def test_delete(ou_object, basic_ous):
    from Cerebrum.Errors import NotFoundError
    if len(basic_ous) < 1:
        pytest.skip('Test needs at least one OU')
    for entry in basic_ous:
        ou_object.find(entry.get('entity_id'))
        ou_object.delete()
        ou_object.clear()
        with pytest.raises(NotFoundError):
            ou_object.find(entry.get('entity_id'))
        ou_object.clear()


def test_search_by_spread(ou_object, basic_ous, ous_with_spreads, ou_spread):
    if any(len(l) < 1 for l in (basic_ous, ous_with_spreads)):
        pytest.skip('Test needs at least three OUs, one with a quarantine, '
                    'one with a spread, and one without.')

    # check that we can search for ous by spread
    results = [r['ou_id'] for r in ou_object.search(spread=ou_spread)]
    expect = [d['entity_id'] for d in ous_with_spreads]
    assert set(results) == set(expect)


def test_search_exclude_quar(ou_object, basic_ous, ous_with_quarantines):
    if any(len(l) < 1 for l in (basic_ous, ous_with_quarantines)):
        pytest.skip('Test needs at least three OUs, one with a quarantine, '
                    'one with a quarantine, and one without.')

    # check that we can search for ous without quarantines
    results = [r['ou_id'] for r in ou_object.search(filter_quarantined=True)]
    expect = [d['entity_id'] for d in basic_ous]
    quarantined = [d['entity_id'] for d in ous_with_quarantines]

    # All our basic ous should be included
    assert len(results) >= len(expect)
    assert set(expect).issubset(set(results))

    # None of our quarantined ous should be included
    assert not set(results).intersection(set(quarantined))


def test_search_all(ou_object, basic_ous, ous_with_spreads,
                    ous_with_quarantines):
    if any(len(l) < 1 for l in (basic_ous, ous_with_quarantines,
                                ous_with_spreads)):
        pytest.skip('Test needs ous with and without spreads and quarantines')

    # check that we can search for all ous
    results = [r['ou_id'] for r in ou_object.search()]
    expect = [d['entity_id'] for d in ous_with_quarantines + ous_with_spreads +
              basic_ous]

    # All of our created ous should be included in the result
    assert len(results) >= len(expect)
    assert set(expect).issubset(set(results))


def test_unset_parent(ou_object, ou_tree, perspective):
    if len(ou_tree) < 2:
        pytest.skip('Test needs at least two OUs')
    from Cerebrum.Errors import NotFoundError
    for e in reversed(ou_tree):
        ou_object.find(e.get('entity_id'))
        ou_object.unset_parent(perspective)
        with pytest.raises(NotFoundError):
            ou_object.get_parent(perspective)
        ou_object.clear()
