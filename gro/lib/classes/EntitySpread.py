from Builder import Method
from DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity
from Types import EntityType, Spread

import Registry
registry = Registry.get_registry()

__all__ = ['EntitySpread']

table = 'entity_spread'

class EntitySpread(DatabaseClass):
    primary = [
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('entity_type', table, EntityType),
        DatabaseAttr('spread', table, Spread)
    ]

    db_attr_aliases = {
        table:{'entity':'entity_id'}
    }

registry.register_class(EntitySpread)

def get_spreads(self):
    s = registry.EntitySpreadSearcher(self)
    s.set_entity(self)
    return s.search()

Entity.register_method(Method('get_spreads', [EntitySpread]), get_spreads)

# arch-tag: 2b120f66-31fc-49db-9b33-6a771be5f96b
