import cerebrum_path
from Cerebrum import Utils
Constants = Utils.Factory.get("Constants")
Database = Utils.Factory.get("Database")
Entity = Utils.Factory.get("Entity")

from lib.data.AccountDAO import AccountDAO
from lib.data.GroupDAO import GroupDAO
from lib.data.PersonDAO import PersonDAO

class EntityFactory(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()

        self.db = db
        self.c = Constants(db)

    def get(self, type_id):
        if isinstance(type_id, self.c.EntityType):
            entity_type = type_id
        else:
            entity_type = self.c.EntityType(type_id)

        if entity_type == self.c.entity_group:
            return GroupDAO(self.db)
        if entity_type == self.c.entity_account:
            return AccountDAO(self.db)
        if entity_type == self.c.entity_person:
            return PersonDAO(self.db)
        raise NotImplementedError("I do not know how to create DAO for type %s" % entity_type)

    def get_dao_by_entity_id(self, entity_id):
        entity_type = self.get_type(entity_id)
        return self.get(entity_type)

    def get_type(self, entity_id):
        entity = Entity(self.db)
        entity.find(entity_id)
        return entity.entity_type

    def create(self, type_id, entity_id):
        dao = self.get(type_id)
        return dao.get_entity(entity_id)

    def create_by_name(self, type_name, entity_name):
        dao = self._create_dao_by_name(type_name)
        return dao.get_entity_by_name(entity_name)

    def _create_dao_by_name(self, type_name):
        type = self.c.EntityType(type_name)
        return self.get(type)

