#! /usr/bin/env python
# -*- coding: utf-8 -*-
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

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.email import sendmail
from Cerebrum.modules.Email import (EmailTarget, EmailForward, EmailDomain)

from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Namespace,
                                           Configuration)
from Cerebrum.config.settings import String
from Cerebrum.config.loader import read, read_config

from Cerebrum.modules.event_consumer.config import AMQPClientConsumerConfig

import json
from collections import defaultdict

logger = Factory.get_logger('cronjob')


class FPECriteriaConfig(Configuration):
    """Configuration of the WebService connectivity."""
    affiliation = ConfigDescriptor(
        String,
        default=u"affiliation_ansatt",
        doc=u"Affiliation to aplly criteria by.")

    source_system = ConfigDescriptor(
        String,
        default='system_sap',
        doc=u"The source system used for lookup of affiliations.")


class FPEEmailConfig(Configuration):
    sender = ConfigDescriptor(
        String,
        doc=u"Sender address")
    subject = ConfigDescriptor(
        String,
        doc=u"Subject of email")
    body_template = ConfigDescriptor(
        String,
        doc=u"Body template of email. '{}' will be filled with the addresses,"
        " separated by newlines")


class FPEConsumerConfig(Configuration):
    """Config combining class."""
    fpe = ConfigDescriptor(Namespace, config=FPECriteriaConfig)
    email_config = ConfigDescriptor(Namespace, config=FPEEmailConfig)
    consumer = ConfigDescriptor(Namespace, config=AMQPClientConsumerConfig)


def load_config(filepath=None):
    """Load config for this consumer."""
    config_cls = FPEConsumerConfig()
    if filepath:
        config_cls.load_dict(read_config(filepath))
    else:
        read(config_cls, 'consumer_enforce_forward_policy')
    config_cls.validate()
    return config_cls


def handle_person(database, source_system, affiliations, send_notifications,
                  email_config, data):
    pe = Factory.get('Person')(database)
    ac = Factory.get('Account')(database)
    et = EmailTarget(database)
    ef = EmailForward(database)
    ed = EmailDomain(database)

    if (data.get('resourceType') == 'persons' and
            'affiliation' in data.get(
                'urn:ietf:params:event:SCIM:modify', {}).get(
                    'attributes', [])):
        ident = int(data.get('sub').split('/')[-1])

        if not pe.list_affiliations(
                person_id=ident,
                source_system=source_system,
                affiliation=affiliations):
            return

        pe.clear()
        pe.find(ident)

        removed_forwards = defaultdict(list)
        for account_id in map(lambda x: x['account_id'],
                              pe.get_accounts(
                                  filter_expired=False)):
            try:
                et.clear()
                et.find_by_target_entity(account_id)
            except Errors.NotFoundError:
                continue
            ef.clear()
            ef.find(et.entity_id)
            for forward in map(lambda x: x['forward_to'],
                               ef.get_forward()):
                try:
                    ed.clear()
                    ed.find_by_domain(forward.split('@')[-1])
                except Errors.NotFoundError:
                    ac.clear()
                    ac.find(account_id)
                    ef.delete_forward(forward)
                    removed_forwards[ac.get_primary_mailaddress()
                                     ].append(forward)
                    logger.info(
                        'Deleted forward {} from {}'.format(
                            forward, ac.account_name))
        if send_notifications:
            for k, v in removed_forwards.items():
                sendmail(
                    toaddr=k,
                    fromaddr=email_config.sender,
                    subject=email_config.subject,
                    body=email_config.body_template.format('\n'.join(v)))
    database.commit()


def callback(database, source_system, affiliations, send_notifications,
             email_config, routing_key, content_type, body):
    """Call appropriate handler function."""

    message_processed = True
    try:
        data = json.loads(body)
        handle_person(database, source_system, affiliations,
                      send_notifications, email_config, data)
        logger.info(u'Successfully processed {}'.format(body))
    except Exception as e:
        message_processed = True
        logger.error(u'Failed processing {}:\n {}'.format(body, e),
                     exc_info=True)

    # Always rollback, since we do an implicit begin and we want to discard
    # possible outstanding changes.
    database.rollback()
    return message_processed


def main(args=None):
    """Start consuming messages."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-c', '--config',
                        dest='configfile',
                        metavar='FILE',
                        default=None,
                        help='Use a custom configuration file')
    parser.add_argument(u'--commit',
                        dest=u'commit',
                        action=u'store_true',
                        default=False,
                        help=u'Commit changes')
    parser.add_argument(u'--send-notification',
                        dest=u'send_notification',
                        action=u'store_true',
                        default=False,
                        help=u'Send information about forward removal')
    args = parser.parse_args(args)
    prog_name = parser.prog.rsplit(u'.', 1)[0]

    import functools
    from Cerebrum.modules.event_consumer import get_consumer

    database = Factory.get('Database')()
    database.cl_init(change_program=prog_name)

    config = load_config(filepath=args.configfile)

    co = Factory.get('Constants')(database)
    source_system = co.human2constant(config.fpe.source_system)
    affiliation = co.human2constant(config.fpe.affiliation)
    assert int(source_system) and int(affiliation), \
        "Error, source system or affiliation identifier is non-existent"

    if not args.commit:
        database.commit = database.rollback

    logger.info('Starting {}'.format(prog_name))
    consumer = get_consumer(functools.partial(callback,
                                              database,
                                              source_system,
                                              affiliation,
                                              args.send_notification,
                                              config.email_config),
                            config=config.consumer)
    with consumer:
        try:
            consumer.start()
        except KeyboardInterrupt:
            consumer.stop()
        consumer.close()
    logger.info('Stopping {}'.format(prog_name))


if __name__ == "__main__":
    main()
