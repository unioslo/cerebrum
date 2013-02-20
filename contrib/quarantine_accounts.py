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

"""
This script sets a quarantine on users without affiliations.

NOTE! The script will delete and re-set quarantines that are temporarily
disabled! Only quarantines of the type supplied to the -q flag are checked
and set.

The script should be extended to do the following:
    - Send an SMS to account owners.
    - Introduce a new command-line option that allows a given set
        of expired affiliations to be extempted by the check.

The flow of the script is something like this:
    1. Parse args and initzialise globals in the main-function. This is
        also where the rest of the action is sparked.
    2. Call the find_affless_persons-function to collect all person IDs
        wich do not have an active affiliation.
    3. Call the set_quarantine-function. This sets a given quarantine on
        all accounts associated with the persons collected in step 2 if
        the notify_users-function sucessfully sends an email to the user.
"""

import sys
import getopt

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Utils

from mx import DateTime
import smtplib
import email

logger = Factory.get_logger('cronjob')

def send_mail(mail_to, mail_from, subject, body, mail_cc=None):
    """
    Function for sending mail to users.

    @type mail_to: string
    @param mail_to: The recipient of the Email.

    @type mail_from: string
    @param mail_from: The senders address.

    @type subject: string
    @param subject: The messages subject.

    @type body: string
    @param body: The message body.

    @type mail_cc: string
    @param mail_cc: An optional address that the mail will be CCed to.

    @rtype: bool
    @return: A boolean that tells if the email was sent sucessfully or not.
    """

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

def notify_users(ac_id, quar_start_in_days):
    """
    Sends an email to users, telling them that a quarantine has been set.

    @type ac_id: int
    @param ac_ids: The account ID to notify

    @type email_info: dict
    @param email_info: A dictionary containing the Email-message to send.

    @type quar_start_in_days: int
    @param quar_start_in_days: An integer representing the number of days
        until the quarantine will be enforced.

    @rtype: bool
    @return: Returns True or False depending on if the user could be notified
    """

    ac.clear()
    ac.find(ac_id)
    try:
        addr = ac.get_primary_mailaddress()
    except Errors.NotFoundError:
        logger.warn('No email address for %s, can\'t notify.' % ac.account_name)
        return False


    body = email_info['Body']
    body = body.replace('${USERNAME}', ac.account_name)
    body = body.replace('${DAYS_TO_START}', str(quar_start_in_days))
    subject = email_info['Subject'].replace('${USERNAME}', ac.account_name)

    return send_mail(addr, email_info['From'], subject, body, email_info['Cc'])

def find_affless_persons():
    """
    Returns all persons who does not have any active affiliation.

    @rtype: list
    @return: Returns a list of person IDs.
    """
    affless = []
    for x in pe.list_persons():
        if not pe.list_affiliations(person_id=x['person_id']):
            affless.append(x['person_id'])
    return affless

def set_quarantine(pids, quar, offset):
    """
    This method sets a given quarantine on a set of accounts.

    @type pids: list
    @param pids: A list of account IDs that will be processed.

    @type quar: _QuarantineCode
    @param quar: The quarantine that will be set on accounts referenced in
        C{pids}.

    @type offset: int
    @param offset: The number of days until the quarantine starts.

    @rtype: dict
    @return: C{{'quarantined': [], 'failed_notify': []}}
    """
    ac.clear()
    ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    creator = ac.entity_id
    quarantined = []
    failed_notify = []
    accounts = 0
    date = DateTime.today() + offset

    for x in pids:
        pe.clear()
        pe.find(x)
        for y in pe.get_accounts():
            accounts += 1
            ac.clear()
            ac.find(y['account_id'])

            if filter(lambda x: x['start_date'] <= date,
                    ac.get_entity_quarantine(type=quar)):
                logger.info('%s is already quarantined' % ac.account_name)
                continue

            if not dryrun and email_info:
                qr = notify_users(ac.entity_id, offset)
            else:
                qr = True
            if qr:
                # Refreshing/setting the quarantine
                ac.delete_entity_quarantine(type=quar)
                ac.add_entity_quarantine(quar, creator, start=date)
                logger.info('%s acquires new quarantine' % ac.account_name)
                quarantined.append(ac.account_name)
            else:
                failed_notify.append(ac.account_name)
    logger.debug('Checked %d accounts' % accounts)
    return {'quarantined': quarantined, 'failed_notify': failed_notify}

def usage():
    print """ %s
-q    quarantine to set (default 'generell')
-d    drydrun
-o    quarantine offset in days (default 7)
        If a quarantine of the same type exists, and is longer away in
        the future than the offset defines, it will be removed and a new
        quarantine will be set.

-m    file containing the message to be sent

-e    debug_verbose
""" % sys.argv[0]

def main():
    global db, co, pe, ac, dryrun, debug_verbose, email_info
    db = Factory.get('Database')()
    db.cl_init(change_program='quarantine_accounts')
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)

    quarantine = co.quarantine_generell
    quarantine_offset = 7
    dryrun = debug_verbose = False
    email_info = None

    opts, j = getopt.getopt(sys.argv[1:], 'q:do:m:eh')
    for opt, val in opts:
        if opt in ('-q',):
            quarantine = co.Quarantine(val)
        elif opt in ('-d',):
            db.commit = db.rollback
            dryrun = True
        elif opt in ('-e',):
            debug_verbose = True
        elif opt in ('-o',):
            quarantine_offset = int(val)
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
                    'Body': msg.get_payload(decode=1)
                }
            except IOError, e:
                logger.error('Mail body file: %s' % e)
                sys.exit(2)
        elif opt in ('-h',):
            usage()
            sys.exit(0)
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
    r = set_quarantine(pids, quarantine, quarantine_offset)
    
    logger.info('%d quarantines added, %d users skipped' %
                (len(r['quarantined']), len(r['failed_notify']),))

    db.commit()

if __name__ == '__main__':
    main()
