from __future__ import generators

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
        Method('get_transactions', APHandler, sequence=True),
        Method('get_transaction', APHandler, args=[('id', int)])
    ]
    def __init__(self, client):
        self.client = client
        self.counter = count()
        self.transactions = {}

    def new_transaction(self):
        id = self.counter.next()
        transaction = APHandler(self.client, id)
        corba_obj = CorbaClass.convert_to_corba(transaction, transaction, APHandler, False)
        self.transactions[id] = corba_obj
        return corba_obj

    def get_transactions(self):
        return self.transactions.values()

    def get_transaction(self, id):
        return self.transactions[id]

    # FIXME legge til:
    #   - LOHandler
    #   - Events
    #   - Gro-admin-ting?
    #       - statistikk
    #       - oversikt over alle brukere/transaksjoner.


classes = []
classes += registry.classes
classes.append(CorbaSession)

idl_source = create_idl_source(classes, 'generated')

omniORB.importIDLString(idl_source, ['-I' + cereconf.IDL_PATH])

import generated__POA
for name, gro_class in registry.map.items():
    idl_class = getattr(generated__POA, name)
    CorbaClass.register_gro_class(gro_class, idl_class)

class CorbaSessionImpl(CorbaSession, generated__POA.CorbaSession):
    pass

# arch-tag: f285d04a-698c-40a1-a442-40438bc3ee37
