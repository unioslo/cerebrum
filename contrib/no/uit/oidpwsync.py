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

#Cereconf values
default_logger = cereconf.OID_LOGGER
ldap_active = cereconf.OID_LDAP
ldap_server = cereconf.OID_LDAP_SERVER
base = cereconf.OID_SEARCH_BASE
who = cereconf.OID_MANAGER
cred = cereconf.OID_MANAGER_PASS
max_changes = cereconf.OID_MAX_PWD_CHANGES


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
        return False

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
                return False
    
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
    global logger, default_logger, ldap_conn, ldap_active, ldap_server, who, cred, max_changes

    logger = Factory.get_logger(default_logger)


    try:
        opts,args = getopt.getopt(sys.argv[1:], \
                                  'c:l:s:u:p:m:',\
                                  ['changelog_id=', 'ldap_server=', 'search_base=', 'username=', 'password=','max_changes='])
    except getopt.GetoptError:
        usage()

    for opt,val in opts:
        if opt in('-c','--changelog_id'):
            ldap_active = val
        elif opt in('-l','--ldap_server'):
            ldap_server = val
        elif opt in('-s','--search_base'):
            base = val
        elif opt in('-u','--username'):
            who = val
        elif opt in('-p','--password'):
            cred = val
        elif opt in ('-m','--max_changes'):
            max_changes = int(val)


    if ldap_active == '' or ldap_active is None:
        logger.error("Empty change handler id! This would go through the entire change-log. No way! Quitting!")
        sys.exit(1)

    changes = cl.get_events(ldap_active, (clco.account_password,))
    num_changes = len(changes)
    if num_changes == 0:
        logger.info("Nothing to do on %s" % ldap_server)
        return
    elif num_changes > max_changes:
        logger.error("Too many changes (%s)! Check if change handler id (%s) is correct, or override limit in command-line or cereconf" %
                     (num_changes, ldap_active))
        sys.exit(1)

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



def usage():
    global cereconf
    
    print """
    usage:: python oidpwsync.py 
    -c | --changelog_id: changelog_id to monitor for changes. Default is %s
    -l | --ldap_server: ldap server to connect to. Default is %s
    -s | --search_base : ldap server search base. Default is %s
    -u | --username: ldap username with admin rights. Default is %s
    -p | --password: ldap password for admin user. Default is ******* (YOU WISH!)
    -m | --max_changes: maximum number of passwords to sync. Default is %s
    Default values are defined in cereconf.
    """ % (cereconf.OID_LDAP, cereconf.OID_LDAP_SERVER, cereconf.OID_SEARCH_BASE, cereconf.OID_MANAGER, cereconf.OID_MAX_PWD_CHANGES)
    sys.exit(1)


if __name__ == '__main__':
    main()
    
