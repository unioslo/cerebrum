#!/usr/bin/env python2.2

import getopt
import sys

import cerebrum_path
import cereconf

from Cerebrum import Account
from Cerebrum import Disk
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.extlib import logging

db = Factory.get('Database')()
db.cl_init(change_program='process_bofhd_r')
const = Factory.get('Constants')(db)
logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
logger = logging.getLogger("cronjob")
# Hosts to connect to, set to None in a production environment:
debug_hostlist = ['cerebellum']

def process_move_requests():
    br = BofhdRequests(db, const)
    for r in br.get_requests(operation=const.bofh_move_user):
        if r['run_at'] < br.now:
            try:
                account, uname, old_host, old_disk = get_account(r['entity_id'])
                new_host, new_disk  = get_disk(r['destination_id'])
            except Errors.NotFoundError:
                logging.error("%i not found" % r['entity_id'])
                continue
            operator = get_account_name(r['requestee_id'])
            if move_user(uname, old_host, old_disk, new_host, new_disk, operator):
                account.disk_id =  r['destination_id']
                account.write_db()
                br.delete_request(r['entity_id'], r['requestee_id'], r['operation'])
                db.commit()
    for r in br.get_requests(operation=const.bofh_move_student):
        # TODO: Må også behandle const.bofh_move_student, men
        # student-auomatikken mangler foreløbig støtte for det.
        pass
    for r in br.get_requests(operation=const.bofh_delete_user):
        account, uname, old_host, old_disk = get_account(r['entity_id'])
        operator = get_account_name(r['requestee_id'])
        if delete_user(uname, old_host, '%s/%s' % (old_disk, uname), operator):
            account.expire_date = br.now
            account.write_db()
            br.delete_request(r['entity_id'], r['requestee_id'], r['operation'])
            db.commit()
    
def delete_user(uname, old_host, old_home, operator):
    cmd = [cereconf.ARUSER_SCRIPT, uname, operator, old_home]
    logging.debug("doing %s" % cmd)
    if debug_hostlist is None or old_host in debug_hostlist:
        errnum = os.spawnv(os.P_WAIT, cmd)
    else:
        errnum = 0
    if not errnum:
        return 1
    logging.error("%s returned %i" % (cereconf.ARUSER_SCRIPT, errnum))
    return 0

def move_user(uname, old_host, old_disk, new_host, new_disk, operator):
    mailto = operator
    receipt = 1
    cmd = [cereconf.MVUSER_SCRIPT, uname, uid, gid, old_disk,
           new_disk, mailto, receipt]
    logging.debug("doing %s" % cmd)
    if debug_hostlist is None or (old_host in debug_hostlist and
                                  new_host in debug_hostlist):
        errnum = os.spawnv(os.P_WAIT, cmd)
    else:
        errnum = 0
    if not errnum:
        return 1
    logging.error("%s returned %i" % (cereconf.ARUSER_SCRIPT, errnum))
    return 0

def get_disk(disk_id):
    disk = Disk.Disk(db)
    disk.clear()
    disk.find(disk_id)
    host = Disk.Host(db)
    host.clear()
    host.find(disk.host_id)
    return host.name, disk.path

def get_account_name(account_id):
    account = Account.Account(db)
    account.clear()
    account.find(account_id)
    return account.account_name

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
    else:
        host = None  # TODO:  How should we handle this?
    return account, uname, host, home

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dp',
                                   ['debug', 'process'])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)
    global debug
    for opt, val in opts:
        if opt in ('-d', '--debug'):
            debug += 1
        elif opt in ('-p', '--process'):
            process_move_requests()
    
def usage(exitcode=0):
    print """Usage: process_bofhd_requests.py
    -d | --debug: turn on debugging
    -p | --process: perform the queued operations"""
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
