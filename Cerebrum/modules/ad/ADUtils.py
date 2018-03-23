# -*- coding: utf-8 -*-

# Copyright 2011-2018 University of Oslo, Norway
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
  the form: [<success flag>, <Message>] Transmitting exceptions through
  XML-RPC is a bit of a hassle, but is doable. And should be worth
  investigating at least.
"""

import time
import xmlrpclib

import cereconf

from Cerebrum.Utils import read_password
from Cerebrum.Utils import Factory


class ADUtils(object):
    """
    This class provides utility methods and an API for some commands
    accessible by the Cerebrum AD agent running on AD DC.
    """

    def __init__(self, db, logger, host, port, ad_domain_admin):
        """
        Connect to AD service
        """
        self.logger = logger
        self.db = db
        self.co = Factory.get("Constants")(self.db)
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
        msg = "Running Update-Recipient for object '%s' against Exchange"
        if self.dryrun:
            self.logger.debug("Not " + msg, ad_obj)
            return
        self.logger.info(msg, ad_obj)

        # Use self.ad_dc if it exists, otherwise try cereconf.AD_DC
        try:
            ad_dc = self.ad_dc
        except AttributeError:
            ad_dc = getattr(cereconf, "AD_DC", None)

        if ad_dc:
            self.run_cmd('run_UpdateRecipient', ad_obj, ad_dc)
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
        if self.dryrun:
            self.logger.debug("DRYRUN: Not setting attributes for %r: %r",
                              dn, changes)
            return

        if self.run_cmd('bindObject', dn):
            # Set attributes in AD
            # Check that no values in changes == None.
            # That is an error and shouldn't be sent
            for k, v in changes.iteritems():
                if v is None:
                    del changes[k]
            self.logger.info("Setting attributes for %r: %r", dn, changes)
            if changes:
                self.run_cmd('putProperties', changes)
                self.run_cmd('setObject')

    def attr_cmp(self, cb_attr, ad_attr):
        """
        Compare new (attribute calculated from Cerebrum data) and old
        ad attribute.

        @param cb_attr: attribute calculated from Cerebrum data
        @type cb_attr: unicode, list or tuple
        @param ad_attr: Attribute fetched from AD
        @type ad_attr: list || unicode || str

        @rtype: cb_attr or None
        @return: cb_attr if attributes differ. None if no difference or
        comparison cannot be made.
        """
        # Sometimes attrs from ad are put in a list
        if isinstance(ad_attr, (list, tuple)) and len(ad_attr) == 1:
            ad_attr = ad_attr[0]

        # Handle list, tuples and (unicode) strings
        if isinstance(cb_attr, (list, tuple)):
            cb_attr = list(cb_attr)
            # if cb_attr is a list, make sure ad_attr is a list
            if not isinstance(ad_attr, (list, tuple)):
                ad_attr = [ad_attr]
            cb_attr.sort()
            ad_attr.sort()

        # Now we can compare the attrs
        if all(isinstance(v, basestring) for v in (ad_attr, cb_attr)):
            # Don't care about case
            if cb_attr.lower() != ad_attr.lower():
                return cb_attr
        else:
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
            self.logger.debug3("Running cmd: %s(%r)", command, args)
            ret = cmd(*args)
        except xmlrpclib.ProtocolError as xpe:
            self.logger.critical("Error connecting to AD service: %s %s",
                                 (xpe.errcode, xpe.errmsg))
            return False,
        except xmlrpclib.Fault as msg:
            self.logger.warn("Exception from AD service: %s", msg)
            return False
        except Exception:
            self.logger.warn("Unexpected exception", exc_info=1)
            self.logger.debug("Failed to run cmd: %s(%r)", command, args)
            return False

        # ret is a list in the form [bool, msg] where the first
        # element tells if the command was successful or not
        if not ret[0]:
            self.logger.warn("Server couldn't execute %s(%r): %r",
                             (command, args, ret[1:]))
            return False
        # cmd was run successfully on the server.
        # If command is create_object and an additional sid is
        # returned we need to return sid instead of True
        if command == "createObject" and len(ret) == 3:
            return ret[2]
        else:
            self.logger.debug3("Command %s ran successfully", command)
            return True

    def move_object(self, dn, ou, obj_type="user"):
        """
        Move given object in Ad to given ou.

        @param dn: AD attribute distinguishedName
        @type dn: str
        @param ou: LDAP path to base ou for the entity type
        @type ou: str
        """
        if self.dryrun:
            self.logger.debug("DRYRUN: Not moving %s %r to %r",
                              obj_type, dn, ou)
            return

        if self.run_cmd('bindObject', dn):
            self.logger.info("Moving %s %r to %r", obj_type, dn, ou)
            self.run_cmd('moveObject', ou)

    def rename_object(self, dn, ou, cn):
        if self.dryrun:
            self.logger.info("DRYRUN: Not renaming %s to %s,%s", dn, cn, ou)
            return

        if self.run_cmd('bindObject', dn):
            self.logger.info("Renaming %s to %s,%s", dn, cn, ou)
            self.run_cmd('moveObject', ou, cn)

    def move_contact(self, dn, ou):
        if self.dryrun:
            self.logger.info("DRYRUN: Not moving contact %s", dn)
            return
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
            self.logger.debug("DRYRUN: Not creating contact %s", name)
            return

        ret = self.run_cmd("createObject", "contact", ou, name)
        if not ret:
            # Don't continue if createObject fails
            return
        self.logger.info("created contact %s", name)

        self.run_cmd("putProperties", attrs)
        self.run_cmd("setObject")
        return ret

    def get_ou(self, dn):
        """
        Extract OU part from distinguishedName
        """
        dn = dn.strip()
        i = dn.find("OU=")
        if dn and i != -1:
            return dn[i:]


class ADUserUtils(ADUtils):
    """
    User specific methods
    """

    def __init__(self, db, logger, host, port, ad_domain_admin):
        ADUtils.__init__(self, db, logger, host, port, ad_domain_admin)
        self.ac = Factory.get("Account")(self.db)
        self.pe = Factory.get("Person")(self.db)

    def move_user(self, dn, ou):
        self.move_object(dn, ou, obj_type="user")

    def deactivate_user(self, ad_user):
        """
        Delete or deactivate user in Cerebrum-controlled OU.

        @param ad_user: AD attributes
        @type dn: dict
        """
        dn = ad_user["distinguishedName"]
        # Delete or disable?
        if self.delete_users:
            self.delete_user(dn)
        else:
            # Check if user is already disabled
            if not ad_user['ACCOUNTDISABLE']:
                self.disable_user(dn)
            # Disabled users lives in AD_LOST_AND_FOUND OU
            if self.get_ou(dn) != self.get_deleted_ou():
                self.move_user(dn, self.get_deleted_ou())

    def delete_user(self, dn):
        """
        Delete user object in AD.

        @param dn: AD attribute distinguishedName
        @type dn: str
        """
        if self.dryrun:
            self.logger.debug("DRYRUN: Not deleting user %s", dn)
            return

        if self.run_cmd('bindObject', dn):
            self.logger.info("Deleting user %s", dn)
            self.run_cmd('deleteObject')

    def disable_user(self, dn):
        """
        Disable user in AD.

        @param dn: AD attribute distinguishedName
        @type dn: str
        """
        if self.dryrun:
            self.logger.debug("DRYRUN: Not disabling user %s", dn)
            return
        self.logger.info("Disabling user %s", dn)
        self.commit_changes(dn, ACCOUNTDISABLE=True)

    def create_ad_account(self, attrs, ou, create_homedir=False):
        """
        Create AD account, set password and default properties.

        @param attrs: AD attrs to be set for the account
        @type attrs: dict
        @param ou: LDAP path to base ou for the entity type
        @type ou: str
        """
        uname = attrs.pop("sAMAccountName")
        if self.dryrun:
            self.logger.debug("DRYRUN: Not creating user %s", uname)
            return

        sid = self.run_cmd("createObject", "User", ou, uname)
        if not sid:
            # Don't continue if createObject fails
            return
        self.logger.info("created user %s with sid %s", uname, sid)

        # Set password
        self.run_cmd("setPassword", self.ac.make_passwd(uname))

        # Set properties. First remove any properties that cannot be set like
        # this
        for a in ("distinguishedName", "cn"):
            if a in attrs:
                del attrs[a]
        # Don't send attrs with value == None
        for k, v in attrs.items():
            if v is None:
                del attrs[k]
        if self.run_cmd("putProperties", attrs) and self.run_cmd("setObject"):
            # TBD: A bool here to decide if createDir should be performed or
            #      not?
            # Create accountDir for new account if attributes where set.
            # Give AD time to take a breath before creating homeDir
            if create_homedir:
                time.sleep(5)
                self.run_cmd("createDir")
        return sid


class ADGroupUtils(ADUtils):
    """
    Group specific methods
    """

    def __init__(self, db, logger, host, port, ad_domain_admin):
        ADUtils.__init__(self, db, logger, host, port, ad_domain_admin)
        self.group = Factory.get("Group")(self.db)

    def commit_changes(self, dn, **changes):
        """
        Set attributes for account

        @param dn: AD attribute distinguishedName
        @type dn: str
        @param changes: attributes that should be changed in AD
        @type changes: dict (keyword args)
        """
        if not self.dryrun and self.run_cmd('bindObject', dn):
            self.logger.info("Setting attributes for %s: %r", dn, changes)
            # Set attributes in AD
            self.run_cmd('putGroupProperties', changes)
            self.run_cmd('setObject')

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
            self.logger.debug("DRYRUN: Not creating group %s", gname)
            return

        # Create group object
        sid = self.run_cmd("createObject", "Group", ou, gname)
        if not sid:
            # Don't continue if createObject fails
            return
        self.logger.info("created group %s with sid %s", gname, sid)
        # # Set other properties
        if "distinguishedName" in attrs:
            del attrs["distinguishedName"]
        self.run_cmd("putGroupProperties", attrs)
        self.run_cmd("setObject")
        # createObject succeded, return sid
        return sid

    def delete_group(self, dn):
        """
        Delete group object in AD.

        @param dn: AD attribute distinguishedName
        @type dn: str
        """
        if self.dryrun:
            self.logger.debug("DRYRUN: Not deleting %s", dn)
            return

        if self.run_cmd('bindObject', dn):
            self.logger.info("Deleting group %s", dn)
            self.run_cmd('deleteObject')

    def sync_members(self, dn, members):
        """
        Sync members for a group to AD.

        @param dn: AD attribute distinguishedName
        @type dn: str
        @param members: List of account and group names
        @type members: list

        """
        if self.dryrun:
            self.logger.debug("DRYRUN: Not syncing members for %s", dn)
            return
        # We must bind to object before calling syncMembers
        if dn and self.run_cmd('bindObject', dn):
            if self.run_cmd("syncMembers", members, False, False):
                self.logger.info("Synced members for group %s", dn)
