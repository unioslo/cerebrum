from __future__ import generators

import md5

import omniORB
import cereconf

from classes.Builder import Attribute, Method
from classes.CorbaBuilder import CorbaBuilder, create_idl_source
from classes.APHandler import APHandler

from classes import Registry
registry = Registry.get_registry()

import CorbaClass

def count():
    i = 0
    while 1:
        yield i
        i += 1

class CorbaSession(CorbaBuilder):
    slots = []
    method_slots = [
        Method('new_transaction', APHandler),
        Method('get_transactions', [APHandler]),
        Method('get_transaction', APHandler, args=[('id', int)]),
        Method('snapshot', APHandler),
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
        transaction = APHandler(self.client, id)
        corba_obj = CorbaClass.convert_to_corba(transaction, transaction, APHandler)
        self.transactions[id] = corba_obj
        return corba_obj

    def snapshot(self):
        return CorbaClass.convert_to_corba(APHandler(self.client, -1), None, APHandler)

    def cleanup(self):
        dirty = []
        for id in self.transactions:
            if not APHandler(self.client, id).transaction_started:
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

    # FIXME legge til:
    #   - LOHandler
    #   - Events
    #   - Gro-admin-ting?
    #       - statistikk
    #       - oversikt over alle brukere/transaksjoner.


registry.build_all()
classes = []
classes += registry.classes
classes.append(CorbaSession)

idl_source = create_idl_source(classes, 'generated')
idl_source_md5 = md5.new(idl_source).hexdigest()

omniORB.importIDLString(idl_source, ['-I' + cereconf.IDL_PATH])

import generated, generated__POA
for name, gro_class in registry.map.items():
    idl_class = getattr(generated__POA, 'Spine' + name)

    idl_struct = getattr(generated, name + 'Struct', None)

    CorbaClass.register_gro_class(gro_class, idl_class, idl_struct)

class CorbaSessionImpl(CorbaSession, generated__POA.SpineCorbaSession):
    pass

# arch-tag: f285d04a-698c-40a1-a442-40438bc3ee37
