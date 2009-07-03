import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

from lib.data.EntityDTO import EntityDTO

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")
Entity = Utils.Factory.get("Entity")

class EntityDAO(object):
    def __init__(self, db=None, EntityType=None):
        if db is None:
            db = Database()

        self.db = db
        self.constants = Constants(self.db)
        
        if EntityType is not None:
            self.entity = EntityType(self.db)

    def get(self, entity_id, entity_type=None):
        if entity_type is None:
            entity = Entity(self.db)
            entity.find(entity_id)
            entity_type = entity.entity_type
        
        from lib.data.EntityFactory  import EntityFactory
        return EntityFactory(self.db).create(entity_type, entity_id)

    def get_by_name(self, name):
        raise NotImplementedError("This method should be overloaded.")

    def get_entity(self, entity_id):
        entity = self._find(entity_id)
        return self._create_entity_dto(entity)

    def get_entity_by_name(self, name):
        entity = self._find_by_name(name)
        return self._create_entity_dto(entity)

    def exists(self, entity_id):
        try:
            self.get(entity_id)
        except NotFoundError, e:
            return False
        return True

    def suggest_usernames(self, entity_id):
        """FIXME: Where should I be?"""

    def _get_name(self, entity):
        return "Unknown"

    def _get_type_id(self):
        raise NotImplementedError, "This method must be overloaded."

    def _get_type_name(self):
        return 'entity'

    def _find(self, entity_id):
        self.entity.clear()
        self.entity.find(entity_id)
        return self.entity

    def _find_by_name(self, name):
        self.entity.clear()
        self.entity.find_by_name(name)
        return self.entity

    def _create_entity_dto(self, entity):
        dto = EntityDTO()
        dto.id = entity.entity_id
        dto.name = self._get_name(entity)
        dto.type_name = self._get_type_name()
        dto.type_id = self._get_type_id()
        return dto
