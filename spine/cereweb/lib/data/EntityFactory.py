import cerebrum_path
from Cerebrum import Utils
Constants = Utils.Factory.get("Constants")
Database = Utils.Factory.get("Database")

from lib.data.AccountDAO import AccountDAO
from lib.data.GroupDAO import GroupDAO
from lib.data.PersonDAO import PersonDAO

class EntityFactory(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()

        self.db = db
        self.c = Constants(db)

    def create(self, type_id, entity_id):
        dao = self._create_dao(type_id)
        return dao.get_entity(entity_id)

    def create_by_name(self, type_name, entity_name):
        dao = self._create_dao_by_name(type_name)
        return dao.gen_entity_by_name(entity_name)

    def _create_dao_by_name(self, type_name):
        type = self.c.EntityType(type_name)
        return self._create_dao(type)

    def _create_dao(self, type_id):
        if type_id == self.c.entity_group or type_id == self.c.entity_group.str:
            return GroupDAO(self.db)
        if type_id == self.c.entity_account or type_id == self.c.entity_account.str:
            return AccountDAO(self.db)
        if type_id == self.c.entity_person or type_id == self.c.entity_person.str:
            return PersonDAO(self.db)
            
        raise NotImplementedError("I do not know how to create DAO for type %s" % type_id)
