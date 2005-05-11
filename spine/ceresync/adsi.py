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

# Windows/ActiveDirectory-only
import sys
import os
#from win32com.client import GetObject
import active_directory as ad
from ad_types import constants
import errors
from sets import Set
import unittest
import tempfile
import win32pipe

class WrongClassError(errors.AlreadyExistsError):
    """Already exists in OU, but is wrong objectClass"""    

class OutsideOUError(errors.AlreadyExistsError):
    """Already exists outside managed OU"""

class _AdsiBack(object):
    """
    Generalized class representing common data for working with adsi objects.
    In general, working with Active Directory, you can either use WinNT:// or
    LDAP:// to search,add,modify,delete objects.
    """
    objectClass = "top"
    def __init__(self, ou_path=None):
        """Initalizes an AD connection. 

           ou_path specifies which OU this backend should manage
           objects.  The backend expects all objects inside this OU to
           be handled by itself, so any unknown objects in this OU will
           be deleted in begin(incr=False).
    
           Specify ou_path as a full LDAP URI, example::

             a = AdsiBack("LDAP://OU=Groups,OU=MyDivision,DC=domain,DC=no")
           
           The actual LDAP connection will not be made until begin() is
           called.  
           """
        self.ou_path = ou_path   
        

    def _domain(self, obj=None):
        """Finds the domain of an AD object, ie. the root node. If
           obj is not specified, the domain of self.ou is returned."""
        if obj is None:
            obj = self.ou
        # Is it possible to do this without walking?    
        while not "domain" in obj.objectClass:
            obj = obj.parent()
        return obj    

    def begin(self, incr=False):
        """Connects to Active Directory"""
        self.incr = incr
        if self.ou_path is None:
            # Use the root      
            self.ou = ad.root()
        else:
            self.ou = ad.AD_object(path=self.ou_path)
        
        # Find all existing objects
        if not self.incr:
            self._remains = {}
            # Don't touch objects of other classes than our
            # (Scenario: groups and users in same OU, both handled
            #  by different subclass)
            for o in self.ou.search("objectClass='%s'" %
                                    self.objectClass):
                # FIXME: should use SUBTREE something to avoid returning
                # self.ou
                if o.distinguishedName == self.ou.distinguishedName:
                    continue

                # Supports both cn=name, ou=name, etc.                    
                name = o.name.split("=")[1]
                self._remains[name] = o

    def close(self):
        """Close the connection to AD"""
        for obj in self._remains.values():
            self._delete(obj)
        self._remains = None
        self.ou = None

    def abort(self):
        """ Abort any ongoing operations. """
        self._remains = None
        self.ou = None

    def _delete(self, ad_obj):
        """Delete object from AD"""
        parent = ad_obj.parent()
        # for instance ou.remove("user", "cn=stain")
        parent.delete(ad_obj.Class, ad_obj.name)

    def delete(self, obj):
        ad_obj = self._find(obj.name)
        self._delete(ad_obj)
        if not self.incr:
            if obj.name in self._remains:
                del self._remains[obj.name]

class _ADAccount(_AdsiBack):                
    """Common abstract class for ADUser and ADGroup. 
       They both use saMAccountName as their unique name (with a shared
       namespace) - and that name is always equal to obj.name from
       Spine.
    """

    def _find(self, accountname, ou=None, objectClass=None):
        """Find an account or group by saMAccountName 
        (unique short-version of username in AD). 

        Searches from self.ou unless parameter ou is specified, which
        must be an OU object.

        Returns the matching AD object.

        Raises WrongClassError if the matched object doesn't 
        implement self.objectClass. (For instance, you're searching for
        a group, but found a username instead. As groups and users share
        the saMAccountName domain in AD, you can't have both). If you
        want to override this, specify the paramter objectClass.
        
        Raises OutsideOUError if a conflicting object with
        the given name exists outside our managed OU self.ou.
        saMAccountName is unique across the domain, so this could happen
        if you get an conflict with manual users in other OUs, like
        "Administrator".

        Returns None if the object is not found at all in AD. This means
        the username is available.
        """
        if not ou:
            ou = self.ou
        if not objectClass:
            objectClass = self.objectClass    
        query = "saMAccountName='%s'" % accountname
        for u in ou.search(query):
            # There's really just one hit, if any. So we can
            # raise/return from inside for-loop.

            #  Wait! Was it the correct class?
            if not objectClass in u.objectClass:
                raise WrongClassError, u
            # it's OK, return it    
            return u
        

        # Not found, might he be outside our ou? If so, raise an
        # OutsideOUError exception
        domain = self._domain()
        for u in domain.search("saMAccountName='%s'" % accountname):
            # There's only one, so let's raise it
            raise OutsideOUError, (u, accountname)
            
        # OK, it's really really not here
        return None   
    
    def add(self, obj):
        already_exists = self._find(obj.name)
        if already_exists:
#            print >>sys.stderr, "Already exists ", already_exists, "updating instead"
            return self.update(obj)
        
        ad_obj = self.ou.create(self.objectClass, "cn=%s" % obj.name)    
        ad_obj.saMAccountName = obj.name
        ad_obj.setInfo()
        # update should fetch object again for auto-generated values 
        ad_obj = self.update(obj)
        if not self.incr:
            if obj.name in self._remains:
                del self._remains[obj.name]
        return ad_obj

    def update(self, obj):
        # Do the specialization here, always return for subclasses to
        # do more work on object
        ad_obj = self._find(obj.name)
        if not ad_obj:
            print >>sys.stderr, "Did not exists ", already_exists, "adding instead"
            return self.add(obj)
        if not self.incr:
            if obj.name in self._remains:
                del self._remains[obj.name]
        return ad_obj    


class ADUser(_ADAccount):
    objectClass = "user"
    """Backend for Users in Active Directory.
       Normally, users will be created flat directly in self.ou,
       with cn=username, ie. the same as saMAccountName.
    """
    # Reference: 
    # http://www.microsoft.com/windows2000/techinfo/howitworks/activedirectory/adsilinks.asp
    # http://search.microsoft.com/search/results.aspx?qu=adsi&View=msdn&st=b&c=4&s=1&swc=4

    def update(self, obj):
        ad_obj = super(ADUser, self).update(obj)
        # FIXME: Should check with quarantines       
        # NOTE: Bug in our AD wrapper forces us to use
        # the com_object directly as AccountDisabled is NOT a 
        # property to be set with put("AccountDisabled", False) but
        # should be set directly. I don't know why.
        ad_obj.com_object.accountDisabled = False
        # FIXME: should fetch names from owner, and not require Posix
        ad_obj.fullName = obj.gecos or ""
        password = obj.passwords.get("cleartext")
        if password is not None:
            print "Setting password for", obj.name
            ad_obj.setPassword(password)
        ad_obj.setInfo()
        return ad_obj
    
                

class ADGroup(_ADAccount):
    """Backend for Groups in Active Directory. 
       Normally, groups are set as "Global Security groups".
    """
    objectClass = "group"

    def update(self, obj):
        ad_obj = super(ADGroup, self).update(obj)
        ad_obj.groupType = (constants.ADS_GROUP_TYPE_SECURITY_ENABLED | 
                            constants.ADS_GROUP_TYPE_GLOBAL_GROUP)
        ad_obj.setInfo()
        def check_members():
            # FIXME: Should supports groups as members of groups
            ad_members = ad_obj.members()
            old = Set([m.saMAccountName for m in ad_members])
            spline = Set(obj.membernames)
            add = spline - old
            remove = old - spline
            if not (add or remove):
                # Nothing changed
                return
            # Ok, convert to nice ldap paths    
            domain = self._domain()
            # search in the whole domain, users only
            add = [self._find(m, ou=domain, objectClass='user') 
                   for m in add]
            # Skip None (not-existing users)
            add = [m.ADsPath for m in add if m]
            remove = [m.ADsPath for m in ad_members 
                      if m.saMAccountName in remove]
            for user in remove:
                ad_obj.remove(user)
            for user in add:
                ad_obj.add(user)    
            ad_obj.setInfo()    
        check_members()           
        return ad_obj

class ADOU(_AdsiBack):
    """Backend for OUs in Active Directory. 
    """
    objectClass = "organizationalUnit"

#class ADAlias(AdsiBack):
#    """Handles mail-aliases (distribution lists) within Exchange/AD"""


# The rest of the module is unit tests.
# TODO: Move out!

def cscript(script, type="vbs"):
    """Run a (VB)script using cscript and return the result"""
    # We will use this to set up the AD environment and test it,
    # using known-to-work VBscript code instead of our own code.
    file = tempfile.mktemp(".%s" % type)
    open(file, "w").write(script)
    # popen4 will also include errors 
    i,o = win32pipe.popen4("cscript /nologo %s" % file)
    # Everything will be returned in the first read() =)
    return o.read().strip()



class TestCscript(unittest.TestCase):
    """Tests our cscript() interface"""
    def testEcho(self):
        self.assertEqual(cscript('Wscript.Echo "Hello world"'), 
                         "Hello world")

class TestAD(unittest.TestCase):
    """Checks that there really is an ldap/AD"""
    def testDefaultNamingContext(self):
        """Will only work on an AD server (?)"""
        context = cscript("""Wscript.Echo(GetObject("LDAP://rootDSE").Get("defaultNamingContext"))""")
        assert context.count("DC=")

class TestOUFramework(unittest.TestCase):
    """Helper functions for managing the AD and OU tests,
       mainly by calling small VBscripts.
    """
    # A separate OU will be created in the root on our test domain
    # server
    ou = "tempOU"
    def ou_uri(self):
        """Full URI for our OU"""
        return "LDAP://ou=%s,%s" % (self.ou, self.context)
    ou_uri = property(ou_uri)    

    def deleteOU(self):
        """Recusively deletes our temporary ou"""
        self.assertEqual(cscript("""
        on error resume next
        set ou = GetObject("%s")
        ou.DeleteObject 0
        """ % self.ou_uri), "")

    def setUp(self):
        # Find our root, ie dc=some,dc=doman,dc=com
        self.context = cscript("""
        Wscript.Echo(GetObject("LDAP://rootDSE").Get("defaultNamingContext"))
        """)
        # delete tempOU if already exist 
        self.deleteOU()

        # Create our working temporary OU
        self.assertEqual(cscript("""
        set root = GetObject("LDAP://%s")
        set tempOU = root.Create("organizationalUnit", "ou=%s")
        tempOU.SetInfo()
        """ % (self.context, self.ou)), "")
    
    def tearDown(self):    
        self.deleteOU()

    def addUser(self, user="temp1337"):
        """Adds a user through vbscript"""
        self.assertEqual(cscript("""
        set ou = GetObject("%s")
        set user = ou.Create("user", "cn=%s")
        user.saMAccountName = "%s"
        user.SetInfo()
        """ % (self.ou_uri, user, user)), "")

    def hasNotUser(self, user="temp1337"):      
        """Fails if the user exists"""
        #  Should not find anything
        self.assertEqual(cscript("""
        On Error Resume Next
        set account = GetObject("LDAP://cn=%s,ou=%s,%s")
        Wscript.Echo(account.distinguishedName)
        """ % (user, self.ou, self.context)), "")

    def hasUser(self, user="temp1337"):      
        """Fails if the user does not exist"""
        dn = "CN=%s,OU=%s,%s" % (user, self.ou, self.context) 
        self.assertEqual(cscript("""
        set account = GetObject("LDAP://%s")
        Wscript.Echo(account.distinguishedName)
        """ % dn), dn)

class TestOU(TestOUFramework):
    def testWasCreated(self):
        self.assertEqual(cscript("""
        set tempOU = GetObject("%s")
        Wscript.Echo tempOU.name""" % self.ou_uri),
        "ou=%s" % self.ou)

class TestADSIBack(TestOUFramework):
    def setUp(self):
        super(TestADSIBack, self).setUp()
        self.adsi = _AdsiBack(self.ou_uri)
        self.adsi.begin()
    
    def testRemainsEmpty(self):
        self.assertEqual(self.adsi._remains, {})
    
    def testContainsUsers(self):
        self.addUser()
        self.adsi.begin() # reload _remains
        self.assertEqual(self.adsi._remains.keys(), ["temp1337"])
        self.hasUser()

    def testRemovesUnknown(self):
        self.addUser()
        self.adsi.begin(incr=False) # reload _remains
        self.adsi.close() # Should delete the user we added

    def testDomain(self):
        self.assertEqual(self.adsi._domain().path(), 
                         "LDAP://%s" % self.context)     
            
class TestADAccount(TestOUFramework):
    def setUp(self):
        super(TestADAccount, self).setUp()
        self.adaccount = _ADAccount(self.ou_uri)
        self.adaccount.begin()

    def testRemoveAccount(self):
        class Account:
            """Dummy account object"""
            name = "temp1337"
        account = Account()    

        self.addUser()
        self.adaccount.begin() 
        # reload _remains to mimic containsUser
        self.adaccount.delete(account)
        #  Should not find anything
        self.hasNotUser()

        self.adaccount.begin() # reload _remains
        # now empty again
        self.assertEqual(self.adaccount._remains.keys(), []) 
        
    

if __name__ == "__main__":
    print "Note that these tests must be run as a domain administrator locally"
    print "on a domain controller to be able to create temporary OUs."
    unittest.main()


# arch-tag: e76356d7-873f-4cb6-95a5-b852638f5524
