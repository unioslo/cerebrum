import Cerebrum.Disk # er det ikke logisk at Host ligger i Disk? :p

from Entity import Entity
from Builder import Attribute

from db import db

__all__ = ['Host']

class Host(Entity):
    slots = Entity.slots + [Attribute('name', 'string', writable=True), 
                            Attribute('description', 'string', writable=True)]

    def _load_host(self):
        e = Cerebrum.Disk.Host(db)
        e.find(self.get_entity_id())

        self._name = e.name
        self._description  = e.description

    def _save_host(self):
        e = Cerebrum.Disk.Host(db)
        e.find(self.get_entity_id())
        e.description = self._description
        e.name = self._name
        e.write_db()
        e.commit()

    load_name = _load_host
    load_description = _load_host

    save_name = _save_host
    save_description = _save_host
