#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006 University of Oslo, Norway
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

import getopt
import sys
import cerebrum_path
import cereconf
import xmlrpclib

from Cerebrum.Utils import Factory


def fetch_cerebrum_data(spread):
    return list(group.search(spread=spread))


def fetch_ad_data():
    temp = server.listObjects('group', True)
    ad_groups = []
    for t in temp:
        rest, name = t.split(',')[0].split('=')
        ad_groups.append(name)
    return ad_groups


def fetch_ad_usrdata():
    # remove all attributes from userattributes-dict except
    # distinguishedName and the default value sAMAccountName.
    #
    server.setUserAttributes()
    return server.listObjects('user', True)


def full_sync(delete_groups, dry_run):
    # fetch group info from AD
    #
    adgroups = fetch_ad_data()
    logger.debug("Fetched %i groups from AD", len(adgroups))	

    # fetch group info from cerebrum
    #
    cerebrumgroups = fetch_cerebrum_data(co.spread_ad_group)
    logger.info("Fetched %i groups from Cerebrum" % len(cerebrumgroups))
        
    # compare group data in cerebrum and AD
    #
    changelist = compare(delete_groups, cerebrumgroups, adgroups)
    logger.info("Found %i changes in group info", len(changelist))


    # execute change-commands in AD
    #
    perform_changes(changelist, dry_run)	
    sync_groups(cerebrumgroups, dry_run)


def perform_changes(changelist, dry_run):
    if dry_run:
        logger.info("Would perform %d changes", len(changelist))
    for chg in changelist:
        if chg['type'] == 'createObject':
            ret = run_cmd(chg['type'],
                          dry_run,
                          'Group',
                          '%s,%s' % (cereconf.AD_DEFAULT_GROUP_OU, cereconf.AD_LDAP),
                          chg['distinguishedName'])
            if not ret[0]:
                logger.error("Could not create group: %s", chg['distinguishedName'])
            else:
                logger.info("Created group %s", chg['distinguishedName']) 
        elif chg['type'] == 'deleteObject':
            adname = 'CN=' + chg['distinguishedName'] +',%s,%s' % (cereconf.AD_DEFAULT_GROUP_OU,
                                                                   cereconf.AD_LDAP)
            run_cmd('bindObject', dry_run, adname)
            ret = run_cmd(chg['type'], dry_run)
            if not ret[0]:
                logger.error("Could not delete object: %s", ret[1])
            else:
                logger.info("Deleted group %s", chg['distinguishedName']) 
        else:
            logger.warn("Unknown change-type: %s", chg['type'])


def sync_groups(cerebrumgroups, dry_run):
    # To reduce traffic send current list of groupmembers to AD
    # The server ensures that each group has correct members.   

    # preload all the names
    entity2name = dict((x["entity_id"], x["entity_name"]) for x in 
                       group.list_names(co.account_namespace))
    entity2name.update((x["entity_id"], x["entity_name"]) for x in
                       group.list_names(co.group_namespace))
    for g in cerebrumgroups:
        group.clear()
        group.find(g['group_id'])
        members = []
        for user in group.search_members(group_id=group.entity_id,
                                         member_spread=co.spread_ad_account):
            # TODO: How to treat quarantined users???, some exist in AD,
            # others do not. They generate errors when not in AD. We still
            # want to update group membership if in AD.
            user_id = int(user["member_id"])
            # skip the ones with unknown names
            if user_id not in entity2name:
                continue
            members.append(entity2name[user_id])
        
        for grp in group.search_members(group_id=group.entity_id,
                                        member_spread=co.spread_ad_group):
            grp_id = int(grp["member_id"])
            if grp_id not in entity2name:
                continue
            members.append('%s%s' % (entity2name[grp_id],
                                     cereconf.AD_GROUP_POSTFIX))
        
        # Try to locate group object in AD
        #
        dn = None
        dn = server.findObject('%s%s' % (g['name'], cereconf.AD_GROUP_POSTFIX))

        if not dn:
            logger.warn("No such group: %s%s" % (g['name'], cereconf.AD_GROUP_POSTFIX))
        else:
            server.bindObject(dn)
            res = server.syncMembers(members, False)
            if not res[0]:
                logger.warn("Failed to syncronize members for %s: %s", dn, res[1])
            else:
                logger.info("Successfully syncronized group %s", dn)


def run_cmd(command, dry_run, arg1=None, arg2=None, arg3=None):
    if dry_run:
        logger.info('Dryrun: server.%s(%s,%s,%s)' % (command, arg1, arg2, arg3))
        #Assume success on all changes.
        #
        return (True, command)
    else:
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


def compare(delete_groups, cerebrumgrp, adgrp):
    changelist = []
    for g in cerebrumgrp:
        adcn = g['name'] +  cereconf.AD_GROUP_POSTFIX
        if adcn in adgrp:
            logger.debug("Found group %s, removing from update list", g['name'])
            adgrp.remove(adcn)
        else:
            logger.debug("Could not find group %s, will create", adcn)
            changelist.append({'type': 'createObject',
                               'distinguishedName' : '%s%s' % (g['name'], cereconf.AD_GROUP_POSTFIX),
                               'description' : g['description']})
    # the remaining groups are not registered in cerebrum and
    # will be deleted
    #
    for adg in adgrp:
        changelist.append({'type' : 'deleteObject',
                           'distinguishedName' : adg}) 
    return changelist


def main():
    global db, co, group, logger, server
    
    delete_groups = False
    dry_run = False	

    db = Factory.get('Database')()
    db.cl_init(change_program="adgsync")
    group = Factory.get('Group')(db)
    co = Factory.get('Constants')(db)
    logger = Factory.get_logger("cronjob")

    passwd = db._read_password(cereconf.AD_SERVER_HOST,
                               cereconf.AD_SERVER_UNAME)

    server = xmlrpclib.Server("https://%s@%s:%i" % (passwd,
                                                    cereconf.AD_SERVER_HOST,
                                                    cereconf.AD_SERVER_PORT))
    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                   ['delete_groups','help', 'dry_run'])
    except getopt.GetoptError:
        usage(1)

    for opt, val in opts:
        if opt == '--delete_groups':
            delete_groups = True
        elif opt == '--help':
            usage(1)
        elif opt == '--dry_run':
            dry_run = True

    logger.info("Syncronizing all groups")
    # Catch protocolError to avoid that url containing password is
    # written to log
    try:
        full_sync(delete_groups, dry_run)
        logger.info("All done")
    except xmlrpclib.ProtocolError, xpe:
        logger.critical("Error connecting to AD service. Giving up!: %s %s" %
                        (xpe.errcode, xpe.errmsg))

    
def usage(exitcode=0):
    print """Usage: [options]
    --delete_groups
    --dry_run
    --help
    """
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
