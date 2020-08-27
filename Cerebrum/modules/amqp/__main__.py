#!/usr/bin/env python
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
Example message broker consumer.

This is a simple, generic example consumer.  It can be used directly (by
providing a config file and callback), or it can be used as an example on how
to implement consumers.
"""
import argparse
import getpass
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.config.loader import read_config as read_config_file
from Cerebrum.utils.module import resolve

from .config import ConsumerConfig, get_connection_params
from .consumer import ChannelSetup, Manager


logger = logging.getLogger(__name__)


def get_config(config_file):
    """ Load a configuration file.

    :param str config_file:
        Read configuration from this file.

    :return ConsumerConfig:
        Returns a configuration object.
    """
    config = ConsumerConfig()
    config.load_dict(read_config_file(config_file))
    config.validate()
    return config


def set_pika_loglevel(level=logging.INFO, force=False):
    """
    Apply a (default) log level for the 'pika' logger.

    :param int level: log level to set
    :param bool force: force the new log level
    """
    log = logging.getLogger('pika')

    if force or log.level == logging.NOTSET:
        log.setLevel(level)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Run a basic AMQP 0.9.1 message consumer',
    )
    parser.add_argument(
        '-c', '--config',
        required=True,
        help='config to use (see Cerebrum.modules.consumer.config)',
    )
    parser.add_argument(
        '--callback',
        default='Cerebrum.modules.amqp.handlers/demo_handler',
        help='callback to process messages with',
    )
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('console', args)
    # pika is very verbose in its logging
    set_pika_loglevel(logging.INFO)

    logger.info("Starting %s", parser.prog)
    logger.debug("args: %r", args)

    config = get_config(args.config)
    callback = resolve(args.callback)

    # Prompt for password if only a username is given
    if config.connection.username and not config.connection.password:
        try:
            config.connection.password = getpass.getpass(
                'password for {0}: '.format(config.connection.username))
        except Exception as e:
            raise SystemExit('Prompt terminated: {0}'.format(e))

    connection_params = get_connection_params(config.connection)
    setup = ChannelSetup(
        exchanges=config.exchanges,
        queues=config.queues,
        bindings=config.bindings,
        flags=ChannelSetup.Flags.ALL,
        consumer_tag_prefix=config.consumer_tag,
    )
    consumer = Manager(connection_params, callback, setup)

    try:
        consumer.run()
    except KeyboardInterrupt:
        logger.info('Stopping (KeyboardInterrupt)')
        consumer.stop()
    except Exception:
        logger.error('Stopping (unhandled exception)', exc_info=True)
        consumer.stop()


if __name__ == '__main__':
    main()
