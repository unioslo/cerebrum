#!/usr/bin/env python2.2

import time
import getopt
import sys
import pickle
import email
from email import Header

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.modules import PasswordHistory

logger = Utils.Factory.get_logger("cronjob")
db = Utils.Factory.get('Database')()
db.cl_init(change_program="notify_ch_pass")
co = Utils.Factory.get('Constants')(db)
account = Utils.Factory.get('Account')(db)

mailed_users = []
splatted_users = []
debug_enabled = False   # If set to true, no e-mail will be sent
debug_verbose = False   # e-mail is shown on stdout (requires debug_enabled)

account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
splattee_id = account.entity_id
db_now = db.Date(*([ int(x) for x in (
    "%d-%d-%d" % time.localtime()[:3]).split('-')]))

def mail_user(account_id, deadline=''):
    account.clear()
    account.find(account_id)
    logger.debug("Mailing %s" % account.account_name)
    try:
        prim_email = account.get_primary_mailaddress()
    except Errors.NotFoundError:
        logger.warn("No email-address for %i" % account_id)
        return
    subject = email_info['Subject']
    subject = subject.replace('${USERNAME}', account.account_name)
    body = email_info['Body']
    body = body.replace('${USERNAME}', account.account_name)
    body = body.replace('${DEADLINE}', deadline)
    
    send_mail(prim_email, email_info['From'], subject, body)
    mailed_users.append(account.account_name)
    return True

def splat_user(account_id):
    account.clear()
    account.find(account_id)
    splatted_users.append(account.account_name)
    account.add_entity_quarantine(
        co.quarantine_autopassord, splattee_id,
        "password not changed", db_now, None)
    db.commit()
    logger.debug("Splatting %s" % account.account_name)

def process_data():
    # mail_data_file always contain information about users that
    # currently has been warned that their account will be locked.
    global max_users
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
    account_ids = [int(x['account_id']) for x in ph.find_old_password_accounts(max_date)]
    account_ids.extend( [int(x['account_id']) for x in ph.find_no_history_accounts() ])
    logger.debug("Found %i users" % len(account_ids))
    for account_id in account_ids:
        max_users -= 1
        if max_users < 0:
            break
        if not mail_data.has_key(account_id):
            if mail_user(account_id, deadline=deadline):
                new_mail_data[account_id] = now
        elif mail_data[account_id] < now - grace_period:
            splat_user(account_id)
        else:
            new_mail_data[account_id] = mail_data[account_id]
    pickle.dump(new_mail_data, open(mail_data_file, 'w'))
    send_mail(
        summary_email_info['To'],
        summary_email_info['From'],
        "notify_change_passord e-mailed %i users and splatted %i" % (
        len(mailed_users), len(splatted_users)),
        ("The following users were e-mailed: \n  %s\n"
         "The following users were splatted: \n  %s\n"
         "\nRegards, Cerebrum\n") % ("\n  ".join(mailed_users),
                                     "\n  ".join(splatted_users),))

def send_mail(mail_to, mail_from, subject, body, mail_cc=None,):
    ret = Utils.sendmail(mail_to, mail_from, subject, body,
                         cc=mail_cc, debug=debug_enabled)
    if debug_verbose:
        print "---- Mail: ---- \n"+ ret

def main():
    try:
        opts, args = getopt.getopt(
            sys.argv[1:], 'p',
            ['help', 'from=', 'to=', 'cc=', 'msg-file=',
             'max-password-age=', 'grace-period=', 'data-file=',
             'max-users='])
    except getopt.GetoptError:
        usage(1)

    global summary_email_info, max_users, max_password_age, \
           grace_period, mail_data_file, email_info
    max_users = 999999
    email_info = {}
    summary_email_info = {}
    mail_data_file = '/cerebrum/var/logs/notify_change_password.dta'

    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-p',):
            process_data()
        elif opt in ('--from',):
            summary_email_info['From'] = val
        elif opt in ('--to',):
            summary_email_info['To'] = val
        elif opt in ('--cc',):
            summary_email_info['Cc'] = val
        elif opt in ('--msg-file',):
            fp = open(val, 'rb')
            msg = email.message_from_file(fp)
            fp.close()
            email_info['Subject'] = Header.decode_header(msg['Subject'])[0][0]
            email_info['From'] = msg['From']
            email_info['Cc'] = msg['Cc']
            email_info['Reply-To'] = msg['Reply-To']
            email_info['Body'] = msg.get_payload(decode=1)
        elif opt in ('--max-password-age',):
            max_password_age = int(val) * 3600 * 24
        elif opt in ('--grace-period',):
            grace_period = float(val) * 3600 * 24
        elif opt in ('--data-file',):
            mail_data_file = val
        elif opt in ('--max-users',):
            max_users = int(val)
    if len(opts) == 0:
        usage(1)

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
    --data-file name : location of the database with info about who was mailed when
    --max-users num : debug purposes only: limit max processed users
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
