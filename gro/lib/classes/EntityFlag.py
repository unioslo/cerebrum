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
    s = registry.EntityFlagSearcher(self)
    s.set_entity(self)
    return s.search()

Entity.register_method(Method('get_flags', [EntityFlag]), get_flags)

# arch-tag: 10c3b8a9-0c09-4a14-8f42-5f000ff9a840
