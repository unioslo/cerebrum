from Builder import Attribute, Method
from GroBuilder import GroBuilder
from Transaction import Transaction

from Entity import Entity

import Registry
registry = Registry.get_registry() 

class APHandler(GroBuilder, Transaction):
    primary = [
        Attribute('client', Entity),
        Attribute('id', int)
    ]
    slots = []
    method_slots = [
        Method('rollback', None),
        Method('commt', None)
    ]

    def __init__(self, *args, **vargs):
        GroBuilder.__init__(self, *args, **vargs)
        Transaction.__init__(self, self.get_client())

for name, gro_class in registry.classes.items():
    method_name = 'get'
    for i in name:
        if i.isupper():
            method_name += '_' + i.lower()
        else:
            method_name += i
    args = []
    for i in gro_class.primary:
        args.append((i.name, i.data_type, i.sequence))

    method = Method(method_name, gro_class, False, args)
    APHandler.register_method(method, gro_class)

registry.register_class(APHandler)
