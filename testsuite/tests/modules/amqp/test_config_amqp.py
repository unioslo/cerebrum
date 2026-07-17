# encoding: utf-8
"""
Tests for mod:`Cerebrum.modules.amqp.config`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import pytest

from Cerebrum.modules.amqp import config as amqp_config


#
# Exchange config tests
#


EXCHANGE_CONFIG = {
    'name': "test-exhange",
    'exchange_type': "topic",
    'durable': True,
}


@pytest.fixture
def exchange_config():
    config = amqp_config.Exchange()
    config.load_dict(EXCHANGE_CONFIG)
    return config


def test_exchange_config(exchange_config):
    exchange_config.validate()
    assert exchange_config.name == EXCHANGE_CONFIG['name']
    assert exchange_config.exchange_type == EXCHANGE_CONFIG['exchange_type']
    assert exchange_config.durable == EXCHANGE_CONFIG['durable']


#
# Queue config tests
#


QUEUE_CONFIG = {
    'name': "test-queue",
    'durable': True,
    'exclusive': False,
    'auto_delete': False,
}


@pytest.fixture
def queue_config():
    config = amqp_config.Queue()
    config.load_dict(QUEUE_CONFIG)
    return config


def test_queue_config(queue_config):
    queue_config.validate()
    assert queue_config.name == QUEUE_CONFIG['name']
    assert queue_config.durable == QUEUE_CONFIG['durable']
    assert queue_config.exclusive == QUEUE_CONFIG['exclusive']
    assert queue_config.auto_delete == QUEUE_CONFIG['auto_delete']


#
# Binding config tests
#


BINDING_CONFIG = {
    'exchange': EXCHANGE_CONFIG['name'],
    'queue': QUEUE_CONFIG['name'],
    'routing_keys': [
        "foo.#",
        "bar.*",
    ],
}


@pytest.fixture
def binding_config():
    config = amqp_config.Binding()
    config.load_dict(BINDING_CONFIG)
    return config


def test_binding_config(binding_config):
    binding_config.validate()
    assert binding_config.exchange == BINDING_CONFIG['exchange']
    assert binding_config.queue == BINDING_CONFIG['queue']
    assert binding_config.routing_keys == BINDING_CONFIG['routing_keys']


#
# Connection config tests
#


PASSWORD = "example-pass"
CONNECTION_CONFIG = {
    'username': "example-user",
    'password': "plaintext:" + PASSWORD,
    'host': "localhost",
    'port': 5671,
    'ssl_enable': True,
    'virtual_host': "default",
}


@pytest.fixture
def connection_config():
    config = amqp_config.Connection()
    config.load_dict(CONNECTION_CONFIG)
    return config


def test_connection_config(connection_config):
    connection_config.validate()
    assert connection_config.host == CONNECTION_CONFIG['host']
    assert connection_config.port == CONNECTION_CONFIG['port']
    assert connection_config.ssl_enable == CONNECTION_CONFIG['ssl_enable']
    assert connection_config.virtual_host == CONNECTION_CONFIG['virtual_host']
    assert connection_config.username == CONNECTION_CONFIG['username']
    assert connection_config.password == CONNECTION_CONFIG['password']


#
# ConsumerConfig tests
#


CONSUMER_CONFIG = {
    'connection': CONNECTION_CONFIG,
    'consumer_tag': "example-tag",
    'exchanges': [EXCHANGE_CONFIG],
    'queues': [QUEUE_CONFIG],
    'bindings': [BINDING_CONFIG],
}


@pytest.fixture
def consumer_config():
    config = amqp_config.ConsumerConfig()
    config.load_dict(CONSUMER_CONFIG)
    return config


def test_consumer_config(consumer_config):
    consumer_config.validate()
    assert consumer_config.consumer_tag == CONSUMER_CONFIG['consumer_tag']
    assert len(consumer_config.exchanges) == len(CONSUMER_CONFIG['exchanges'])
    assert len(consumer_config.queues) == len(CONSUMER_CONFIG['queues'])
    assert len(consumer_config.bindings) == len(CONSUMER_CONFIG['bindings'])


#
# ConsumerConfig tests
#


PUBLISHER_CONFIG = {
    'connection': CONNECTION_CONFIG,
    'exchange': EXCHANGE_CONFIG,
}


@pytest.fixture
def publisher_config():
    config = amqp_config.PublisherConfig()
    config.load_dict(PUBLISHER_CONFIG)
    return config


def test_publisher_config(publisher_config):
    publisher_config.validate()
    assert True


#
# Helper tests
#


def test_get_credentials(connection_config):
    creds = amqp_config.get_credentials(connection_config)
    assert creds.username == CONNECTION_CONFIG['username']
    assert creds.password == PASSWORD


def test_get_ssl_options(connection_config):
    ssl_opts = amqp_config.get_ssl_options(connection_config)
    assert ssl_opts.server_hostname == CONNECTION_CONFIG['host']
    assert ssl_opts.context.check_hostname


def test_get_ssl_options_disabled(connection_config):
    connection_config.ssl_enable = False
    ssl_opts = amqp_config.get_ssl_options(connection_config)
    assert ssl_opts is None


def test_get_connection_params(connection_config):
    conn_params = amqp_config.get_connection_params(connection_config)
    conn_params.host == CONNECTION_CONFIG['host']
    conn_params.port == CONNECTION_CONFIG['port']
