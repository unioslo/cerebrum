#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for api.v1.group."""

from __future__ import unicode_literals

from flask import url_for


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
    assert res.json.get("members") == []
    group_bar.add_member(account_foo.entity_id)
    res = client.get(
        url_for("api_v1.group-members-list", name=group_bar.group_name),
        headers=auth_header,
    )
    assert res.status_code == 200
    assert res.json.get("members")[0].get("name") == account_foo.account_name


def test_group_members_crud(client, auth_header, group_bar, account_foo):
    url = url_for(
        "api_v1.group-members",
        name=group_bar.group_name,
        member_id=account_foo.entity_id,
    )
    not_a_member = client.get(url, headers=auth_header)
    assert not_a_member.status_code == 404
    put = client.put(url, headers=auth_header)
    assert put.json.get("name") == account_foo.account_name
    get = client.get(url, headers=auth_header)
    assert get.json.get("name") == account_foo.account_name
    delete = client.delete(url, headers=auth_header)
    assert delete.status_code == 204  # no content
    deleted = client.get(url, headers=auth_header)
    assert deleted.status_code == 404
