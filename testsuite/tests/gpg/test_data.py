#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Tests for Cerebrum.modules.gpg.data """

import datetime
import pytest

import Cerebrum.Entity
import Cerebrum.modules.gpg.config
import Cerebrum.modules.gpg.data
from Cerebrum.Errors import NotFoundError
from Cerebrum.utils.gpg import gpgme_encrypt


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
def gpg_data(database):
    return Cerebrum.modules.gpg.data.GpgData(database)


@pytest.fixture
def entity_type_code(constant_module):
    return getattr(constant_module, '_EntityTypeCode')


@pytest.fixture
def entity_type(entity_type_code):
    code = entity_type_code('ed644db80a1051e1',
                            description='test type for gpg entity')
    code.insert()
    return code


@pytest.fixture
def entity(database, cereconf, gpg_config, entity_type):

    encrypter = Cerebrum.modules.gpg.config.GpgEncrypter(gpg_config)

    class GpgEntity(
        Cerebrum.modules.gpg.data.EntityGPGData,
        Cerebrum.Entity.Entity,
    ):
        _gpg_encrypter = encrypter

    obj = GpgEntity(database)
    obj.populate(entity_type)
    obj.write_db()
    return obj


def test_add_message(entity, gpg_key, gpg_data):
    tag = 'some-tag'
    payload = gpgme_encrypt(message='not encrypted, but who cares',
                            recipient_key_id=gpg_key)

    row = gpg_data.add_message(entity.entity_id, tag, gpg_key, payload)
    assert row['message_id'] > 0
    assert (
        row['entity_id'],
        row['tag'],
        row['recipient'],
        row['message']) == (entity.entity_id, tag, gpg_key, payload)


def test_get_message_by_id(entity, gpg_key, gpg_data):
    tag = 'some-tag'
    payload = gpgme_encrypt(message='secret message',
                            recipient_key_id=gpg_key)
    row = gpg_data.add_message(entity.entity_id, tag, gpg_key, payload)
    fetched = gpg_data.get_message_by_id(row['message_id'])
    assert dict(fetched) == dict(row)


@pytest.fixture
def gpg_message(database, entity, gpg_key, gpg_data):
    tag = 'some-unique-tag-ea7e7b0bb82c825f'
    payload = gpgme_encrypt(message='a super secret message',
                            recipient_key_id=gpg_key)
    orig = gpg_data.add_message(entity.entity_id, tag, gpg_key, payload)

    # manipulate the message so it looks a bit older
    database.execute(
        """
        UPDATE
          [:table schema=cerebrum name=entity_gpg_data]
        SET created = :ts
        WHERE message_id = :msgid
        """,
        {
            'msgid': orig['message_id'],
            'ts': datetime.datetime.now() - datetime.timedelta(days=1),
        })
    return dict(gpg_data.get_message_by_id(orig['message_id']))


def test_get_missing_message_by_id(gpg_data):
    message_id = -1  # should never exist
    with pytest.raises(NotFoundError):
        gpg_data.get_message_by_id(message_id)


def test_delete_message_by_id(gpg_message, gpg_data):
    message_id = gpg_message['message_id']
    row = gpg_data.delete_message_by_id(message_id)
    assert dict(row) == gpg_message
    with pytest.raises(NotFoundError):
        gpg_data.get_message_by_id(message_id)


def test_delete_missing_message_by_id(gpg_data):
    message_id = -1  # should never exist
    with pytest.raises(NotFoundError):
        gpg_data.delete_message_by_id(message_id)


def test_delete_by_tag(gpg_message, gpg_data):
    deleted = gpg_data.delete(tag=gpg_message['tag'])
    assert [dict(d) for d in deleted] == [gpg_message]


def test_delete_by_recipient(gpg_message, gpg_data):
    deleted = gpg_data.delete(recipient=gpg_message['recipient'])
    assert [dict(d) for d in deleted] == [gpg_message]


def test_delete_no_match(gpg_message, gpg_data):
    entity_id = -1  # shouldn't exist
    deleted = gpg_data.delete(entity_id=entity_id)
    assert len(list(deleted)) == 0


def test_search_by_tag(gpg_message, gpg_data):
    results = gpg_data.search(tag=gpg_message['tag'])
    assert [dict(d) for d in results] == [gpg_message]


def test_search_by_recipient(gpg_message, gpg_data):
    results = gpg_data.search(recipient=gpg_message['recipient'])
    assert [dict(d) for d in results] == [gpg_message]


def test_search_order(database, gpg_message, gpg_data):
    duplicate = gpg_data.add_message(gpg_message['entity_id'],
                                     gpg_message['tag'],
                                     gpg_message['recipient'],
                                     gpg_message['message_id'])
    results = gpg_data.search(tag=gpg_message['tag'])
    assert len(results) == 2
    assert dict(results[0]) == dict(duplicate)
    assert dict(results[1]) == gpg_message


def test_get_recipient(database, gpg_message, gpg_data):
    duplicate = gpg_data.add_message(gpg_message['entity_id'],
                                     gpg_message['tag'],
                                     gpg_message['recipient'],
                                     gpg_message['message_id'])
    results = gpg_data.get_messages_for_recipient(gpg_message['entity_id'],
                                                  gpg_message['tag'],
                                                  gpg_message['recipient'])
    assert len(results) == 2
    assert dict(results[0]) == dict(duplicate)
    assert dict(results[1]) == gpg_message


def test_get_recipient_latest(database, gpg_message, gpg_data):
    duplicate = gpg_data.add_message(gpg_message['entity_id'],
                                     gpg_message['tag'],
                                     gpg_message['recipient'],
                                     gpg_message['message_id'])
    results = gpg_data.get_messages_for_recipient(gpg_message['entity_id'],
                                                  gpg_message['tag'],
                                                  gpg_message['recipient'],
                                                  latest=True)
    assert len(results) == 1
    assert dict(results[0]) == dict(duplicate)


def test_add_gpg_data_valid_tags(entity):
    message_ids = entity.add_gpg_data("foo", "hello")
    assert len(message_ids) == 1
    message_ids = entity.add_gpg_data("bar", "what")
    assert len(message_ids) == 0


def test_add_gpg_data_invalid_tag(entity):
    with pytest.raises(ValueError, message="expecting ValueError"):
        entity.add_gpg_data("nope", "disregard this")


@pytest.fixture
def gpg_messages(gpg_data, entity):
    tags = ["TA-bb1c041fdfdac", "TB-640c7dff11c9b", "TB-640c7dff11c9b"]
    recp = ["RA-31c47e8a8b098", "RA-31c47e8a8b098", "RB-a5dda0c020fcc"]
    msgs = ["MA-0cea75b2ac88d", "MB-5d7dce5d5c3eb", "MC-fde294dffe2df"]

    messages = []
    for tag, recipient, encrypted in zip(tags, recp, msgs):
        messages.append(dict(gpg_data.add_message(
            entity_id=entity.entity_id,
            tag=tag,
            recipient=recipient,
            encrypted=encrypted,
        )))
    return messages


def test_search_gpg_data_by_entity(gpg_data, entity, gpg_messages):
    by_entity = list(gpg_data.search(entity_id=entity.entity_id))
    assert len(by_entity) == len(gpg_messages)

    message_ids = set(r['message_id'] for r in gpg_messages)
    result_ids = set(r['message_id'] for r in by_entity)
    assert result_ids == message_ids


def test_search_gpg_data_by_tag(gpg_data, gpg_messages):
    tag = gpg_messages[0]['tag']
    expected = [m for m in gpg_messages if m['tag'] == tag]

    by_tag = gpg_data.search(tag=tag)
    assert len(by_tag) == len(expected)

    result_ids = set(r['message_id'] for r in by_tag)
    message_ids = set(r['message_id'] for r in expected)
    assert result_ids == message_ids


def test_search_gpg_data_by_tags(gpg_data, gpg_messages):
    tags = set(r['tag'] for r in gpg_messages)

    by_tag = gpg_data.search(tag=tags)
    assert len(by_tag) == len(gpg_messages)

    result_ids = set(r['message_id'] for r in by_tag)
    message_ids = set(r['message_id'] for r in gpg_messages)
    assert result_ids == message_ids


def test_search_gpg_data_by_recipient(gpg_data, gpg_messages):
    recipient = gpg_messages[0]["recipient"]
    expected = [m for m in gpg_messages if m['recipient'] == recipient]

    by_recipient = gpg_data.search(recipient=recipient)
    assert len(by_recipient) == len(expected)

    result_ids = set(r['message_id'] for r in by_recipient)
    message_ids = set(r['message_id'] for r in expected)

    assert result_ids == message_ids


def test_search_gpg_data_by_recipients(gpg_data, gpg_messages):
    recipients = set(r['recipient'] for r in gpg_messages)

    by_recipient = gpg_data.search(recipient=recipients)
    assert len(by_recipient) == len(gpg_messages)

    result_ids = set(r['message_id'] for r in by_recipient)
    message_ids = set(r['message_id'] for r in gpg_messages)
    assert result_ids == message_ids


def test_search_gpg_data_by_message_id(gpg_data, gpg_messages):
    message_id = gpg_messages[0]['message_id']
    by_id = list(gpg_data.search(message_id=message_id))
    assert len(by_id) == 1
    assert by_id[0]['message_id'] == message_id


def test_search_gpg_data_by_message_ids(gpg_data, gpg_messages):
    message_ids = set(r['message_id'] for r in gpg_messages)

    by_id = list(gpg_data.search(message_id=message_ids))
    assert len(by_id) == len(message_ids)

    result_ids = set(r['message_id'] for r in by_id)
    assert result_ids == message_ids
