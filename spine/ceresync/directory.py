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

""" Directory-based backend - in this case LDAP """

import ldap,ldif,dsml
import urllib
from ldap import modlist
from ldif import LDIFParser,LDIFWriter
from dsml import DSMLParser,DSMLWriter 

import unittest
from doc_exception import DocstringException

import config

class LdapConnectionError(DocstringException):
    print "Could not connect to LDAP server"

class DsmlHandler(DSMLParser):
    """Class for a DSMLv1 parser. Overrides method handle from class dsml.DSMLParser"""

    def handle():
        """Do something meaningful """
        pass

class LdifHandler(LDIFParser):
    """Class for LDIF records"""

class DsmlBack( DSMLParser ):
    """XML-based files. xmlns:dsml=http://www.dsml.org/DSML """
    def __init_(self,output_file=None,input_file=None,base64_attrs=None,cols=76,line_sep='\n'):
        self.output_file = output_file
        self._input_file = input_file
        self.base64_attrs = base64_attrs
        self.cols = cols
        self.line_sep = line_sep

    def handler(self,*args,**kwargs):
        pass

    def readin(self,srcfile,type="dsml"):
        """Default, the dsml.DSMLParser only wants to parse LDIF-files
        to convert it into DSML before we save it as <filenam>.dsml.
        This function will do both
        """
        pass
    
    def writeout(self):
        dsml.DSMLWriter.writeHeader()
        for record in self.records:
            dsml.DSMLWriter.writeRecord(record.dn,record.entry)
        dsml.DSMLWriter.writeFooter()

class LdifBack( object ):
    """LDIF-based files. 
    """
    def __init__(self,output_file=None, base64_attrs=None,cols=76,line_sep='\n'):
        self.output_file = output_file # or rather from a config-file or something
        self.base64_attrs = base64_attrs
        self.cols = cols
        self.line_sep = line_sep

    def readin(self,srcfile):
        self.file = srcfile
        try:
            file = open(self.file)
            self.records = ldif.ParseLDIF(file) # ldif.ParseLDIF is deprecated... re-implement later
            file.close() 
        except IOError,e:
            print "An error occured while importing file: ", srcfile
            print e

    def writeout(self):
        self.outfile = open(self.output_file,"w")
        for entry in self.records:
            self.outfile.write(ldif.CreateLDIF(entry[0],entry[1],self.base64_attrs,self.cols))
        self.outfile.close()
        
class LdapBack:
    """
    All default values such as basedn for each type of object shall be fetch
    from a configuration file. If config is misconfigured, this module should
    log this in somewhat human readable form.

    PosixUser,PosixGroup etc will inherit this class.
    """
    l = None

    def __init__(self):
        self.l = False # Holds the authenticated ldapConnection object

    def begin(self,incr=False,uri="ldaps://localhost:636",binddn="",bindpw=""):
        """
        If incr is true, updates will be incremental, ie the 
        original content will be preserved, and can be updated by
        update() and delete()

        begin() opens a connection to the server running LDAP and 
        tries to authenticate
        """
        self.incr = incr
        try:
            self.l.open(hostname)
            self.l.simple_bind_s(binddn,bindpw)
        except ldap.LDAPError,e:
            raise LdapConnectionError

    def get_connection(self):
        return self.l

    def close(self):
        """
        Close ongoing operations and disconnect from server
        """
        try:
            self.l.close()
        except ldap.LDAPError,e:
            print "Error occured while closing LDAPConnection: %s" % (e)

    def abort(self):
        """
        Close ongoing operations and disconnect from server
        """
        self.l.close()

    def _add(self,obj):
        """
        Add object into LDAP. If the object exist, we update all attributes given.
        """
        try:
            self.l.add_s(obj[0],obj[1])
        except ldap.ALREADY_EXIST,e:
            print "%s already exist. Trying update instead..." % (obj[0])
            _update(obj)
        except ldap.LDAPError,e:
            print "An error occured while adding %s" % (obj[0])
            print e

    def _update(self,obj,old=None):
        """
        Update object in LDAP. If the object does not exist, we add the object. 
        """
        (dn,attrs) = (obj[0],obj[1])
        if old == None:
            # Fetch old values from LDAP
            res = search(dn) # using dn as base, and fetch first record
            old_attrs = res[1]
        mod_attrs = modlist.modifyModlist(old_attrs,attrs)
        try:
            self.l.modify_s(dn,mod_attrs)
        except ldap.LDAPError,e:
            print "An error occured while modifying %s" % (dn)

    def _delete(self,obj):
        """
        Delete object from LDAP. 
        """
        pass

    def search(self,conn,base="dc=example,dc=com",scope=ldap.SCOPE_SUBTREE,filterstr='(objectClass=*)',attrslist=None,attrsonly=0):
        try:
            result = conn.search_s(base,scope,filterstr,attrslist,attrsonly)
        except ldap.LDAPError,e:
            print "Error occured while searching with filter: %s" % (filterstr)
            return [] # Consider raise exception later
        return res

###
###
###

class PosixUser(LdapBack):
    """Stub object for representation of an account."""
    def __init__(self,conn=None,base="ou=users,dc=ntnu,dc=no"):
        self.conn = conn
        self.base = base
        self.obj_class = ['top','person','posixAccount','shadowAccount'] # Need 'person' for structural-objectclass

    def get_attributes(self,obj):
        """Convert Account-object to map ldap-attributes"""
        s = {}
        s['objectClass'] = self.obj_class
        s['cn'] = obj.fullname
        s['sn'] = obj.fullname.split()[len(obj.fullname)-1] # presume last name, is surname
        s['uid'] = obj.name
        s['uidNumber'] = obj.uid
        s['userPassword'] = '{MD5}' + obj.password # until further notice, presume md5-hash
        s['gidNumber'] = obj.gid
        s['gecos'] = self.gecos(obj.fullname)
        s['homeDirectory'] = obj.home
        s['loginShell'] = obj.shell
        return s

    def get_dn(self,obj):
        # Maybe generalize this to LdapBack instead
        return "uid=" + obj.name + "," + config.sync.get('ldap','user_base')

    def add(self,obj,conn):
        # Convert obj into a useful LDAPObject
        self.dn = self.get_dn(obj)
        self.attrs = self.get_attributes(obj)
        try:
            self._add(self.dn,self.attrs,conn)
        except ldap.LDAPError,e:
            print "Error adding %s: %s" % (self.dn,e)

    def delete(self,obj):
        # Convert obj into something more usefule...
        self.dn = self.get_dn(obj)
        try:
            self._delete(self.dn)
        except ldap.LDAPError,e:
            print "Error removing %s: %s" % (self.dn,e)

    def update(self,obj):
        # Convert obj into something more usefule...
        self.dn = self.get_dn(obj)
        self.old_attrs = self.get_attributes(obj)
        self.new_attrs = self.search(base=dn)[0][1] # Only interested in the first record returned.. ('dn','dict_of_attributes')


class PosixGroup(LdapBack):
    '''Abstraction of a group of accounts'''
    def __init__(self,base="ou=groups,dc=ntnu,dc=no"):
        self.base = base
        self.obj_class = ['top','posixGroup']

    def get_attributes(self,obj):
        s = {}
        s['objectClass'] = self.obj_class
        s['cn'] = obj.name
        s['memberUid'] = obj.membernames
        s['description'] = obj.description
        s['gidNumber'] = obj.gid
        return s

    def get_dn(self,obj):
        return "cn=" + obj.name + "," + config.sync.get('ldap','group_base')

    def add(self,obj,conn):
        self.dn = self.get_dn(obj)
        self.attrs = self.get_attributes(obj)
        try:
            self._add(dn,attrs,conn)
        except ldap.ALREADY_EXIST,e:
            # Log error, and run update instead
            self.update(obj,conn)
        except ldap.LDAPError,e:
            print "Error adding %s: %s" % (self.dn,e)

    def update(self,obj,conn):
        self.dn = self.get_dn(obj)
        self.old_attrs = self.get_attributes(obj)
        self.new_attrs = self.search(base=dn)[0][1] # Only interested in the first record returned.. ('dn','dict_of_attributes')
        try:
            self._update(self.dn,self.old_attributes,self.new_attributes)
        except ldap.NO_SUCH_OBJECT,e:
            # If object, does not exist - add it, and log the event...
            self.add(obj,conn)
        except ldap.LDAPError,e:
            print "Error modifying %s: %s" % (self.dn,e)

    def delete(self,obj,conn):
        self.dn = self.get_dn(obj)
        try:
            self._delete(self.dn,conn)
        except ldap.NO_SUCH_OBJECT,e:
            # if object does not exist, log the event
            print "Object not found trying to delete %s: %s" % (self.dn,e)
        except ldap.LDAPError,e:
            print "Error modifying %s: %s" % (self.dn,e)

class EduPerson:
    def __init__(self,base="ou=People,dc=ntnu,dc=no"):
        self.base = base
        self.obj_class = ['top','person','organizationalPerson','inetorgperson','eduperson','noreduperson']

    def get_dn(self,obj):
        return "cn=" + obj.name + "," + config.sync.get('ldap','people_base')

    def get_attributes(self,obj):
        s = {}
        s['objectClass'] = self.obj_class
        s['cn'] = obj.fullname
        s['sn'] = obj.fullname.split()[len(obj.fullname)-1] # presume last name, is surname
        s['uid'] = obj.name
        s['userPassword'] = '{MD5}' + obj.password # until further notice, presume md5-hash
        s['eduPersonPrincipalName'] = obj.name + "@" + config.sync.get('ldap','eduperson_realm')
        s['norEduPersonNIN'] = '01012005 99999' # Norwegian "Birth number" / SSN
        s['mail'] = self.email
        return s

    def add(self,obj,conn):
        self.dn = self.get_dn(obj)
        self.attrs = self.get_attributes(obj)
        try:
            self._add(self.dn,self.attrs,conn)
        except ldap.ALREADY_EXIST,e:
            # Log error, and run update instead
            self.update(obj,conn)
        except ldap.LDAPError,e:
            print "Error adding %s: %s" % (self.dn,e)

    def update(self,obj,conn):
        self.dn = self.get_dn(obj)
        self.old_attrs = self.get_attributes(obj)
        self.new_attrs = self.search(base=dn)[0][1] # Only interested in the first record returned.. ('dn','dict_of_attributes')
        try:
            self._update(self.dn,self.old_attributes,self.new_attributes)
        except ldap.NO_SUCH_OBJECT,e:
            # If object, does not exist - add it, and log the event...
            self.add(obj,conn)
        except ldap.LDAPError,e:
            print "Error modifying %s: %s" % (self.dn,e)

class Alias:
    """ Mail aliases, for setups that store additional mailinglists and personal aliases in ldap."""
    def __init__(self,base=""):
        self.base = base

class OU:
    """ OrganizationalUnit, where people work or students follow studyprograms.
    Needs name,id and parent as minimum.
    """
    def __init__(self,base="ou=organization,dc=ntnu,dc=no"):
        self.base = base
        self.obj_class = ['top','organizationalUnit']



###
### UnitTesting is good for you
###

class testLdapBack(unittest.TestCase):
    def setUp():
        self.lback = LdapBack()

    def testBegin(self):
        self.lback.begin()

    def testBeginFails(self):
        self.assertRaises(LdapConnectionError, self.lback.begin, hostname='doesnotexist.bizz')

    def testClose(self):
        self.lback.close()

if __name__ == "__main__":
    print "Run unittesting..."
    unittest.main()
    print "Finished unittesting"

# arch-tag: ec6c9186-9e3a-4c18-b467-a72d0d8861fc
