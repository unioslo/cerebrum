from Builder import Method
from DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity
from Types import ValueDomain

import Registry
registry = Registry.get_registry()

__all__ = ['EntityName']

table = 'entity_name'

class EntityName(DatabaseClass):
    primary = [
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('value_domain', table, ValueDomain)
    ]
    slots = [
        DatabaseAttr('name', table, str)
    ]

    db_attr_aliases = {
        table:{
            'entity':'entity_id',
            'name':'entity_name'
        }
    }

registry.register_class(EntityName)

def get_entity_name(self, value_domain):
    s = registry.EntityNameSearch((self, value_domain))
    s.set_entity(self)
    s.set_value_domain(self)
    (name, ) = s.search()
    return name

m = Method('get_entity_name', EntityName)
Entity.register_method(m, get_entity_name)
