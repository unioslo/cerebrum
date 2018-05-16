#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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
This script scans the changelog for changes related to the quarantines defined
in cereconf.QUARANTINE_NOTIFY_DATA. This dict also contains which actions
should trigger an email notification for specific quarantines, as well as
the email sender/recipient and a quarantine-specific CLHandler-key.
If sendmail is enabled, events will be confirmed in CLHandler, and emails
will be sent instead of outputted to the logger instance.
"""

import argparse

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.email import sendmail as sendmail_util
from Cerebrum.utils import json
from Cerebrum.modules import CLHandler

logger = Factory.get_logger('cronjob')
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
cl = CLHandler.CLHandler(db)


def check_changelog_for_quarantine_triggers(logger, sendmail):
    """
    Scans the changelog for changes related to the quarantines defined in
    cereconf.QUARANTINE_NOTIFY_DATA. This dict also contains which actions
    should trigger an email notification for specific quarantines, as well as
    the email sender/recipient and a quarantine-specific CLHandler-key.
    If sendmail is enabled, events will be confirmed in CLHandler, and emails
    will be sent instead of outputted to the logger instance.

    :param logger: Factory-generated logger-instance
    :param sendmail: Turns on event confirming to CLHandler and email sending
    :type: bool
    """
    for quarantine in cereconf.QUARANTINE_NOTIFY_DATA:
        logger.info('Checking changelog for triggers for quarantine %s'
                    % quarantine)
        quar_data = cereconf.QUARANTINE_NOTIFY_DATA[quarantine]
        triggers = tuple(
            getattr(co, trigger) for trigger in quar_data['triggers'])
        for event in cl.get_events(quar_data['cl_key'],
                                   triggers):
            change_params = {}
            if event['change_params']:
                change_params = json.loads(event['change_params'])
            if change_params['q_type'] == int(co.Quarantine(quarantine)):
                # Generate dicts with relevant info for email
                quar_info = generate_quarantine_info(quarantine, quar_data)
                event_info = generate_event_info(event)

                logger.info('Found trigger for quarantine %s in change_ID %d'
                            % (quarantine, event_info['change_id']))
                try:
                    if sendmail:
                        generate_mail_notification(quar_info, event_info)
                        logger.info(
                            'Email for change-ID: %d generated and sent.' %
                            event_info['change_id'])
                        cl.confirm_event(event)
                        logger.info('change-ID %d confirmed in CLHandler.'
                                    % event_info['change_id'])
                    else:
                        logger.debug('Mail output for change-ID %d:'
                                     % event_info['change_id'])
                        logger.debug(generate_mail_notification(quar_info,
                                                                event_info,
                                                                debug=True))
                except Exception, e:
                    logger.exception(e)
                    raise
            else:
                # Irrelevant quarantines should simply be confirmed
                if sendmail:
                    cl.confirm_event(event)
        if sendmail:
            cl.commit_confirmations()


def generate_quarantine_info(quarantine, metadata):
    quarantine_info = dict()
    quarantine_info['name'] = quarantine
    quarantine_info['mail_to'] = metadata['mail_to']
    quarantine_info['mail_from'] = metadata['mail_from']
    return quarantine_info


def generate_event_info(event):
    event_info = dict()
    event_info['change_id'] = event['change_id']
    change_type = str(co.ChangeType(event['change_type_id']))
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
    event_info['time_stamp'] = event['tstamp'].strftime()
    return event_info


def generate_mail_notification(quar_info, event_info, debug=False):
    if event_info['change_type'] == 'quarantine:mod':
        event_type = 'altered'
    elif event_info['change_type'] == 'quarantine:add':
        event_type = 'added'
    elif event_info['change_type'] == 'quarantine:del':
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


def main():

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sendmail', action='store_true',
                        help='Actually send generated e-mails')
    args = parser.parse_args()
    check_changelog_for_quarantine_triggers(logger, args.sendmail)


if __name__ == '__main__':
    main()
