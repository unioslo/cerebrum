from Builder import Method
from DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity
from Date import Date
from Types import QuarantineType

import Registry
registry = Registry.get_registry()

__all__ = ['EntityQuarantine']

table = 'entity_quarantine'

class EntityQuarantine(DatabaseClass):
    primary = [
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('type', table, QuarantineType),
    ]
    slots = [
        DatabaseAttr('creator', table, Entity),
        DatabaseAttr('description', table, str),
        DatabaseAttr('create_date', table, Date),
        DatabaseAttr('start_date', table, Date),
        DatabaseAttr('end_date', table, Date)
    ]

    db_attr_aliases = {
        table:{
            'entity':'entity_id',
            'type':'quarantine_type',
            'creator':'creator_id'
        }
    }

registry.register_class(EntityQuarantine)

def get_quarantines(self):
    s = registry.EntityQuarantineSearch(self)
    s.set_entity(self)
    return s.search()

Entity.register_method(Method('get_quarantines', EntityQuarantine, sequence=True), get_quarantines)

def is_quarantined(self):
    import Cerebrum.Entity
    import Cerebrum.QuarantineHandler
    import time

    account = Cerebrum.Entity.EntityQuarantine(self.get_database())
    account.entity_id = self.get_id()

    # koka fra bofhd
    quarantines = []      # TBD: Should the quarantine-check have a utility-API function?

    # FIXME: hente tid med sql pga sikkerhetshensyn
    now = self.get_database().DateFromTicks(time.time())
    for qrow in account.get_entity_quarantine():
        if (qrow['start_date'] <= now
            and (qrow['end_date'] is None or qrow['end_date'] >= now)
            and (qrow['disable_until'] is None 
            or qrow['disable_until'] < now)):
            # The quarantine found in this row is currently
            # active.
            quarantines.append(qrow['quarantine_type'])
    qh = Cerebrum.QuarantineHandler.QuarantineHandler(self.get_database(), quarantines)
    if qh.should_skip() or qh.is_locked():
        return True
    return False

Entity.register_method(Method('is_quarantined', bool, sequence=True), is_quarantined)
