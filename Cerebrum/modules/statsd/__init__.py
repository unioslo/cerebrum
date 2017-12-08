# encoding: utf-8
#
# Copyright 2017 University of Oslo, Norway
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
""" Cerebrum statsd client and factory.


Usage
-----

    from Cerebrum.modules.statsd import make_client
    from Cerebrum.modules.statsd.config import load_config

    config = load_config()
    client = make_client(config, prefix='my-test')

    # Stats will be prefixed '[<config.prefix>.]my-test'
    # Use according to docs: https://statsd.readthedocs.io/

    client.incr('foo')

    with client.pipeline() as p:
        p.gauge('bar', 4)
        p.decr('foo')

    with client.timer('time'):
        import time
        time.sleep(0.5)


Dummy client
------------
If `config.enable` is set to `False`, the `NullStatsClient` will be used.


Debug
-----
To see what stats are sent/would be sent, add
`Cerebrum.modules.statsd:StatsLoggerMixin` to `config.mixins`, and make sure
that log messages to the logger `Cerebrum.modules.statsd` are handled
somewhere.

"""
from __future__ import absolute_import

import logging
import statsd
import statsd.client
from Cerebrum.utils.module import resolve


logger = logging.getLogger(__name__)


class StatsLoggerMixin(statsd.client.StatsClientBase):
    """ A statsd client mixin that logs all sent stats. """

    log_level = logging.INFO

    def _send(self, data):
        logger.log(self.log_level, 'send: {0}'.format(repr(data)))
        super(StatsLoggerMixin, self)._send(data)


class NullStatsClient(statsd.client.StatsClientBase):
    """ StatsClient implementation that does nothing.

    This client should be used if there's no wish to actually send metrics.  It
    is more or less identical to `StatsClient`, but will simply not attempt to
    send any metrics.
    """
    def __init__(self, prefix=None, maxudpsize=512, **kwargs):
        self._prefix = prefix
        # Needed to support the default pipeline implementation:
        self._maxudpsize = maxudpsize

    def _send(self, data):
        """ Don't actually send anything. """
        pass

    def pipeline(self):
        return statsd.client.Pipeline(self)


def _build_client_cls(config):
    """ Build a statsd client class from config.

    :param StatsConfig config:

    :return type:
        Returns a subclass of ``cls`` and ``mixins``.
    """
    base = NullStatsClient
    if config.enable:
        base = statsd.client.StatsClient
    mixins = [resolve(i) for i in config.mixins]

    for cls in mixins:
        if not (isinstance(cls, type) and
                issubclass(cls, statsd.client.StatsClientBase)):
            raise TypeError("invalid mixin: {0!r}".format(cls))

    bases = tuple(mixins or ()) + (base, )
    return type('_StatsClient', bases, {})


def make_client(config, prefix=None):
    """ Get an appropriate Statsd client from config.

    :param StatsConfig config:
        The config to get a client for.

    :param str prefix:
        A sub-prefix to give the client.

    :return StatsClientBase:
        A statsd client.
    """
    cls = _build_client_cls(config)
    prefix = '.'.join(part for part in (config.prefix, prefix) if part)

    logger.info("statsd client: prefix={0} enabled={1}".format(prefix,
                                                               config.enable))
    logger.debug("statsd client: mro={0}".format(repr(cls.mro()[1:])))

    return cls(prefix=prefix,
               host=config.host,
               port=config.port,
               ipv6=config.ipv6)
