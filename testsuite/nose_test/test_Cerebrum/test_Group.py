#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""Basic tests for Cerebrum/Group.py.

Searching (members and groups) has to be thoroughly tested.
"""
import sys
from nose.tools import raises, with_setup
from mx.DateTime import now, DateTimeDelta

import cerebrum_path, cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors


database = None
group = None
account = None
constants = None

default_groups = ({"entity_id": None,
                   "group_name": "group1",
                   "description": "Test group 1",},

                  {"entity_id": None,
                   "group_name": "group2",
                   "description": "Test group 2",},

                  {"entity_id": None,
                   "group_name": "group3",
                   "description": "Test group 3",
                   "expire_date": now() - DateTimeDelta(10)},
                  
                  {"entity_id": None,
                   "group_name": "group4",
                   "description": "Test group 4",},

                  {"entity_id": None,
                   "group_name": "group5",
                   "description": "Test group 5",},
                  )
default_no_expired = tuple(e for e in default_groups if not e.get("expire_date"))


def setup_module():
    global database, group, constants, account
    database = Factory.get("Database")()
    database.cl_init(change_program="nosetests")
    group = Factory.get("Group")(database)
    account = Factory.get("Account")(database)
    constants = Factory.get("Constants")(database)
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
# end setup_module


def teardown_module():

    for entry in default_groups:
        group.clear()
        try:
            group.find_by_name(entry["group_name"])
        except Errors.NotFoundError:
            continue
        
        group.delete()
        group.write_db()

        if "entity_id" in entry:
            del entry["entity_id"]
        
    database.commit()
# teardown_module


def create_groups(sequence):
    def wrapper():
        for entry in sequence:
            group.clear()
            group.populate(account.entity_id, constants.group_visibility_all,
                           entry["group_name"], entry["description"],
                           expire_date=entry.get("expire_date"))
            group.write_db()
            entry["entity_id"] = group.entity_id
            assert entry["entity_id"] is not None
        database.commit()
        group.clear()
        for entry in sequence:
            assert entry["entity_id"] is not None
    # return a closure to delay the actual group creation. Think a bit about
    # when the arguments to with_setup are evaluated.
    return wrapper
# end create_groups


def remove_groups(sequence):
    def wrapper():
        for entry in sequence:
            group.clear()
            group.find_by_name(entry["group_name"])
            group.delete()
            group.write_db()

            del entry["entity_id"]

        database.commit()

    return wrapper
# end teardown_module


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_simple_find():
    """Test Group.find()"""

    for entry in default_groups:
        group.clear()
        group.find(entry["entity_id"])
# end test_simple_find


@raises(Errors.NotFoundError)
def test_simple_find_fail():
    group.clear()
    group.find(-10) # negative IDs are impossible in Cerebrum
# end test_simple_find_fail


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_find_by_name():
    """Test Group.find_by_name."""

    for entry in default_groups:
        group.clear()
        group.find_by_name(entry["group_name"])
# end test_find_by_name


@raises(Errors.NotFoundError)
def test_find_by_name_fail():
    group.clear()
    group.find_by_name("asdasdasd1231231æøasdlasd")
# end test_find_by_name_fail


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_group_expired():

    for entry in default_groups:
        if not entry.get("expired_date"):
            continue
        
        group.find(entry["entity_id"])
        assert group.is_expired()
# end test_group_expired


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_membership1():
    """Test simple group membership"""

    e1 = default_groups[0] # does not matter which one
    e2 = default_groups[1]

    group.clear()
    group.find(e1["entity_id"])
    group.add_member(e2["entity_id"])
    group.write_db()
    assert group.has_member(e2["entity_id"])
    group.remove_member(e2["entity_id"])
    assert not group.has_member(e2["entity_id"])
# end test_membership1


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_membership2():
    """Test a bunch of add/has/remove members."""

    e1 = default_groups[0]
    test_case = default_groups[1:4]
    group.clear()
    group.find_by_name(e1["group_name"])

    for entry in test_case:
        group.add_member(entry["entity_id"])
    try:
        for entry in test_case:
            assert group.has_member(entry["entity_id"])
    finally:
        for entry in test_case:
            group.remove_member(entry["entity_id"])
# end test_membership2


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_search_id():
    """Group.search(group_id)"""

    group.clear()
    dg = default_groups
    assert len(list(group.search(group_id=dg[0]["entity_id"]))) == 1

    for seq_type in (tuple, set, list):
        result = list(group.search(group_id=seq_type((dg[0]["entity_id"],
                                                      dg[1]["entity_id"]))))
        assert len(result) == 2
# end test_search_id


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_search_result():
    """Check attributes in Group.search()'s db_rows'"""

    attributes = ("group_id", "name", "description", "visibility",
                  "creator_id", "create_date", "expire_date")
    group.clear()
    dg = default_groups
    db_row = list(group.search(group_id=dg[0]["entity_id"]))
    assert len(db_row) == 1

    db_row = db_row[0]
    for attr_name in attributes:
        assert db_row.has_key(attr_name)
# end test_search_result
    

def modify_chain(chain, operation):
    """Help function for creating/deleting memberships"""
    for index, item in enumerate(chain[:-1]):
        group.clear()
        group.find(item["entity_id"])
        operation(chain[index+1]["entity_id"])
# end modify_chain


def add_member(g, member):
    group.clear()
    group.find(g["entity_id"])
    group.add_member(member["entity_id"])
# end add_member


def remove_member(group, member):
    group.clear()
    group.find(group["entity_id"])
    group.remove_member(member["entity_id"])
# end add_member


@with_setup(create_groups(default_no_expired), remove_groups(default_no_expired))
def test_search_member():
    """Group.search(member_id)"""

    groups = default_no_expired
    assert len(groups) > 2

    group.clear()
    modify_chain(groups, group.add_member)

    # Now that the chain is built, let's search groups with member_id
    # First, let's search via direct membership.
    group.clear()
    result = list(group.search(member_id=groups[1]["entity_id"],
                               indirect_members=False))
    assert len(result) == 1
    assert result[0]["group_id"] == groups[0]["entity_id"]

    # And now via the transitive closure
    result = list(group.search(member_id=groups[-1]["entity_id"],
                               indirect_members=True))
    # The answer is the entire chain we've built
    assert len(result) == len(groups)-1
    assert (set(x["entity_id"] for x in groups[:-1]) ==
            set(x["group_id"] for x in result))

    modify_chain(groups, group.remove_member)
# end test_search_member


@with_setup(create_groups(default_no_expired), remove_groups(default_no_expired))
def test_search_member2():
    """Group.search(member_id) (complex membership graph)"""

    groups = default_no_expired
    assert len(groups) > 2

    group.clear()
    modify_chain(groups, group.add_member)
    modify_chain((groups[0], groups[2]), group.add_member)

    # now group test3 is a member of test2 and test1.

    result = list(group.search(member_id=groups[-1]["entity_id"],
                               indirect_members=True))
    assert len(result) == len(groups)-1
    assert (set(x["entity_id"] for x in groups[:-1]) ==
            set(x["group_id"] for x in result))
    modify_chain(groups, group.remove_member)
    modify_chain((groups[0], groups[2]), group.remove_member)
# end test_search_member2


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_search_name():
    """Group.search(name)"""

    group.clear()
    result = list(group.search(name="group1"))
    assert len(result) == 1
# end test_search_name


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_search_name_wildcard():
    """Group.search(name='%...%')"""

    group.clear()
    result = list(group.search(name="group%", filter_expired=False))
    assert len(result) == len(default_groups)
# end test_search_name_wildcard


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_search_description():
    """Group.search(description)"""

    group.clear()
    result = list(group.search(description="Test group 1"))
    assert len(result) == 1
# end test_search_name


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_search_description_wildcard():
    """Group.search(description='%...%')"""

    group.clear()
    result = list(group.search(description="Test group%", filter_expired=False))
    assert len(result) == len(default_groups)
# end test_search_name_wildcard


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_search_expired():
    """Check Group.search(filter_expired)"""

    group.clear()
    result = list(group.search(filter_expired=True, name="group%"))
    sample = list(x for x in default_groups if not x.get("expire_date"))
    assert (len(result) == len(sample))

    result = list(group.search(filter_expired=False, name="group%"))
    assert (len(result) == len(default_groups))
# end test_search_expired


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_search_spread():
    """Group.search(spread)."""
    
    group.clear()
    group.find(default_groups[0]["entity_id"])

    # It does not really matter which spread we pick out, as long as it is
    # something.
    any_spread = None
    for s in constants.fetch_constants(constants.Spread):
        if s._entity_type == constants.entity_group:
            any_spread = s
            break

    assert any_spread is not None
    group.add_spread(any_spread)

    result = list(group.search(spread=s))
    assert len(result) == 1
    assert result[0]["group_id"] == default_groups[0]["entity_id"]

    group.delete_spread(s)
# end test_search_spread


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_empty_search():
    """Group.search(<no params>)"""

    group.clear()
    result = list(group.search())
    assert len(result) == len(default_groups)
    assert (set(x["group_id"] for x in result).issuperset(
            set(x["entity_id"] for x in default_groups
                if not x.get("expire_date"))))
# end test_empty_search
    

@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_cyclic_membership():
    """Check if Group-API handles cyclic memberships."""

    group.clear()
    modify_chain(default_groups, group.add_member)
    modify_chain(default_groups[::-1], group.add_member)

    # Now that we have a cycle spanning the entire default_groups, let's look
    # for groups where default_groups[-1] is an indirect member.

    result = list(group.search(member_id=default_groups[-1]["entity_id"],
                               indirect_members=True,
                               filter_expired=False))
    assert len(result) == len(default_groups)

    modify_chain(default_groups, group.remove_member)
    modify_chain(default_groups[::-1], group.remove_member)
# end test_cyclic_membership


@with_setup(create_groups(default_no_expired), remove_groups(default_no_expired))
def test_search_members_simple():
    """Group.search_members(group_id)."""

    groups = default_no_expired
    members = groups[1], groups[2]
    
    group.clear()
    for m in members:
        add_member(groups[0], m)

    result = list(group.search_members(group_id=groups[0]["entity_id"]))
    assert len(result) == len(members)
    assert (set(x["member_id"] for x in result) ==
            set(x["entity_id"] for x in members))
# end test_search_members_simple


@with_setup(create_groups(default_no_expired), remove_groups(default_no_expired))
def test_search_members_group_id_indirect():
    """Group.search_members(group_id, indirect_members)."""

    chain = default_no_expired
    modify_chain(chain, group.add_member)
    
    # members of default_groups[0] are *all* other groups
    result = list(group.search_members(group_id=chain[0]["entity_id"],
                                       indirect_members=True))
    assert len(result) == len(chain)-1
    assert (set(x["member_id"] for x in result) ==
            set(x["entity_id"] for x in chain[1:]))
# end test_search_members_group_id_indirect


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_search_members_assert_keys():
    """Check that all keys are returned by Group.search_members()."""

    groups = default_groups
    add_member(groups[0], groups[1])

    result = list(group.search_members(group_id=groups[0]["entity_id"]))
    assert len(result) == 1
    x = result[0]
    attributes = ("member_type", "member_id", "expire_date")
    for attr in attributes:
        assert x.has_key(attr)
# end test_search_members_assert_keys

    
@with_setup(create_groups(default_no_expired), remove_groups(default_no_expired))
def test_search_members_by_id():
    """Group.search_members(member_id)"""
    
    groups = default_no_expired
    members = groups[1], groups[2]
    
    group.clear()
    for m in members:
        add_member(groups[0], m)

    ids = set(x["entity_id"] for x in members)
    result = list(group.search_members(member_id=ids))
    assert len(result) == len(members)
    assert (set(x["member_id"] for x in result) == ids)
# end test_search_members_by_id


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_search_members_member_id_indirect():
    """Group.search_members(member_id, indirect_members, member_filter_expired=False)."""

    modify_chain(default_groups, group.add_member)
    
    # members of default_groups[0] are *all* other groups
    result = list(group.search_members(member_id=default_groups[-1]["entity_id"],
                                       indirect_members=True,
                                       member_filter_expired=False))
    assert len(result) == len(default_groups)-1
    assert (set(x["member_id"] for x in result) ==
            set(x["entity_id"] for x in default_groups[1:]))
# end test_search_members_member_id_indirect


@with_setup(create_groups(default_no_expired), remove_groups(default_no_expired))
def test_search_members_member_id_indirect_expired():
    """Group.search_members(member_id, indirect_members, member_filted_expired=True)."""

    chain = default_no_expired
    modify_chain(chain, group.add_member)
    
    # members of chain[0] are *all* other groups
    result = list(group.search_members(member_id=chain[-1]["entity_id"],
                                       indirect_members=True))
    assert len(result) == len(chain)-1
    assert (set(x["member_id"] for x in result) ==
            set(x["entity_id"] for x in chain[1:]))
# end test_search_members_member_id_indirect_expired


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_search_members_by_type():
    """Group.search_members(member_type)"""

    groups = default_groups
    members = groups[1], {"entity_id": account.entity_id}

    for m in members:
        add_member(groups[0], m)

    result = list(group.search_members(member_type=constants.entity_account,
                                       group_id=groups[0]["entity_id"],))
    assert len(result) == 1
    assert result[0]["member_id"] == account.entity_id

    result = list(group.search_members(member_type=constants.entity_group,
                                       group_id=groups[0]["entity_id"],))
    assert len(result) == 1
    assert result[0]["member_id"] == groups[1]["entity_id"]
# end test_search_members_by_type


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_search_members_by_spread():
    """Group.search_members(member_spread)"""

    parent, child = default_groups[:2]

    # It does not really matter which spread we pick out, as long as it is
    # something suitable for groups.
    any_spread = None
    for s in constants.fetch_constants(constants.Spread):
        if s._entity_type == constants.entity_group:
            any_spread = s
            break

    assert any_spread is not None

    # assign the spread to child
    group.clear()
    group.find(child["entity_id"])
    group.add_spread(any_spread)

    # make child a member of parent
    group.clear()
    group.find(parent["entity_id"])
    group.add_member(child["entity_id"])

    result = list(group.search_members(member_spread=s))
    assert len(result) == 1
    assert result[0]["member_id"] == child["entity_id"]

    group.delete_spread(s)
# end test_search_members_by_spread


@with_setup(create_groups(default_groups), remove_groups(default_groups))
def test_search_members_expired():
    """Group.search_members(member_filter_expired)"""

    chain = default_groups
    expired = type(chain)(x for x in chain
                          if "expire_date" in x and x["expire_date"] <= now())
    total_memberships = len(chain)-1
    expired_memberships = len(expired)
    if expired[0] == chain[0]:
        expired_memberships -= 1
    
    assert expired
    assert expired_memberships > 0

    # make a chain with all memberships, including expired groups
    modify_chain(chain, group.add_member)

    # Check that everything is there, when we disregard expired
    result = list(group.search_members(
                      group_id=tuple(x["entity_id"] for x in chain),
                      member_filter_expired=False))
    assert len(result) == total_memberships

    result = list(group.search_members(
                      group_id=tuple(x["entity_id"] for x in chain),
                      member_filter_expired=True))
    assert len(result) == total_memberships - expired_memberships
    assert not set(x["member_id"] for x in result).intersection(
                   set(x["entity_id"] for x in expired))
# end test_search_members_expired

    
    

