import Cerebrum.Disk # er det ikke logisk at Host ligger i Disk? :p

from Cerebrum.gro.Utils import Cached, Lazy, LazyMethod, Clever

from Entity import Entity

from db import db

__all__ = ['Disk']

class Disk(Entity):
    slots = ['host', 'path', 'description']
    def __init__(self, id, parents=Lazy, children=Lazy, *args, **vargs):
        Entity.__init__(self, id, parents, children)
        Clever.__init__(self, Disk, *args, **vargs)

    def load(self):
        import Host
        e = Cerebrum.Disk.Disk(db)
        e.find(self.id)

        self._host = Host.Host(int(e.host_id))
        self._path = e.path
        self._description  = e.description

Clever.prepare(Disk, 'load')
