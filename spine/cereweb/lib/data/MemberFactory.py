import cerebrum_path
from Cerebrum import Utils
Constants = Utils.Factory.get("Constants")
Database = Utils.Factory.get("Database")

from lib.data.AccountDAO import AccountDAO
from lib.data.GroupDAO import GroupDAO
from lib.data.PersonDAO import PersonDAO

class MemberFactory(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()

        self.db = db
        self.c = Constants(db)

    def get(self, type_id, entity_id):
        return self.get_dao(type_id).get(entity_id)

    def get_dao_by_name(self, type_name):
        type = self.c.EntityType(type_name)
        return self.get_dao(type)

    def get_dao(self, type_id):
        if type_id == self.c.entity_group:
            return GroupDAO(self.db)
        if type_id == self.c.entity_account:
            return AccountDAO(self.db)
        if type_id == self.c.entity_person:
            return PersonDAO(self.db)
            
        return None
