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


"""Kerberos-based backend for ceresync."""

import unittest
import config

try:
    import kadm5
except:
    kadm5 = None

import heimdal_error
import mit_error

class Account:

    def __init__(self):
        self.k = None # Holds the authenticated kadm object

    def begin(incr=False):
        """
        Initiate connection to local or remote kadmin
        """
        if not kadm5:
            return None
        haveMIT = False
        haveHeimdal = False

        try:
            kadm5.init_libs(kadm5.KRB_FLAVOR_HEIMDAL)
        except OSError,err:
            print "info: unable to initialize Heimdal kerberos: %s" % err
        else:
            haveHeimdal = True

        try:
            kadm5.init_libs(kadm5.KRB_FLAVOR_MIT)
        except OSError,err:
            print "info: unable to initialize MIT kerberos: %s" % err
        else:
            haveMIT = True

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

        # Using first principal as default, or later principalname+password from config
        principal = principals[0]
        print "Found principal: %s" % (principal)

        # OK.. not far left
        self.k = kadm5.KADM5()
        self.k.connect(princ=principal)

    def close():
        """
        Close connection to local or remote kadmin. 
        """
        self.k = None # Room for improvement? 
        # We still may have a valid ticket available

    def abort():
        """
        Abort current transaction.
        """
        pass

    def add(account):
        """Add account into kerberos database.
           Create a new principal, optionally specifying a password and options.
        """
        try:
            princ = account.name + '@' + self.k.realm # or from config
            # FIXME: What do we do if we can't get cleartext password?
            password = account.password or None
            options = None # or some defaults from config in dict-format
            self.k.CreatePrincipal(princ,password,options)
        except Exception,err:
            # FIXME: If Principal exist.. update password and options
            print err

    def update(account):
        """Update account in kerberos database
        """
        # Update password? guess so
        princ = account.name + '@' + self.k.realm # or from config
        # needs to be cleartext, pgp to decrypt?
        password = account.password 
        try:
            self.k.SetPassword(princ,password)
        except Exception,err:
            # FIXME: If Principal does not exist, run add(account)
            print err

    def delete(account):
        """Delete account from kerberos database
        """
        princ = account.name + '@' + self.k.realm # or from config
        try:
            self.k.DeletePrincipal(princ)
        except Exception,err:
            #FIXME: if account/principal doesn't exist, log it
            print err

class testKerberosBack(unittest.TestCase):

    def setUp(self):
        self.kback = Account()

    def testBegin(self):
        self.kback.begin()

    def testClose(self):
        self.kback.close()

    """
    Missing test-cases:
    Add/update/delete principal
    Sync a test-REALM
    """

if __name__ == '__main__':
    unittest.main()
