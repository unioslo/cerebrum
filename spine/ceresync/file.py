# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

"""File based backends for ceresync. (like /etc/passwd)"""

import os
import errors


# Need to handle exceptions better?
class MultiHandler:
    def __init__(self, *handlers):
        self.handlers=handlers

    def begin(self):
        for h in self.handlers: 
            h.begin()
            
    def close(self):
       for h in self.handlers: 
           h.close()
           
    def add(self, obj):
        for h in self.handlers: 
            h.add(obj)

    def delete(self, obj):
        for h in self.handlers: 
            h.delete(obj)

    def update(self, obj):
        for h in self.handlers: 
            h.update(obj)

    def abort(self):
        for h in self.handlers:
            try:
                h.abort()
            except:
                pass #This is abort, so it's ok.

class FileBack:
    def __init__(self, filename=None, mode=0644):
        if filename: 
            self.filename=filename
        self.mode=mode
        self.incr = None
        self.tempname = None
        self.f = None

    def begin(self, incr=False):
        """Begin operation on file. 
        If incr is true, updates will be incremental, ie. the
        original content will be preserved, and can be updated by
        update() and delete()."""
        self.incr=incr
        if self.incr: 
            self.readin(self.filename)
        # use tempfile or something    
        self.tmpname=self.filename + ".tmp." + str(os.getpid())
        self.f=open(self.tmpname, 'w')
        os.chmod(self.tmpname, self.mode)

    def close(self):
        if self.incr: 
            self.writeout()
        self.f.flush()
        os.fsync(self.f.fileno())
        self.f.close()
        # Move the old file to .old, which we delete first in case it
        # exists.
        old = self.filename + ".old"
        try:
            os.remove(old)
        except OSError:    
            pass
        try:
            os.rename(self.filename, old)
        except OSError:
            old = None
        # Note that on win32 os.rename won't work if self.filename
        # exists.
        try:
            os.rename(self.tmpname, self.filename)
        except OSError:
            if old:
                # Roll back to the old file, since we renamed it
                os.rename(old, self.filename)    

    def abort(self):
        self.f.close()
        os.remove(self.tmpname)

    def add(self, obj):
        if self.incr:
            self.records[obj.name]=self.format(obj)
        else:
            self.f.write(self.format(obj))
            
    def update(self, obj):
        if not self.incr: 
            raise errors.WrongModeError, "update"
        self.records[obj.name]=self.format(obj)

    def delete(self, obj):
        if not self.incr: 
            raise errors.WrongModeError, "delete"
        del self.records[obj.name]
    
    def format(self, obj):
        """Returns the formatted string to be added to the file based on
        the given object. Must include any ending linefeeds."""    
        raise NotImplementedError, "format"

class CLFileBack(FileBack):
    """Line-based files, colon separated, primary key in first column"""
    def readin(self, srcfile):
        self.records={}
        for l in open(srcfile):
            key=l.split(":",1)[0]
            self.records[key]=l
            
    def writeout(self):
        for l in self.records.values():
            self.f.write(l)

# classic: name:crypt:uid:gid:gcos:home:shell
# shadow:  name:crypt:lastchg:min:max:warn:inactive:expire
# bsd:     name:crypt:uid:gid:class:change:expire:gcos:home:shell

class PasswdFile(CLFileBack):
    filename="/etc/ceresync/passwd"
    def format(self, account):
        if account.posix_uid is None:
            raise errors.NotPosixError, account.name
        return "%s:%s:%s:%s:%s:%s:%s\n" % (
            account.name, "x", account.posix_uid, account.primary_group.posix_gid,
            account.gecos, account.home, account.shell)


class GroupFile(CLFileBack):
    filename="/etc/ceresync/group"
    def format(self, group):
        if group.posix_gid is None:
            raise errors.NotPosixError, group.name
        return "%s:*:%d:%s\n" % (
            group.name, group.posix_gid, ",".join(group.membernames))


class ShadowFile(CLFileBack):
    filename="/etc/ceresync/shadow"
    def format(self, account):
        if account.posix_uid is None:
            raise errors.NotPosixError, account.name
        return "%s:%s:::::::\n" % ( account.name, account.password )

class AliasFile(CLFileBack):
    filename="/etc/ceresync/aliases"
    def format(self, addr):
        if addr.primary:
            to=addr.user
            mod="<>"
        else:
            to=addr.primary
            mod=">>"
        return "%s: %s %s\n" % ( addr.name, mod, to)

class SambaFile(CLFileBack):
    """An entry in a samba passwordfile lookes like this:
    <username>:<uid>:<lanman-hash>:<nt-hash>:<Long Name>:<homedir>:<user shell>"""
    filename="/etc/cerecync/smbpasswd"
    def format(self,account):
        if account.uid is None:
            raise errors.NotPosixError, account.name
        return "%s:%s:%s:%s:%s:%s:%s\n" % ( account.name,account.uid,account.lmhash,\
            account.nthash,account.fullname,account.homedir,account.shell)


# When using the file backend the user will want to save the id of the
# last recorded update to a file. (But will the users of other backends
# like LDAP and AD also want to use a file?)
class LastUpdate:
    filename="/etc/ceresync/lastupdate"
    def __init__(self, filename=None):
        if filename:
            self.filename=filename
    def get(self):
        return int(open(self.filename).read().strip())
    def set(self, id):
        open(self.filename,'w').write("%d\n" % id)
    def exists(self):
        return os.path.exists(self.filename)


# arch-tag: 15c0dab6-50e3-4093-ba64-5be1b5789d90
