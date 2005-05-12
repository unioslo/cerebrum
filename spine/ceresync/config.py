#!/usr/bin/env python
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

import ConfigParser
import unittest
import os

conf = ConfigParser.ConfigParser()
conf.read(('client.conf.template', 'client.conf'))

sync = ConfigParser.ConfigParser()
sync.read(('sync.conf.template', 'sync.conf'))

def apply_quarantine(obj, typestr):
    for q in obj.get_quarantines:
        try:
            a=sync.get('%s_quarantenes' % typestr, q.name)
        except ConfigParser.NoOptionError:
            try:
                a=sync.get('%s_quarantenes' % typestr, "DEFAULT")
            except ConfigParser.NoOptionError:
                return
        try:
            (var, val) = a.split('=')
            #val=eval(val)  # ouch! but needed for strings/ints/etc
        except ValueError:
            logging.error("Bad quarantene action \"%s\"" % a)
        setattr(obj, var, val)

def apply_override(obj, typestr):
    section='%s_override' % typestr
    attribs=obj.__dict__.copy()
    for a in sync.options(section):
        setattr(obj, a, sync.get(section, a, vars=attribs))

def apply_default(obj, typestr):
    section='%s_default' % typestr
    attribs=obj.__dict__.copy()
    for a in sync.options(section):
        if not obj.__dict__.has_key(a):
            setattr(obj, a, sync.get(section, a, vars=attribs))

# Not only tests that config file contains values, but that they make
# sense too, like that files referenced do exist
class TestConf(unittest.TestCase):
    def testSections(self):
        assert conf.has_section("spine")
        assert conf.has_section("corba")
        assert conf.has_section("idl")
        assert conf.has_section("ssl")

    def testSSL(self):
        # Let's just try to fetch them, they will fail
        # if they don't exist 
        key_file = conf.get("ssl", "key_file")
        assert os.path.isfile(key_file)
        ca_file = conf.get("ssl", "ca_file")
        assert os.path.isfile(ca_file)
        conf.get("ssl", "password")
    
    def testGro(self):
        if conf.getboolean("spine", "cache"):
            path = conf.get("spine", "cache_dir")
            assert os.path.isdir(path)
    
    def testCorba(self):
        # Connection testing will be done by Gro.py
        #conf.get("corba", "context")        
        #conf.get("corba", "service")
        #conf.get("corba", "object")
        conf.get("corba", "url")
    
    def testIDL(self):
        path = conf.get("idl", "path")
        assert os.path.isdir(path)
        core_idl = conf.get("idl", "core")
        assert os.path.isfile(os.path.join(path, core_idl))

class TestSync(unittest.TestCase):
    def testSections(self):
        assert sync.has_section("spine")
        assert sync.has_section("file")
        assert sync.has_section("ldap")

    def testGro(self):
        assert sync.get("spine", "login")
        assert sync.get("spine", "password")
        last_change = sync.get("spine", "last_change")
        # we cannot know if the file exist, but the dir must exist 
        # (why this 'or "."' thing? os.path.dirname() returns
        # a blank string instead of . if there is no dirname)
        assert os.path.isdir(os.path.dirname(last_change) or ".")
  
    def testFile(self):
        # Check if the dirs exists, at least, we are the one
        # to create these files if they don't exist 
        passwd = sync.get("file", "passwd")
        assert os.path.isdir(os.path.dirname(passwd) or ".")
        assert sync.get("file", "hash")
        group = sync.get("file", "group")
        assert os.path.isdir(os.path.dirname(group) or ".")
        if sync.getboolean("file", "use_shadow"):
            shadow = sync.get("file", "shadow")
            assert os.path.isdir(os.path.dirname(shadow) or ".")
 
    def testLdap(self):
        assert sync.get("ldap", "host")
        assert sync.get("ldap", "base")
        assert sync.get("ldap", "bind")
        assert sync.get("ldap", "password")
        assert sync.getboolean("ldap", "tls")

        
if __name__ == "__main__":
    unittest.main()

# arch-tag: 822897c4-fded-4788-9d1a-fbe22b2f7219
