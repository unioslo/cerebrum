#!/usr/bin/env python2.2

import getopt
import sys
from Cerebrum.modules.no.uio import AutoStud
from Cerebrum.modules.no import fodselsnr
from Cerebrum import Account
from Cerebrum import Person
from Cerebrum.Utils import Factory

import pprint
pp = pprint.PrettyPrinter(indent=4)

db = Factory.get('Database')()
co = Factory.get('Constants')(db)

debug = 0

def create_user(fnr, profile):
    print "Create %s: %s" % (fnr, profile)
    return "account_id"

def update_account(profile, account_ids, do_move=0):
    account = Account.Account(db)
    for a in account_ids:
        account.clear()
        account.find(a)
        # get_groups, add/delete

def get_student_accounts():
    account = Account.Account(db)
    person = Person.Person(db)
    ret = {}
    for a in account.find_accounts_by_type(affiliation=co.affiliation_student):
        account.clear()
        account.find(a)
        if account.owner_type == co.entity_person:
            person.find(account.owner_id)
            for it, ss, eid in person.get_external_id(id_type=co.externalid_fodselsnr):
                eid = fodselsnr.personnr_ok(eid)
                ret.set_default(eid, []).append(account.entity_id)
    return ret

def process_topics(update_accounts=0, create_users=0):
    students = get_student_accounts()
    autostud = AutoStud.AutoStud()

    for t in autostud.get_topics_list():
        profile = autostud.get_profile(t)
        fnr = fodselsnr.personnr_ok("%06d%05d" % (int(t[0]['fodselsdato']),
                                                  int(t[0]['personnr'])))
        if create_users and not students.has_key(fnr):
            students.set_default(fnr, []).append(create_user(fnr, profile))

        if update_account:
            update_accounts(profile, students[fnr])
    

def main():
    opts, args = getopt.getopt(sys.argv[1:], 'dcu',
                               ['debug', 'create-users', 'update-accounts'])
    global debug
    update_account = create_users = 0
    for opt, val in opts:
        if opt in ('-d', '--debug'):
            debug += 1
        elif opt in ('-c', '--create-users'):
            create_users = 1
        elif opt in ('-u', '--update-accounts'):
            update_accounts = 1
        else:
            usage()
    if(not update_accounts and not create_users):
        usage()
    process_topics(update_accounts, create_users)

def usage():
    print """Usage: process_students.py -d | -a
    """
    sys.exit(0)

if __name__ == '__main__':
    main()
