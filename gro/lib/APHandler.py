# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

from Cerebrum.gro.Cerebrum_core import Errors
from Cerebrum.gro import Account, Builder, Transaction
from Cerebrum.gro.registry import APRegistry
from Builder import CorbaBuilder, Attribute, Method

class APHandler(CorbaBuilder):
    """Access point handler.

    Each client has his own access point, wich will be used to identify the client
    so we can lock down objects to the client and check if the client has access to
    make the changes he tries to do. The client has to provide GRO a username
    and password before he gets the APHandler. This information will be stored in
    this object.
    """

    method_slots = [Method('begin','void'), Method('rollback', 'void'), Method('commit', 'void')]

    def __init__(self, com, username, password):
        # Login raises exception if it fails, or returns entity_id if not.
        self.entity_id = self.login(username, password)
        self.username = username
        self.com = com
        self.transaction = None
        for name, cls in APRegistry.classes.items():
            def get(*args, **vargs):
                return com.get_corba_representation(cls(*args, **vargs))
            method_name = 'get_%s' % name.lower()
            setattr(self, method_name, get)
            method_slots.append(Method(method_name, name))

    def login(self, username, password):
        """Login the user with the username and password.
        """
        # Check username
        for char in ['*','?']:
            if char in username:
                raise Errors.LoginError('Username contains invalid characters.')

        search = Account.build_search_class()()
        search.set_name(username)
        unames = search.search()
        if len(unames) != 1:
            raise Errors.LoginError('Wrong username or password.')
        account = unames[0]

        # Check password
        if not account.authenticate(password):
            raise Errors.LoginError('Wrong username or password.')

        # Check quarantines
        if account.is_quarantined():
            raise Errors.LoginError('Account has active quarantine, access denied.')

        # Log successfull login..
        
        return account.get_entity_id()
    
    def get_username(self):
        """Returns the username of the client.
        """
        return self.username

    def begin(self):
        """Starts a new transaction. If this APHandler already got a transaction
        running, an error will be raised.
        """
        if self.transaction is None:
            self.transaction = Transaction.Transaction(self)
        else:
            raise Errors.TransactionError("Transaction already created.")

    def rollback(self):
        """Rollback changes done in the transaction.
        """
        self.transaction.rollback()
        self.transaction = None
        
    def commit(self):
        """Commit changes to the database.

        Tries first to commit all nodes, then unlocks them.
        """
        self.transaction.commit()
