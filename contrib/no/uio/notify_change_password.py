#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004-2007 University of Oslo, Norway
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

import time
import getopt
import sys
import pickle
import re
import email
import smtplib
from email import Header

import cerebrum_path
import cereconf
from Cerebrum.Constants import _SpreadCode
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.modules import PasswordHistory

# TODO: the pickle solution means that if the script dies
# unexpectedly, one must manually fix the datafile using data from the
# debug-log.  This should be fixed.

logger = Utils.Factory.get_logger("cronjob")
db = Utils.Factory.get('Database')()
db.cl_init(change_program="notify_ch_pass")
co = Utils.Factory.get('Constants')(db)
account = Utils.Factory.get('Account')(db)
disk = Utils.Factory.get('Disk')(db)

mailed_users = {}
splatted_users = []
debug_enabled = False   # If set to true, no e-mail will be sent
debug_verbose = False   # e-mail is shown on stdout (requires debug_enabled)
debug_account_ids = None

account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
splattee_id = account.entity_id
db_now = db.Date(*([ int(x) for x in (
    "%d-%d-%d" % time.localtime()[:3]).split('-')]))

def mail_user(account_id, mail_type, deadline='', first_time=''):
    account.clear()
    account.find(account_id)
    try:
        home = account.get_homepath(co.Spread(spread))
    except Errors.NotFoundError:
        home = 'ukjent'
    logger.debug("Mailing %s to %s (home=%s)" % (
        mail_type, account.account_name, home))
    try:
        prim_email = account.get_primary_mailaddress()
    except Errors.NotFoundError:
        logger.warn("No email-address for %i" % account_id)
        return
    subject = email_info[mail_type]['Subject']
    subject = subject.replace('${USERNAME}', account.account_name)
    body = email_info[mail_type]['Body']
    body = body.replace('${USERNAME}', account.account_name)
    body = body.replace('${DEADLINE}', deadline)
    body = body.replace('${FIRST_TIME}', first_time)
    
    if send_mail(prim_email, email_info[mail_type]['From'], subject, body):
        mailed_users.setdefault(mail_type, []).append(account.account_name)
    return True

def splat_user(account_id):
    account.clear()
    account.find(account_id)
    splatted_users.append(account.account_name)
    logger.debug("Splatting %s" % account.account_name)
    if debug_enabled:
        return
    account.add_entity_quarantine(
        co.quarantine_autopassord, splattee_id,
        "password not changed", db_now, None)
    db.commit()

def fix_manual_updates(excempt_users):
    """quarantine_autopassord should only be updated by this script.
    We do not honour change of end-date, and only allow delaying the
    quarantine up to 7 days.
    """
    tmp = []
    guest_prefix = 'guest'
    for u in excempt_users.split(","):
        if not u:
            continue
        # special syntax for uio guest users
        if re.match('%s\d\d\d-\d\d\d' % guest_prefix, u):
            first, last = u.split('-')
            first = int(first[len(guest_prefix):])
            last = int(last)
            for i in range(first, last+1):
                tmp.append('%s%03d' % (guest_prefix, i))
        else:
            # Normal case
            tmp.append(u)

    excempt_account_ids = []
    for u in tmp:
        account.clear()
        account.find_by_name(u)
        excempt_account_ids.append(int(account.entity_id))
    
    threshold = db.Date(*([ int(x) for x in (
        "%d-%d-%d" % time.localtime(time.time()+3600*24*7)[:3]).split('-')]))
    change_quarantines = {}
    for row in account.list_entity_quarantines():
        if row['quarantine_type'] == int(co.quarantine_autopassord):
            if int(row['entity_id']) in excempt_account_ids:
                continue
            if row['end_date']:
                logger.debug("Clearing end-date for %i" % row['entity_id'])
                account.clear()
                account.find(row['entity_id'])
                account.delete_entity_quarantine(int(co.quarantine_autopassord))
                account.add_entity_quarantine(
                    co.quarantine_autopassord, splattee_id,
                    "password not changed", db_now, None)
                db.commit()
            if row['disable_until'] is not None and row['disable_until'] > threshold:
                logger.debug("reducing disable_until to threshold for %i" %
                             row['entity_id'])
                account.clear()
                account.find(row['entity_id'])
                account.disable_entity_quarantine(int(co.quarantine_autopassord),
                                                  threshold)
                db.commit()
                
def process_data(status_mode=False, normal_mode=False):
    # mail_data_file always contain information about users that
    # currently has been warned that their account will be locked.
    global max_users, spread
    if not spread:
        print "\nHome spread must be given (i.e. enter --home-spread spread_foo)\n"
        usage(1)
    logger.info("process_data started, debug_enabled=%i, debug_verbose=%i" % (
        debug_enabled, debug_verbose))
    try:
        mail_data = pickle.load(open(mail_data_file))
    except IOError:
        mail_data = {}
    new_mail_data = {}
    now = time.time()
    logger.debug("Loaded info about %i emailed users" % len(mail_data))
    deadline = time.strftime('%Y-%m-%d', time.localtime(now + grace_period))

    max_date = time.strftime('%Y-%m-%d',
                             time.localtime(time.time()-max_password_age))
    ph = PasswordHistory.PasswordHistory(db)
    if debug_account_ids is None:
        account_ids = [int(x['account_id']) for x in ph.find_old_password_accounts(max_date)]
        account_ids.extend( [int(x['account_id']) for x in ph.find_no_history_accounts() ])
    else:
        account_ids = debug_account_ids
    logger.debug("Found %i users" % len(account_ids))
    num_mailed = num_splatted = num_previously_warned = num_reminded = 0
    for account_id in account_ids:
        max_users -= 1
        if max_users < 0:
            break
        if not mail_data.has_key(account_id):
            if normal_mode:
                if mail_user(account_id, 'first', deadline=deadline):
                    new_mail_data[account_id] = {'first': now }
            num_mailed += 1
        elif mail_data[account_id]['first'] < now - grace_period:
            if normal_mode:
                splat_user(account_id)
            num_splatted += 1
        else:
            num_previously_warned += 1
            if (reminder_delay and
                (mail_data[account_id]['first'] < now - reminder_delay) and
                not mail_data[account_id].has_key('reminder')):
                if normal_mode:
                    tmp = time.strftime(
                        '%Y-%m-%d', time.localtime(mail_data[account_id]['first'] +
                                                   grace_period))
                    first_time = time.strftime(
                        '%Y-%m-%d', time.localtime(mail_data[account_id]['first']))
                    if mail_user(account_id, 'reminder', deadline=tmp,
                                 first_time=first_time):
                        mail_data[account_id]['reminder'] = now
                num_reminded += 1
            new_mail_data[account_id] = mail_data[account_id]
    if status_mode:
        print ("Users with old password: %i\nWould splat: %i\n"
               "Would mail: %i\nPreviously warned: %i\nNum reminded: %i"%(
            len(account_ids), num_splatted, num_mailed,
            num_previously_warned, num_reminded))
    if not normal_mode:
        return
    pickle.dump(new_mail_data, open(mail_data_file, 'w'))
    send_mail(
        summary_email_info['To'],
        summary_email_info['From'],
        "notify_change_passord e-mailed %i users and splatted %i" % (
        (len(mailed_users.get('first', [])) +
         len(mailed_users.get('reminder', []))), len(splatted_users)),
        ("The following users were 'first' e-mailed: \n  %s\n"
         "The following users were 'reminder' e-mailed: \n  %s\n"
         "The following users were splatted: \n  %s\n"
         "\nRegards, Cerebrum\n") % ("\n  ".join(mailed_users.get('first', [])),
                                     "\n  ".join(mailed_users.get('reminder', [])),
                                     "\n  ".join(splatted_users)))

def send_mail(mail_to, mail_from, subject, body, mail_cc=None):
    if debug_enabled and not debug_verbose:
        return True
    try:
        ret = Utils.sendmail(mail_to, mail_from, subject, body,
                             cc=mail_cc, debug=debug_enabled)
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

def parse_mail(fname):
    fp = open(fname, 'rb')
    msg = email.message_from_file(fp)
    fp.close()
    return {
        'Subject': Header.decode_header(msg['Subject'])[0][0],
        'From': msg['From'],
        'Cc': msg['Cc'],
        'Reply-To': msg['Reply-To'],
        'Body': msg.get_payload(decode=1)
        }

def main():
    try:
        opts, args = getopt.getopt(
            sys.argv[1:], 'p',
            ['help', 'from=', 'to=', 'cc=', 'msg-file=',
             'max-password-age=', 'grace-period=', 'data-file=',
             'max-users=', 'debug', 'status', 'reminder-delay=',
             'reminder-msg-file=', 'debug-data=', 'fix-manual-updates=',
             'home-spread='])
    except getopt.GetoptError:
        usage(1)
    if len(opts) == 0:
        usage(1)

    global summary_email_info, max_users, max_password_age, \
           grace_period, mail_data_file, email_info, reminder_delay, \
           spread
    max_users = 999999
    email_info = {}
    summary_email_info = {}
    reminder_delay = None
    spread = ""
    mail_data_file = '/cerebrum/var/logs/notify_change_password.dta'

    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--home-spread',):
            spread = val
        elif opt in ('-p',):
            process_data(normal_mode=True)
        elif opt in ('--from',):
            summary_email_info['From'] = val
        elif opt in ('--to',):
            summary_email_info['To'] = val
        elif opt in ('--debug',):
            global debug_enabled
            debug_enabled = True
            if logger.name != 'console':
                print "Use --logger-name=console so that logs don't get changed"
                sys.exit(1)
        elif opt in ('--debug-data',):
            global debug_account_ids
            debug_account_ids = []
            for name in val.split(","):
                account.clear()
                account.find_by_name(name)
                debug_account_ids.append(int(account.entity_id))
        elif opt in ('--cc',):
            summary_email_info['Cc'] = val
        elif opt in ('--msg-file',):
            email_info['first'] = parse_mail(val)
        elif opt in ('--reminder-msg-file',):
            email_info['reminder'] = parse_mail(val)
        elif opt in ('--max-password-age',):
            max_password_age = int(val) * 3600 * 24
        elif opt in ('--grace-period',):
            grace_period = float(val) * 3600 * 24
        elif opt in ('--reminder-delay',):
            reminder_delay = float(val) * 3600 * 24
        elif opt in ('--data-file',):
            mail_data_file = val
        elif opt in ('--max-users',):
            max_users = int(val)
        elif opt in ('--status', ):
            if not debug_enabled:
                print "Must use --debug with --status"
                sys.exit(1)
            process_data(status_mode=True)
        elif opt in ('--fix-manual-updates',):
            fix_manual_updates(val)

def usage(exitcode=0):
    print """Usage: [options]
    Force users to change passwords regularly.
    
    -p  : splatt/mail users that hasn't changed their password
    --from address  : for the summary sent to admin
    --to address    : for the summary sent to admin
    --cc address    : for the summary sent to admin
    --msg-file file : file with message.  Formated as a normal e-mail,
         body, cc, subject, from and reply-to will be extracted.  To
         will be set to the end-users address.
    --max-password-age days : warn/splatt when password is older that this # of days
    --grace-period days : minimum time between warn and splat
    --reminder-delay days: send a reminder after this number of days
         after the first message.
    --reminder-msg-file file : like --msg-file but with the reminder mail
    --data-file name : location of the database with info about who was mailed when
    --max-users num : debug purposes only: limit max processed users
    --debug : Will not send mail or splat accounts (updates data-file).
              Use with --logger-name=console
    --debug-data: comma separated username list of users with expired passwords
    --status : Show statistics about what would happen if the script
         was ran now.  Does not update files/send mail.
    --home-spread : enter spread in which user must have a home in order to be
         considered active (i.e. spread_uio_nis_user)
    --fix-manual-updates excempt_users: Override any manual changes
      that has been done to a password-quarantine.  excempt_users is a
      comma separated list of users that are skipped

Example: notify_change_password.py --logger-name=console --debug --debug-data uname --from foo@bar.com --to foo@bar.com --msg-file templates/no_NO/email/skiftpassordmail.txt --reminder-msg-file templates/no_NO/email/skiftpassordmail_reminder.txt --max-password-age 350 --grace-period 30 --reminder-delay 16 --data-file notify_change_password.dat --home-spread home_spread_foo -p
         """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

# arch-tag: 8e553a68-4576-4c67-a6c3-8d8f0a0c02ab
