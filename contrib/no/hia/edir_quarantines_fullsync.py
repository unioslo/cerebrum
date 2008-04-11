#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2002-2005 University of Oslo, Norway
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

# UiA-specific ext. 
# Synchronise all quarantine data

import sys, os, getopt, time, string, ldap, ldif

import cerebrum_path
import cereconf

from mx import DateTime

from Cerebrum import Constants
from Cerebrum.modules.no.hia import EdirUtils
from Cerebrum.modules.no.hia import EdirLDAP
from Cerebrum import Errors
from Cerebrum.extlib import logging
from Cerebrum.Utils import Factory
from Cerebrum import QuarantineHandler

def check_quarantine(account):
    now = DateTime.now()
    if account.get_entity_quarantine(only_active=True):
        return True
    return False
        
def main():
    global db, constants
    global edir_util, logger
    
    db = Factory.get('Database')()
    constants = Factory.get('Constants')(db)
    account = Factory.get("Account")(db)
    logger = Factory.get_logger('console')
    edir_object_class = 'objectClass=inetOrgPerson'

    all_accounts_cerebrum = account.list()
    
    passwd = db._read_password(cereconf.NW_LDAPHOST,
                               cereconf.NW_ADMINUSER.split(',')[:1][0])
    ldap_handle = EdirLDAP.LDAPConnection(db, cereconf.NW_LDAPHOST,
                                          cereconf.NW_LDAPPORT,
                                          binddn=cereconf.NW_ADMINUSER,
                                          password=passwd, scope='sub')

    edir_util = EdirUtils.EdirUtils(db, ldap_handle)

    for a in all_accounts_cerebrum:
        account.clear()
        account.find(a['account_id'])
        uname = account.account_name
        if not account.has_spread(constants.spread_hia_novell_user):
            logger.debug("%s not an eDir user", uname)
            continue
        quarantine_cerebrum = check_quarantine(account)
        account_edir = edir_util._find_object(uname, edir_object_class)
        if account_edir:
            quarantine_edir = edir_util.account_get_quarantine_status(uname)
        else:
            logger.error("No account fond in eDir for %s", uname)
            continue
        if quarantine_cerebrum:
            if quarantine_edir:
                logger.debug("Skipping %s, quarantined in both cerebrum and edir.", uname)
            else:
                logger.error("%s quarantined in cerebrum but not in eDir should update eDir", uname)
                # logger.info("%s quarantined in cerebrum but not in eDir, updating eDir", uname)
                # edir_utils.account_set_quarantine(uname)
        else:
            if quarantine_edir:
                logger.error("%s quarantined in eDir but not in Cerebrum", uname)

    ldap_handle.close_connection()
    
if __name__ == '__main__':
    main()
