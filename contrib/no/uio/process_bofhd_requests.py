#!/usr/bin/env python2.2

import getopt
import sys
import cereconf

from Cerebrum import Account
from Cerebrum import Disk
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.utils import BofhdRequests

db = Factory.get('Database')()
db.cl_init(change_program='process_students')
const = Factory.get('Constants')(db)

def process_move_requests():
    br = BofhdRequests(db, const)
    for r in br.get_requests(operation=const.bofh_move_user):
        if r['run_at'] < br.now:
            try:
                account, uname, old_host, old_home = get_account(r['entity_id'])
                new_host, new_home_disk  = get_disk(r['destination_id'])
            except Errors.NotFoundError:
                print "ERROR for %i" % r['entity_id']
                continue
            if move_user(uname, old_host, old_home, new_host, new_home_disk):
                account.disk_id =  r['destination_id']
                account.write_db()
                br.delete_request(r['entity_id'], r['requestee_id'], r['operation'])
                db.commit()
    for r in br.get_requests(operation=const.bofh_move_student):
        # TODO: Må også behandle const.bofh_move_student, men
        # student-auomatikken mangler foreløbig støtte for det.
        pass
    for r in br.get_requests(operation=const.bofh_delete_user):
        account, uname, old_host, old_home = get_account(r['entity_id'])
        if delete_user(uname, old_host, old_home):
            account.expire_date = br.now
            account.write_db()
            br.delete_request(r['entity_id'], r['requestee_id'], r['operation'])
            db.commit()

def delete_user(uname, old_host, old_home):
    print "delete: %s@%s:%s" % (uname, old_host, old_home)
    return 1

def move_user(uname, old_host, old_home, new_host, new_home_disk):
    print "%s@%s:%s -> %s:%s" % (uname, old_host, old_home, new_host, new_home_disk)
    return 1

def get_disk(disk_id):
    disk = Disk.Disk(db)
    disk.clear()
    disk.find(disk_id)
    host = Disk.Host(db)
    host.clear()
    host.find(disk.host_id)
    return host.name, disk.path

def get_account(account_id):
    account = Account.Account(db)
    account.clear()
    account.find(account_id)
    home = account.home
    uname = account.get_account_name()
    if home is None:
        if account.disk_id is None:
            raise Errors.NotFoundError, "Bad disk for %s" % uname
        host, home = get_disk(account.disk_id)
        home += "/"+uname
    else:
        host = None  # TODO:  How should we handle this?
    return account, uname, host, home

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'd',
                                   ['debug'])
    except getopt.GetoptError:
        usage(1)
    global debug
    for opt, val in opts:
        if opt in ('-d', '--debug'):
            debug += 1
        else:
            usage()
    process_move_requests()
    
def usage(exitcode=0):
    print """Usage:     """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
