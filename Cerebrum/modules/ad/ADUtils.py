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

* the AD service should use exceptions instead of returning a list on
  the form: [<succes flag>, <Message>] Transmitting exceptions through
  XML-RPC is a bit of a hassle, but is doable. And should be worth
  investigating at least.
"""


import xmlrpclib
import cerebrum_path
import cereconf
from Cerebrum.Utils import read_password


class ADUtils(object):
    """
    This class provides utility methods and an API for some commands
    accessible by the Cerebrum AD agent running on AD DC.
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


    def update_Exchange(self, ad_obj):
        """
        Telling the AD-service to start the Windows Power Shell command
        Update-Recipient on object in order to prep them for Exchange.
        
        @param ad_objs : object to run command on
        @type  ad_objs: str
        """
        self.logger.info("Running Update-Recipient for object '%s' "
                         "against Exchange" % ad_obj)
        if cereconf.AD_DC:
            self.run_cmd('run_UpdateRecipient', ad_obj, cereconf.AD_DC)
        else:
            self.run_cmd('run_UpdateRecipient', ad_obj)
        

    def commit_changes(self, dn, **changes):
        """
        Set attributes for account

        @param dn: AD attribute distinguishedName 
        @type dn: str
        @param changes: attributes that should be changed in AD
        @type changes: dict (keyword args)
        """
        if not self.dryrun and self.run_cmd('bindObject', dn):
            self.logger.info("Setting attributes for %s: %s" % (dn, changes))
            # Set attributes in AD
            self.run_cmd('putProperties', changes)
            self.run_cmd('setObject')


    def attr_cmp(self, cb_attr, ad_attr):
        """
        Compare new (attribute calculated from Cerebrum data) and old
        ad attribute. 

        @param cb_attr: attribute calculated from Cerebrum data
        @type cb_attr: unicode 
        @param ad_attr: Attribute fetched from AD
        @type ad_attr: list || unicode || str
        
        @rtype: str or None
        @return: cb_attr if attributes differ. None if no difference or
        comparison cannot be made.
        """
        if isinstance(ad_attr, list):
            if len(ad_attr) != 1:
                self.logger.warn("Attr %s from ad is a list. Cannot compare" %
                                 str(ad_attr))
                return
            else:
                ad_attr = ad_attr[0]
        if cb_attr != ad_attr:
            return cb_attr


    def run_cmd(self, command, *args):
        """
        Run the given command with arguments on th AD service

        @param command: command to run via rpc on AD server
        @type command: str
        @param args: args to command
        @type args: tuple 
        """
        cmd = getattr(self.server, command)
        try:
            ret = cmd(*args)
        except xmlrpclib.ProtocolError, xpe:
            self.logger.critical("Error connecting to AD service: %s %s" %
                                 (xpe.errcode, xpe.errmsg))
            return False
        except xmlrpclib.Fault, msg:
            self.logger.warn("Exception from AD service:", msg)
            return False
        # ret is a list in the form [bool, msg] where the first
        # element tells if the command was succesful or not
        if not ret[0]:
            self.logger.warn("Server couldn't execute %s(%s): %s" %
                             (command, args, ret[1]))
        return ret[0]


    def move_object(self, dn, ou, obj_type="user"):
        """
        Move given object in Ad to given ou.

        @param dn: AD attribute distinguishedName 
        @type dn: str
        @param ou: LDAP path to base ou for the entity type
        @type ou: str        
        """
        if self.dryrun:
            self.logger.debug("DRYRUN: Not moving %s %s to %s" % (
                obj_type, dn, ou))
            return

        if self.run_cmd('bindObject', dn):
            self.logger.info("Moving %s %s to %s" % (obj_type, dn, ou))
            self.run_cmd('moveObject', ou)


    def move_contact(self, dn, ou):
        self.move_object(dn, ou, obj_type="contact")
        

    # TBD: correct placement?
    def create_ad_contact(self, attrs, ou):
        """
        Create AD account, set password and default properties. 

        @param attrs: AD attrs to be set for the account
        @type attrs: dict        
        @param ou: LDAP path to base ou for the entity type
        @type ou: str        
        """
        name = attrs.pop("sAMAccountName")
        if self.dryrun:
            self.logger.debug("DRYRUN: Not creating contact %s" % name)
            return
        
        ret = self.run_cmd("createObject", "contact", ou, name)
        if not ret[0]:
            # Don't continue if createObject fails
            return
        self.logger.info("created contact %s" % name)

        self.run_cmd("putProperties", attrs)
        self.run_cmd("setObject")
        return ret[0]


class ADUserUtils(ADUtils):
    """
    User specific methods
    """

    def move_user(self, dn, ou):
        self.move_object(dn, ou, obj_type="user")


    def deactivate_user(self, dn):
        """
        Delete or deactivate user in Cerebrum-controlled OU.

        @param dn: AD attribute distinguishedName 
        @type dn: str
        """
        # Delete or disable?
        if self.delete_users:
            self.delete_user(dn)
        else:
            self.disable_user(dn)
            # Disabled users lives in AD_LOST_AND_FOUND OU
            self.move_user(dn, cereconf.AD_LOST_AND_FOUND)


    def delete_user(self, dn):
        """
        Delete user object in AD.

        @param dn: AD attribute distinguishedName 
        @type dn: str
        """
        if self.dryrun:
            self.logger.debug("DRYRUN: Not deleting user %s" % dn)
            return
        
        if self.run_cmd('bindObject', dn):
            self.logger.info("Deleting user %s" % dn)
            self.run_cmd('deleteObject')


    def disable_user(self, dn):
        """
        Disable user in AD.

        @param dn: AD attribute distinguishedName 
        @type dn: str
        """
        self.logger.info("Disabling user %s" % dn)
        self.commit_changes(dn, ACCOUNTDISABLE=True)
         

    def create_ad_account(self, attrs, ou):
        """
        Create AD account, set password and default properties. 

        @param attrs: AD attrs to be set for the account
        @type attrs: dict        
        @param ou: LDAP path to base ou for the entity type
        @type ou: str        
        """
        uname = attrs.pop("sAMAccountName")
        if self.dryrun:
            self.logger.debug("DRYRUN: Not creating user %s" % uname)
            return
        
        ret = self.run_cmd("createObject", "User", ou, uname)
        if not ret[0]:
            # Don't continue if createObject fails
            return
        self.logger.info("created user %s" % uname)

        # Set password
        pw = unicode(self.ac.make_passwd(uname), cereconf.ENCODING)
        self.run_cmd("setPassword", pw)
        # Set other properties
        if attrs.has_key("distinguishedName"):
            del attrs["distinguishedName"]
        self.run_cmd("putProperties", attrs)
        self.run_cmd("setObject")
        # createObject succeded, return sid
        return ret[2]


class ADGroupUtils(ADUtils):
    """
    Group specific methods
    """
    
    def create_ad_group(self, attrs, ou):
        """
        Create AD group.

        @param attrs: AD attrs to be set for the account
        @type attrs: dict        
        @param ou: LDAP path to base ou for the entity type
        @type ou: str        
        """
        gname = attrs.pop("name")
        if self.dryrun:
            self.logger.debug("DRYRUN: Not creating group %s" % gname)

        if self.run_cmd("createObject", "Group", ou, gname):
            self.logger.info("created group %s" % gname)


    def delete_group(self, dn):
        """
        Delete group object in AD.

        @param dn: AD attribute distinguishedName 
        @type dn: str
        """
        if self.dryrun:
            self.logger.debug("DRYRUN: Not deleting %s" % dn)
            return

        if self.run_cmd('bindObject', dn):
            self.logger.info("Deleting group %s" % dn)
            self.run_cmd('deleteObject')


    def sync_members(self, dn, members):
        """
        Sync members for a group to AD.

        @param dn: AD attribute distinguishedName 
        @type dn: str
        @param members: List of account and group names
        @type members: list
        
        """
        # We must bind to object before calling syncMembers
        if not self.dryrun and self.run_cmd('bindObject', dn):
            if self.run_cmd("syncMembers", members, False, False):
                self.logger.info("Synced members for group %s" % dn)


