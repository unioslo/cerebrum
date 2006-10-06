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

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum.modules import CLHandler
from Cerebrum import Person
from Cerebrum.modules.no.hia import ADUtils

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
clco = Factory.get('CLConstants')(db)
entity = Entity.Entity(db)
entityname = Entity.EntityName(db)
account = Factory.get('Account')(db)
cl = CLHandler.CLHandler(db)
logger = Factory.get_logger("console")

delete_users = 0
delete_groups = 0
debug = False


def quick_user_sync():

    answer=cl.get_events('ad',(clco.account_password,clco.quarantine_mod))

    for ans in answer:
        chg_type = ans['change_type_id']
        if debug:
            print "change_id:",ans['change_id']
        if chg_type == clco.account_password:
            change_params = pickle.loads(ans['change_params'])
            if change_pw(ans['subject_entity'],change_params):
        else:
            logger.info("unknown chg_type %i" % chg_type)

        cl.confirm_event(ans)
        
    cl.commit_confirmations()    


def change_pw(account_id,pw_params):
    account.clear()
    account.find(account_id)
    if account.has_spread(int(co.spread_hia_ad_account)):
        pw=pw_params['password']
        pw=pw.replace('%','%25')
        pw=pw.replace('&','%26')
        user = id_to_name(account_id,'user')
        sock.send('ALTRUSR&%s/%s&pass&%s\n' % (cereconf.AD_DOMAIN,user,pw))
        returnans = sock.read()
        if  returnans == ['210 OK']:
	    return True
        else:
            logger.warn("Failed change password for %s:%s" % (user, returnans))
    else:
        if debug:
            print "Change password: Account %s, missing ad_spread" % (account_id)
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
        grp_postfix = cereconf.AD_GROUP_POSTFIX
    entityname.clear()
    entityname.find(id)
    name = entityname.get_name(namespace)
    obj_name = "%s%s" % (name,grp_postfix)
    return obj_name
    
        
def get_args():
    global delete_users
    global delete_groups
    for arrrgh in sys.argv:
        if arrrgh == '--delete_users':
            delete_users = 1
        elif arrrgh == '--delete_groups':
            delete_groups = 1


if __name__ == '__main__':
    sock = ADUtils.SocketCom()  
    arg = get_args()    
    quick_user_sync()
    sock.close()
    
# arch-tag: c9f5feae-1bd7-4798-ad76-a1ab690000ed
