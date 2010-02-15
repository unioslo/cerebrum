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
from ceresync import errors
from ceresync import config
import re

# Need to handle exceptions better?
class MultiHandler:
    def __init__(self, *handlers):
        self.handlers=handlers

    def begin(self, *args, **kwargs):
        for h in self.handlers:
            h.begin(*args, **kwargs)
            
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

class FileBack(object):
    def __init__(self, filename=None, mode=0644):
        if filename: 
            self.filename=filename
        self.mode=mode
        self.incr = None
        self.tempname = None
        self.f = None
        self.unicode = False
        self.encoding="iso-8859-1"  # FIXME: Read from config

    def begin(self, incr=False, unicode=False):
        """Begin operation on file. 
        If incr is true, updates will be incremental, ie. the
        original content will be preserved, and can be updated by
        update() and delete()."""
        self.incr=incr
        self.unicode=unicode
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
        if os.link:
            try:
                os.remove(old)
                os.link(self.filename, old)
            except OSError:
                pass
            os.rename(self.tmpname, self.filename)
        else:
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
            raise errors.WrongModeError("update")
        self.records[obj.name]=self.format(obj)

    def delete(self, obj):
        if not self.incr: 
            raise errors.WrongModeError("delete")
        del self.records[obj.name]
    
    def format(self, obj):
        """Returns the formatted string to be added to the file based on
        the given object. Must include any ending linefeeds."""    
        raise NotImplementedError("format")

class CLFileBack(FileBack):
    """Line-based files, colon separated, primary key in first column"""
    def readin(self, srcfile):
        self.records={}
        for l in open(srcfile):
            key=l.split(":",1)[0]
            if self.unicode:
                key=unicode(key, self.encoding)
            self.records[key]=l
            
    def writeout(self):
        for l in self.records.values():
            self.f.write(l)

    word_illegal_char=re.compile("[:\n]")
    def wash(self, word):
        if not word:
            return ''

        word = self.unicode and unicode(word) or str(word)

        if self.word_illegal_char.match(word):
            raise errors.FormatError("%s contains illegal characters." % word)

        return word

# classic: name:crypt:uid:gid:gcos:home:shell
# shadow:  name:crypt:lastchg:min:max:warn:inactive:expire
# bsd:     name:crypt:uid:gid:class:change:expire:gcos:home:shell

class PasswdFile(CLFileBack):
    def format(self, account):
        if not account.posix_uid:
            raise errors.NotPosixError(account.name)
        res="%s:%s:%s:%s:%s:%s:%s\n" % (
            self.wash(account.name),
            "x",
            self.wash(account.posix_uid),
            self.wash(account.posix_gid),
            self.wash(account.gecos),
            self.wash(account.homedir) or "/dev/null",
            self.wash(account.shell) or "/bin/false")
        if self.unicode:
            return res.encode(self.encoding)
        else:
            return res

class GroupFile(CLFileBack):
    filename="/etc/ceresync/group"
    def format(self, group):
        if not group.posix_gid:
            raise errors.NotPosixError(group.name)
        res="%s:*:%s:%s\n" % (
            self.wash(group.name),
            self.wash(group.posix_gid),
            self.wash(",".join(group.members)))
        if self.unicode:
            return res.encode(self.encoding)
        else:
            return res

class ShadowFile(CLFileBack):
    filename="/etc/ceresync/shadow"
    def format(self, account):
        if not account.posix_uid:
            raise errors.NotPosixError(account.name)
        res="%s:%s:::::::\n" % (
            self.wash(account.name),
            self.wash(account.passwd) or "*")
        if self.unicode:
            return res.encode(self.encoding)
        else:
            return res

class AliasFile(CLFileBack):
    filename="/etc/ceresync/aliases"
    def add(self, obj):
        if not obj.primary_address_id:
            return
        else:
            super(AliasFile, self).add(obj)

    def format(self, addr):
        if addr.address_id == addr.primary_address_id:
            res="%s@%s: <> %s\n" % (
                self.wash(addr.local_part),
                self.wash(addr.domain),
                self.wash(addr.account_name))
        else:
            res="%s@%s: %s@%s\n" % (
                self.wash(addr.local_part),
                self.wash(addr.domain),
                self.wash(addr.primary_address_local_part),
                self.wash(addr.primary_address_domain))

        if self.unicode:
            return res.encode(self.encoding)
        else:
            return res


class AltAliasFile(CLFileBack):
    filename="/etc/ceresync/mailaliases"
    def format(self, addr):
        """Alternate alias file format:
        alias@domain:primaryaddr@domain:accountname:servername
        """
        primary=""
        if addr.primary_address_id:
            primary="%s@%s" % (
                self.wash(addr.primary_address_local_part),
                self.wash(addr.primary_address_domain))
        
        res="%s@%s:%s:%s:%s\n" % (
            self.wash(addr.local_part),
            self.wash(addr.domain),
            primary,
            self.wash(addr.account_name),
            self.wash(addr.server_name))
            
        if self.unicode:
            return res.encode(self.encoding)
        else:
            return res


class SambaFile(CLFileBack):
    """an entry in a samba passwordfile lookes like this:
    <username>:<uid>:<lanman-hash>:<nt-hash>:[<account flags>]:LCT-<hex of unixtime of last change time>:
    Additional colonseparated options are ignored. man 5 smbpasswd for further info.  """
        
    def format(self, account, hashes=None):
        import time
        if not account.posix_uid:
            raise errors.NotPosixError(account.name)

        if hashes:
            lmhash = hashes[0]
            nthash = hashes[1]
        else:
            lmhash = "*Missing_lmhash*"
            nthash = "*Missing_nthash*"

        res="%s:%s:%s:%s:%s:%s\n" % (
                self.wash(account.name),
                self.wash(account.posix_uid),
                self.wash(lmhash),
                self.wash(nthash),
                "[UX         ]",
                "LCT-%s" % hex(int( time.time() ))[2:] )

        if self.unicode:
            return res.encode(self.encoding)
        else:
            return res

    def add(self, obj, hashes=None):
        # duplicated code, needed due to overridden interface. (ish)
        if self.incr:
            self.records[obj.name]=self.format(obj, lmhash, nthash)
        else:
            self.f.write(self.format(obj, hashes=hashes) )

class PasswdFileCryptHash(CLFileBack):
    def format(self, account):
        if not account.posix_uid:
            raise errors.NotPosixError(account.name)
        res="%s:%s:%s:%s:%s:%s:%s\n" % (
            self.wash(account.name),
            self.wash(account.passwd) or "*",
            self.wash(account.posix_uid),
            self.wash(account.posix_gid),
            self.wash(account.gecos),
            self.wash(account.homedir) or "/dev/null",
            self.wash(account.shell) or "/bin/false")

        if self.unicode:
            return res.encode(self.encoding)
        else:
            return res

def Group():
    return GroupFile(filename=config.get("file", "group"))

def Account():
    return MultiHandler(PasswdFile(filename=config.get("file", "passwd")),
                        ShadowFile(filename=config.get("file","shadow")))

def Alias(altformat=False):
    filename=config.get("file", "aliases")
    if altformat:
        return AltAliasFile(filename=filename)
    else:
        return AliasFile(filename=filename)

def PasswdWithHash():
    return PasswdFileCryptHash(filename=config.get("file","passwd"))

def Samba():
    return SambaFile(filename=config.get("file","smbpasswd"))

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
