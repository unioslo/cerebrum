from Builder import Attribute, Method
from GroBuilder import GroBuilder
from Transaction import Transaction

from Entity import Entity
from Types import CodeType

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
    method_name = 'get_' + name[0].lower()
    last = name[0]
    for i in name[1:]:
        if last.islower() and i.isupper():
            method_name += '_'
        last = i
        method_name += i.lower()

    if issubclass(gro_class, CodeType):
        def blipp(gro_class):
            def get_method(self, name):
                return gro_class(name=name)
            return get_method
        m = blipp(gro_class)
        args = [('name', str)]
    else:
        m = gro_class
        args = []
        for i in gro_class.primary:
            args.append((i.name, i.data_type))

    method = Method(method_name, gro_class, args)
    APHandler.register_method(method, m)

registry.register_class(APHandler)

# arch-tag: 042e8f2b-e0fa-4277-9c43-f434f0b3015c
