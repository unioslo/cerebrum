from Searchable import Searchable
from Builder import Builder

class Registry(object):
    def __init__(self):
        self.classes = {}

    def register_class(self, gro_class):
        name = gro_class.__name__

        assert not name in self.classes

        if issubclass(gro_class, Builder):
            gro_class.build_methods()

        if issubclass(gro_class, Searchable) and issubclass(gro_class, Builder):
            self.register_class(gro_class.create_search_class())

        self.classes[name] = gro_class

    def get_gro_classes(self):
        gro_classes = {}
        for name, cls in self.classes.items():
            if issubclass(cls, Builder):
                gro_classes[name] = cls
        return gro_classes

    def __getattr__(self, key):
        return self.classes[key]

_registry = None
def get_registry():
    global _registry
    if _registry is None:
        _registry = Registry()
    return _registry
