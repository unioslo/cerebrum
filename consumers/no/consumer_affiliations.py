#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2019 University of Oslo, Norway
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
"""Consumer to handle things related to affiliations

Currently this only deals with removing group memberships for accounts owned by
persons without affiliations.
"""

import argparse
import functools
import json
import logging

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.config.configuration import (ConfigDescriptor, Configuration,
                                           Namespace)
from Cerebrum.config.loader import read, read_config
from Cerebrum.modules.event.mapping import CallbackMap
from Cerebrum.modules.event_consumer import get_consumer
from Cerebrum.modules.event_consumer.config import AMQPClientConsumerConfig
from Cerebrum import logutils
from Cerebrum.Errors import NotFoundError

logger = logging.getLogger(__name__)

callback_functions = CallbackMap()
callback_filters = CallbackMap()


class FPEConsumerConfig(Configuration):
    """Config combining class."""
    consumer = ConfigDescriptor(Namespace, config=AMQPClientConsumerConfig)


def load_config(filepath=None):
    """Load config for this consumer."""
    config_cls = FPEConsumerConfig()
    if filepath:
        config_cls.load_dict(read_config(filepath))
    else:
        read(config_cls, 'consumer_affiliations')
    config_cls.validate()
    return config_cls


@callback_functions('no.uio.cerebrum.scim.persons.modify')
def handle_person(database, data):
    """Remove group memberships if no more affiliations on person

    Assumes that the event has been generated after the removal of the
    affiliation, and that a pe.get_affiliations() call returns the remaining
    ones.

    :param database: Cerebrum database object
    :param data:
    :return:
    """
    pid = int(data.get('sub').split('/')[-1])
    pe = Factory.get('Person')(database)
    try:
        pe.find(pid)
    except NotFoundError:
        logger.info('Person id %s not found. Skipping', pid)
        return
    if not pe.get_affiliations():
        logger.info(
            'Person %s has no affiliations. Removing group memberships', pid)
        pu = Factory.get('PosixUser')(database)
        gr = Factory.get('Group')(database)
        ac = Factory.get('Account')(database)
        for acc_row in pe.get_accounts():
            pu.clear()
            acc_id = acc_row['account_id']
            try:
                pu.find(acc_id)
                acc_name = pu.account_name
                gid_id = pu.gid_id
            except Errors.NotFoundError:
                # If there is no posix user with the account name, we assume it
                # is a regular account, which does not have a personal file
                # group to treat specifically. The pu.gid_id attribute is then
                # None. The only groups to be skipped then would be groups with
                # no entity_id which should be impossible.
                ac.clear()
                ac.find(acc_id)
                acc_name = ac.account_name
                gid_id = None
            for group_row in gr.search(member_id=acc_id):
                group_id = group_row['group_id']
                group_name = group_row['name']
                # Leave personal file groups alone
                if group_id == gid_id:
                    continue
                gr.remove_member_from_group(acc_id, group_id)
                logger.info('Removed account %s(%s) from group %s(%s)',
                            acc_name,
                            acc_id,
                            group_name,
                            group_id)
        database.commit()


def callback(database, routing_key, content_type, body):
    if content_type == 'application/json':
        body = json.loads(body)
    message_processed = True

    for cb in callback_functions.get_callbacks(routing_key):
        filters = callback_filters.get_callbacks(cb)
        if not filters or all((lambda x: x(), filters)):
            cb(database, body)

    # Always rollback, since we do an implicit begin and we want to discard
    # possible outstanding changes.
    database.rollback()
    return message_processed


def main(inargs=None):
    """Start consuming messages."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-c', '--config',
                        dest='configfile',
                        metavar='FILE',
                        default=None,
                        help='Use a custom configuration file')
    parser = add_commit_args(parser)

    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)

    prog_name = parser.prog.rsplit('.', 1)
    database = Factory.get('Database')()
    config = load_config(filepath=args.configfile)

    if not args.commit:
        database.commit = database.rollback

    logger.info('Starting %s', prog_name)
    consumer = get_consumer(functools.partial(callback, database),
                            prog_name,
                            config=config.consumer)
    with consumer:
        try:
            consumer.start()
        except KeyboardInterrupt:
            consumer.stop()
        consumer.close()
    logger.info('Stopping %s', prog_name)


if __name__ == "__main__":
    main()
