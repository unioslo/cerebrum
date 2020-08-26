#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for api.v1.group."""

from __future__ import unicode_literals

import jsonschema
import six

from flask import url_for

from Cerebrum.rest.api import db, utils
from Cerebrum.rest.api.v1.group import GroupMember


def test_group_crud(client, auth_header, group_bar):
    name = group_bar.group_name
    group_bar.delete()
    data = {"description": "my group ❤", "visibility": "all"}
    url = url_for("api_v1.group", name=name)
    create = client.put(url, data=data, headers=auth_header)
    assert create.status_code == 201  # created
    get = client.get(url, headers=auth_header)
    assert get.status_code == 200
    assert create.json.get("id") == get.json.get("id")
    assert create.json.get("name") == get.json.get("name") == name
    assert create.json.get("visibility") == get.json.get("visibility") == "all"
    assert create.json.get("created_at") == get.json.get("created_at")
    data["description"] == "foo"
    update = client.put(url, data=data, headers=auth_header)
    assert update.json.get("description") == data.get("description")
    delete = client.delete(url, headers=auth_header)
    assert delete.status_code == 204  # no content
    deleted = client.get(url, headers=auth_header)
    assert deleted.status_code == 404


def test_group_members_list(client, auth_header, group_bar, account_foo):
    res = client.get(
        url_for("api_v1.group-members-list", name=group_bar.group_name),
        headers=auth_header,
    )
    assert res.status_code == 200
    assert_group_member_list(res.json, [])
    group_bar.add_member(account_foo.entity_id)
    res = client.get(
        url_for("api_v1.group-members-list", name=group_bar.group_name),
        headers=auth_header,
    )
    assert res.status_code == 200
    assert_group_member_list(res.json, [account_foo])


def test_group_members_crud(client, auth_header, group_bar, account_foo):
    url = url_for(
        "api_v1.group-members",
        name=group_bar.group_name,
        member_id=account_foo.entity_id,
    )
    not_a_member = client.get(url, headers=auth_header)
    assert not_a_member.status_code == 404
    put = client.put(url, headers=auth_header)
    assert put.status_code == 200
    assert_group_member(put.json, account_foo)
    get = client.get(url, headers=auth_header)
    assert get.status_code == 200
    assert_group_member(get.json, account_foo)
    delete = client.delete(url, headers=auth_header)
    assert delete.status_code == 204  # no content
    deleted = client.get(url, headers=auth_header)
    assert deleted.status_code == 404


def assert_group_member_list(json, members):
    for member, account in six.moves.zip(json.get("members"), members):
        assert_group_member(member, account)


def assert_group_member(json, account):
    jsonschema.validate(json, GroupMember.__schema__)
    assert json == {
        "href": href(account),
        "type": str(getattr(db.const, "EntityType")(account.entity_type)),
        "id": account.entity_id,
        "name": account.account_name,
    }


def href(account):
    return utils.href_from_entity_type(
        entity_type=account.entity_type,
        entity_id=account.entity_id,
        entity_name=utils.get_entity_name(account),
    )
