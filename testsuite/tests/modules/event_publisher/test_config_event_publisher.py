# encoding: utf-8
""" Unit tests for `Cerebrum.modules.event_publisher.config`. """

import Cerebrum.modules.event_publisher.config


ep_config = Cerebrum.modules.event_publisher.config


EXAMPLE_CONFIG_CONNECTION = {
    'host': "localhost",
    'port': 5671,
    'ssl_enable': True,
    'virtual_host': "default",
    'username': "guest",
    'password': "plaintext:guest",
}

EXAMPLE_CONFIG_FORMATTER = {
    'issuer': "http://localhost/",
    'urltemplate': "http://localhost/v1/{entity_type}/{entity_id}",
    'keytemplate': "localhost.scim.{entity_type}.{event}",
}


EXAMPLE_CONFIG_COLLECTOR = {
    'run_interval': 180,
    'failed_limit': 10,
    'failed_delay': 1200,
    'unpropagated_delay': 5400,
}


EXAMPLE_CONFIG = {
    'event_publisher': {
        'connection': EXAMPLE_CONFIG_CONNECTION,
        'exchange': {
            'durable': True,
            'exchange_type': "topic",
            'name': "from_cerebrum",
        },
    },
    'event_formatter': EXAMPLE_CONFIG_FORMATTER,
    'event_daemon_collector': EXAMPLE_CONFIG_COLLECTOR,
}


def test_scim_formatter_config():
    # This probably belongs in another test module
    config = ep_config.ScimFormatterConfig()
    config.load_dict(EXAMPLE_CONFIG_FORMATTER)
    config.validate()
    config.dump_dict() == EXAMPLE_CONFIG_FORMATTER


def test_event_collector_config():
    config = ep_config.EventCollectorConfig()
    config.load_dict(EXAMPLE_CONFIG_COLLECTOR)
    config.validate()
    config.dump_dict() == EXAMPLE_CONFIG_COLLECTOR


def test_event_daemon_config():
    config = ep_config.EventDaemonConfig()
    config.load_dict(EXAMPLE_CONFIG)
    config.validate()
    config.dump_dict() == EXAMPLE_CONFIG
