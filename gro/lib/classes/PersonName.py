from Builder import Method
from DatabaseClass import DatabaseClass, DatabaseAttr

from Person import Person
from Types import NameType, SourceSystem

import Registry
registry = Registry.get_registry()

class PersonName(DatabaseClass):
    primary = [
        DatabaseAttr('person', 'person_name', Person),
        DatabaseAttr('name_variant', 'person_name', NameType),
        DatabaseAttr('source_system', 'person_name', SourceSystem),
    ]
    slots = [
        DatabaseAttr('name', 'person_name', str)
    ]

registry.register_class(PersonName)

def get_names(self):
    s = registry.PersonNameSearch(self)
    s.set_person(self)
    return s.search()

Person.register_method(Method('get_names', PersonName, sequence=True), get_names)

# arch-tag: 9117b60d-11a9-4f3a-963d-cb078f5b6595
