#!/usr/bin/env python

import ConfigParser
import unittest
import os

conf = ConfigParser.ConfigParser()
conf.read(('client.conf.template', 'client.conf'))

sync = ConfigParser.ConfigParser()
sync.read(('sync.conf.template', 'sync.conf'))

# Not only tests that config file contains values, but that they make
# sense too, like that files referenced do exist
class TestConf(unittest.TestCase):
    def testSections(self):
        assert conf.has_section("gro")
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
        if conf.getboolean("gro", "cache"):
            path = conf.get("gro", "cache_dir")
            assert os.path.isdir(path)
    
    def testCorba(self):
        # Connection testing will be done by Gro.py
        conf.get("corba", "context")        
        conf.get("corba", "service")
        conf.get("corba", "object")
    
    def testIDL(self):
        path = conf.get("idl", "path")
        assert os.path.isdir(path)
        gro_idl = conf.get("idl", "gro")
        assert os.path.isfile(os.path.join(path, gro_idl))
        errors_idl = conf.get("idl", "errors")
        assert os.path.isfile(os.path.join(path, errors_idl))

class TestSync(unittest.TestCase):
    def testSections(self):
        assert sync.has_section("gro")
        assert sync.has_section("file")
        assert sync.has_section("ldap")

    def testGro(self):
        assert sync.get("gro", "login")
        assert sync.get("gro", "password")
        last_change = sync.get("gro", "last_change")
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
