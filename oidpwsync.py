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
logger = None
ldap_conn = None
ldap_active = 'OID'
ldap_server = "ldap://portalt1.uit.no"
base = "dc=uit,dc=no"
who = "cn=orcladmin,cn=users,dc=uit,dc=no"
cred = "t4ntdy4l4m4"


def pwd_sync(changes):

    for chg in changes:
        chg_type = chg['change_type_id']
        logger.debug("change_id:%s" % chg['change_id'])
        if chg_type == clco.account_password:
            changed = False
            change_params = pickle.loads(chg['change_params'])
            if change_pw(chg['subject_entity'],change_params):
                changed = True
        else:
            logger.warn("unknown chg_type %i" % chg_type)
        
        if changed:
            cl.confirm_event(chg)
        
    cl.commit_confirmations()    


def change_pw(account_id,pw_params):

    global ldap_conn, base, scope, filter

    account.clear()
    try:
        account.find(account_id)
    except Exception, ex:
        logger.error("Account not found in BAS (%s)" % account_id)

    result_set = []
    all = 0 # receive results as they are returned (do not wait until all results are received)
    
    scope = ldap.SCOPE_SUBTREE
    filter = "(cn=" + "*" + account.account_name + "*)"

    pw = pw_params['password']
    #pw = pw.replace('%', '%25')
    #pw = pw.replace('&', '%26')
    
    try:
        entries_found = 0
        entries_modified = 0
        result_id = ldap_conn.search(base, scope, filter, None)
        
        while 1:
            result_type, result_data = ldap_conn.result(msgid=result_id, all=all)
            if result_data == []:
                break
            if result_type != ldap.RES_SEARCH_ENTRY:
                continue
            
            entries_found = entries_found + 1
            dn = result_data[0][0]
            modified = 0

            # UNDER Python 2.5 USE ->  hashlib.md5(pw).digest()
            md5pw = "{MD5}%s" % base64.encodestring(md5.new(pw).digest()).rstrip()
            
            logger.info("Modifying password for %s..." % (account.account_name))
            try:
                ldap_conn.modify_s(dn, [(ldap.MOD_REPLACE,'userpassword', md5pw)])
                logger.info("  - Modified password for %s in %s" % (dn, ldap_active))
                entries_modified = entries_modified + 1
            except ldap.LDAPError, error_message:
                logger.error("  - Failed modifying password for %s on %s. Error follows: %s" %
                             (account.account_name, ldap_active, error_message))
    
        if entries_found == 0:
            logger.info("Account %s NOT FOUND in %s" % (account.account_name, ldap_active))
        elif entries_found > 1:
            logger.info("Account %s FOUND % TIMES AND UPDATED %s TIMES  in %s" %
                        (account.account_name, entries_found, entries_modified, ldap_active))
        return True
    
    except ldap.LDAPError, error_message:
        logger.error(error_message)
        return False


def main():
    global logger, ldap_conn, ldap_active, ldap_server, who, cred

    logger = Factory.get_logger('console')

    changes = cl.get_events(ldap_active, (clco.account_password,))
    num_changes = len(changes)
    if num_changes == 0:
        logger.info("Nothing to do on %s" % ldap_server)
        return

    logger.info("Starting to sync %s password changes since last sync" % num_changes)
    
    try:
        logger.info("Initializing communication with %s" % ldap_server)
        ldap_conn = ldap.initialize(ldap_server)
        ldap_conn.simple_bind_s(who,cred)
        logger.info("Successfully bound to server %s" % ldap_server)
        
    except ldap.LDAPError, error_message:
        logger.error("Couldn't connect to %s. ERROR: %s" % (ldap_server, error_message))
        sys.exit(1)

    pwd_sync(changes)

    try:
        ldap_conn.unbind_s()
        logger.info("Successfully unbound from server %s" % ldap_server)
    except ldap.LDAPError, error_message:
        logger.error("Couldn't disconnect from %s. ERROR: %s" % (ldap_server, error_message))
        sys.exit(1)

    return


if __name__ == '__main__':
    main()
    
