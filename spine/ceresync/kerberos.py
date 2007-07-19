#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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


""" Kerberos-based backend """

import unittest

import kadm5
import heimdal_error
import mit_error
import errors
import config
import os
import re
from sync import Pgp
from sets import Set as set
import sys

verbose= '-v' in sys.argv

def info(msg):
    if verbose:
        sys.stdout.write(msg)
        sys.stdout.flush()
class Account:

    def __init__(self, principal=None, keytab=None, flavor=None):
        self.k = None # Holds the authenticated kadm object
        self.incr = False
        self.pgp = Pgp()
        self.principal= principal or config.conf.get('kerberos','principal')
        self.keytab= keytab or config.conf.get('kerberos', 'keytab')

        flavor= flavor or config.conf.get('kerberos','flavor')
        if flavor.lower() == 'heimdal':
            self.flavor= kadm5.KRB_FLAVOR_HEIMDAL
        elif flavor.lower() == 'mit':
            self.flavor= kadm5.KRB_FLAVOR_MIT
        else:
            raise errors.BackendError("Invalid kerberos flavor '%s'"%flavor)

    def begin(self,incr=False):
        """
        Initiate connection to local or remote kadmin
        """
        self.incr = incr
        #FIXME! Find a better way to authenticate
        os.system('kinit --keytab=%s %s'%(self.keytab,self.principal))
        try:
            kadm5.init_libs(self.flavor)
        except:
            raise errors.BackendError("Kerberos libs not found")

        self.k = kadm5.KADM5()
        try:
            self.k.connect(princ=self.principal)
        except Exception,e:
            raise errors.BackendError("Unable to connect: %s"%e)

        if (not self.incr):
            self.added_princs = set([])

    def close(self,):
        """
        Close connection to local or remote kadmin. 
        """
        if not self.incr:
            # Could possibly just check for a '/' instead ...
            regex= re.compile('^([a-z0-9]+)@%s$' % self.k.realm)
            for princ in self.k.ListPrincipals():
                # The default principal should be left alone
                if princ.startswith('default@'): continue                  

                # remove users that were not added in this bulk
                m= regex.match(princ)
                if m and princ not in self.added_princs:
                    self.delete(User(name=m.group(1), passwd=''))
        self.k = None

    def abort(self):
        """Only here for compability reasons
        """
        pass

    def add(self,account):
        """Add account into kerberos database.
           Create a new principal, optionally specifying a password and options
           If no password is found, a random password is generated
        """
        try:
            princ = account.name + '@' + self.k.realm # or from config
            password = self.pgp.decrypt(account.passwd)
            options = None # or some defaults from config in dict-format
            if not password:
                info("'%s' has blank password. Not adding.\n"%princ)
                return
            self.k.CreatePrincipal(princ,password,options)
            info("'%s' added\n"%princ)
            if (not self.incr):
                self.added_princs.add(princ)
        except heimdal_error.KADM5_DUP,kdup:
            # FIXME! Fetch override from config. If we set new password
            # the user will get a new kvno and things might break.
            info("'%s' allready exists... "%princ)
            self.update(account)

    def update(self,account):
        """Update account in kerberos database
        """
        # Update password? guess so
        princ = account.name + '@' + self.k.realm # or from config
        password = self.pgp.decrypt(account.passwd)
        try:
            self.k.SetPassword(princ,password)
            info("password updated for '%s'\n"%princ)
            if (not self.incr):
                self.added_princs.add(princ)
        except Exception,err:
            print err

    def delete(self,account):
        """Delete account from kerberos database
        """
        princ = account.name + '@' + self.k.realm # or from config
        self.k.DeletePrincipal(princ)
        info("'%s' removed.\n"%princ)

class User:
   def __init__(self, name='testuser', passwd='testpw'):
       self.name = name
       self.passwd= Pgp().encrypt(passwd)

class HeimdalTestCase(unittest.TestCase):
    """TestCase that tests adding, changing and removing users from a 
    heimdal kdc."""
    def setUp(self):
        self.account= Account(flavor='heimdal')

    def tearDown(self):
        self.account= None

    def testConnection(self):
        """Checks that connection works, and that a simple listing of 
        principals work"""
        self.account.begin()
        self.assert_(self.account.principal in self.account.k.ListPrincipals())
        self.account.close()

    def testAdd(self):
        """Checks that adding a user works"""
        user= User()
        self.account.begin()
        self.account.add(user)
        principal= "%s@%s" % (user.name, self.account.k.realm)

        self.assert_(self.account.k.GetPrincipal(principal))

        self.account.k.DeletePrincipal(principal)
        self.account.close()

    def testAddTwice(self):
        """Adding a user that allready exists should not fail"""
        user= User()
        self.account.begin()
        self.account.add(user)
        self.account.add(user)
        principal= "%s@%s" % (user.name, self.account.k.realm)

        self.assert_(self.account.k.GetPrincipal(principal))

        self.account.k.DeletePrincipal(principal)
        self.account.close()

    def testAddBadPassword(self):
        """Adding a user with blank password should be silently ignored"""
        user= User(passwd='')
        self.account.begin()
        self.account.add(user)
        principal= "%s@%s" % (user.name, self.account.k.realm)

        self.assertRaises(heimdal_error.KADM5_UNK_PRINC, 
                self.account.k.GetPrincipal,
                principal) 

        self.account.close()

    def testDelete(self):
        """Check that removing a user works"""
        user= User()
        self.account.begin()
        self.account.add(user)
        self.account.delete(user)
        principal= "%s@%s" % (user.name, self.account.k.realm)

        self.assertRaises(heimdal_error.KADM5_UNK_PRINC, 
                self.account.k.GetPrincipal,
                principal) 

        self.account.close()

    def testDeleteNonExisting(self):
        """Adds a user then deletes it twice. The last delete should raise
        an exception"""
        user= User()
        self.account.begin()
        self.account.add(user)
        self.account.delete(user)

        self.assertRaises(heimdal_error.KADM5_UNK_PRINC,
                self.account.delete,
                user)
        
        self.account.close()

    def setPassword(self):
        """Changes password on a user, and checks that the modification 
        date on the principal has changed"""
        user= User(passwd='oldpass')
        self.account.begin()
        self.account.add(user)

        principal= "%s@%s" % (user.name, self.account.k.realm)
        info1= self.account.k.GetPrincipal(principal)

        user= User(passwd='newpass')
        self.account.update(user)
        info2= self.account.k.GetPrincipal(principal)
        assertNotEquals(info1['mod_date'], info2['mod_date'])

        self.account.k.DeletePrincipal(principal)
        self.account.close()

    def testSync(self):
        """ Adds two users then simulates a bulk sync with only one of the
        users. The ommited user should then be deleted when close() is called
        """
        user1= User('test1','testpw1')
        user2= User('test2','testpw2')
        self.account.begin()
        self.account.add(user1)
        self.account.add(user2)
        self.account.close()

        self.account.begin(incr=False)
        self.account.add(user1)
        self.account.close()
        # user2 should now have been removed

        self.account.begin()
        principal1= "%s@%s" % (user1.name, self.account.k.realm)
        principal2= "%s@%s" % (user2.name, self.account.k.realm)
        princlist= self.account.k.ListPrincipals()
        self.assert_(principal1 in princlist and principal2 not in princlist)

        self.account.k.DeletePrincipal(principal1)
        self.account.close()

if __name__ == '__main__':
    unittest.main()
