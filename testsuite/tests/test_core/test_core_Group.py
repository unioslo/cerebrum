#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Basic tests for Cerebrum/Group.py (GROUP_CLASS). """
from __future__ import unicode_literals

import pytest
import datasource


@pytest.fixture
def group_ds():
    u""" Data source for creating groups. """
    return datasource.BasicGroupSource()


@pytest.fixture
def database(database):
    u""" Database with cl_init set. """
    database.cl_init(change_program='test_core_Group')
    return database


@pytest.fixture
def gr(database, factory):
    u""" Empty, initialized group entity. """
    return factory.get('Group')(database)


@pytest.fixture
def group_spread(constant_module, initial_group):
    u""" A new, unique group spread. """
    code = constant_module._SpreadCode
    spread = code('c8df4be6be5b9dca',
                  entity_type=initial_group.entity_type,
                  description='spread')
    spread.insert()
    return spread


@pytest.fixture
def group_visibility(constant_module):
    u""" A new, unique group visibility setting. """
    code = constant_module._GroupVisibilityCode
    vis = code('8d9cbd5ac0e9b4f8', description='test visibility')
    vis.insert()
    return vis


@pytest.fixture
def group_type(constant_module):
    u""" A new, unique group type setting. """
    code = constant_module._GroupTypeCode
    gt = code('3e94030c921dbdee', description='test group type')
    gt.insert()
    return gt


@pytest.fixture
def groups(gr, group_visibility, group_type, group_ds, initial_account):
    u""" Group info on five new groups. """
    groups = list()
    for entry in group_ds(limit=5):
        try:
            # creator_id = self.get_initial_account_id()
            gr.populate(
                creator_id=initial_account.entity_id,
                visibility=int(group_visibility),
                name=entry['group_name'],
                description=entry['description'],
                group_type=int(group_type),
            )
            gr.expire_date = entry.get('expire_date')
            gr.write_db()
            entry['entity_id'] = gr.entity_id
            entry['entity_type'] = gr.entity_type
            groups.append(entry)
        except Exception:
            gr._db.rollback()
            raise
        finally:
            gr.clear()
    return groups


def modify_chain(chain, operation):
    u""" Helper function for creating/deleting memberships.

    For every item in chain, but the last, do operation with arguments (this
    items entity_id, next items entity_id)

    """
    for index, item in enumerate(chain[:-1]):
        operation(chain[index]['entity_id'], chain[index+1]['entity_id'])


def modify_add_member(obj):
    u""" Helper function for adding a member_id to a group. """
    def add(group_id, member_id):
        obj.find(group_id)
        obj.add_member(member_id)
        obj.clear()
    return add


def test_find(gr, groups):
    if len(groups) < 1:
        pytest.skip('Test needs at least one group')
    for entry in groups:
        gr.find(entry['entity_id'])
        gr.clear()


def test_find_error(gr):
    from Cerebrum.Errors import NotFoundError
    with pytest.raises(NotFoundError):
        gr.find(-10)  # negative IDs are impossible in Cerebrum
        gr.clear()


def test_find_by_name(gr, groups):
    if len(groups) < 1:
        pytest.skip('Test needs at least one group')
    for entry in groups:
        gr.find_by_name(entry['group_name'])
        gr.clear()


def test_find_by_name_error(gr):
    from Cerebrum.Errors import NotFoundError
    with pytest.raises(NotFoundError):
        # entity_name is a varchar(256), no group with longer name should exist
        gr.find_by_name('n' * (256+1))
        gr.clear()


def test_is_expired(gr, groups):
    non_expired = set((v['entity_id'] for v in
                       filter(datasource.nonexpired_filter, groups)))

    if len(non_expired) < 1:
        pytest.skip('Test needs at least one non-expired group')
    if len(non_expired) == len(groups):
        pytest.skip('Test needs at least one expired group')

    for entry in groups:
        gr.find(entry['entity_id'])
        if gr.entity_id in non_expired:
            assert not gr.is_expired()
        else:
            assert gr.is_expired()
        gr.clear()


def test_has_member(gr, groups):
    if len(groups) < 2:
        pytest.skip('Test needs at least two groups')
    member_id = groups[1]['entity_id']
    gr.find_by_name(groups[0]['group_name'])
    gr.add_member(member_id)
    gr.write_db()
    assert gr.has_member(member_id)
    gr.remove_member(member_id)
    assert not gr.has_member(member_id)


def test_add_remove_member(gr, groups):
    if len(groups) < 2:
        pytest.skip('Test needs at least two groups')
    e1 = groups[0]
    test_case = groups[1:4]
    gr.find_by_name(e1['group_name'])

    for entry in test_case:
        gr.add_member(entry['entity_id'])
    try:
        for entry in test_case:
            assert gr.has_member(entry['entity_id'])
    finally:
        for entry in test_case:
            gr.remove_member(entry['entity_id'])


def test_search_id(gr, groups):
    if len(groups) < 2:
        pytest.skip('Test needs at least two groups')
    assert len(list(gr.search(group_id=groups[0]['entity_id'],
                              filter_expired=False))) == 1

    for seq_type in (tuple, set, list):
        result = list(gr.search(group_id=seq_type((groups[0]['entity_id'],
                                                   groups[1]['entity_id'])),
                                filter_expired=False))
        assert len(result) == 2


def test_search_result(gr, groups):
    if len(groups) < 2:
        pytest.skip('Test needs at least two groups')
    attributes = ('group_id', 'name', 'description', 'visibility',
                  'creator_id', 'created_at', 'expire_date')
    rows = list(gr.search(group_id=[g['entity_id'] for g in groups],
                          filter_expired=False))
    assert len(rows) == len(groups)

    for row in rows:
        for attr_name in attributes:
            assert attr_name in row.dict()


def test_search_member_id(gr, groups):
    """ Group.search(member_id). """
    if len(groups) < 3:
        pytest.skip('Test needs at least three groups')

    # Make memberships
    modify_chain(groups, modify_add_member(gr))

    # Each group, except the first, should now be member of exactly ONE
    # group.
    for index, group in enumerate(groups):
        if index == 0:
            continue  # ...all groups except the first
        result = list(gr.search(member_id=groups[index]['entity_id'],
                                indirect_members=False,
                                filter_expired=False))
        assert len(result) == 1
        assert result[0]['group_id'] == groups[index-1]['entity_id']

    # And now via the transitive closure
    result = list(gr.search(member_id=groups[-1]['entity_id'],
                            indirect_members=True,
                            filter_expired=False))

    # The answer is the remaining chain
    assert len(result) == len(groups)-1
    assert (set(x['entity_id'] for x in groups[:-1])
            == set(x['group_id'] for x in result))


def test_search_member_complex(gr, groups):
    """ Group.search(member_id) (complex membership graph). """
    if len(groups) < 3:
        pytest.skip('Test needs at least three groups')

    modify_chain(groups, modify_add_member(gr))
    modify_chain((groups[0], groups[2]), modify_add_member(gr))
    # now groups[2] is a direct member of groups[0] as well

    result = list(gr.search(member_id=groups[-1]['entity_id'],
                            indirect_members=True,
                            filter_expired=False))
    assert len(result) == len(groups)-1
    assert (set(x['entity_id'] for x in groups[:-1])
            == set(x['group_id'] for x in result))


def test_search_name(gr, groups):
    """ Group.search() for name. """
    if len(groups) < 1:
        pytest.skip('Test needs at least one group')
    for item in groups:
        result = list(gr.search(name=item['group_name'], filter_expired=False))
        assert len(result) == 1


def test_search_name_wildcard(gr, groups, group_ds):
    """ Group.search() for name with wildcards. """
    if len(groups) < 1:
        pytest.skip('Test needs at least one group')
    search_expr = group_ds.get_name_prefix() + '%'
    result = list(gr.search(name=search_expr, filter_expired=False))
    assert len(result) == len(groups)


def test_search_description(gr, groups):
    """ Group.search() for description. """
    if len(groups) < 1:
        pytest.skip('Test needs at least one group')
    for item in groups:
        result = list(gr.search(description=item['description'],
                                filter_expired=False))
        assert len(result) == 1


def test_search_description_wildcard(gr, groups, group_ds):
    """Group.search() for description with wildcards. """
    if len(groups) < 1:
        pytest.skip('Test needs at least one group')
    search_expr = group_ds.get_description_prefix() + '%'
    results = list(gr.search(description=search_expr, filter_expired=False))
    assert len(results) == len(groups)


def test_search_expired(gr, groups, group_ds):
    """ Group.search() filter_expired keyword argument. """
    non_expired = filter(datasource.nonexpired_filter, groups)
    if (len(groups) - len(non_expired)) < 1:
        pytest.skip('Test needs at least one expired group')

    search_expr = group_ds.get_name_prefix() + '%'

    result = list(gr.search(filter_expired=True, name=search_expr))
    assert (len(result) == len(non_expired))

    result = list(gr.search(filter_expired=False, name=search_expr))
    assert (len(result) == len(groups))


def test_search_spread(gr, groups, group_spread):
    """ Group.search() for spread. """
    if len(groups) < 1:
        pytest.skip('Test needs at least one group')

    gr.find_by_name(groups[0]['group_name'])

    # It does not really matter which spread we pick out, as long as it is
    # something that applies to groups.
    assert group_spread is not None

    gr.add_spread(group_spread)

    try:
        result = list(gr.search(spread=group_spread, filter_expired=False))
        assert len(result) == 1
        assert result[0]['group_id'] == groups[0]['entity_id']
    finally:
        gr.delete_spread(group_spread)


def test_empty_search(gr, groups):
    """ Group.search() without args. """
    non_expired = filter(datasource.nonexpired_filter, groups)
    if len(non_expired) < 1:
        pytest.skip('Test needs at least one non-expired group')

    result = list(gr.search())
    assert len(result) >= len(non_expired)
    assert set(x['group_id'] for x in result).issuperset(set(x['entity_id'] for
                                                             x in non_expired))


def test_cyclic_membership(gr, groups):
    """Check if Group-API handles cyclic memberships."""
    if len(groups) < 2:
        pytest.skip('Test needs at least two groups')

    # Make every group[x+1] a member of group[x]
    modify_chain(groups, modify_add_member(gr))
    # Make every group[x] a member of group[x+1]
    modify_chain(groups[::-1], modify_add_member(gr))

    # Now that we have a cycle spanning the entire default_groups, let's
    # look for groups where default_groups[-1] is an indirect member.
    result = list(gr.search(member_id=groups[-1]['entity_id'],
                            indirect_members=True,
                            filter_expired=False))
    assert len(result) == len(groups)


def test_search_members_simple(gr, groups):
    """ Group.search_members() by group_id. """
    if len(groups) < 3:
        pytest.skip('Test needs at least three groups')

    members = [g['entity_id'] for g in groups[1:3]]
    for m in members:
        modify_add_member(gr)(groups[0]['entity_id'], m)

    result = list(gr.search_members(group_id=groups[0]['entity_id'],
                                    member_filter_expired=False))
    assert len(result) == len(members)
    assert set(x['member_id'] for x in result) == set(members)


def test_search_members_group_id_indirect(gr, groups):
    """ Group.search_members() indirect members of given group. """
    if len(groups) < 3:
        pytest.skip('Test needs at least three groups')

    modify_chain(groups, modify_add_member(gr))

    # *all* other groups are transient members of groups[0]
    result = list(gr.search_members(group_id=groups[0]['entity_id'],
                                    indirect_members=True,
                                    member_filter_expired=False))
    assert len(result) == len(groups)-1
    assert (set(x['member_id'] for x in result)
            == set(x['entity_id'] for x in groups[1:]))


def test_search_members_assert_keys(gr, groups):
    """ Check that required keys are returned by Group.search_members(). """
    if len(groups) < 2:
        pytest.skip('Test needs at least two groups')

    attributes = ('member_type', 'member_id', 'expire_date')
    modify_add_member(gr)(groups[0]['entity_id'], groups[1]['entity_id'])

    result = list(gr.search_members(group_id=groups[0]['entity_id'],
                                    member_filter_expired=False))
    assert len(result) == 1
    for attr in attributes:
        assert attr in result[0].dict()


def test_search_members_by_id(gr, groups):
    """ Group.search_members() multiple member_ids. """
    if len(groups) < 3:
        pytest.skip('Test needs at least three groups')

    members = [g['entity_id'] for g in groups[1:3]]
    for m in members:
        modify_add_member(gr)(groups[0]['entity_id'], m)
    result = list(gr.search_members(member_id=members,
                                    member_filter_expired=False))
    assert len(result) == len(members)
    assert (set(x['member_id'] for x in result) == set(members))


def test_search_members_member_id_indirect_expired(gr, groups):
    """ Group.search_members() indirect members, filtering expired. """
    non_expired = filter(datasource.nonexpired_filter, groups)
    if len(non_expired) < 3:
        pytest.skip('Test needs at least three non-expired groups')

    modify_chain(non_expired, modify_add_member(gr))

    # *all* non_expired groups are indirect members of non_expired[0]
    result = list(gr.search_members(member_id=non_expired[-1]['entity_id'],
                                    indirect_members=True,
                                    member_filter_expired=True))
    assert len(result) == len(non_expired) - 1
    assert (set(x['member_id'] for x in result)
            == set(x['entity_id'] for x in non_expired[1:]))


def test_search_members_by_type(gr, groups, initial_account):
    non_expired = filter(datasource.nonexpired_filter, groups)
    if len(non_expired) < 2:
        pytest.skip('Test needs at least two non-expired groups')

    for m in (non_expired[1]['entity_id'], initial_account.entity_id):
        modify_add_member(gr)(non_expired[0]['entity_id'], m)

    result = list(gr.search_members(member_type=initial_account.entity_type,
                                    group_id=non_expired[0]["entity_id"],
                                    member_filter_expired=False))
    assert len(result) == 1
    assert result[0]['member_id'] == initial_account.entity_id

    result = list(gr.search_members(member_type=non_expired[1]['entity_type'],
                                    group_id=non_expired[0]["entity_id"]))
    assert len(result) == 1
    assert result[0]['member_id'] == non_expired[1]['entity_id']


def test_search_members_by_spread(gr, groups, group_spread):
    non_expired = filter(datasource.nonexpired_filter, groups)
    if len(non_expired) < 2:
        pytest.skip('Test needs at least two non-expired groups')

    gr.find_by_name(non_expired[1]['group_name'])
    gr.add_spread(group_spread)
    gr.clear()

    # Make group[1] a child of group[0]
    modify_chain(non_expired[:2], modify_add_member(gr))
    result = list(gr.search_members(member_spread=group_spread))
    assert len(result) == 1
    assert result[0]['member_id'] == non_expired[1]['entity_id']


def test_search_members_expired(gr, groups):
    U""" Group.search_members() with member_filter_expired. """
    non_expired = set((g['entity_id'] for g in
                       filter(datasource.nonexpired_filter, groups)))
    expired = set((g['entity_id'] for g in groups)) - non_expired

    if len(expired) < 1:
        pytest.skip('Test needs at least one expired group')

    # Check our sets
    assert not expired.intersection(non_expired)
    assert expired.union(non_expired) == set((g['entity_id'] for g in groups))

    modify_chain(groups, modify_add_member(gr))
    # Check that everything is there, when we disregard expired
    result = list(gr.search_members(group_id=expired.union(non_expired),
                                    member_filter_expired=False,))
    assert len(result) == len(groups)-1

    # Check that every *member* group that is *not expired* is returned
    result = list(gr.search_members(group_id=expired.union(non_expired),
                                    member_filter_expired=True,))
    expected_results = (len(expired) - 1
                        if groups[0]['entity_id'] in expired
                        else len(expired))
    assert len(result) == len(groups) - 1 - expected_results
    assert not set(x['member_id'] for x in result).intersection(expired)
