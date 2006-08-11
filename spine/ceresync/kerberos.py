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
#import config

try:
    import kadm5
except:
    kadm5 = None

import heimdal_error
import mit_error

class Account:

    def __init__(self):
        self.k = None # Holds the authenticated kadm object


    def begin(self,incr=False):
        """
        Initiate connection to local or remote kadmin
        """
        if not kadm5:
            return None
        haveMIT = False
        haveHeimdal = False

        try:
            kadm5.init_libs(kadm5.KRB_FLAVOR_HEIMDAL)
            haveHeimdal = True
        except OSError,err:
            print "info: unable to initialize Heimdal kerberos: %s" % err

        # Decomment if using MIT and not Heimdal. Make it configurable. 
        #try:
        #    kadm5.init_libs(kadm5.KRB_FLAVOR_MIT)
        #    haveMIT = True
        #except OSError,err:
        #    print "info: unable to initialize MIT kerberos: %s" % err

        if not (haveMIT or haveHeimdal):
            print "No kreberos libs found"
            return None

        krb = kadm5.KRB5()

        try:
            principals = krb.klist()
        except Exception,err:
            print err
            return None

        if (not principals):
            return None

        # Using first principal as default, or later from config
        principal = principals[0]
        assert 'admin' in principal

        # OK.. not far left
        self.k = kadm5.KADM5()
        try:
            self.k.connect(princ=principal)
        except Exception,e:
            print "Error connecting. Reason: %s" % e
            raise SystemExit

        if (not incr):
            self.added_princs = []
            
    def close(self,):
        """
        Close connection to local or remote kadmin. 
        """
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
            password = account.password
            options = None # or some defaults from config in dict-format
            self.k.CreatePrincipal(princ,password,options)
            if (not incr):
                self.added_princs.append(princ)
        except heimdal_error.KADM5_DUP,kdup:
            # FIXME! Fetch override from config. If we set new password
            # the user will get a new kvno and things might break.
            pass
        except Exception,err:
            print err

    def update(self,account):
        """Update account in kerberos database
        """
        # Update password? guess so
        princ = account.name + '@' + self.k.realm # or from config
        # Needs to be cleartext, pgp to decrypt?
        password = account.password 
        try:
            self.k.SetPassword(princ,password)
        except Exception,err:
            print err

    def delete(self,account):
        """Delete account from kerberos database
        """
        princ = account.name + '@' + self.k.realm # or from config
        try:
            self.k.DeletePrincipal(princ)
        except Exception,err:
            print err

    def syncronize(self):
        """Delete any old account not supposed to be here.
        """
        if not self.incr:
            added = self.added_princs
            princs = self.k.ListPrincipals()
            for princ in princs:
                p = self.k.GetPrincipal(princ)
                if p['mod_name'] == self.principal:
                    if princ not in added:
                    try:
                        self.k.DeletePrincipal(princ)
                    except Exception,err:
                        print err



class User:
   def __init__(self):
       self.name = 'testuser'
       self.password = 'testpw'

class KerberosBackTest(unittest.TestCase):

    def setUp(self):
        self.account = Account()

    def testBegin(self):
        self.account = Account()
        self.account.begin()

    def testAdd(self):
        user = User()
        self.account = Account()
        self.account.begin()
        self.account.add(user)

    def testSetPassword(self):
        user = User()
        self.account = Account()
        self.account.begin()
        self.account.update(user)

    def testDelete(self):
        user = User()
        self.account = Account()
        self.account.begin()
        self.account.delete(user)

    def testClose(self):
        self.account = Account()
        self.account.begin()
        self.account.close()


if __name__ == '__main__':
    unittest.main()
