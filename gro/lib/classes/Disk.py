import Cerebrum.Disk

from Entity import Entity
from Builder import Attribute
from db import db

__all__ = ['Disk']

class Disk(Entity):
    slots = Entity.slots + [Attribute('host', 'Host', writable=True),
                            Attribute('path', 'string', writable=True),
                            Attribute('description', 'string', writable=True)]

    def _load_disk(self):
        import Host
        e = Cerebrum.Disk.Disk(db)
        e.find(self._entity_id)

        self._host = Host.Host(int(e.host_id))
        self._path = e.path
        self._description  = e.description

    def _save_disk(self):
        e = Cerebrum.Disk.Disk(db)
        e.find(self._entity_id)

        e.host_id = self._host.get_entity_id()
        e.path = self._path
        e.description = self._description
        e.write_db()
        e.commit()


    load_host = load_path = load_description = _load_disk
    save_host = save_path = save_description = _save_disk
