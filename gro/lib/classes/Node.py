from Cerebrum.extlib import sets

from Caching import Caching
from Locking import Locking
from Clever import Clever, LazyMethod, Lazy

__all__ = ['Node']

class Node(Caching, Locking, Clever):
    slots = ['parents', 'children']
    readSlots = [] + slots
    writeSlots = []

    def __init__(self, parents=Lazy, children=Lazy):
        Caching.__init__(self)
        if Clever.__init__(self, Node, parents=parents, children=children):
            return
        Locking.__init__(self)

    # internal cache

    def getKey(): # this will make it a singleton
        pass
    getKey = staticmethod(getKey)

    # load

    def loadParents(self):
        self._parents = sets.Set()
    def loadChildren(self):
        self._children = sets.Set()

    # properties
    
    getParents = LazyMethod('_parents', 'loadParents')
    getChildren = LazyMethod('_children', 'loadChildren')

    def rollback(self):
        for var in self.updated:
            setattr(self, '_' + var, Lazy)

    def commit(self):
        updated = self.updated
        print 'updating', updated
        self.updated = sets.Set()
        return updated

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, getattr(self, 'id', ''))

Clever.prepare(Node)
