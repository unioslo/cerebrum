# -*- coding: iso-8859-1 -*-

# Copyright: See COPYING

import re
import string
import sys
import time
import sets
import random

import cyruslib
import cyrusconf

class CyrusConnectError(Exception):
    pass

class Account:
    """
    Wrapper-class for talking to a Cyrus-backend. 
    Initiate connection with self.begin() and close
    connection with self.close()

    objects as argument for add,update,delete are
    structs or plain old python objects - both with
    the attribute 'name' and possibly the attribute
    'quota'

    All configuration is stored in cyrusconf.py
    """

    def __init__(self,verbose=True):
        self.verbose=verbose

    def begin(self,incr=False):
        """
        Initiation-method. Must be called first after __init__()
        and before add(args),update(args) etc
        """
        self.incr = incr
        if not self.incr:
            self._in_sync = sets.Set() # placeholder for synced objects
        self.group = cyrusconf.default_group
        self.default_quota = cyrusconf.default_quota 
        self.default_acl = cyrusconf.default_acl 

        self.user_quota = cyrusconf.user_quota
        self.backends = cyrusconf.backends
        self.partitions = cyrusconf.partitions
        self._conns = {}
        for auth in self.backends:
            # Fetch an authenticated imap-object
            my_auth = self.connect(hostname=auth)
            # Fetch list of users from each backend
            users = my_auth.lm().get(cyrusconf.default_group)
            # Store auth-object and userlist
            self._conns[auth] = {'auth': my_auth, 'users': users} 

    def _get_partition(self):
        # TBD: add support for weighing the partitions according to the weight-key
        #      in the cyrusconf.partitions-dict
        items = self.partitions.keys()
        return random.choice(items)

    def _exists(self,username):
        backends = self._conns.keys()
        if len(backends) < 1:
            raise CyrusConnectError
        else:
            for backend in self._conns.keys():
                users = self._conns[backend].get("users")
                if username in users: 
                    return (True,backend)
                else:
                    return (False,'')

    def connect(self,hostname=None,username=None,as_admin=True):
        conn = cyruslib.CYRUS(host=hostname)
        if self.verbose:
            conn.verbose = True
        conn.login(cyrusconf.binduser,cyrusconf.bindpw)
        return conn

    def close(self):
        """
        Close all connections to all Cyrus-backends
        """
        if not self.incr :
            self.syncronize()
        for conn in self._conns.keys():
            co = self._conns[conn].get("auth")
            co.auth = False # Hehehe.. it actually works

    def syncronize(self):
        """
        Remove/disable mailboxes that shouldn't be here anymoe
        """
        if not self.incr:
            cur_users = sets.Set()
            to_be_deleted = sets.Set()
            for backend in self._conns.keys():
                cur_users.union_update(self._conns[backend].get("users"))
            # Get a list from cur_users not in _in_sync
            for user in cur_users:
                if user not in self._in_sync:
                    to_be_deleted.add(user)
            for user in to_be_deleted:
                self.delete(_Dummy(user))
        else:
            return

    def abort(self):
        """
        Close ongoing operations and disconnect from server
        """
        print "Not applicable for this backend"
        return

    def _get_quota(self,obj):
        """Returns the quota for this user.
        Default quota is stored in cyrusconf, 
        named users can be overriden in cyrusconf as well
        or be set in the obj-struct as attribute 'quota'.
        """
        if obj.name in self.user_quota.keys():
            quota = self.user_quota[obj.name]
        elif hasattr(obj,"quota"):
            quota = obj.quota
        else:
            quota = self.default_quota
        return quota

    def add(self, obj, update_if_exists=True):
        """
        Add a user to Cyrus-backend. Duh!
        """
        exists,host = self._exists(obj.name)
        if exists and update_if_exists:
            self.update(obj)
        else:
            part = self._get_partition()
            host = self.partitions[part].get("host")
            co = self._conns[host].get("auth")
            try:
                op = co.cm(group=self.group,user=obj.name,partition=part)
                op2 = co.sq(group=self.group,user=obj.name,limit=self._get_quota(obj))
                mailboxes = cyrusconf.default_mailboxes
                # Each user should have a default set of Mailboxes (e.g. sent, draft etc)
                for mailbox in mailboxes:
                    mailbox = obj.name + co.sep + mailbox
                    opm = co.cm(group=self.group,user=mailbox,partition=part)
                    opm2 = co.sq(group=self.group,user=mailbox,limit=self._get_quota(obj))
            except Exception,e:
                print "Exception caught while adding user %s. Reason: %s" % (obj.name,str(e))
                return False
            # Add user to the list of user on this partition
            self._conns[host].get("users").append(obj.name)
            if not self.incr:
                self._in_sync.union_update(obj.name)
            return True

    def update(self,obj):
        """
        Since passwords are handled by Kerberos, only thing
        update will do, is to set ACL and quota
        """
        exists,backend = self._exists(obj.name)
        if exists:
            co = self._conns[backend].get("auth")
            try:
                # Update quota
                co.sq(self.group,obj.name,self._get_quota(obj))
                # Update ACL
                co.sam(self.group,obj.name,'cyrproxy',cyrusconf.default_acl)
                if not self.incr:
                    self._in_sync.union_update(obj.name)
                return True
            except Exception,e:
                print "Error occured while update quota and ACL for %s. Reason: %s" % (obj.name,str(e))
                return False

    def delete(self,obj=None,really_delete=False):
        """
        Deletes a mailbox owned by <obj>.name in group self.group
        """
        exists,host = self._exists(obj.name)
        if exists:
            co = self._conns[host].get("auth")
            co.sam(self.group,obj.name,co.admin,co.admin_acl) # Needed to delete a mailbox
            mailbox_pattern = cyrusconf.default_group + co.sep + obj.name + co.sep + '*'
            status, mailboxes = co.m.list(pattern=mailbox_pattern)
            if status == 'OK':

                def get_folder(folder):
                    folder = folder.split()
                    folder = folder[len(folder)-1]
                    folder = folder.strip('"')
                    folder = folder.split(co.sep)
                    tmp = ""
                    for i in range(len(folder)):
                        if i>0:
                            if i==1:
                                tmp += folder[i]
                            else:
                                tmp += co.sep+folder[i]
                    result = tmp
                    return result

                for folderinfo in mailboxes:
                    folder = get_folder(folderinfo)
                    co.sam(self.group,folder,co.admin,co.admin_acl)
            
            if really_delete:
                try:
                    co.dm(self.group,obj.name)
                    # Remove user from userlist for $backend
                    try:
                        self._conns[host].get("users").remove(obj.name)
                        if not self.incr:
                            self._in_sync.remove(obj.name)
                    except AttributeError:
                        pass
                except Exception,e:
                    print "Exception caught while removing %s. Reason: %s" % (obj.name,str(e))
                    return False
            return True
