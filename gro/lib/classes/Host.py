import Cerebrum.Disk # er det ikke logisk at Host ligger i Disk? :p

from Cerebrum.gro.Utils import Lazy, LazyMethod, Clever

from Entity import Entity

from db import db

__all__ = ['Host']

class Host(Entity):
    slots = ['name', 'description']
    def __init__(self, id, parents=Lazy, children=Lazy, *args, **vargs):
        Entity.__init__(self, id, parents, children)
        Clever.__init__(self, Host, *args, **vargs)

    def load(self):
        e = Cerebrum.Disk.Host(db)
        e.find(self.id)

        self._name = e.name
        self._description  = e.description

Clever.prepare(Host, 'load')
