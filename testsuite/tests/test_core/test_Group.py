#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Basic tests for Cerebrum/Group.py.

Searching (members and groups) has to be thoroughly tested.

"""
#import sys
from nose.tools import raises, with_setup

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.Constants import _SpreadCode as SpreadCode

# Cerebrum-specific test modules
from datasource import BasicGroupSource
#from datasource import expired_filter
from datasource import nonexpired_filter
from dbtools import DatabaseTools

# Global cererbum objects
db = None
gr = None
co = None

# Group datasource generator
group_ds = None

# Groups, global list of groups in a given test
groups = None

# Database tools to do common tasks
db_tools = None

# A group spread constant
group_spread = None
group_spread_name = 'gipyzhfeqzpqjzde'


def setup_module():
    """ Setup for this test module.

    This function is called is called once (and only once) by nosetests before
    any test in this script is performed.

    """
    global db, gr, co, group_spread, group_ds, db_tools
    db = Factory.get('Database')()
    db.cl_init(change_program='nosetests')
    db.commit = db.rollback  # Let's try not to screw up other tests

    gr = Factory.get('Group')(db)
    co = Factory.get('Constants')(db)

    # Data source for groups
    group_ds = BasicGroupSource()

    # Tools for creating and destroying temporary db items
    db_tools = DatabaseTools(db)

    # Create group_spread
    group_spread = db_tools.insert_constant(SpreadCode,
                                            group_spread_name,
                                            co.entity_group,
                                            'Temp group spread (test)')


def teardown_module():
    """ Clean up this module.

    This function is called once by nosetests after performing tests in this
    module. It is called regardless of the test results, but may not be called
    it the test itself crashes.

    """

    db_tools.clear_groups()
    db_tools.clear_accounts()
    db_tools.clear_persons()
    db_tools.clear_constants()
    db.rollback()


def create_groups(num=5):
    """ Create a set of groups to use in a test.

    See C{groups} in this file for format.

    """
    def wrapper():
        global groups
        groups = []
        for entry in group_ds(limit=num):
            entity_id = db_tools.create_group(entry)
            entry['entity_id'] = entity_id
            groups.append(entry)
        for entry in groups:
            assert entry['entity_id'] is not None
    return wrapper


def remove_groups():
    """ Remove all groups.

    Complementary function/cleanup code for C{create_groups}.

    """
    def wrapper():
        global groups
        for entry in groups:
            db_tools.delete_group_id(entry['entity_id'])
        groups = None
    return wrapper


def modify_chain(chain, operation):
    """ Helper function for creating/deleting memberships.

    For every item in chain, but the last, do operation with arguments (this
    items entity_id, next items entity_id)

    """
    for index, item in enumerate(chain[:-1]):
        operation(chain[index]['entity_id'], chain[index+1]['entity_id'])


def add_member(group_id, member_id):
    """ Helper function for adding a member_id to a group. """
    gr.clear()
    gr.find(group_id)
    gr.add_member(member_id)


def remove_member(group_id, member_id):
    """ Helper function for removing a member_id from a group. """
    gr.clear()
    gr.find(group_id)
    gr.remove_member(member_id)


@with_setup(create_groups(num=5), remove_groups())
def test_simple_find():
    """ Group.find() existing entity. """
    for entry in groups:
        gr.clear()
        gr.find(entry['entity_id'])


@raises(Errors.NotFoundError)
def test_simple_find_fail():
    """ Group.find() non-existing entity. """
    gr.clear()
    gr.find(-10)  # negative IDs are impossible in Cerebrum


@with_setup(create_groups(num=5), remove_groups())
def test_find_by_name():
    """ Group.find_by_name() existing name. """

    for entry in groups:
        gr.clear()
        gr.find_by_name(entry['group_name'])


@raises(Errors.NotFoundError)
def test_find_by_name_fail():
    """ Group.find_by_name() non-existing name. """
    gr.clear()
    gr.find_by_name('n' * (256+1))  # entity_name is a varchar(256), no group
                                    # with longer name should exist.


@with_setup(create_groups(num=5), remove_groups())
def test_group_expired():
    """ Group.is_expired() on known set. """
    non_expired = set((g['entity_id'] for g in
                       filter(nonexpired_filter, groups)))

    # We must have at least one expired and one non-expired group
    assert (len(non_expired) > 0 and
            len(non_expired) < len(set((g['entity_id'] for g in groups))))

    for entry in groups:
        gr.clear()
        gr.find(entry['entity_id'])
        if gr.entity_id in non_expired:
            assert not gr.is_expired()
        else:
            assert gr.is_expired()


@with_setup(create_groups(num=5), remove_groups())
def test_membership1():
    """ Group.add_member/has_member() test membership. """
    assert len(groups) >= 2  # We need min 2 groups for this test
    member_id = groups[1]['entity_id']

    gr.clear()
    gr.find_by_name(groups[0]['group_name'])
    gr.add_member(member_id)
    gr.write_db()
    assert gr.has_member(member_id)
    gr.remove_member(member_id)
    assert not gr.has_member(member_id)


@with_setup(create_groups(num=5), remove_groups())
def test_membership2():
    """ Group, test a bunch of add/has/remove members."""

    e1 = groups[0]
    test_case = groups[1:4]
    gr.clear()
    gr.find_by_name(e1['group_name'])

    for entry in test_case:
        gr.add_member(entry['entity_id'])
    try:
        for entry in test_case:
            assert gr.has_member(entry['entity_id'])
    finally:
        for entry in test_case:
            gr.remove_member(entry['entity_id'])


@with_setup(create_groups(num=5), remove_groups())
def test_search_id():
    """ Group.search() with group_id keyword argument. """
    assert len(list(gr.search(group_id=groups[0]['entity_id'],
                              filter_expired=False))) == 1

    assert len(groups) >= 2  # We need min 2 groups for this test
    for seq_type in (tuple, set, list):
        result = list(gr.search(group_id=seq_type((groups[0]['entity_id'],
                                                   groups[1]['entity_id'])),
                                filter_expired=False))
        assert len(result) == 2


@with_setup(create_groups(num=5), remove_groups())
def test_search_result():
    """ Group.search() db_row result attributes. """
    assert len(groups) >= 2  # We need min 2 groups for this test
    attributes = ('group_id', 'name', 'description', 'visibility',
                  'creator_id', 'create_date', 'expire_date')
    rows = list(gr.search(group_id=[g['entity_id'] for g in groups],
                          filter_expired=False))
    assert len(rows) == len(groups)

    for row in rows:
        for attr_name in attributes:
            assert attr_name in row.dict()


@with_setup(create_groups(num=5), remove_groups())
def test_search_for_member():
    """ Group.search(member_id). """
    assert len(groups) >= 3  # We need at least 3 groups for this test

    modify_chain(groups, add_member)

    try:
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
        assert (set(x['entity_id'] for x in groups[:-1]) ==
                set(x['group_id'] for x in result))
    finally:
        modify_chain(groups, remove_member)


@with_setup(create_groups(num=5), remove_groups())
def test_search_member2():
    """ Group.search(member_id) (complex membership graph). """
    assert len(groups) >= 3  # We need at least 3 groups for this test

    modify_chain(groups, add_member)
    modify_chain((groups[0], groups[2]), add_member)
    # now groups[2] is a direct member of groups[0] as well

    try:
        result = list(gr.search(member_id=groups[-1]['entity_id'],
                                indirect_members=True,
                                filter_expired=False))
        assert len(result) == len(groups)-1
        assert (set(x['entity_id'] for x in groups[:-1]) ==
                set(x['group_id'] for x in result))
    finally:
        modify_chain(groups, remove_member)
        modify_chain((groups[0], groups[2]), remove_member)


@with_setup(create_groups(num=5), remove_groups())
def test_search_name():
    """ Group.search() for name. """
    assert len(groups) >= 1  # We need at least 1 group for this test
    for item in groups:
        result = list(gr.search(name=item['group_name'], filter_expired=False))
        assert len(result) == 1


@with_setup(create_groups(num=5), remove_groups())
def test_search_name_wildcard():
    """ Group.search() for name with wildcards. """
    assert len(groups) >= 1  # We need at least 1 group for this test
    search_expr = group_ds.get_name_prefix() + '%'
    result = list(gr.search(name=search_expr, filter_expired=False))
    assert len(result) == len(groups)


@with_setup(create_groups(num=5), remove_groups())
def test_search_description():
    """ Group.search() for description. """
    assert len(groups) >= 1  # We need at least 1 group for this test
    for item in groups:
        result = list(gr.search(description=item['description'],
                                filter_expired=False))
        assert len(result) == 1


@with_setup(create_groups(num=5), remove_groups())
def test_search_description_wildcard():
    """Group.search() for description with wildcards. """
    assert len(groups) >= 1  # We need at least 1 group for this test
    search_expr = group_ds.get_description_prefix() + '%'
    results = list(gr.search(description=search_expr, filter_expired=False))
    assert len(results) == len(groups)


@with_setup(create_groups(num=5), remove_groups())
def test_search_expired():
    """ Group.search() filter_expired keyword argument. """
    non_expired = filter(nonexpired_filter, groups)
    assert (len(groups) - len(non_expired)) >= 1  # We need at least 1 expired
                                                  # group for this test

    search_expr = group_ds.get_name_prefix() + '%'

    result = list(gr.search(filter_expired=True, name=search_expr))
    assert (len(result) == len(non_expired))

    result = list(gr.search(filter_expired=False, name=search_expr))
    assert (len(result) == len(groups))


@with_setup(create_groups(num=5), remove_groups())
def test_search_spread():
    """ Group.search() for spread. """
    assert len(groups) >= 1  # We need at least 1 group for this test

    gr.clear()
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


@with_setup(create_groups(num=5), remove_groups())
def test_empty_search():
    """ Group.search() without args. """
    non_expired = filter(nonexpired_filter, groups)
    assert len(non_expired) >= 1  # We need at least 1 non-expired group for
                                  # this test

    result = list(gr.search())
    assert len(result) >= len(non_expired)
    assert (set(x['group_id'] for x in result).issuperset(
            set(x['entity_id'] for x in non_expired)))


@with_setup(create_groups(num=5), remove_groups())
def test_cyclic_membership():
    """Check if Group-API handles cyclic memberships."""
    assert len(groups) >= 2  # We need at least 2 groups for this test

    # Make every group[x+1] a member of group[x]
    modify_chain(groups, add_member)
    # Make every group[x] a member of group[x+1]
    modify_chain(groups[::-1], add_member)

    # Now that we have a cycle spanning the entire default_groups, let's
    # look for groups where default_groups[-1] is an indirect member.
    try:
        result = list(gr.search(member_id=groups[-1]['entity_id'],
                                indirect_members=True,
                                filter_expired=False))
        assert len(result) == len(groups)
    finally:
        modify_chain(groups, remove_member)
        modify_chain(groups[::-1], remove_member)


@with_setup(create_groups(num=5), remove_groups())
def test_search_members_simple():
    """ Group.search_members() by group_id. """
    assert len(groups) >= 3  # We need at least 3 groups for this test

    members = [g['entity_id'] for g in groups[1:3]]
    for m in members:
        add_member(groups[0]['entity_id'], m)

    try:
        result = list(gr.search_members(group_id=groups[0]['entity_id'],
                                        member_filter_expired=False))
        assert len(result) == len(members)
        assert (set(x['member_id'] for x in result) == set(members))
    finally:
        for m in members:
            remove_member(groups[0]['entity_id'], m)


@with_setup(create_groups(num=5), remove_groups())
def test_search_members_group_id_indirect():
    """ Group.search_members() indirect members of given group. """
    assert len(groups) >= 3  # We need at least 3 groups for this test

    modify_chain(groups, add_member)

    # *all* other groups are transient members of groups[0]
    try:
        result = list(gr.search_members(group_id=groups[0]['entity_id'],
                                        indirect_members=True,
                                        member_filter_expired=False))
        assert len(result) == len(groups)-1
        assert (set(x['member_id'] for x in result) ==
                set(x['entity_id'] for x in groups[1:]))
    finally:
        modify_chain(groups, remove_member)


@with_setup(create_groups(num=5), remove_groups())
def test_search_members_assert_keys():
    """ Check that required keys are returned by Group.search_members(). """
    assert len(groups) >= 2  # We need at least 2 groups for this test

    attributes = ('member_type', 'member_id', 'expire_date')
    add_member(groups[0]['entity_id'], groups[1]['entity_id'])

    try:
        result = list(gr.search_members(group_id=groups[0]['entity_id']))
        assert len(result) == 1
        for attr in attributes:
            assert attr in result[0].dict()
    finally:
        remove_member(groups[0]['entity_id'], groups[1]['entity_id'])


@with_setup(create_groups(num=5), remove_groups())
def test_search_members_by_id():
    """ Group.search_members() multiple member_ids. """
    assert len(groups) >= 3  # We need at least 3 groups for this test

    members = [g['entity_id'] for g in groups[1:3]]
    for m in members:
        add_member(groups[0]['entity_id'], m)
    try:
        result = list(gr.search_members(member_id=members,
                                        member_filter_expired=False))
        assert len(result) == len(members)
        assert (set(x['member_id'] for x in result) == set(members))
    finally:
        for m in members:
            remove_member(groups[0]['entity_id'], m)


@with_setup(create_groups(num=5), remove_groups())
def test_search_members_member_id_indirect_expired():
    """ Group.search_members() indirect members, filtering expired. """
    non_expired = filter(nonexpired_filter, groups)
    assert len(non_expired) >= 3  # We need at least 2 non-expired groups for
                                  # this test
    modify_chain(non_expired, add_member)

    # *all* non_expired groups are indirect members of non_expired[0]
    try:
        result = list(gr.search_members(member_id=non_expired[-1]['entity_id'],
                                        indirect_members=True,
                                        member_filter_expired=True))
        assert len(result) == len(non_expired)-1
        assert (set(x['member_id'] for x in result) ==
                set(x['entity_id'] for x in non_expired[1:]))
    finally:
        modify_chain(non_expired, remove_member)


@with_setup(create_groups(num=5), remove_groups())
def test_search_members_by_type():
    """ Group.search_members() by member_type. """
    assert len(groups) >= 2  # We need at least 2 groups for this test

    account_id = db_tools.get_initial_account_id()

    members = groups[1]['entity_id'], account_id
    for m in members:
        add_member(groups[0]['entity_id'], m)

    try:
        result = list(gr.search_members(member_type=co.entity_account,
                                        group_id=groups[0]["entity_id"],))
        assert len(result) == 1
        assert result[0]['member_id'] == account_id

        result = list(gr.search_members(member_type=co.entity_group,
                                        group_id=groups[0]["entity_id"],))
        assert len(result) == 1
        assert result[0]['member_id'] == groups[1]['entity_id']
    finally:
        for m in members:
            remove_member(groups[0]['entity_id'], m)


@with_setup(create_groups(num=5), remove_groups())
def test_search_members_by_spread():
    """ Group.search_members() by spread. """
    assert len(groups) >= 2  # We need at least 2 groups for this test
    assert group_spread is not None

    gr.clear()
    gr.find_by_name(groups[1]['group_name'])
    gr.add_spread(group_spread)

    try:
        # Make group[1] a child of group[0]
        modify_chain(groups[:2], add_member)
        result = list(gr.search_members(member_spread=group_spread,
                                        member_filter_expired=False,))
        assert len(result) == 1
        assert result[0]['member_id'] == groups[1]['entity_id']
    finally:
        gr.delete_spread(group_spread)
        modify_chain(groups[:2], remove_member)


@with_setup(create_groups(num=5), remove_groups())
def test_search_members_expired():
    """ Group.search_members() with member_filter_expired. """
    non_expired = set((g['entity_id'] for g in
                       filter(nonexpired_filter, groups)))
    expired = set((g['entity_id'] for g in groups)) - non_expired
    assert len(expired) >= 1  # We need at least one expired group
    # Check our sets
    assert not expired.intersection(non_expired)
    assert expired.union(non_expired) == set((g['entity_id'] for g in groups))

    modify_chain(groups, add_member)
    try:
        # Check that everything is there, when we disregard expired
        result = list(gr.search_members(group_id=expired.union(non_expired),
                                        member_filter_expired=False,))
        assert len(result) == len(groups)-1

        # Check that every *member* group that is *not expired* is returned
        result = list(gr.search_members(group_id=expired.union(non_expired),
                                        member_filter_expired=True,))
        expected_results = [len(expired),
                            len(expired)-1][int(groups[0]['entity_id']
                                                in expired)]
        assert len(result) == len(groups) - 1 - expected_results
        assert not set(x['member_id'] for x in result).intersection(expired)
    finally:
        modify_chain(groups, remove_member)
