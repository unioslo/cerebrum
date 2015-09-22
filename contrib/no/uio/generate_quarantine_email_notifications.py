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

import getopt
import pickle
import sys
import cereconf
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler

progname = __file__.split("/")[-1]
__doc__ = """
This script checks the changelog for changes to quarantines defined in
cereconf.QUARANTINE_NOTIFY_DATA. If a change marked as a trigger is detected,
an email with relevant info is generated and sent to the specified recipient.

Usage: %s [options]
  -h, --help: Display this message
  -d, --debug: Don't send email, output email to logger instead
  -l, --logger-name <name>: logger-name (default: cronjob)

""" % progname

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
cl = CLHandler.CLHandler(db)


def check_changelog_for_quarantine_triggers(logger, debug):
    """
    Scans the changelog for changes related to the quarantines defined in
    cereconf.QUARANTINE_NOTIFY_DATA. This dict also contains which actions
    should trigger an email notification for specific quarantines, as well as
    the email sender/recipient and a quarantine-specific CLHandler-key.
    If debug is enabled, events will not be confirmed in CLHandler, and email
    sending will be disabled, and outputted to the logger instance instead.

    :param logger: Factory-generated logger-instance
    :param debug: Turns off event confirming to CLHandler and email sending
    :type: bool
    """
    for quarantine in cereconf.QUARANTINE_NOTIFY_DATA:
        logger.info('Checking changelog for triggers for quarantine %s'
                    % quarantine)
        quar_data = cereconf.QUARANTINE_NOTIFY_DATA[quarantine]
        triggers = tuple(getattr(co, trigger) for \
                         trigger in quar_data['triggers'])
        for event in cl.get_events(quar_data['cl_key'],
                                   triggers):
            change_params = pickle.loads(event['change_params'])
            if change_params['q_type'] == int(co.Quarantine(quarantine)):
                # Generate dict with relevant info for email
                event_info = dict()
                event_info['change_id'] = event['change_id']
                event_info['quar_name'] = quarantine
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
                event_info['mail_to'] = quar_data['mail_to']
                event_info['mail_from'] = quar_data['mail_from']

                logger.info('Found trigger for quarantine %s in change_ID %d'
                            % (quarantine, event_info['change_id']))
                try:
                    if debug:
                        logger.debug('Mail output for change-ID %d:'
                                     % event_info['change_id'])
                        logger.debug(generate_mail_notification(event_info, debug))
                    else:
                        generate_mail_notification(event_info)
                        logger.info('Email for change-ID: %d generated.'
                                    % event_info['change_id'])
                        cl.confirm_event(event)
                        logger.info('change-ID %d confirmed in CLHandler.'
                                    % event_info['change_id'])
                except Exception, e:
                    logger.exception(e)
                    raise
            else:
                # Irrelevant quarantines should simply be confirmed
                if not debug:
                    cl.confirm_event(event)
        if not debug:
            cl.commit_confirmations()


def generate_mail_notification(event_info, debug=False):
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
              (event_info['quar_name'], event_type, event_info['subject'])
    body = ('Quarantine %s %s on %s.\n\n'
            'When: %s\n'
            'By: %s\n'
            'Change-ID: %s') % (event_info['quar_name'],
                                event_type,
                                event_info['subject'],
                                event_info['time_stamp'],
                                event_info['change_by'],
                                event_info['change_id'])
    return Utils.sendmail(event_info['mail_to'],
                          event_info['mail_from'],
                          subject,
                          body,
                          debug=debug)

def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hdl:',
                                   ['help', 'debug', 'logger-name'])
    except getopt.GetoptError:
        usage(1)

    debug = False
    logger = None
    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
        elif opt in ('-d', '--debug',):
            debug = True
        elif opt in ('-l', 'logger-name'):
            logger = Factory.get_logger(val)

    if not logger:
        logger = Factory.get_logger('cronjob')
    check_changelog_for_quarantine_triggers(logger, debug)

if __name__ == '__main__':
    main()

