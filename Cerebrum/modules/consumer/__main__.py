#!/usr/bin/env python
# encoding: utf-8
"""
Main consumer object.

This is an example consumer, which can be used to handle MQ messages.
"""
import argparse
import getpass
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.config.loader import read_config as read_config_file
from Cerebrum.utils.module import resolve

from . import Manager, ChannelSetup
from .config import ConsumerConfig, get_connection_params


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
    return config


def set_pika_loglevel(level=logging.INFO, force=False):
    log = logging.getLogger('pika')

    if force or log.level == logging.NOTSET:
        log.setLevel(level)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Run a basic AMQP message consumer',
    )
    parser.add_argument(
        '-c', '--config',
        required=True,
        help='config to use (see Cerebrum.modules.consumer.config)',
    )

    parser.add_argument(
        '--callback',
        default='Cerebrum.modules.consumer/demo_callback',
        help='callback to process messages with',
    )
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('console', args)

    # pika is very verbose in its logging
    set_pika_loglevel(logging.INFO)

    logger.info("Starting %s", parser.prog)
    logger.debug("args: %r", args)

    # TODO: Load from file using tofh.config
    config = get_config(args.config)
    callback = resolve(args.callback)

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
