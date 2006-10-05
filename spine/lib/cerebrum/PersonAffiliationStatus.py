from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from Types import PersonAffiliationType, CodeType
from SpineLib import Registry

registry = Registry.get_registry()

table = 'person_aff_status_code'
# This is really a code value table in Cerebrum, and
# should be CodeType, not DatabaseClass.
# However, CodeType does not handle this table because status_str
# is not globally unique. (status_str is unique per affiliation.)
# care should be taken so that entries are not edited run-time.
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
