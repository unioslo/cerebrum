from Builder import Method
from DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity
from Types import EntityType, Flag

import Registry
registry = Registry.get_registry()

__all__ = ['EntityFlag']

table = 'entity_flag'

class EntityFlag(DatabaseClass):
    primary = [
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('flag', table, Flag)
    ]

    db_attr_aliases = {
        table:{'entity':'entity_id'}
    }

registry.register_class(EntityFlag)

def get_flags(self):
    s = registry.EntityFlagSearch(self)
    s.set_entity(self)
    return s.search()

Entity.register_method(Method('get_flags', EntityFlag, sequence=True), get_flags)

# arch-tag: 2b120f66-31fc-49db-9b33-6a771be5f96b
