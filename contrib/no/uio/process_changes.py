#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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

# This script should be run regularly.  It processes the changelog,
# and performs a number of tasks:
#
# - when a user has been creted: create users homedir

# TBD: If this script is only going to be used for creating users, it
# should probably be renamed.  There are already other scrits, like
# nt/notes sync that process the changelog themselves.  We need to
# determine wheter it is a good idea to have multiple small scripts
# doing this, or if there is an advantage into merging all of them
# into a bigger script, perhaps with some plugin-like structure for
# subscribing to certain event types.

import os
import sys
import getopt
import pickle

import cerebrum_path
import cereconf
from Cerebrum.extlib import logging
from Cerebrum.modules import CLHandler
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup

logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
logger = logging.getLogger("cronjob")
db = Factory.get('Database')()
db.cl_init(change_program="process_changes")
cl_const = Factory.get('CLConstants')(db)
const = Factory.get('Constants')(db)
posix_user = PosixUser.PosixUser(db)
posix_group = PosixGroup.PosixGroup(db)
host = Factory.get('Host')(db)
disk = Factory.get('Disk')(db)
debug_hostlist = None
SUDO_CMD = "/usr/bin/sudo"     # TODO: move to cereconf

# TODO: change if we decide to allow different homedirs for same user
home_spread = const.spread_uio_nis_user   

def insert_account_in_cl(account_name):
    """Add an account_create event to the ChangeLog.  Useful for
    testing, or if forcing an operation"""
    db.cl_init(change_by=None, change_program='process_changes')
    posix_user.clear()
    posix_user.find_by_name(account_name)
    db.log_change(posix_user.entity_id, cl_const.account_create, None)
    db.commit()

def get_make_user_data(entity_id):
    posix_user.clear()
    posix_user.find(entity_id)
    posix_group.clear()
    posix_group.find(posix_user.gid_id)
    disk.clear()
    home = posix_user.get_home(home_spread)
    homedir = posix_user.get_posix_home(home_spread)
    disk.find(home['disk_id'])
    host.clear()
    host.find(disk.host_id)

    return {'uname': posix_user.account_name,
            'home': posix_user.get_posix_home(home_spread),
            'uid': str(posix_user.posix_uid),
            'gid': str(posix_group.posix_gid),
            'gecos': posix_user.get_gecos(),
            'host': host.name,
            'home': home,
            'homedir': homedir}

def make_user(entity_id):
    try:
        info = get_make_user_data(entity_id)
    except Errors.NotFoundError:
        logger.warn("NotFound error for entity_id %s" % entity_id)
        raise
    if int(info['home']['status']) == const.home_status_on_disk:
        logger.warn("User already on disk? %s" % entity_id)
        return
    if info['homedir'] is None:
        logger.warn("No home for %s" % entity_id)
        return

    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'mkhome',
           # info['host'],  # the mkhome script figures out the host
           info['uname'], info['homedir'], info['uid'], info['gid'],
           info['gecos']]

    #cmd = cmd[1:]  # DEBUG

    logger.debug("Doing: %s" % str(cmd))
    if debug_hostlist is None or info['host'] in debug_hostlist:
        errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
    else:
        errnum = 0
    if not errnum:
        return 1
    logger.error("%s returned %i" % (cmd, errnum))
    return 0

def process_changes():
    # Note that CLHandler gets its own database handle
    ei = CLHandler.CLHandler(Factory.get('Database')())
    for evt in ei.get_events('uio_ch', [cl_const.account_home_added]):
        if evt['change_params']:
            params = pickle.loads(evt['change_params'])
        else:
            params = {}
        if (evt.change_type_id == int(cl_const.account_create) or
            (evt.change_type_id == int(cl_const.account_home_added) and
             params.get('spread', 0) == int(home_spread))):
            logger.debug("Creating entity_id=%s" % (evt.subject_entity))
            try:
                if make_user(evt.subject_entity):
                    status = const.home_status_on_disk
                else:
                    status = const.home_status_create_failed
            except Errors.NotFoundError:
                ei.confirm_event(evt)
                continue  # A reserved user or similar that don't get a homedir
            # posix_user was set by get_make_user_data
            home = posix_user.get_home(home_spread)
            posix_user.set_home(home_spread, disk_id=home['disk_id'],
                                home=home['home'], status=status)

        ei.confirm_event(evt)
    ei.commit_confirmations()
    db.commit()

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
