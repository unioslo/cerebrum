from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from Types import PersonAffiliationType
from SpineLib import Registry

registry = Registry.get_registry()

table = 'person_aff_status_code'
class PersonAffiliationStatus(DatabaseClass):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('affiliation', table, PersonAffiliationType),
        DatabaseAttr('name', table, str),
        DatabaseAttr('description', table, str)
    )
    db_attr_aliases = {
        table : {
            'id' : 'status',
            'name' : 'status_str'
        }
    }

registry.register_class(PersonAffiliationStatus)

# arch-tag: f049a00c-5524-11da-8986-57d9d05763c0
