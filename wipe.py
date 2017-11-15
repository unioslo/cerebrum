#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
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


import sys
import getopt
import pickle
import time

import cerebrum_path
import cereconf

import ldap
import md5 # DEPRECATED IN Python 2.5, USE hashlib WHEN AVAILABLE!!!
import base64

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum.modules import CLHandler

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
clco = Factory.get('CLConstants')(db)
entity = Entity.Entity(db)
entityname = Entity.EntityName(db)
account = Factory.get('Account')(db)
cl = CLHandler.CLHandler(db)

# GLOBALS
ldap_conn = None
logger = None
dryrun = False

#Cereconf values
default_logger = cereconf.DEFAULT_LOGGER_TARGET
changelog_tracker = cereconf.PWD_WIPE_EVENT_HANDLER_KEY
max_changes = cereconf.PWD_MAX_WIPES
age_threshold = cereconf.PWD_AGE_THRESHOLD


def pwd_wipe(changes):

    global cl
    
    now = time.time()

    for chg in changes:
        changed = False
        age = now - chg['tstamp'].ticks()
        if age > age_threshold:
            logger.debug('Password will be wiped: ' + str(chg['change_id']))
            change_params = pickle.loads(chg['change_params'])
            #print change_params
            #print chg['change_params']
            #print chg['change_id']
            if wipe_pw(chg['change_id'],change_params):
                changed = True
        else:
            logger.debug('Password will not be wiped (too recent): ' + str(chg['change_id']))
                
        if changed:
            cl.confirm_event(chg)

    if not dryrun:
        logger.info('Commiting changes')
        cl.commit_confirmations()
    else:
        logger.info('Changes not committed (dryrun)')


def wipe_pw(change_id,pw_params):

    global cl
    
    if pw_params.has_key('password'):
        del(pw_params['password'])
        if not dryrun:
            db.update_log_event(change_id, pw_params)
            logger.debug("Wiped password for change_id=%i" % change_id)
            return True
        else:
            return False
    else:
        #print pw_params.keys()
        return True


def main():
    global logger, default_logger, changelog_tracker, max_changes, age_threshold, dryrun

    logger = Factory.get_logger(default_logger)

    try:
        opts,args = getopt.getopt(sys.argv[1:], \
                                  'c:m:a:d',\
                                  ['changelog_tracker=', 'max_changes=', 'age_threshold=', 'dryrun'])
    except getopt.GetoptError:
        usage()

    for opt,val in opts:
        if opt in('-c','--changelog_tracker'):
            changelog_tracker = val
        elif opt in ('-m','--max_changes'):
            max_changes = int(val)
        elif opt in ('-a','--age_threshold'):
            age_threshold = int(val)
        elif opt in ('-d','--dryrun'):
            dryrun = True


    if changelog_tracker == '' or changelog_tracker is None:
        logger.error("Empty changelog tracker! This would go through the entire change-log. No way! Quitting!")
        sys.exit(1)

    changes = cl.get_events(changelog_tracker, (clco.account_password,))
    num_changes = len(changes)
    if num_changes == 0:
        logger.info("No passwords to wipe!")
        return
    elif num_changes > max_changes:
        logger.error("Too many changes (%s)! Check if changelog tracker (%s) is correct, or override limit in command-line or cereconf" %
                     (num_changes, changelog_tracker))
        sys.exit(1)

    logger.info("Starting to wipe %s password changes since last wipe" % num_changes)
    pwd_wipe(changes)
    logger.info("Finished wiping passwords")
    return



def usage():
    global cereconf
    
    print """
    usage:: python wipe.py 
    -c | --changelog_tracker: evthdlr_key to monitor for changes. Default is %s
    -m | --max_changes: maximum number of passwords to wipe. Default is %s
    -a | --age_threshold: how old passwords need to be before they are wiped. Default is %s
    Default values are defined in cereconf.
    """ % (cereconf.PWD_WIPE_EVENT_HANDLER_KEY, cereconf.PWD_MAX_WIPES, cereconf.PWD_AGE_THRESHOLD)
    sys.exit(1)


if __name__ == '__main__':
    main()

