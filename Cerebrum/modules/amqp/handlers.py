# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
"""
Abstract callbacks for use with :mod:`.consumer`

Example
=======

::

    class MyHandler(AbstractConsumerHandler):

        def __init__(self, config):
            self.config = config

        def handle(self, event):
            encoding = event.headers.get('Content-Encoding', 'utf-8')
            body = (b'' or event.body).decode(encoding)
            if body == self.config.get('expected'):
                print('got expected!')
            else:
                print('not really interested...')
"""
import abc
import collections
import logging

import six


logger = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class AbstractConsumerCallback(collections.Callable):
    """ A minimal callback API.

    Consumer callbacks are callables that takes a given set of arguments.
    """

    @abc.abstractmethod
    def __call__(self, channel, method, props, body):
        """
        :type channel: pika.channel.Channel
        :type method: pika.spec.Deliver
        :type props: pika.spec.BasicProperties
        :type body: bytes
        """
        pass


class Event(object):
    """ A simple wrapper for messages and message metadata. """

    default_content_type = 'text/plain'
    default_content_encoding = 'ascii'

    def __init__(self, channel, method, props, body):
        """
        :type channel: pika.channel.Channel
        :type method: pika.spec.Deliver
        :type props: pika.spec.BasicProperties
        :type body: bytes
        """
        self.channel = channel
        self.method = method
        self.props = props
        self.body = body

    @property
    def content_type(self):
        """ Content-Type """
        return self.props.content_type or self.default_content_type

    @property
    def content_encoding(self):
        """ Content-Encoding """
        return self.props.content_encoding or self.default_content_encoding

    @property
    def headers(self):
        """ Headers. """
        # TODO: Wrap in werkzeug.datastructures.Headers or similar
        # case-insensitive dict-like?
        return self.props.headers or {}

    def __repr__(self):
        return '<{cls.__name__} type={ct} enc={ce} len={bl} key={rk}>'.format(
            cls=type(self),
            ct=self.content_type,
            ce=self.content_encoding,
            bl=len(self.body),
            rk=self.method.routing_key,
        )


@six.add_metaclass(abc.ABCMeta)
class AbstractConsumerHandler(collections.Callable):
    """
    A minimal callback *handler*.

    :meth:`.handle`
        Handle events.

    :meth:`.on_ok`
        Called if :meth:`.handle` completes without errors.  Typically used to
        *ack* an event.

    :meth:`.on_error`
        Called if an unhandled exception is raised from :meth:`.handle`.
        Typically used to *reschedule* an event or report fatal errors.
    """

    def __init__(self, *args, **kwargs):
        pass

    def _make_event(self, channel, method, header, body):
        return Event(channel, method, header, body)

    def __call__(self, channel, method, header, body):
        event = Event(channel, method, header, body)

        try:
            self.handle(event)
        except Exception as error:
            logger.debug(
                "Unhandled error on channel=%r, method=%r",
                channel, method)
            if not self.on_error(event, error):
                raise
        else:
            self.on_ok(event)

    @abc.abstractmethod
    def handle(self, event):
        """ Handle event.  """
        pass

    @abc.abstractmethod
    def reschedule(self, event, dates):
        """Reschedule future events."""
        pass

    def on_error(self, event, error):
        """
        Handle unexpected error.

        :return bool:
            If this method returns a truthy value, the error is considered
            *handled*.
        """
        # Note: You generally don't want to nack - as the message will be
        # immediately re-queued and re-processed (if queue is empty)
        # ct = event.method.consumer_tag
        # dt = event.method.delivery_tag
        # logger.debug('requeue %s/%s', ct, dt)
        # event.channel.basic_nack(delivery_tag=dt)

    def on_ok(self, event):
        """
        Handle completion.

        This is typically used to *ack* messages after successful handling of
        the event.
        """
        ct = event.method.consumer_tag
        dt = event.method.delivery_tag
        logger.debug('confirm %s/%s', ct, dt)
        event.channel.basic_ack(delivery_tag=dt)


class _Demo(AbstractConsumerHandler):
    """ Demo handler. """

    def handle(self, event):
        logger.info('got event: %r on channel %r', event, event.channel)
        if 'fail' in event.body.decode(event.content_encoding):
            raise RuntimeError('intentional, body contains "fail"')

    def reschedule(self, event, dates):
        pass


demo_handler = _Demo()
