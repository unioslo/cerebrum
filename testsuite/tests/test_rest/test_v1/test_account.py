#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Tests for api.v1.account """

from flask import url_for


def test_get_account(client, auth_header, account_foo, person_foo):
    assert account_foo.account_name
    res = client.get(url_for('api_v1.account',
                             name=account_foo.account_name),
                     headers=auth_header)
    assert res.json.get('name') == account_foo.account_name
    assert res.json.get('owner').get('id') == person_foo.entity_id
