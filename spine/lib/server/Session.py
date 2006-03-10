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

import os
import codecs
import md5
import sets

import omniORB

import cereconf

from Corba import create_idl_source, convert_to_corba, register_spine_class, drop_associated_objects
import Communication
import SessionHandler
import Authorization

from Cerebrum.spine.CerebrumHandler import CerebrumHandler
from Cerebrum.spine.SpineLib import Builder

from Cerebrum.spine.SpineLib.SpineExceptions import NotFoundError
from Cerebrum.spine.SpineLib.Transaction import TransactionError

def count():
    i = 0
    while True:
        i += 1
        yield i

class Session:
    """
    This class implements sessions in Spine.

    It has to be an old-style object, since the IDL definition says that Spine
    should return an Object when logged in.
    """
    
    slots = ()
    method_slots = ()

    def new_transaction(self):
        pass

    new_transaction.signature = CerebrumHandler

    def get_transactions(self):
        pass

    get_transactions.signature = [CerebrumHandler]

    def get_encoding(self):
        pass

    get_encoding.signature = str

    def set_encoding(self, encoding):
        pass

    set_encoding.signature = None
    set_encoding.signature_args = [str]
    set_encoding.signature_exceptions = [NotFoundError]

    def get_timeout(self):
        pass

    get_timeout.signature = int

    def logout(self):
        pass

    logout.signature = None

# Build corba-classes and IDL

Builder.build_everything()
classes = []
for cls in Builder.get_builder_classes():
    if cls not in classes:
        if list(Builder.get_builder_methods(cls)): # only export classes with methods
            classes.append(cls)

classes.append(Session)

idl_source = create_idl_source(classes, 'SpineIDL')
idl_source_md5 = md5.new(idl_source).hexdigest()
idl_source_commented = create_idl_source(classes, 'SpineIDL', docs=True)

try:
    omniORB.importIDLString(idl_source)
except ImportError:
    name = '/tmp/idlsource.%s.idl' % os.getpid()
    fd = open('/tmp/idlsource.%s.idl' % os.getpid(), 'w')
    fd.write(idl_source)
    fd.close()
    raise Exception('unable to compile idl %s, try checking it with omniidl' % name)

import SpineIDL, SpineIDL__POA

for cls in classes:
    name = cls.__name__
    idl_class = getattr(SpineIDL__POA, 'Spine' + name)
    idl_struct = getattr(SpineIDL, name + 'Struct', None)
    register_spine_class(cls, idl_class, idl_struct)

class SessionImpl(Session, SpineIDL__POA.SpineSession):
    def __init__(self, client):
        self._encoding = getattr(cereconf, 'SPINE_DEFAULT_CLIENT_ENCODING', 'iso-8859-1')
        self.counter = count()
        self.client = client
        self._transactions = {}

    def reset_timeout(self):
        """This method resets the timeout of this session in its session handler."""
        handler = SessionHandler.get_handler()
        handler.update(self)

    def new_transaction(self):
        self.reset_timeout()
        transaction = CerebrumHandler(self, self.client.get_id(), self.counter.next())
        corba_obj = convert_to_corba(transaction, transaction, CerebrumHandler)
        self._transactions[transaction] = corba_obj

        transaction.authorization = Authorization.Authorization(transaction.get_database(), transaction.get_my_entities())
        return corba_obj

    def get_encoding(self):
        return self._encoding

    def set_encoding(self, encoding):
        try:
            codecs.lookup(encoding)
        except LookupError:
            raise SpineIDL.Errors.NotFoundError('Requested encoding %s is unknown.' % encoding)
        self._encoding = encoding

    def get_timeout(self):
        """Returns the time it takes for _a_ session to time out."""
        return getattr(cereconf, 'SPINE_SESSION_TIMEOUT', 900)

    def get_transactions(self):
        self.reset_timeout()
        return self._transactions.values() # NOTE: Returns CORBA references

    def destroy(self):
        """Rollback all transactions and drop the references to them."""
        # Get all keys since the dict will change size and raise RuntimeError
        # if we iterate over it
        transactions = self._transactions.keys() 
        for transaction in transactions:
            transaction.rollback() # This will make the transaction remove itself
        self.client = None

    def remove_transaction(self, transaction):
        """Remove all objects associated with the transaction, and remove the
        sessions reference to the transaction."""
        assert transaction in self._transactions
        drop_associated_objects(transaction)
        del self._transactions[transaction]
        
    def logout(self):
        handler = SessionHandler.get_handler()
        handler.remove(self)
        self.destroy()

# arch-tag: 6fceeb42-b06a-4779-a088-7316dd68a981
