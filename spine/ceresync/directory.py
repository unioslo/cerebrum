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

""" Directory-based backend - in this case LDAP """

import re,string,sys

import ldap,ldif,dsml
import urllib
from ldap import modlist
from ldif import LDIFParser,LDIFWriter
from dsml import DSMLParser,DSMLWriter 

import unittest
from errors import ServerError

import config



class LdapConnectionError(ServerError):
    pass

class DsmlHandler(DSMLParser):
    """Class for a DSMLv1 parser. Overrides method handle from class dsml.DSMLParser"""

    def handle(self):
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
        self.l = None # Holds the authenticated ldapConnection object

    def utf8_encode(str):
        """ Return utf8-encoded string """
        return unicode(str, "iso-8859-1").encode("utf-8")
        
    def utf8_decode(str):
        "Return decoded utf8-string"
        return unicode(str,"utf-8").encode("iso-8859-1")

    def begin(self,incr=False,uri=None,binddn=None,bindpw=None):
        """
        If incr is true, updates will be incremental, ie the 
        original content will be preserved, and can be updated by
        update() and delete()

        begin() opens a connection to the server running LDAP and 
        tries to authenticate
        """
        self.incr = incr
        if uri == None:
            self.uri = config.sync.get("ldap","uri")
        if binddn == None:
            self.binddn = config.sync.get("ldap","binddn")
        if bindpw == None:
            self.bindpw = config.sync.get("ldap","bindpw")
        try:
            self.l = ldap.initialize(self.uri)
            self.l.simple_bind_s(self.binddn,self.bindpw)
            self.notinsync = []
            if incr == False:
                res = self.search(filterstr=self.filter,attrslist=["dn"]) # Only interested in attribute dn to be received
                for entry in res:
                    self.notinsync.append(entry[0])
        except ldap.LDAPError,e:
            #raise LdapConnectionError
            print "Error connecting to server: %s" % (e)

    def close(self):
        """
        Syncronize current base if incr=False, then
        close ongoing operations and disconnect from server
        """
        if self.incr == False:
            self.syncronize()
        try:
            self.l.unbind_s()
        except ldap.LDAPError,e:
            print "Error occured while closing LDAPConnection: %s" % (e)

    def syncronize(self):
        """ Deletes objects not to be found in given base.
        Only for use when incr is set to False.
        """
        print "Syncronizing LDAP database"
        for entry in self.notinsync:
            print "Found %s in database.. should not be here.. removing" % entry
            self.delete(dn=entry)
        print "Done syncronizing"

    def abort(self):
        """
        Close ongoing operations and disconnect from server
        """
        try:
            self.l.unbind_s()
        except ldap.LDAPError,e:
            print "Error occured while closing LDAPConnection: %s" % (e)

    def add(self, obj, ignore_attr_types=['',]):
        """
        Add object into LDAP. If the object exist, we update all attributes given.
        """
        dn=self.get_dn(obj)
        attrs=self.get_attributes(obj)
        try:
            self.l.add_s(dn,modlist.addModlist(attrs,ignore_attr_types))
            if self.incr == False:
                try:
                    self.notinsync.remove(dn)
                except:
                    pass
        except ldap.ALREADY_EXISTS,e:
            print "%s already exist. Trying update instead..." % (obj.name)
            self.update(obj)
        except ldap.LDAPError,e:
            print "An error occured while adding %s: e" % (dn,e)

    def update(self,obj,old=None,ignore_attr_types=[], ignore_oldexistent=0):
        """
        Update object in LDAP. If the object does not exist, we add the object. 
        """
        dn=self.get_dn(obj)
        attrs=self.get_attributes(obj)
        if old == None:
            # Fetch old values from LDAP
            res = self.search(base=dn) # using dn as base, and fetch first record
            old_attrs = res[0][1]
        else:
            old_attrs = {}
        mod_attrs = modlist.modifyModlist(old_attrs,attrs,ignore_attr_types,ignore_oldexistent)
        try:
            self.l.modify_s(dn,mod_attrs)
            self.notinsync.remove(dn)
            print "%s updated successfully" % (obj.name)
        except ldap.NO_SUCH_OBJECT,e:
            # Object does not exist.. add it instead
            self.add(obj)
        except ldap.LDAPError,e:
            print "An error occured while modifying %s" % (dn)

    def delete(self,obj=None,dn=None):
        """
        Delete object from LDAP. 
        """
        if not obj == None:
            dn=self.get_dn(obj)
        try:
            self.l.delete_s(dn)
        except ldap.NO_SUCH_OBJECT,e:
            print "%s not found when trying to remove from database" % (dn)
        except ldap.LDAPError,e:
            print "Error occured while trying to remove %s from database: %s" % (dn,e)

    def search(self,base=None,scope=ldap.SCOPE_SUBTREE,filterstr='(objectClass=*)',attrslist=None,attrsonly=0):
        if base == None:
            base = self.base
        try:
            result = self.l.search_s(base,scope,filterstr,attrslist,attrsonly)
        except ldap.LDAPError,e:
            print "Error occured while searching with filter: %s" % (filterstr)
            return [] # Consider raise exception later
        return result

###
###
###

class PosixUser(LdapBack):
    """Stub object for representation of an account."""
    def __init__(self,conn=None,base=None):
        if base == None:
            self.base = config.sync.get("ldap","user_base")
        else:
            self.base = base
        self.filter = config.sync.get("ldap","userfilter")
        self.obj_class = ['top','person','posixAccount','shadowAccount'] # Need 'person' for structural-objectclass

    def get_attributes(self,obj):
        """Convert Account-object to map ldap-attributes"""
        s = {}
        s['objectClass'] = self.obj_class
        s['cn'] = obj.gecos
        s['sn'] = obj.gecos.split()[len(obj.gecos.split())-1] # presume last name, is surname
        s['uid'] = obj.name
        s['uidNumber'] = str(obj.posix_uid)
        s['userPassword'] = '{MD5}' + obj.password # until further notice, presume md5-hash
        s['gidNumber'] = str(obj.primary_group.posix_gid)
        s['gecos'] = self.gecos(obj.gecos)
        s['homeDirectory'] = obj.home
        s['loginShell'] = obj.shell
        return s

    def gecos(self,s,default=1):
        # Taken from cerebrum/contrib/generate_ldif.py and then modified.
        """  Convert special chars to 7bit ascii for gecos-attribute. """
        if default == 1:
            translate = {'Æ' : 'Ae', 'æ' : 'ae', 'Å' : 'Aa', 'å' : 'aa','Ø' : 'Oe','ø' : 'oe' }
        elif default == 2:
            translate = {'Æ' : 'A', 'æ' : 'a', 'Å' : 'A', 'å' : 'a','Ø' : 'O','ø' : 'o' }
        elif default == 3:
            translate = {'Æ' : '[', 'æ' : '{', 'Å' : ']', 'å' : '}','Ø' : '\\','ø' : '|' }
        s = string.join(map(lambda x:translate.get(x, x), s), '')
        return s

    def get_dn(self,obj):
        # Maybe generalize this to LdapBack instead
        return "uid=" + obj.name + "," + self.base

class PosixGroup(LdapBack):
    '''Abstraction of a group of accounts'''
    def __init__(self,base=None):
        if base == None:
            self.base = config.sync.get("ldap","user_base")
        else:
            self.base = base
        self.filter = config.sync.get("ldap","groupfilter")
        self.obj_class = ['top','posixGroup']
        # posixGroup supports attribute memberUid, which is multivalued (i.e. can be a list, or string)

    def get_attributes(self,obj):
        s = {}
        s['objectClass'] = self.obj_class
        s['cn'] = obj.name
        if (len(obj.membernames) > 0):
            s['memberUid'] = obj.membernames
        if (len(obj.description) > 0):
            s['description'] = obj.description
        s['gidNumber'] = str(obj.posix_gid)
        return s

    def get_dn(self,obj):
        return "cn=" + obj.name + "," + self.base


class Person:
    def __init__(self,base="ou=People,dc=ntnu,dc=no"):
        self.base = base
        self.filter = config.sync.get("ldap","peoplefilter")
        self.obj_class = ['top','person','organizationalPerson','inetorgperson','eduperson','noreduperson']

    def get_dn(self,obj):
        return "cn=" + obj.name + "," + config.sync.get('ldap','people_base')

    def get_attributes(self,obj):
        s = {}
        s['objectClass'] = self.obj_class
        s['cn'] = obj.full_name
        s['sn'] = obj.full_name.split()[len(obj.full_name)-1] # presume last name, is surname
        s['uid'] = obj.name
        # FIXME
        #s['userPassword'] = '{MD5}' + 'secrethashhere' 
        #obj.password # until further notice, presume md5-hash
        s['eduPersonPrincipalName'] = obj.name + "@" + config.sync.get('ldap','eduperson_realm')
        s['norEduPersonBirthDate'] = str(obj.birth_date) # Norwegian "Birth date" 
        #FIXME
        #s['norEduPersonNIN'] = str(obj.birth_date) # Norwegian "Birth number" / SSN
        s['mail'] = s['eduPersonPrincipalName'] # FIXME 
        #s['description'] = obj.description
        return s

class Alias:
    """ Mail aliases, for setups that store additional mailinglists and personal aliases in ldap."""
    def __init__(self,base=""):
        self.base = base
        self.filter = config.sync.get("ldap","aliasfilter")

    def get_dn(self,obj):
        pass

    def get_attributes(self,obj):
        pass

class OU:
    """ OrganizationalUnit, where people work or students follow studyprograms.
    Needs name,id and parent as minimum.
    """
    def __init__(self,base="ou=organization,dc=ntnu,dc=no"):
        self.base = base
        self.filter = config.sync.get("ldap","oufilter")
        self.obj_class = ['top','organizationalUnit']

    def get_dn(self,obj):
        #FIXME
        pass

    def get_attributes(self,obj):
        #FIXME: add support for storing unit-id,parent-id and rootnode-id
        s = {}
        s['objectClass'] = ('top','organizationalUnit')
        s['ou'] = obj.name
        s['description'] = obj.description
        return s



###
### UnitTesting is good for you
###

class testLdapBack(unittest.TestCase):
    def setUp(self):
        self.lback = LdapBack()

    def testBeginFails(self):
        self.assertRaises(LdapConnectionError, self.lback.begin, hostname='doesnotexist.bizz')

    def testClose(self):
        self.lback.close()

if __name__ == "__main__":
    unittest.main()

# arch-tag: ec6c9186-9e3a-4c18-b467-a72d0d8861fc
