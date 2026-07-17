#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Tests for api.v1.person """

from __future__ import unicode_literals

from flask import url_for
from six import text_type


def test_get_person(client, auth_header, person_foo):
    url = url_for('api_v1.person', id=person_foo.entity_id)
    get = client.get(url, headers=auth_header)
    assert get.status_code == 200
    assert get.json.get('id') == person_foo.entity_id
    assert text_type(person_foo.birth_date) in get.json.get('birth_date')


def test_get_person_accounts(client, auth_header, person_foo, account_foo):
    url = url_for('api_v1.person-accounts', id=person_foo.entity_id)
    get = client.get(url, headers=auth_header)
    assert get.status_code == 200
    assert get.json.get('accounts')[0]['name'] == account_foo.account_name
