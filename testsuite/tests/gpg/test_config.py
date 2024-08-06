#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Tests for Cerebrum.modules.gpg.config """
import pytest

import Cerebrum.Account
import Cerebrum.Errors
import Cerebrum.modules.gpg.config
import Cerebrum.modules.gpg.data


@pytest.fixture
def gpg_tags(gpg_key):
    return {
        'foo': [gpg_key],
        'bar': [],
    }


@pytest.fixture
def gpg_config(gpg_tags):
    config = Cerebrum.modules.gpg.config.GPGDataConfig({
        'tag_to_recipient_map': [
            {'tag': tag, 'recipients': rcp}
            for tag, rcp in gpg_tags.items()
        ],
    })
    return config


@pytest.fixture
def gpg_encrypter(gpg_config):
    return Cerebrum.modules.gpg.config.GpgEncrypter(gpg_config)


def test_encrypter_recipient_map(gpg_tags, gpg_encrypter):
    assert gpg_tags == gpg_encrypter.recipient_map


def test_encrypter_get_recipients(gpg_tags, gpg_encrypter):
    for tag in gpg_tags:
        assert gpg_encrypter.get_recipients(tag) == gpg_tags[tag]


def test_encrypter_get_invalid_recipients(gpg_encrypter):
    tag = 'this-tag-should-not-exist-f99a63edeebbe1cc'
    with pytest.raises(ValueError):
        assert gpg_encrypter.get_recipients(tag)


def test_encrypter_encrypt(gpg_encrypter, gpg_key):
    messages = list(
        gpg_encrypter.encrypt_message("foo", "super secret message"))
    assert len(messages) == 1
    assert len(messages[0]) == 3
    tag, key, gpg_message = messages[0]
    assert tag == "foo"
    assert key == gpg_key
    assert gpg_message


def test_encrypter_encrypt_empty(gpg_encrypter):
    messages = list(
        gpg_encrypter.encrypt_message("bar", "super secret message"))
    assert len(messages) == 0
