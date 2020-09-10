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
HR import consumer.
"""
import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.config.loader import read_config as read_config_file
from Cerebrum.modules.amqp.config import get_connection_params
from Cerebrum.modules.amqp.consumer import ChannelSetup, Manager
from Cerebrum.modules.hr_import.config import HrImportConfig
from Cerebrum.modules.hr_import.handler import EmployeeHandler
from Cerebrum.utils.module import resolve
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.Utils import Factory


logger = logging.getLogger(__name__)


def get_config(config_file):
    """ Load config.

    :param str config_file:
        Read configuration from this file.

    :return ConsumerConfig:
        Returns a configuration object.
    """
    config = HrImportConfig()
    config.load_dict(read_config_file(config_file))
    return config


def set_pika_loglevel(level=logging.INFO, force=False):
    log = logging.getLogger('pika')

    if force or log.level == logging.NOTSET:
        log.setLevel(level)


def get_consumer(consumer_config, callback):
    connection_params = get_connection_params(consumer_config.connection)
    setup = ChannelSetup(
        exchanges=consumer_config.exchanges,
        queues=consumer_config.queues,
        bindings=consumer_config.bindings,
        flags=ChannelSetup.Flags.ALL,
        consumer_tag_prefix=consumer_config.consumer_tag,
    )
    return Manager(connection_params, callback, setup)


def get_importer(importer_config):
    im_init = resolve(importer_config.module)
    return im_init(importer_config.config_file)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Run a basic AMQP message consumer',
    )
    parser.add_argument(
        '-c', '--config',
        required=False,
        help='config to use (see Cerebrum.modules.consumer.config)',
    )

    add_commit_args(parser)

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('cronjob', args)
    # pika is very verbose in its logging
    set_pika_loglevel(logging.INFO)

    logger.info("Starting %s", parser.prog)
    logger.debug("args: %r", args)

    config = get_config(args.config)

    importer = get_importer(config.importer)
    logger.info('employee importer: %r', importer)

    callback = EmployeeHandler(
        import_init=importer,
        db_init=Factory.get('Database'),
        dryrun=not args.commit)

    consume = get_consumer(config.consumer, callback)
    try:
        consume.run()
    except KeyboardInterrupt:
        logger.info('Stopping (KeyboardInterrupt)')
    except Exception:
        logger.error('Stopping (unhandled exception)')
        raise
    finally:
        consume.stop()


if __name__ == '__main__':
    main()
