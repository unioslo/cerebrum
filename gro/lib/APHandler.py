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

from Cerebrum.Utils import Factory
from Cerebrum.gro.Cerebrum_core import Errors
from Cerebrum.gro.classes.db import db
from Cerebrum.gro import Cerebrum_core__POA
from Cerebrum.gro import Builder, Entity, Locking, Locker, Account
from Cerebrum.gro import Transaction

from omniORB.any import to_any, from_any
import mx.DateTime


class APHandler(Cerebrum_core__POA.APHandler, Locker):
    """Access point handler.

    Each client has his own access point, wich will be used to identify the client
    so we can lock down nodes to the client and check if the client got access to
    make the changes he tries to do. The client has to provide the GRO a username
    and password before he gets the aphandler. This information will be stored in
    this object.
    """

    def __init__(self, com, username, password):
        # Login raises exception if it fails, or returns entity_id if not.
        self.entity_id = self.login(username, password)
        self.username = username
        self.com = com
        self.transaction = None

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

class APObject(Cerebrum_core__POA.APObject):
    """ Access point proxy node.

    The APOBject contains the APHandler and an object. It acts as a proxy for the object.
    This is to give us a sort of automatic session handling that will solve two problems:
    1 - The client does not have to deal with a session id
    2 - GRO can perform locking on objects requested by an client,
        using the APHandler to identify it.
    """

    def __init__(self, ap, obj):
        self.ap = ap
        self.obj = obj

    def _convert(self, obj):
        """Convert an object.
    
        If the object is a list, it will be converted to a tuple.
        If the object is a node, it will be converted to a corba-node.
        If the object is an int, a long, a float or a string it will not be converted.
        """
        if hasattr(obj, '__iter__') or type(obj) in (list, tuple):
            return [self._convert(i) for i in obj]

        elif type(obj) in (int, long, float, str):
            return obj

        elif type(obj) == mx.DateTime.DateTimeType:
            return obj.ticks()

        elif isinstance(obj, Builder):
            ap_object = APObject(self.ap, obj)
            return self.ap.com.get_corba_representation(ap_object)

        elif obj is None:
            return 'wtf. None!'

        else:
            raise Errors.ServerError('Server failed to convert object')

    def get_primary_key(self):
        """ Returns a tuple with the primary key changed into an anyobject. """
        key = self.obj.get_primary_key()[1]
        if type(key) != tuple:
            key = [key]
        return to_any(self._convert(key))

    def get_class_name(self):
        """ Returns the classname for the object. """
        return self.obj.__class__.__name__

    def get_read_attributes(self):
        """ Returns a list over all readable attributes for the object. """
        return self.obj.read_slots

    def get_write_attributes(self):
        """ Returns a list over all writeable attributes for the node. """
        return self.obj.write_slots

    def begin(self):
        """Begins a transaction.
    
        A read lock will be requested on this node. Raises an 
        AlreadyLockedError if the node is already locked for writing.
        """
        self.lock_for_reading()

    def rollback(self):
        """Remove/drop changes done to the node.
    
        Rollbacks changes done to this node, and unlocks all locks on this node.
        """
        self.obj.rollback()

    def commit(self):
        """Save changes to the database.
    
        Commits the changes in this node to the database. Returns a list with
        al changed attributes. Raises a NotLockedError if the node isn't locked
        for writing.
        """
        if not self.updated:
            return []

        updated = self.obj.updated
        changed = self.obj.commit()
        assert updated.issubset(changed)
        return updated
