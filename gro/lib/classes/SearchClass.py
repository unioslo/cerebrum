from __future__ import generators

from Cerebrum.extlib import sets

from GroBuilder import GroBuilder
from Builder import Attribute, Method

import Registry
registry = Registry.get_registry()

def create_id_iterator(start=0):
    while 1:
        yield start
        start += 1

class SearchClass(GroBuilder):
    primary = []
    slots = []
    search_slots = []
    method_slots = []

    search_id_iterator = create_id_iterator()

    def __init__(self, search_id=None):
        if GroBuilder.__init__(self):
            return
        self._unions = []
        self._intersections = []
        self._differences = []

    def save(self):
        pass

    def reset(self):
        pass

    def create_primary_key(cls, search_id=None):
        if search_id is None:
            search_id = cls.search_id_iterator.next()

        return (search_id, )

    create_primary_key = classmethod(create_primary_key)

    def get_alive_slots(self): # FIXME: dårlig navn?
        alive = {}
        mine = object() # make a unique object
        for attr in self.slots:
            val = getattr(self, '_' + attr.name, mine)
            if val is not mine:
                alive[attr.name] = val
        return alive


    def search(self):
        unions = sets.Set()
        intersections = sets.Set()
        differences = sets.Set()

        if not hasattr(self, '_result') or self.updated:
            alive = self.get_alive_slots()
            unions.update(self._search(**alive))
            self.updated.clear()
        else:
            unions.update(self._result)

        def convert(objs):
            if not objs:
                return objs

            data_type = objs[0].__class__
            if issubclass(data_type, self._cls):
                return objs

            print 'hæ?', objs
            return []

        for i in self._unions:
            unions.update(convert(i.search()))
        for i in self._intersections:
            intersections.update(convert(i.search()))
        for i in self._differences:
            differences.update(convert(i.search()))

        if intersections:
            unions.intersection_update(intersections)
        if differences:
            unions.difference_update(differences)

        self._result = list(unions)

        return self._result

registry.register_class(SearchClass)

def set_unions(self, unions):
    self._unions = unions
def set_intersections(self, intersections):
    self._intersections = intersections
def set_differences(self, differences):
    self._differences = differences

SearchClass.register_method(Method('set_unions', SearchClass, sequence=True, write=True), set_unions)
SearchClass.register_method(Method('set_intersections', SearchClass, sequence=True, write=True), set_intersections)
SearchClass.register_method(Method('set_differences', SearchClass, sequence=True, write=True), set_differences)


