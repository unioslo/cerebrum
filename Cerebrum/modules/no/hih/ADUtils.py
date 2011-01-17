#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2011 University of Oslo, Norway
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

"""
This module contains classes and methods that handle communication and
interaction with the AD service. The idea is to let this module be a
layer between the AD service and the different AD syncs. 

TODO:

* Let the module reside here for the moment. It should be general
  enough to be in Cerebrum/modules but there's an old and probably
  deprecated module there with the name ADutils.py. Need to find out
  if I can remove that module first. (or rename this one)

* Command API is flawed. The run_cmd method and the other methods in
  ADutilMixIn.py are quite bad, but then again the AD service's API
  is also quite stupid. So where to begin to clean up?

  At the moment we just adapt to the existing API, but there are a
  couple of thing's I'd like to improve in the future:

   * the AD service should use exceptions instead of returning a
     list on the form: [<succes flag>, <Message>]
     Transmitting exceptions through XML-RPC is a bit of a hassle,
     but is doable. And should be worth investigating at least.

   * Split to different classes for User, Group, etc?

"""


import time
import xmlrpclib
import cerebrum_path
import cereconf
from Cerebrum.Utils import read_password
from Cerebrum.modules import ADutilMixIn


class ADUtils(ADutilMixIn.ADutil):
    """
    HiH extension of ADutilMixIn.ADutil
    """

    def __init__(self, logger, host, port, ad_domain_admin):
        """
        Connect to AD service
        """
        self.logger = logger
        # Create connection to AD agent
        password = read_password(ad_domain_admin, host)
        url = "https://%s:%s@%s:%s" % (ad_domain_admin, password, host, port)
        self.server = xmlrpclib.Server(url)


    # def run_cmd(self, command, *args):
    #     """
    #     Chech if command is a AD service method. Run command unless dryrun is set
    #     """
    #     if self.dryrun:
    #         self.logger.debug('server.%s%s' % (command, args))
    #         return
    #     try:
    #         cmd = getattr(self.server, command)
    #         return cmd(args)
    #     except xmlrpclib.ProtocolError, xpe:
    #         self.logger.critical("Error connecting to AD service. Giving up!: %s %s" %
    #                              (xpe.errcode, xpe.errmsg))
    #     except Exception, e:
    #         self.logger.warn("Unexpected exception", exc_info=1)
    #         self.logger.debug("Command: %s%s" % (command, args))
            

    def move_user(self, dn, ou):
        self.logger.info("Moving user %s to %s" % (dn, ou))
        changes = {"distinguishedName": dn,
                   "OU": ou,
                   "type": "move_object"}
        self.perform_changes(changes, self.dryrun)


    def deactivate_user(self, dn):
        """
        Delete or deactivate user in Cerebrum-controlled OU.
        """
        # Delete or move?
        if self.delete_users:
            self.delete_user(dn)
        else:
            # disable and move to AD_LOST_AND_FOUND OU
            self.disable_user(dn)
            self.move_user(dn, cereconf.AD_LOST_AND_FOUND)


    def delete_user(self, dn):
        """
        Delete user object in AD.
        """
        self.logger.info("Deleting user %s" % dn)
        changes = {"distinguishedName": dn,
                   "type": "delete_object"}
        self.perform_changes(changes, self.dryrun)


    def disable_user(self, dn):
        """
        Disable user in AD.
        """
        self.logger.info("Disabling user %s" % dn)
        changes = {"distinguishedName": dn,
                   "ACCOUNTDISABLE": True,
                   "type": "alter_object"}
        self.perform_changes(changes, self.dryrun)


    def create_ad_account(self, attrs, ou):
        """
        Create AD account, set password and default properties. 
        """
        # This will be a bit ugly since we depend on old code...
        uname = attrs.pop("sAMAccountName")
        ret = self.run_cmd("createObject", self.dryrun, "User", ou, uname)
        if not ret[0]:
            self.logger.error("create user %s failed: %r", uname, ret)
            return
        elif not self.dryrun:
            self.logger.info("created user %s" % ret)

        # Set password
        pw = unicode(self.ac.make_passwd(uname), "iso-8859-1")
        ret = self.run_cmd("setPassword", self.dryrun, pw)
        if not ret[0]:
            self.logger.warning("setPassword on %s failed: %s", uname, ret)
            return
        # Set other properties
        if attrs.has_key("distinguishedName"):
            del attrs["distinguishedName"]
        ret = self.run_cmd("putProperties", self.dryrun, attrs)
        if not ret[0]:
            self.logger.warning("putproperties on %s failed: %r", uname, ret)
        ret = self.run_cmd("setObject", self.dryrun)
        if not ret[0]:
            self.logger.warning("setObject on %s failed: %r", uname, ret)


    def update_Exchange(self, ad_objs):
        """
        Telling the AD-service to start the Windows Power Shell command
        Update-Recipient on object in order to prep them for Exchange.
        
        @param ad_objs : objects to run command on
        @type  ad_objs: list
        @param dry_run : Flag
        """
        if not ad_objs:
            return
        
        self.logger.debug("Sleeping for 5 seconds to give ad-ldap time to update") 
        time.sleep(5)
        for obj in ad_objs:
            self.logger.info("Running Update-Recipient for object '%s' "
                             "against Exchange" % obj)
            if cereconf.AD_DC:
                ret = self.run_cmd('run_UpdateRecipient', self.dryrun, obj,
                                   cereconf.AD_DC)
            else:
                ret = self.run_cmd('run_UpdateRecipient', self.dryrun, obj)
            if not ret[0]:
                self.logger.error("run_UpdateRecipient on %s failed: %r", 
                                    obj, ret)
        self.logger.info("Ran Update-Recipient against Exchange for %i objects", 
                         len(ad_objs))
        

    def commit_changes(self, changes, dn, op_type="alter_object"):
        changes["distinguishedName"] = dn
        changes["type"] = op_type
        self.perform_changes(changes, self.dryrun)
        


class ADGroupUtils(ADUtils):
    def alter_object(self, chg, dry_run):
        """
        Binds to AD group objects and updates given attributes

        @param chg: group_name -> group info mapping
        @type chg: dict
        @param dry_run: Flag
        """
        distName = chg['distinguishedName']                 
        #Already bound
        del chg['type']             
        del chg['distinguishedName']

        #ret = self.run_cmd('putGroupProperties', dry_run, chg)
        #run_cmd in ADutilMixIn.py not written for group updates
        if not dry_run:
            ret = self.server.putGroupProperties(chg)
        else:
            ret = (True, 'putGroupProperties')
        if not ret[0]:
            self.logger.warning("putGroupProperties on %s failed: %r",
                                distName, ret)
        else:
            ret = self.run_cmd('setObject', dry_run)
            if not ret[0]:
                self.logger.warning("setObject on %s failed: %r",
                                    distName, ret)         

    def create_ad_group(self, attrs, ou):
        """
        Create AD group.
        """
        gname = attrs.pop("name")
        ret = self.run_cmd("createObject", self.dryrun, "Group", ou, gname)
        if ret[0]:
            if not self.dryrun:
                self.logger.info("created group %s" % ret)
        else:
            self.logger.error("create group %s failed: %r", gname, ret)


    def delete_group(self, dn):
        """
        Delete group object in AD.
        """
        self.logger.info("Deleting group %s" % dn)
        changes = {"distinguishedName": dn,
                   "type": "delete_object"}
        self.perform_changes(changes, self.dryrun)


    def sync_members(self, dn, members):
        # Send dn instead of doing findObject for each group. Saves
        # quite some time
        #dn = self.server.findObject(gname)
        if not dn:
            self.logger.debug("unknown group: %s", dn)
        elif self.dryrun:
            self.logger.debug("Dryrun: don't sync members for group %s" %
                              dn)
        else:
            self.server.bindObject(dn)
            res = self.server.syncMembers(members, False, False)
            if not res[0]:
                self.logger.warning("syncMembers %s failed for:%r" %
                                  (dn, res[1:]))
            else:
                self.logger.info("Synced members for group %s" % dn)
    

