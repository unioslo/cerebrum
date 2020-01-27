#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Tests for Cerebrum.modules.gpg.data """

import pytest

import Cerebrum.Account
import Cerebrum.modules.gpg
import Cerebrum.modules.gpg.data


@pytest.fixture
def entity(database, cereconf, gpg_key):

    class ConfiguredAccount(
        Cerebrum.Account.Account,
        Cerebrum.modules.gpg.data.EntityGPGData,
    ):
        @property
        def _tag_to_recipients(self):
            return {
                'foo': [gpg_key],
                'bar': []
            }
    cac = ConfiguredAccount(database)
    cac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    return cac


def test_add_gpg_data_valid_tags(entity):
    message_ids = entity.add_gpg_data("foo", "hello")
    assert(len(message_ids) == 1)
    message_ids = entity.add_gpg_data("bar", "what")
    assert(len(message_ids) == 0)


def test_add_gpg_data_invalid_tag(entity):
    with pytest.raises(ValueError, message="expecting ValueError"):
        entity.add_gpg_data("nope", "disregard this")


def test_remove_gpg_data_by_tag(entity):
    entity.add_gpg_data("foo", "hello")
    removed = entity.remove_gpg_data_by_tag("foo")
    assert(removed == 1)


def test_search_gpg_data(entity):
    message_id = entity.add_gpg_message(
        tag="foo", recipient="me", message="hello")
    entity.add_gpg_message(tag="foo", recipient="me", message="hi there")
    entity.add_gpg_message(tag="foo", recipient="other", message="hello")
    assert (3 == len(entity.search_gpg_data(entity_id=entity.entity_id)))
    assert (3 == len(entity.search_gpg_data(tag="foo")))
    assert (2 == len(entity.search_gpg_data(recipient="me")))
    assert (1 == len(entity.search_gpg_data(message_id=message_id)))


def test_add_and_remove_gpg_messages(entity):
    message_id = entity.add_gpg_message(
        tag="faz", recipient="me", message="hello")
    removed = entity.remove_gpg_message(message_id=message_id)
    assert(removed == 1)
