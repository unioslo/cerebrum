#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2021 University of Oslo, Norway
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
This script scans the changelog for quarantine events, and sends a notification
email to an interested party.

Note that each quarantine event generates a separate email.


Commit
------
This script automatically commits if the --sendmail flag is present.

Commit happens after processing each quarantine preset in
``cereconf.QUARANTINE_NOTIFY_DATA``.  If processing of a quarantine preset
fails, we may end up in a situation where the notification email is sent, but
the changehandler is not updated (i.e.  database rollback).


Configuration
-------------
The cereconf setting ``QUARANTINE_NOTIFY_DATA`` controls which changelog-events
this script acts on.  The overall structure of this setting is:
::

    {
        '<quarantine-name>': {
            'triggers': [
                '<change-type-name>',
                ...
            ]
            'cl_key': '<change-handler-key>',
            'mail_to': '<recipient-email>',
            'mail_from': '<sender-email>',
        },
        ...
    }

"""
import argparse
import logging

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.email import sendmail as sendmail_util
from Cerebrum.utils import json
from Cerebrum.modules import CLHandler

logger = logging.getLogger(__name__)


def check_changelog_for_quarantine_triggers(db, sendmail):
    """
    :param db: database connection
    :param bool sendmail: confirm events and send email
    """
    co = Factory.get('Constants')(db)
    clconst = Factory.get('CLConstants')(db)
    cl = CLHandler.CLHandler(db)

    for quarantine in cereconf.QUARANTINE_NOTIFY_DATA:
        logger.info('processing quarantine %s', quarantine)
        q_type = int(co.Quarantine(quarantine))
        q_data = cereconf.QUARANTINE_NOTIFY_DATA[quarantine]
        q_stats = {'confirm': 0, 'ignore': 0}
        triggers = tuple(
            getattr(clconst, trigger) for trigger in q_data['triggers'])
        for event in cl.get_events(q_data['cl_key'],
                                   triggers):
            change_params = {}
            if event['change_params']:
                change_params = json.loads(event['change_params'])
            if change_params['q_type'] == q_type:
                # Generate dicts with relevant info for email
                quar_info = generate_quarantine_info(quarantine, q_data)
                event_info = generate_event_info(db, event)

                logger.info('found trigger for quarantine %s in change-id %d',
                            quarantine, event_info['change_id'])
                try:
                    if sendmail:
                        generate_mail_notification(quar_info, event_info)
                        logger.info(
                            'email for change-id: %d generated and sent',
                            event_info['change_id'])
                        cl.confirm_event(event)
                        logger.info('change-id %d confirmed in CLHandler',
                                    event_info['change_id'])
                    else:
                        logger.debug('mail output for change-id %d:',
                                     event_info['change_id'])
                        logger.debug(generate_mail_notification(quar_info,
                                                                event_info,
                                                                debug=True))
                except Exception as e:
                    logger.exception(e)
                    raise
                q_stats['confirm'] += 1
            else:
                # irrelevant quarantines should simply be confirmed
                if sendmail:
                    cl.confirm_event(event)
                q_stats['ignore'] += 1

        if sendmail:
            logger.info('confirming changehandler, key %s', q_data['cl_key'])
            cl.commit_confirmations()

        logger.info('changelog events for %s: %s', quarantine, repr(q_stats))
        logger.info('done processing quarantine %s', quarantine)


def generate_quarantine_info(quarantine, metadata):
    quarantine_info = dict()
    quarantine_info['name'] = quarantine
    quarantine_info['mail_to'] = metadata['mail_to']
    quarantine_info['mail_from'] = metadata['mail_from']
    return quarantine_info


def generate_event_info(db, event):
    ac = Factory.get('Account')(db)
    clconst = Factory.get('CLConstants')(db)
    event_info = dict()
    event_info['change_id'] = event['change_id']
    change_type = str(clconst.ChangeType(event['change_type_id']))
    event_info['change_type'] = change_type
    ac.clear()
    ac.find(event['subject_entity'])
    event_info['subject'] = ac.get_account_name()
    if event['change_by'] is not None:
        ac.clear()
        ac.find(event['change_by'])
        event_info['change_by'] = ac.get_account_name()
    else:
        event_info['change_by'] = event['change_program']
    event_info['time_stamp'] = event['tstamp'].strftime("%c")
    return event_info


def generate_mail_notification(quar_info, event_info, debug=False):
    if event_info['change_type'] == 'quarantine:modify':
        event_type = 'altered'
    elif event_info['change_type'] == 'quarantine:add':
        event_type = 'added'
    elif event_info['change_type'] == 'quarantine:remove':
        event_type = 'deleted'
    else:
        raise Errors.CerebrumError('Unknown quarantine action: %s'
                                   % event_info['change_type'])
    subject = 'Quarantine %s %s on account %s' % \
              (quar_info['name'], event_type, event_info['subject'])
    body = ('Quarantine %s %s on %s.\n\n'
            'When: %s\n'
            'By: %s\n'
            'Change-ID: %s') % (quar_info['name'],
                                event_type,
                                event_info['subject'],
                                event_info['time_stamp'],
                                event_info['change_by'],
                                event_info['change_id'])
    return sendmail_util(quar_info['mail_to'],
                         quar_info['mail_from'],
                         subject,
                         body,
                         debug=debug)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Send email warnings on quarantine changes",
    )
    parser.add_argument(
        '--sendmail',
        action='store_true',
        help='Commit and actually send generated e-mails',
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('start %s', parser.prog)
    logger.debug('args: %s', repr(args))

    db = Factory.get('Database')()
    check_changelog_for_quarantine_triggers(db, args.sendmail)

    logger.info('done %s', parser.prog)


if __name__ == '__main__':
    main()
