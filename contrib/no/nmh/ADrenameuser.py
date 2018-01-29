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
import getopt, sys
import cerebrum_path
import cereconf
import re

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum.modules import ADutilMixIn

db = Factory.get("Database")()
account = Factory.get("Account")(db)
constants = Factory.get("Constants")(db)
person = Factory.get("Person")(db)
logger = Factory.get_logger("console")

class ADrenameHack(ADutilMixIn.ADuserUtil):

    def renameObj(self, old_name, new_name):		
        dry_run = False
        prop = {}
        move_to = cereconf.AD_LDAP

        # use empty dict in order to clear the user attribute
        # does not actually do anything as the attributes are not
        # removed for AD
        #
        userAC = {}
        userAttributes = ("sAMAccountName", "userPrincipalName",
                          "homeDirectory")
        self.run_cmd('setUserAttributes', dry_run, userAttributes , userAC)
        logger.info("Cleared sAMAccountName, userPrincipalName and homeDirectory for account %s", old_uname)

        dncn = self.run_cmd('findObject', old_name)
        logger.info("Found object %s", dncn)

        if dncn:
            ret = self.run_cmd('bindObject', dncn)
            logger.info("Bound object %s", dncn)

            if not ret:
                logger.warn("Could not bind object %s.", dncn)

            # Rename home directory
            ret = self.run_cmd('getProperties', dry_run)
            logger.debug("Properties: %s", ret.keys())
            if ret['homeDirectory']:
                oldHomeDir = ret['homeDirectory']
                newHomeDir = re.sub(old_name, new_name, oldHomeDir)
                ret = self.run_cmd('moveObject', dry_run, move_to, 'cn=%s' % new_name)
                if ret[0]:
                    logger.info("Attemping to rename homedir for %s", old_name)
                    homedir = self.run_cmd('renameHomeDir', dry_run, newHomeDir)
                if homedir:
                    prop['sAMAccountName'] = new_name
                    prop['userPrincipalName'] = new_name
                    prop['homeDirectory'] = newHomeDir
                    logger.debug("Trying to set new account attributes (sAMAN, uPN, hD)")
                    properties = self.run_cmd('putProperties', dry_run, prop)
                    if properties:
                        ret = self.run_cmd('setObject', dry_run)
                    if ret:
                        logger.info("Successfully updated object %s (-> %s)" % (old_name, new_name))
                else:
                    logger.warn("Could not create homeDir for %s (-> %s)" % (old_name, new_name))
        else:
            logger.warn("Account %s not found in AD", old_name)


def get_old_and_new_unames():
    ret = {}
    for row in person.list_external_ids(source_system=None,
                                        id_type=constants.externalid_uname):
        person.clear()
        person.find(row['entity_id'])
        old_uname = row['external_id']
        acc_id = person.get_primary_account()
        if acc_id != None:
            account.clear()
            account.find(acc_id)
            new_uname = account.account_name
        else:
            logger.debug("No new uname for %s", old_uname)
            continue
        ret[old_uname] = new_uname
    return ret


def main():

    passwd = db._read_password(cereconf.AD_SERVER_HOST,
                               cereconf.AD_SERVER_UNAME)
    adrename = ADrenameHack(db, constants,
                            url= "https://%s@%s:%i" % (passwd,
                                                       cereconf.AD_SERVER_HOST,
                                                       cereconf.AD_SERVER_PORT ))

    dict = get_old_and_new_unames()
    logger.info("Will attempt to rename %d accounts.", len(dict))

    for oldname in dict:
        if oldname != dict[oldname]:
            logger.debug("Renaming %s (-> %s)" % (oldname, dict[oldname])
            adrename.renameObj(oldname, dict[oldname])


if __name__ == '__main__':
    main()
