#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

import getopt
import sys
import os

import cerebrum_path
import cereconf

from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
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
SUDO_CMD="/usr/bin/sudo"

def process_move_requests():
    br = BofhdRequests(db, const)
    for r in br.get_requests(operation=const.bofh_move_user):
        if r['run_at'] < br.now:
            try:
                account, uname, old_host, old_disk = get_account(
                    r['entity_id'], type='PosixUser')
                new_host, new_disk  = get_disk(r['destination_id'])
            except Errors.NotFoundError:
                logger.error("%i not found" % r['entity_id'])
                continue
            operator = get_account(r['requestee_id'])[0].account_name
            group = get_group(account.gid_id, grtype='PosixGroup')
            if move_user(uname, int(account.posix_uid), int(group.posix_gid),
                         old_host, old_disk, new_host, new_disk, operator):
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
        operator = get_account(r['requestee_id'])[0].account_name
        if delete_user(uname, old_host, '%s/%s' % (old_disk, uname), operator):
            account.expire_date = br.now
            account.write_db()
            br.delete_request(r['entity_id'], r['requestee_id'], r['operation'])
            db.commit()
    
def delete_user(uname, old_host, old_home, operator):
    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'aruser', uname,
           operator, old_home]
    cmd = ["%s" % x for x in cmd]
    logger.debug("doing %s" % cmd)
    if debug_hostlist is None or old_host in debug_hostlist:
        errnum = os.spawnv(os.P_WAIT, cmd)
    else:
        errnum = 0
    if not errnum:
        return 1
    logger.error("%s returned %i" % (cmd, errnum))
    return 0

def move_user(uname, uid, gid, old_host, old_disk, new_host, new_disk, operator):
    mailto = operator
    receipt = 1
    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'mvuser', uname, uid,
           gid, old_disk, new_disk, mailto, receipt]
    cmd = ["%s" % x for x in cmd]
    logger.debug("doing %s" % cmd)
    if debug_hostlist is None or (old_host in debug_hostlist and
                                  new_host in debug_hostlist):
        errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
    else:
        errnum = 0
    if not errnum:
        return 1
    logger.error("%s returned %i" % (cmd, errnum))
    return 0

def get_disk(disk_id):
    disk = Disk.Disk(db)
    disk.clear()
    disk.find(disk_id)
    host = Disk.Host(db)
    host.clear()
    host.find(disk.host_id)
    return host.name, disk.path

def get_account(account_id, type='Account'):
    if type == 'Account':
        account = Account.Account(db)
    elif type == 'PosixUser':
        account = PosixUser.PosixUser(db)        
    account.clear()
    account.find(account_id)
    home = account.home
    uname = account.account_name
    if home is None:
        if account.disk_id is None:
            return account, uname, None, None
        host, home = get_disk(account.disk_id)
    else:
        host = None  # TODO:  How should we handle this?
    return account, uname, host, home

def get_group(id, grtype="Group"):
    if grtype == "Group":
        group = Group.Group(db)
    elif grtype == "PosixGroup":
        group = PosixGroup.PosixGroup(db)
    group.clear()
    group.find(id)
    return group

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
