from Builder import Method
from DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity
from Types import SourceSystem, ContactInfoType

import Registry
registry = Registry.get_registry()

__all__ = ['EntityContactInfo']

table = 'entity_contact_info'

class EntityContactInfo(DatabaseClass):
    primary = [
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('source_system', table, SourceSystem),
        DatabaseAttr('contact_type', table, ContactInfoType),
        DatabaseAttr('contact_pref', table, int)
    ]
    slots = [
        DatabaseAttr('contact_value', table, str, write=True),
        DatabaseAttr('description', table, str, write=True)
    ]

    db_attr_aliases = {
        table:{'entity':'entity_id'}
    }

registry.register_class(EntityContactInfo)

def get_contact_info(self):
    s = registry.EntityContactInfoSearch(self)
    s.set_entity(self)
    return s.search()

Entity.register_method(Method('get_contact_info', EntityContactInfo, sequence=True), get_contact_info)

# arch-tag: 6de264a4-7076-4d31-8084-742a0d5cfdac
