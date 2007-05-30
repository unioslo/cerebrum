import cerebrum_path
import cereconf

import getopt
import sys, os

from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules import Email

def write_email_file(email_data, outfile):
    stream = open(outfile, 'w')
    for k in email_data:
        line = k + ':' + email_data[k] + '\n'
        stream.write(line)

def generate_email_data():
    all_accounts = account.list()
    all_email_data = {}
    est = Email.EmailServerTarget(db)
    es = Email.EmailServer(db)
    for k in all_accounts:
        account.clear()
        account.find(k['account_id'])
        email_server = None
        try:
            primary = account.get_primary_mailaddress()
        except Errors.NotFoundError:
            logger.warn("No primary address for %s", account.account_name)
            continue
        try:
            est.clear()
            est.find_by_entity(account.entity_id)
        except Errors.NotFoundError:
            logger.warn("No server registered for %s", account.account_name)
            email_server = "N/A"
        if email_server <> "N/A":
            es.clear()    
            es.find(est.email_server_id)
            email_server = es.name
        all_email_data[account.account_name] = primary + ':' + email_server
    return all_email_data
    
def usage():
    print """Usage: dump_email_data.py
    -f, --file    : File to write.
    """
    sys.exit(0)

def main():
    global db, constants, account
    global logger, outfile, person

    outfile = None
    logger = Factory.get_logger("cronjob")
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:',
                                   ['file='])
    except getopt.GetoptError:
        usage()

    dryrun = False
    for opt, val in opts:
        if opt in ('-f', '--file'):
            outfile = val

    if outfile is None:
        outfile = '/cerebrum/dumps/MAIL/mail_data.dat'

    db = Factory.get('Database')()
    constants = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    person = Factory.get('Person')(db)

    email_data = generate_email_data()
    write_email_file(email_data, outfile)

if __name__ == '__main__':
    main()

