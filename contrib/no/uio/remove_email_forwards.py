#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2021 University of Oslo, Norway
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
"""Script to enforce forwarding restrictions of emails"""

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import argparse

from collections import defaultdict

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.email import sendmail
from Cerebrum.modules.Email import (EmailTarget, EmailForward, EmailDomain)
from Cerebrum.config.settings import String
from Cerebrum.config.loader import read, read_config
from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Namespace,
                                           Configuration)

logger = Factory.get_logger('cronjob')


class FPECriteriaConfig(Configuration):
    """Configuration of the WebService connectivity."""
    affiliation = ConfigDescriptor(
        String,
        default="affiliation_ansatt",
        doc="Affiliation to apply criteria by.")

    source_system = ConfigDescriptor(
        String,
        default='system_dfo_sap',
        doc="The source system used for lookup of affiliations.")


class FPEEmailConfig(Configuration):
    sender = ConfigDescriptor(
        String,
        doc="Sender address")
    subject = ConfigDescriptor(
        String,
        doc="Subject of email")
    body_template = ConfigDescriptor(
        String,
        doc="Body template of email. '{}' will be filled with the addresses,"
        " separated by newlines")


class FPEConfig(Configuration):
    """Config combining class."""
    fpe = ConfigDescriptor(Namespace, config=FPECriteriaConfig)
    email_config = ConfigDescriptor(Namespace, config=FPEEmailConfig)


def load_config(filepath=None):
    """Load config for this consumer."""
    config_cls = FPEConfig()
    if filepath:
        config_cls.load_dict(read_config(filepath))
    else:
        read(config_cls, 'enforce_forward_policy')
    config_cls.validate()
    return config_cls


def remove_email_forward(db, pe, person, args, config):
    ac = Factory.get('Account')(db)
    et = EmailTarget(db)
    ef = EmailForward(db)
    ed = EmailDomain(db)

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

    if args.send_notification:
        for k, v in removed_forwards.items():
            try:
                sendmail(
                    toaddr=k,
                    fromaddr=config.email_config.sender,
                    subject=config.email_config.subject,
                    body=config.email_config.body_template.format('\n'.join(v)))
            except Exception:
                logger.error('Failed to send email to %s', k)

    db.commit()
    ac.clear()


def iterate_persons(db, args, config):
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)
    affiliation = co.human2constant(config.fpe.affiliation)
    all_persons = pe.list_affiliated_persons(aff_list=affiliation)
    for person in all_persons:
        try:
            pe.find(person['person_id'])
            remove_email_forward(db, pe, person, args, config)
        except NotFoundError:
            logger.error("Person %s not found", person['person_id'])
        finally:
            pe.clear()


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-c', '--config',
                        dest='configfile',
                        metavar='FILE',
                        default=None,
                        help='Use a custom configuration file')
    parser.add_argument('--commit',
                        dest='commit',
                        action='store_true',
                        default=False,
                        help='Commit changes')
    parser.add_argument('--send-notification',
                        dest='send_notification',
                        action='store_true',
                        default=False,
                        help='Send information about forward removal')
    args = parser.parse_args(args)
    prog_name = parser.prog.rsplit('.', 1)[0]
    logger.info(args.send_notification)

    db = Factory.get('Database')()
    db.cl_init(change_program=prog_name)

    config = load_config(filepath=args.configfile)

    if not args.commit:
        db.commit = db.rollback

    iterate_persons(db, args, config)

    logger.info('Starting {}'.format(prog_name))


if __name__ == "__main__":
    main()
