from Builder import Method
from DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity
from Types import SourceSystem, AddressType

import Registry
registry = Registry.get_registry()

__all__ = ['EntityAddress']

table = 'entity_address'

# TODO: country

class EntityAddress(DatabaseClass):
    primary = [
        DatabaseAttr('entity', table,  Entity),
        DatabaseAttr('source_system', table, SourceSystem),
        DatabaseAttr('address_type', table, AddressType),
    ]
    slots = [
        DatabaseAttr('address_text', table, str, write=True), 
        DatabaseAttr('p_o_box', table, str, write=True),
        DatabaseAttr('postal_number', table, str, write=True),
        DatabaseAttr('city', table, str, write=True),
        DatabaseAttr('country', table, str, write=True)
    ]

    db_attr_aliases = {
        table:{'entity':'entity_id'}
    }

registry.register_class(EntityAddress)

def get_addresses(self):
    s = registry.EntityAddressSearch(self)
    s.set_entity(self)
    return s.search()

Entity.register_method(Method('get_addresses', [EntityAddress]), get_addresses)

# arch-tag: 28c9c7fa-3191-4c48-b48c-e0f63c796f43
