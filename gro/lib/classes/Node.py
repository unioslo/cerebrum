from Cerebrum.extlib import sets

from Cerebrum.gro.Utils import Cached, Lazy, LazyMethod, Clever

__all__ = ['Node']

class Node(Cached, Clever):
    slots = ['parents', 'children']
    def __init__(self, parents=Lazy, children=Lazy):
        Cached.__init__(self)
        Clever.__init__(self, Node, parents=parents, children=children)

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

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, getattr(self, 'id', ''))

Clever.prepare(Node)

