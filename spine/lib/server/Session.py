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
import cereconf

from Corba import create_idl_source, convert_to_corba, register_spine_class
from Cerebrum.spine.CerebrumHandler import CerebrumHandler
from Cerebrum.spine.SpineLib.Builder import Attribute, Method

from Cerebrum.spine.SpineLib import Registry
registry = Registry.get_registry()


def count():
    i = 0
    while 1:
        yield i
        i += 1

class Session:
    slots = []
    method_slots = [
        Method('new_transaction', CerebrumHandler),
        Method('get_transactions', [CerebrumHandler]),
        Method('get_transaction', CerebrumHandler, args=[('id', int)]),
        Method('snapshot', CerebrumHandler),
        Method('logout', None)
    ]
    builder_parents = ()
    builder_children = ()
    
    def __init__(self, client):
        print 'login', client
        self.client = client
        self.counter = count()
        self.transactions = {}

    def new_transaction(self):
        id = self.counter.next()
        transaction = CerebrumHandler(self.client, id)
        corba_obj = convert_to_corba(transaction, transaction, CerebrumHandler)
        self.transactions[id] = corba_obj
        return corba_obj

    def snapshot(self):
        id = self.counter.next()
        cache = {}
        transaction = CerebrumHandler(self.client, id, cache=cache)
        transaction.snapshot = cache
        corba_obj = convert_to_corba(transaction, transaction, CerebrumHandler)
        self.transactions[id] = corba_obj
        return corba_obj

    def cleanup(self):
        dirty = []
        for id in self.transactions:
            if not CerebrumHandler(self.client, id).transaction_started:
                dirty.append(id)

        for id in dirty:
            del self.transactions[id]

    def get_transactions(self):
        self.cleanup()
        return self.transactions.values()

    def get_transaction(self, id):
        return self.transactions[id]

    def logout(self):
        print 'logout', self.client
        for i in self.transactions.values():
            try:
                i.rollback()
            except Exception, e:
                print i, e

        self.cleanup()

    # TODO legge til:
    #   - Events
    #   - Spine-admin-ting?
    #       - statistikk
    #       - oversikt over alle brukere/transaksjoner.


registry.build_all()
classes = []
classes += registry.classes
classes.append(Session)

idl_source = create_idl_source(classes, 'generated')
idl_source_md5 = md5.new(idl_source).hexdigest()

omniORB.importIDLString(idl_source, ['-I' + cereconf.IDL_PATH])

import generated, generated__POA
for name, cls in registry.map.items():
    idl_class = getattr(generated__POA, 'Spine' + name)
    idl_struct = getattr(generated, name + 'Struct', None)
    register_spine_class(cls, idl_class, idl_struct)

class SessionImpl(Session, generated__POA.SpineSession):
    pass

# arch-tag: 6fceeb42-b06a-4779-a088-7316dd68a981
