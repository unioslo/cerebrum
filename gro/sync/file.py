# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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

    def begin(self, incremental=False):
        self.incr=incremental
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
        os.rename(self.tmpname, self.filename)

    def abort(self):
        self.f.close()
        os.unlink(self.tmpname)

    def add(self, obj):
        if self.incr:
            self.records[obj.name]=self.format(obj)
        else:
            self.f.write(self.format(obj))
            
    def update(self, obj):
        if not self.incr: 
            raise "not supported in this mode of operation"
        self.records[obj.name]=self.format(obj)

    def delete(self, obj):
        if not self.incr: 
            raise "not supported in this mode of operation"
        del self.records[obj.name]

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

# classic: name:crypt:uid:gid:gcos:dir:shell
# shadow:  name:crypt:lastchg:min:max:warn:inactive:expire
# bsd:     name:crypt:uid:gid:class:change:expire:gcos:dir:shell

class PasswdFile(CLFileBack):
    filename="/etc/ceresync/passwd"
    def format(self, account):
        return "%s:%s:%d:%d:%s:%s:%s\n" % (
            account.name, "x", account.uid, account.gid,
            account.fullname, account.dir, account.shell )


class GroupFile(CLFileBack):
    filename="/etc/ceresync/group"
    def format(self, group):
        return "%s:*:%d:%s\n" % (
            group.name, group.gid, ",".join(group.members) )


class ShadowFile(CLFileBack):
    filename="/etc/ceresync/shadow"
    def format(self, account):
        return "%s:%s:::::::" % ( account.name, account.cryptpasswd )

class AliasFile(CLFileBack):
    filename="/etc/ceresync/aliases"
    def format(self, addr):
        if addr.primary:
            to=addr.user
            mod="<>"
        else:
            to=addr.primary
            mod=">>"
        return "%s: %s %s" % ( addr.name, mod, to)

# arch-tag: 15c0dab6-50e3-4093-ba64-5be1b5789d90
