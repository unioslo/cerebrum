#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2013 University of Oslo, Norway
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

import sys
import getopt
import re

import cerebrum_path
import cereconf
getattr(cerebrum_path, '', 'Silence!')
getattr(cereconf, '', 'Silence!')

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Utils

from mx import DateTime
import smtplib
import email

logger = Factory.get_logger('cronjob')

def send_mail(mail_to, mail_from, subject, body, mail_cc=None):
    if dryrun and not debug_verbose:
        return True
    try:
        ret = Utils.sendmail(mail_to, mail_from, subject, body,
                             cc=mail_cc, debug=dryrun)
        if debug_verbose:
            print "---- Mail: ---- \n"+ ret
    except smtplib.SMTPRecipientsRefused, e:
        failed_recipients = e.recipients
        logger.info("Failed to notify <%d> users", len(failed_recipients))
        for email, condition in failed_recipients.iteritems():
            logger.info("Failed to notify: %s", condition)
    except smtplib.SMTPException, msg:
        logger.warn("Error sending to %s: %s" % (mail_to, msg))
        return False
    return True

def notify_users(ac_ids, email_info, quar_start_in_days):
    notified_users = []
    for x in ac_ids:
        ac.clear()
        ac.find(x)
        try:
            addr = ac.get_primary_mailaddress()
        except Errors.NotFoundError:
            logger.warn('No email address for %i, can\'t notify.' % x)
            continue


        body = email_info['Body']
        body = body.replace('${USERNAME}', ac.account_name)
        body = body.replace('${DAYS_TO_START}', str(quar_start_in_days))
        subject = email_info['Subject'].replace('${USERNAME}', ac.account_name)

        if send_mail(addr, email_info['From'], subject, body):
            notified_users.append(ac.account_name)
        
    return notified_users

def find_affless_persons():
    affless = []
    for x in pe.list_persons():
        if not pe.list_affiliations(person_id=x['person_id']):
            affless.append(x['person_id'])
    return affless

def set_quarantine(pids, quar, offset):
    ac.clear()
    ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    creator = ac.entity_id
    quarantined = []

    for x in pids:
        pe.clear()
        pe.find(x)
        for y in pe.get_accounts():
            ac.clear()
            ac.find(y['account_id'])
            # Refreshing/setting the quarantine
            if ac.get_entity_quarantine(type=quar, only_active=True):
                continue
            ac.delete_entity_quarantine(type=quar)
            date = DateTime.today() + offset
            ac.add_entity_quarantine(quar, creator, start=date)
            quarantined.append(ac.entity_id)
    return quarantined

def usage():
    print """ %s
-q    quarantine to set (default 'generell')
-d    drydrun
-o    quarantine offset in days (default 7)

-f    from-address for email-notification
-m    file containing the message to be sent

-e    debug_verbose
""" % sys.argv[0]

def main():
    global db, co, pe, ac, dryrun, debug_verbose
    db = Factory.get('Database')()
    db.cl_init(change_program='quarantine_accounts')
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)

    quarantine = co.quarantine_generell
    quarantine_offset = 7
    dryrun = debug_verbose = False
    email_info = {}

    opts, j = getopt.getopt(sys.argv[1:], 'q:do:f:m:eh')
    for opt, val in opts:
        if opt in ('-q',):
            quarantine = co.Quarantine(val)
        elif opt in ('-d',):
            db.commit = db.rollback
            dryrun = True
        elif opt in ('-e',):
            debug_verbose = True
        elif opt in ('-o',):
            quarantine_offset = val
        elif opt in ('-f',):
            email_info['From'] = val
        elif opt in ('-m',):
            try:
                f = open(val)
                msg = email.message_from_file(f)
                f.close()
                email_info = {
                    'Subject': email.Header.decode_header(
                                                        msg['Subject'])[0][0],
                    'From': msg['From'],
                    'Cc': msg['Cc'],
                    'Reply-To': msg['Reply-To'],
                    'Body': msg.get_payload(decode=1)
                }
            except IOError, e:
                logger.error('Mail body file: %s' % e)
                sys.exit(2)
        elif opt in ('-h',):
            usage()
            sys.exit(1)
        else:
            print "Error: Invalid argument."
            usage()
            sys.exit(1)

    try:
        int(quarantine)
    except Errors.NotFoundError:
        logger.error('Invalid quarantine')

    logger.debug('Finding persons without affiliation')
    pids = find_affless_persons()
    logger.debug('Setting quarantine on affless persons')
    quarantined = set_quarantine(pids, quarantine, quarantine_offset)
    
    notified = []
    if not dryrun and 'From' in email_info and 'Body' in email_info:
        notified = notify_users(quarantined, email_info, quarantine_offset)

    logger.info('%d quarantines added, %d users notified' % (len(pids),
                                                             len(notified),))

    db.commit()

if __name__ == '__main__':
    main()
