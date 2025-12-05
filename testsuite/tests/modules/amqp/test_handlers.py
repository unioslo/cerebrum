# encoding: utf-8
"""
Tests for mod:`Cerebrum.modules.amqp.handlers`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import pytest

from Cerebrum.modules.amqp import handlers as amqp_handlers
from Cerebrum.testutils.log_utils import StrictNullHandler


@pytest.fixture(scope="module", autouse=True)
def logger():
    return logging.getLogger(__name__)


@pytest.fixture(scope="module", autouse=True)
def _patch_logging(logger):
    """ catch badly formatted log records in log messages. """
    logger.addHandler(StrictNullHandler())
    logger.setLevel(-100)
    amqp_handlers.logger = logger


#
# AbstractConsumerCallback tests
#


def test_abstract_callback():
    with pytest.raises(TypeError):
        amqp_handlers.AbstractConsumerCallback()


#
# Event tests
#


class MockObject(object):

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockChannel(object):

    def __init__(self, channel_no):
        self.channel_no = int(channel_no)
        self.acked = []
        self.nacked = []

    def basic_ack(self, **kwargs):
        self.acked.append(kwargs)

    def basic_nack(self, **kwargs):
        self.nacked.append(kwargs)


@pytest.fixture
def event_channel():
    return MockChannel(1)


@pytest.fixture
def event_method():
    return MockObject(
        consumer_tag="foo",
        delivery_tag="bar",
        routing_key="foo.bar",
    )


@pytest.fixture
def event_props():
    return MockObject(
        content_type="application/json",
        content_encoding=None,
        headers={
            'X-Foo': "Bar",
        },
    )


@pytest.fixture
def event_body():
    return '{"text": "Hello world"}'.encode("utf-8")


@pytest.fixture
def event(event_channel, event_method, event_props, event_body):
    return amqp_handlers.Event(event_channel, event_method,
                               event_props, event_body)


def test_event_init(event):
    assert event


def test_event_content_type(event):
    assert event.content_type == "application/json"

    event.props.content_type = None
    assert event.content_type == "application/octet-stream"


def test_event_content_type_default(event):
    event.props.content_type = None
    assert event.content_type == "application/octet-stream"


def test_event_content_encoding(event):
    event.props.content_encoding = "deflate"
    assert event.content_encoding == "deflate"


def test_event_headers(event):
    assert event.headers == {'X-Foo': "Bar"}


def test_event_repr(event):
    repr_text = repr(event)
    assert "Event" in repr_text
    assert "type=application/json" in repr_text
    assert "key=foo.bar" in repr_text


#
# AbstractConsumerHandler tests
#


def test_abstract_handler_init():
    with pytest.raises(TypeError):
        amqp_handlers.AbstractConsumerHandler()


class CollectHandler(amqp_handlers.AbstractConsumerHandler):

    def __init__(self, handle_errors=False):
        self.ok = []
        self.errors = []
        self.handle_errors = handle_errors

    def handle(self, event):
        if event.body == "fail":
            raise RuntimeError("failed")

    def on_ok(self, event):
        super(CollectHandler, self).on_ok(event)
        self.ok.append(event)

    def on_error(self, event, error):
        super(CollectHandler, self).on_error(event, error)
        self.errors.append(event)
        return self.handle_errors


def test_handler_unhandled_error(event_channel, event_method, event_props):
    handle_event = CollectHandler(handle_errors=False)
    with pytest.raises(RuntimeError):
        handle_event(event_channel, event_method, event_props, "fail")

    assert len(handle_event.errors) == 1
    assert len(event_channel.acked) == 0


def test_handler_handled_error(event_channel, event_method, event_props):
    handle_event = CollectHandler(handle_errors=True)
    handle_event(event_channel, event_method, event_props, "fail")
    assert len(handle_event.errors) == 1
    assert len(event_channel.acked) == 0


def test_handler_ok(event_channel, event_method, event_props):
    handle_event = CollectHandler(handle_errors=False)
    handle_event(event_channel, event_method, event_props, "foo")
    assert len(handle_event.ok) == 1
    assert len(event_channel.acked) == 1


#
# test the demo handler
#


def test_demo_handler_ok(event_channel, event_method, event_props):
    handle_event = amqp_handlers.demo_handler
    handle_event(event_channel, event_method, event_props,
                 "foo".encode("ascii"))
    assert len(event_channel.acked) == 1


def test_demo_handler_error(event_channel, event_method, event_props):
    handle_event = amqp_handlers.demo_handler
    with pytest.raises(RuntimeError):
        handle_event(event_channel, event_method, event_props,
                     "fail".encode("ascii"))
    assert len(event_channel.acked) == 0
