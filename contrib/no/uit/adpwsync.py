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
import pickle
import getopt

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum.modules import CLHandler
from Cerebrum import Person
import adutils

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
clco = Factory.get('CLConstants')(db)
entity = Entity.Entity(db)
entityname = Entity.EntityName(db)
account = Factory.get('Account')(db)
cl = CLHandler.CLHandler(db)

logger = Factory.get_logger('cronjob')
sock=None

delete_users = 0
delete_groups = 0

def quick_user_sync():

    answer=cl.get_events('%s' % (cereconf.OMNI_NETBIOS_DOMAIN),(clco.account_password,clco.quarantine_mod))

    for ans in answer:
        chg_type = ans['change_type_id']
        logger.debug("change_id:%s" % ans['change_id'])
        if chg_type == clco.account_password:
            changed = False
            change_params = pickle.loads(ans['change_params'])
            if change_pw(ans['subject_entity'],change_params):
                changed = True
        else:
            logger.info("unknown chg_type %i" % chg_type)
        # do a check on change_pw success??
        if changed:
            cl.confirm_event(ans)
        
    cl.commit_confirmations()    


def change_pw(account_id,pw_params):
    account.clear()
    try:
        account.find(account_id)
    except Errors.NotFoundError:
        logger.debug("Account_ID %s not found! Account deleted?" % account_id)
        return True
    if (account.has_spread(int(co.spread_uit_fd)) or
        account.has_spread(int(co.spread_uit_ad_admin)) or
        account.has_spread(int(co.spread_uit_ad_lit_admin))):
        pw=pw_params['password']
        pw=pw.replace('%','%25')
        pw=pw.replace('&','%26')
        user = id_to_name(account_id,'user')
        sock.send('ALTRUSR&%s/%s&pass&%s\n' % (cereconf.OMNI_DOMAIN,user,pw))
        returnans = sock.read()
        if  returnans == ['210 OK']:
            logger.info("Changed passord for %s in %s" % (account.account_name,cereconf.OMNI_DOMAIN))
	    return True
        else:
            logger.error("Failed change password for %s:%s" % (user, returnans))
    else:
        logger.debug("Change password: Account %s, missing fd_spread" % (account_id))
        return True
    return False

            
def id_to_name(id,entity_type):
    grp_postfix = ''
    if entity_type == 'user':
        e_type = int(co.entity_account)
        namespace = int(co.account_namespace)
    elif entity_type == 'group':
        e_type = int(co.entity_group)
        namespace = int(co.group_namespace)
        grp_postfix = cereconf.OMNI_GROUP_POSTFIX
    entityname.clear()
    entityname.find(id)
    name = entityname.get_name(namespace)
    obj_name = "%s%s" % (name,grp_postfix)
    return obj_name


def usage(exit_code=0):
    print """

    usage stuff here


    """
    sys.exit(exit_code)
        
def get_args():
    global delete_users
    global delete_groups
    global logger_name

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h',
                                   ['help','delete_users', 'delete_groups'])
    except getopt.GetoptError:
        usage(1)

    for opt, val in opts:
        if opt == '--delete_users':
            delete_users = 1
        elif opt == '--delete_groups':
            delete_groups = 1
        elif opt in ('-h','--help'):
            usage(0)

    


def main():
    global sock
    arg = get_args()
    try:
        logger.info("Initializing communication")
        sock = adutils.SocketCom()
    except Exception,m:
        logger.error("Failed to connect AD server: %s" % m)
        sys.exit(1)

    quick_user_sync()
    sock.close()

if __name__ == '__main__':
    main()
