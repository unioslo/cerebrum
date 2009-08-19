import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")

from lib.data.DTO import DTO
from lib.data.EntityDAO import EntityDAO

class TraitDAO(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()
        self.db = db
        self.constants = Constants(self.db)
        self.dao = EntityDAO(self.db)

    def create_from_entity(self, entity):
        traits = []
        for trait_type, data in entity.get_traits().items():
            dto = self.create_dto(trait_type, data)
            traits.append(dto)
        return traits

    def create_dto(self, trait_type, data):
        dto = DTO()
        dto.name = trait_type.str
        target_id = data['target_id']
        dto.target = EntityDAO().get(target_id)
        dto.number = data['numval']
        dto.string = data['strval']
        dto.date = data['date']
        return dto
