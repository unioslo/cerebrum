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

import sys

import Communication

import Cerebrum_core__POA
import Cerebrum_core

import CorbaSession

import classes.Registry
registry = classes.Registry.get_registry()

from classes.Account import get_account_by_name

# The major version number of Gro
GRO_MAJOR_VERSION = 0

# The minor version of Gro
GRO_MINOR_VERSION = 1

class GroImpl(Cerebrum_core__POA.Gro):
    """
    Implements the methods in the Gro interface.
    These are provided to remote clients"""

    def __init__(self):
        self.sessions = {}

    def get_idl(self):
        return CorbaSession.idl_source

    def get_idl_md5(self):
        return CorbaSession.idl_source_md5

    def get_version(self):
        return Cerebrum_core.Version(GRO_MAJOR_VERSION, GRO_MINOR_VERSION)
        
    def test(self, txt=None):
        if txt is None:
            txt = 'foomeeee'
        print "server: %s"% (txt)
        return txt
    
    def login(self, username, password):
        """Login the user with the username and password.
        """
        # We will always throw the same exception in here.
        # this is important

        exception = Cerebrum_core.Errors.LoginError('Wrong username or password')

        # Check username
        for char in ['*','?']:
            if char in username or char in password:
                raise exception

        try:
            account = get_account_by_name(username)
        except:
            raise exception

        # Check password
        if not account.authenticate(password):
            raise exception

        # Check quarantines
        if account.is_quarantined():
            raise exception

        # Log successfull login..
        
        if account in self.sessions:
            return self.sessions[account]

        session = CorbaSession.CorbaSessionImpl(account)
        com = Communication.get_communication()
        corba_obj = com.servant_to_reference(session)
        self.sessions[account] = corba_obj

        return corba_obj

# arch-tag: 92c1fc71-f0db-4cd7-b8ed-4d2cf1033b6d
