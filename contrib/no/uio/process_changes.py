#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# This script should be ran regularly.  It process the changelog, and
# performs a number of tasks:
#
# - when a user has been creted: create users homedir

import cerebrum_path

import os
import sys
import getopt
import cereconf

from Cerebrum.extlib import logging
from Cerebrum.modules import CLHandler
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum import Disk
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup

logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
logger = logging.getLogger("cronjob")
db = Factory.get('Database')()
const = Factory.get('CLConstants')(db)
posix_user = PosixUser.PosixUser(db)
posix_group = PosixGroup.PosixGroup(db)
host = Disk.Host(db)
disk = Disk.Disk(db)
debug_hostlist = None

def insert_account_in_cl(account_name):
    """Add an account_create event to the ChangeLog.  Useful for
    testing, or if forcing an operation"""
    db.cl_init(change_by=None, change_program='process_changes')
    posix_user.clear()
    posix_user.find_by_name(account_name)
    db.log_change(posix_user.entity_id, const.account_create, None)
    db.commit()

def get_make_user_data(entity_id):
    posix_user.clear()
    posix_user.find(entity_id)
    posix_group.clear()
    posix_group.find(posix_user.gid_id)
    disk.clear()
    disk.find(posix_user.disk_id)
    host.clear()
    host.find(disk.host_id)
    return {'uname': posix_user.account_name,
            'disk': disk.path,
            'uid': str(posix_user.posix_uid),
            'gid': str(posix_group.posix_gid),
            'gecos': posix_user.get_gecos(),
            'host': host.name}

# TODO: remove this method iff we dont need to quote rsh cmd
def quote_list(lst):  # TODO: check that input is in [a-zA-Z0-9-_ '"]
    ret = ""
    for n in range(len(lst)):
        t = str(lst[n])
        t.replace('"', '\"')
        t.replace('\\', '\\\\')
        if t.find(" ") >= 0:
            t = '"'+t+'"'
        lst[n] = t
    return " ".join(lst)

def make_user(entity_id):
    try:
        info = get_make_user_data(entity_id)
    except Errors.NotFoundError:
        logger.warn("NotFound error for entity_id %s" % entity_id)
        return
    cmd = [cereconf.CREATE_USER_SCRIPT, info['uname'],
           "%s/%s" % (info['disk'], info['uname']),
           info['uid'], info['gid'], cereconf.POSIX_HOME_TEMPLATE_DIR,
           cereconf.POSIX_USERMOD_SCRIPTDIR, info['gecos']]

    # TODO: It seems that ssh properly handles the arguments to the
    # remote command, but this must be investigated further to prevent
    # malicious abuse.
    cmd = (cereconf.RSH_CMD, '-n', info['host']) + tuple(cmd)

    logger.debug("Doing: %s" % str(cmd))
    if debug_hostlist is None or info['host'] in debug_hostlist:
        os.spawnv(os.P_WAIT, cereconf.RSH_CMD, cmd)

def process_changes():
    # Note that CLHandler gets its own database handle
    ei = CLHandler.CLHandler(Factory.get('Database')())
    for evt in ei.get_events('uio_ch', [const.account_create]):
        if evt.change_type_id == int(const.account_create):
            logger.debug("Creating entity_id=%s" % (evt.subject_entity))
            make_user(evt.subject_entity)
        ei.confirm_event(evt)
    ei.commit_confirmations()
    #db.commit()

def usage(exitcode=0):
    print """process_changes.py [options]
    -h | --help
    -i | --insert account_name
    -p | --process-changes
    --debug-hosts <comma-serparated list> limit rsh targets to hosts in host_info"""
    sys.exit(exitcode)

def main():
    global debug_hostlist
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hi:p',
                                   ['help', 'insert=', 'process-changes',
                                    'debug-hosts='])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)
    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-i', '--insert'):
            insert_account_in_cl(val)
        elif opt in ('-p', '--process-changes'):
            process_changes()
        elif opt == '--debug-hosts':
            debug_hostlist = val.split(",")
            print debug_hostlist
if __name__ == '__main__':
    main()
