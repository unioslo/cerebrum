from Builder import Attribute, Method
from GroBuilder import GroBuilder
from Transaction import Transaction

from Entity import Entity

import Registry
registry = Registry.get_registry() 

class APHandler(Transaction, GroBuilder):
    primary = [
        Attribute('client', Entity),
        Attribute('id', int)
    ]
    slots = []
    method_slots = [
        Method('rollback', None),
        Method('commit', None)
    ]

    def __init__(self, *args, **vargs):
        if not GroBuilder.__init__(self, *args, **vargs):
            Transaction.__init__(self, self.get_client())

for name, gro_class in registry.map.items():
    method_name = 'get'
    for i in name:
        if i.isupper():
            method_name += '_' + i.lower()
        else:
            method_name += i

    method_name = 'get_' + name[0].lower()
    last = name[0]
    for i in name[1:]:
        if last.islower() and i.isupper():
            method_name += '_'
        last = i
        method_name += i.lower()

    args = []
    for i in gro_class.primary:
        args.append((i.name, i.data_type, i.sequence))

    method = Method(method_name, gro_class, False, args)
    APHandler.register_method(method, gro_class)

registry.register_class(APHandler)

# arch-tag: 042e8f2b-e0fa-4277-9c43-f434f0b3015c
