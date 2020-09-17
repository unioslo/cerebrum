#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016 University of Oslo, Norway
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
tiny_consumer is still in POC stage.
"""

import argparse
import collections
import datetime
import errno
import json
import os
import ssl
import sys

import pika

from Cerebrum.Utils import Factory, read_password
from Cerebrum.modules.celery_tasks.apps.scheduler import schedule_message


class ConsumerCallback(collections.Callable):
    """
    """
    def __init__(self, args, **kwargs):
        """
        """
        self._args = args
        self._logger = args.logger

    def __call__(self, channel, method, header, body):
        """
        """
        try:
            self._handle_scim_data(method, body)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            self._logger.error('Consumer-callback error: {0}\n'.format(e))

    def _handle_scim_data(self, method, body):
        """
        """
        data_dict = json.loads(body)
        jti = data_dict.get('jti', 'unknown-jti')
        nbf = data_dict.get('nbf')
        if nbf is None:
            self._logger.debug(
                'Message {jti} contains no scheduling data'.format(
                    jti=jti))
            return False
        if not nbf or not str(nbf).isdigit():
            self._logger.warn(
                'Message {jti} contains invalid or empty "nbf" field'.format(
                    jti=jti))
            return False
        eta = datetime.datetime.fromtimestamp(int(nbf))
        result_ticket = schedule_message.apply_async(
            kwargs={'routing_key': method.routing_key,
                    'body': body},
            eta=eta)
        self._logger.info(
            'Scheduled {jti} for {eta} as {ticket_id}'.format(
                jti=jti,
                eta=eta,
                ticket_id=result_ticket.id))
        return True


def main():
    """
    """
    logger = Factory.get_logger('cronjob')
    parser = argparse.ArgumentParser(
        description='The following options are available')
    parser.add_argument(
        '-H', '--hostname',
        metavar='HOSTNAME/IP',
        type=str,
        dest='hostname',
        default='localhost',
        help='MQ hostname / IP address (default: localhost)')
    parser.add_argument(
        '-d', '--dryrun',
        action='store_true',
        dest='dryrun',
        default=False,
        help='Do not actually schedule the tasks. Just logg and be happy')
    parser.add_argument(
        '-q', '--queue',
        metavar='QUEUE',
        type=str,
        dest='queue',
        default='q_scheduling',
        help='Queue to consume from (default: q_scheduling)')
    parser.add_argument(
        '-P', '--port',
        metavar='PORT',
        type=int,
        dest='port',
        default=5671,
        help='AMQP port (default: 5671)')
    parser.add_argument(
        '-p', '--password',
        metavar='PASSWORD[FILE]',
        type=str,
        dest='password',
        default='',
        help=('Password / text-file containing the target password'
              ' (default & recommended: prompt for passwd)'))
    parser.add_argument(
        '-t', '--consumer-tag',
        metavar='TAG',
        type=str,
        dest='consumer_tag',
        default='tiny_scheduler',
        help='Consumer tag (default: tiny_scheduler)')
    parser.add_argument(
        '-u', '--username',
        metavar='USERNAME',
        type=str,
        dest='username',
        default='cerebrum',
        help='Subscriber username (default: cerebrum)')
    parser.add_argument(
        '-V', '--vhost',
        metavar='VHOST',
        type=str,
        dest='vhost',
        default='/no/uio/integration',
        help='Vhost (default: /no/uio/integration)')
    args = parser.parse_args()
    args.logger = logger
    logger.info('tiny_scheduler started')
    if not args.password:
        try:
            args.password = read_password(args.username, args.hostname)
        except Exception as e:
            logger.error(
                'Unable to retrieve password for user {username}: '
                '{error}'.format(username=args.username, error=e))
            sys.exit(errno.EACCES)
    elif os.path.isfile(args.password):
        try:
            with open(args.password, 'r') as fp:
                passwd = fp.readline()
                if passwd.strip():
                    args.password = passwd.strip()
        except Exception as e:
            logger.error('Unable to open password file: {0}'.format(e))
            sys.exit(1)
    creds_broker = pika.PlainCredentials(args.username, args.password)
    ssl_context = ssl.create_default_context()
    ssl_opts = pika.SSLOptions(ssl_context, args.hostname)
    conn_params = pika.ConnectionParameters(args.hostname,
                                            args.port,
                                            virtual_host=args.vhost,
                                            ssl_options=ssl_opts,
                                            credentials=creds_broker)
    conn_broker = pika.BlockingConnection(conn_params)
    channel = conn_broker.channel()
    consumer_callback = ConsumerCallback(args)
    channel.basic_consume(
        on_message_callback=consumer_callback,
        queue=args.queue,
        auto_ack=True,
        consumer_tag=args.consumer_tag)
    logger.info('Consumer active!')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info('Terminating...')


if __name__ == '__main__':
    main()
