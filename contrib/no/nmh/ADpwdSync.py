#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006, 2010 University of Oslo, Norway
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


import getopt, sys, pickle
import cerebrum_path
import cereconf
import xmlrpclib

from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler


def run_cmd(command, arg1=None, arg2=None, arg3=None):
    cmd = getattr(server, command)
    if arg1 == None:
        ret = cmd()
    elif arg2 == None:
        ret = cmd(arg1)
    elif arg3 == None:
        ret = cmd(arg1, arg2)
    else:
        ret = cmd(arg1, arg2, arg3)    
    return ret


def quick_sync(spread, dry_run):
    # We reverse the set of events, so that if the same account has
    # multiple password changes, only the last will be updated. If we
    # didn't reverse, and if the first password update fails, then
    # this would be retried in the next run, and the next password
    # update(s) will not be rerun afterwards, leaving the user with an
    # older password than the last.
    handled = set()
    answer = reversed(cl.get_events('adpwd', (co.account_password,)))
    for ans in answer:
        confirm = True
        if (ans['change_type_id'] == co.account_password and
            not ans['subject_entity'] in handled):
            handled.add(ans['subject_entity'])
            pw = pickle.loads(ans['change_params'])['password']
            confirm = change_pw(ans['subject_entity'], spread, pw, dry_run)
        else:
            logger.debug("Unknown change_type_id %i" % ans['change_type_id'])

        if confirm:
            cl.confirm_event(ans)
    cl.commit_confirmations()    
    logger.info("Commited all changes, updated c_l_handler.")


def change_pw(account_id, spread, pw, dry_run):
    ac.clear()
    ac.find(account_id)

    if ac.has_spread(spread):
        dn = server.findObject(ac.account_name)
        logger.debug("Found object %s.", ac.account_name)
        ret = run_cmd('bindObject', dn)
        pwUnicode = unicode(pw, 'iso-8859-1')
        if not dry_run:
            ret = run_cmd('setPassword', pwUnicode)
        if ret[0]:
            logger.info('Changed password: %s' % ac.account_name)
            return True
    else:
        # Account without ADspread, do nothing and return.
        return True

    # Something went wrong.
    logger.error('Failed change password: %s' % ac.account_name)
    return False


def main():
    global cl, db, co, ac, logger, server
    
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    logger = Factory.get_logger("cronjob")
    cl = CLHandler.CLHandler(db)

    delete_objects = False
    user_spread = None
    dry_run = False
    
    passwd = db._read_password(cereconf.AD_SERVER_HOST,
                               cereconf.AD_SERVER_UNAME)

    # Connect to AD-service at NMH
    #
    server = xmlrpclib.Server("https://%s@%s:%i" % (passwd,
                                                    cereconf.AD_SERVER_HOST,
                                                    cereconf.AD_SERVER_PORT))    

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hds:',
                                   ['user_spread=',
                                    'help',
                                    'dry_run'])
    except getopt.GetoptError:
        usage()

    for opt, val in opts:
        if opt == '--user_spread':
            user_spread = getattr(co, val)  # TODO: Need support in Util.py
        elif opt == '--help':
            usage()
        elif opt == '--dry_run':
            dry_run = True

    if not user_spread:
        usage()

    logger.info("Syncronizing passwords...")
    quick_sync(user_spread, dry_run)
    logger.info("All done.")
                
    
def usage(exitcode=0):
    print """Usage: ADpwdSync.py --user_spread spread_ad_account
                    -s, --user_spread: update onlys for users with spread to AD
                    -d, --dry_run: don't do any changes in AD
                    -h, --help: print this text"""


if __name__ == '__main__':
    main()
