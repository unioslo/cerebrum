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

from __future__ import generators

import md5

import omniORB

from Corba import create_idl_source, convert_to_corba, register_spine_class, drop_associated_objects
import Communication
import SessionHandler
from Cerebrum.spine.CerebrumHandler import CerebrumHandler
from Cerebrum.spine.SpineLib.Builder import Attribute, Method

from Cerebrum.spine.SpineLib import Registry
from Cerebrum.spine.SpineLib.Transaction import TransactionError

registry = Registry.get_registry()

def count():
    i = 0
    while 1:
        yield i
        i += 1

class Session:
    """User-spesific session.

    This is returned to the client when they succesfully login. If they
    dont logout, the same session will be returned next time they login.

    This has to be an old-style object, since the idl definition says
    that Spine should return an Object when logged in.
    """
    
    slots = []
    method_slots = [
        Method('new_transaction', CerebrumHandler),
        Method('get_transactions', [CerebrumHandler]),
        Method('get_transaction', CerebrumHandler, args=[('id', int)]),
        Method('logout', None)
    ]
    builder_parents = ()
    builder_children = ()
    
    def __init__(self, client):
        self.client = client
        self.counter = count()
        self.transactions = {}
        self.corba_transactions = {}

    def reset_timeout(self):
        """This method resets the timeout of this session in its session handler."""
        handler = SessionHandler.get_session_handler()
        handler.update(self)

    def new_transaction(self):
        self.cleanup()
        id = self.counter.next()
        transaction = CerebrumHandler(self, self.client, id)
        corba_obj = convert_to_corba(transaction, transaction, CerebrumHandler)
        self.transactions[id] = transaction
        self.corba_transactions[id] = corba_obj
        return corba_obj

    def cleanup(self):
        dirty = []
        for id in self.transactions:
            if not self.transactions[id].transaction_started:
                dirty.append(id)

        for id in dirty:
            drop_associated_objects(self.transactions[id])
            del self.corba_transactions[id]
            del self.transactions[id]

    def get_transactions(self):
        self.cleanup()
        self.reset_timeout()
        return self.corba_transactions.values()

    def get_transaction(self, id):
        self.reset_timeout()
        return self.corba_transactions[id]

    def destroy(self):
        """ Rollback all transactions and drop the references to them."""
        for transaction in self.transactions.values():
            transaction.rollback()
        self.cleanup()
        self.client = None

    def invalidate_transaction(self, transaction):
        com = Communication.get_communication()
        for id in self.transactions:
            if self.transactions[id] == transaction:
                #com.remove_reference(self.corba_transactions[id])
                break
        drop_associated_objects(self.transactions[id])
        del self.corba_transactions[id]
        del self.transactions[id]

    def logout(self):
        handler = SessionHandler.get_session_handler()
        handler.remove(self)
        self.destroy()

    # TODO legge til:
    #   - is_admin()?
    #   - is_superuser()??
    #   - Events
    #   - Spine-admin-ting?
    #       - statistikk
    #       - oversikt over alle brukere/transaksjoner.

# Build corba-classes and idls.
registry.build_all()
classes = []
classes += registry.classes
classes.append(Session)

idl_source = create_idl_source(classes, 'SpineIDL')
idl_source_md5 = md5.new(idl_source).hexdigest()
idl_source_commented = create_idl_source(classes, 'SpineIDL', docs=True)

omniORB.importIDLString(idl_source)

import SpineIDL, SpineIDL__POA

for name, cls in registry.map.items():
    idl_class = getattr(SpineIDL__POA, 'Spine' + name)
    idl_struct = getattr(SpineIDL, name + 'Struct', None)
    register_spine_class(cls, idl_class, idl_struct)

class SessionImpl(Session, SpineIDL__POA.SpineSession):
    pass

# arch-tag: 6fceeb42-b06a-4779-a088-7316dd68a981
