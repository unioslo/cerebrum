#!/usr/bin/env python2.2

import time
import getopt
import sys
import pickle

import cerebrum_path
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.modules import PasswordHistory

# TODO: bruk cereconf e.l. for adresser, fil-med-mail-body osv.

mail_data_file = "/tmp/mail.dta"
max_user_response_time = 3600*24*14  # max time to respond to
                                     # "change your password" notice
max_user_response_time = 2 # DEBUG
max_password_age = 3600*24*300
mail_to = 'cerebrum-drift@usit.uio.no'
mail_cc = ''
mail_from = 'cerebrum-drift@usit.uio.no'
mailed_users = []
splatted_users = []

Factory = Utils.Factory
db = Factory.get('Database')()
db.cl_init(change_program="bytt_passord")
co = Factory.get('Constants')(db)
account = Factory.get('Account')(db)
account.find_by_name("bootstrap_account")
splattee_id = account.entity_id
db_now = db.Date(*([ int(x) for x in (
    "%d-%d-%d" % time.localtime()[:3]).split('-')]))

brev_body = """Bla. bla bla... """

def mail_user(account_id):
    account.clear()
    account.find(account_id)
    print "Mailing %s" % account.account_name
    # logger.info("Mailing %s" % account.account_name)
    try:
        prim_email = account.get_primary_mailaddress()
    except Errors.NotFoundError:
        # logger.warn("")
        print "Ingen mail-adresse for brukeren"  # TBD: Bruke @ulrik?
        return
    send_mail(
        prim_email,
        "Pålegg fra sentral drift: passordbytte for " + account.account_name,
        brev_body)
    mailed_users.append(account.account_name)
    return True

def splat_user(account_id):
    account.clear()
    account.find(account_id)
    splatted_users.append(account.account_name)
    account.add_entity_quarantine(
        co.quarantine_autopassord, splattee_id,
        "Ikke byttet passord", db_now, None)
    db.commit()
    print "Splatting %s" % account.account_name
    # logger.info("Splatting %s" % account.account_name)

def process_data():
    # mail_data_file always contain information about users that
    # currently has been warned that their account will be locked.
    
    try:
        mail_data = pickle.load(open(mail_data_file))
    except IOError:
        mail_data = {}
    new_mail_data = {}
    now = time.time()

    stop = 999999  # DEBUG: begrens mengden
    ph = PasswordHistory.PasswordHistory(db)
    # TODO: få med de som av en eller annen grunn ikke er i PasswordHistory
    for account_id in ph.find_old_password_accounts(
        time.strftime('%Y-%m-%d',
                      time.localtime(time.time()-max_password_age))):
        stop -= 1
        if stop < 0:
            break
        if not mail_data.has_key(account_id):
            if mail_user(account_id):
                new_mail_data[account_id] = now
        elif mail_data[account_id] < now - max_user_response_time:
            splat_user(account_id)
        else:
            new_mail_data[account_id] = mail_data[account_id]
    pickle.dump(new_mail_data, open(mail_data_file, 'w'))
    send_mail(
        mail_to,
        "bytt_passord varslet %i brukere og sperret %i" % (
        len(mailed_users), len(splatted_users)),
        ("Følgende brukere ble varslet: \n  %s\n"
         "Følgende brukere ble sperret: \n  %s\n"
         "\nHilsen Cerebrum\n") % ("\n  ".join(mailed_users),
                                   "\n  ".join(splatted_users),))

def send_mail(mail_to, subject, body, mail_cc=mail_cc, mail_from=mail_from):
    # TODO: finne python modul som mailer+mime-encoder, inkl. subject
    if mail_cc:
        mail_cc = "Cc: %s\n" % mail_cc
    print ("To: %s\n%sFrom: %s\nSubject: %s\n\n%s" % (
        mail_to, mail_cc, mail_from, subject, body))

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'p',
                                   ['help'])
    except getopt.GetoptError:
        usage(1)
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-p',):
            process_data()
    if len(opts) == 0:
        usage(1)

def usage(exitcode=0):
    print """Usage: [options]
    -p  : splatt/mail brukere som ikke har skiftet passord
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
