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

# account_add, account_rem, account_mod?
# group add account, group rem account
# group_add, group_rem
# quarantine_add, quarantine_rem, quarantine_mod

#
import sys, os, getopt, time, string, pickle, re, ldap, ldif

import cerebrum_path
import cereconf
from Cerebrum import Constants
from Cerebrum.modules.no.hia import EdirUtils
from Cerebrum.modules.no.hia import EdirLDAP
from Cerebrum import Errors
from Cerebrum import Group
from Cerebrum import Entity
from Cerebrum.extlib import logging
from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler


## TODO:
## def edir_build_group(group_id):
##     group = Factory.get("Group")(db)
##     group.clear()
##     group.find(group_id)
##     group_name = cereconf.NW_GROUP_PREFIX + '-' + group.group_name
##     utf8_dn = unicode('cn=%s' % group_name, 'iso-8859-1').encode('utf-8')
##     ## TODO: how de we decide group-ou?!?
##     ldap_dn = utf8_dn + ',ou=grp,ou=Stud,' + cereconf.NW_LDAP_ROOT
##     attr_dict = {'objectClass': ['group'],
##                  'cn': [group_name],
##                  'member': [],
##                  'description': ['test']}
##     edir_util.object_edir_create(ldap_dn, attr_dict)
##             if event['change_type_id'] == constants.spread_add:
##                 ch_p = pickle.loads(event['change_params'])
##                 if ch_p['spread'] == int(constants.spread_hia_novell_group):
##                     cl_events.append(event)
##             elif event['change_type_id'] == constants.spread_del:
##                 ent = Factory.get('Entity')(db)
##                 ent.clear()
##                 ent.find(event['subject_entity'])
##                 if ent.entity_type == int(constants.entity_account):
##                     logger.info('Account delete is handled by process_deleted.py!')
##                     continue
##                elif ent.entity_type == int(constants.entity_group):
##                    cl_events.append(event)


def group_mod(mod_type, group_id, member_id):
    group = Factory.get("Group")(db)
    grp = Factory.get("Group")(db)
    acc = Factory.get("Account")(db)
    ent_name = ""
    ent_type = "account"
    edir_group = False
    group.clear()
    group.find(group_id)

    for row in group.get_spread():
        if int(constants.spread_hia_novell_group) == row['spread']:
            edir_group = True
    if not edir_group:
        logger.debug("Skipping, group %s not in eDir", group.group_name)
        return

    group_name = cereconf.NW_GROUP_PREFIX + '-' + group.group_name
    op = constants.group_memberop_union
    subj_ent = Factory.get('Entity')(db)
    subj_ent.clear()
    try:
        subj_ent.find(member_id)
    except Errors.NotFoundError:
        logger.warn('No such entity %s.', member_id)
        return
    if subj_ent.entity_type == constants.entity_account:
        acc.find(member_id)
        ent_name = acc.account_name
    elif subj_ent.entity_type == constants.entity_group:
        grp.find(member_id)
        ent_type = "group"
        ent_name = cereconf.NW_GROUP_PREFIX + '-' + grp.group_name
    else:
        logger.warn("Only groups or accounts may be members!")
        return

    if mod_type == constants.group_add:
        logger.info('Adding to group')
        edir_util.group_modify('add', group_name, ent_name, ent_type)
        logger.info('New member %s added to %s' % (ent_name, group_name))
    elif mod_type == constants.group_rem:
        logger.info('Removing from group')
        edir_util.group_modify('delete', group_name, ent_name, ent_type)
        logger.info('Member %s removed from %s' % (ent_name, group_name))

        
def main():
    global db, constants
    global edir_util, logger
    
    db = Factory.get('Database')()
    constants = Factory.get('Constants')(db)
    cl_handler = CLHandler.CLHandler(db)
    logger = Factory.get_logger('cronjob')

    cl_events = []

    passwd = db._read_password(cereconf.NW_LDAPHOST,
                               cereconf.NW_ADMINUSER.split(',')[:1][0])
    ldap_handle = EdirLDAP.LDAPConnection(db, cereconf.NW_LDAPHOST,
                                          cereconf.NW_LDAPPORT,
                                          binddn=cereconf.NW_ADMINUSER,
                                          password=passwd, scope='sub')
    edir_util = EdirUtils.EdirUtils(db, ldap_handle)

    try:
        cl_events = cl_handler.get_events('edirgroups', (constants.group_add,
                                                         constants.group_rem))
        if cl_events == []:
            logger.info("Nothing to do.")
            ldap_handle.close_connection()
            sys.exit(0)
            
        for event in cl_events:
            if event['change_type_id'] in [constants.group_add, constants.group_rem,]:
                group_mod(event['change_type_id'],
                          event['dest_entity'],
                          event['subject_entity'])
                cl_handler.confirm_event(event)
    except TypeError, e:
        logger.warn("No such event, %s" % e)
        return None
    cl_handler.commit_confirmations()

    ldap_handle.close_connection()
    
if __name__ == '__main__':
    main()
