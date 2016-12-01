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
import getpass
import json
import os
import sys

import pika

from Cerebrum.modules.celery_tasks.apps.scheduler import schedule_message


class ConsumerCallback(collections.Callable):
    """
    """
    def __init__(self, args, **kwargs):
        """
        """
        self._args = args

    def __call__(self, channel, method, header, body):
        """
        """
        # or maybe ack after execution? ....
        channel.basic_ack(delivery_tag=method.delivery_tag)
        self._handle_scim_data(method, body)

    def _handle_scim_data(self, method, body):
        """
        """
        try:
            data_dict = json.loads(body)
            nbf = data_dict.get('nbf')
            if nbf is None:
                print('DEBUG: Message contains no scheduling data')
                return False
            eta = datetime.datetime.fromtimestamp(int(nbf))
            result_ticket = schedule_message.apply_async(
                kwargs={'routing_key': method.routing_key,
                        'body': body},
                eta=eta)
            print('DEBUG: Scheduled {jti} for {eta} as {ticket_id}'.format(
                jti=data_dict.get('jti', 'unknown-jti'),
                eta=eta,
                ticket_id=result_ticket.id))
        except Exception as e:
            sys.stderr.write('consumer_callback error: {0}\n'.format(e))
            sys.stderr.flush()


def main():
    """
    """
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
        '-e', '--target-exchange',
        metavar='EXCHANGE',
        type=str,
        dest='target_exchange',
        default='ex_scheduled_messages',
        help=('Exchage to send scheduled messages to '
              '(default: ex_scheduled_messages)'))
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
        default='tiny_consumer',
        help='Consumer tag (default: tiny_consumer)')
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
    if not args.password:
        try:
            args.password = getpass.getpass()
        except Exception as e:
            sys.stderr.write('Prompt terminated\n')
            sys.exit(errno.EACCES)
    elif os.path.isfile(args.password):
        try:
            with open(args.password, 'r') as fp:
                passwd = fp.readline()
                if passwd.strip():
                    args.password = passwd.strip()
        except Exception as e:
            sys.stderr.write('Unable to open password file: {0}'.format(e))
            sys.exit(1)
    creds_broker = pika.PlainCredentials(args.username, args.password)
    conn_params = pika.ConnectionParameters(args.hostname,
                                            args.port,
                                            virtual_host=args.vhost,
                                            ssl=True,
                                            credentials=creds_broker)
    conn_broker = pika.BlockingConnection(conn_params)
    channel = conn_broker.channel()
    consumer_callback = ConsumerCallback(args)
    channel.basic_consume(consumer_callback,
                          queue=args.queue,
                          no_ack=False,
                          consumer_tag=args.consumer_tag)
    print('Consumer active!')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print('Terminating...')


if __name__ == '__main__':
    main()
