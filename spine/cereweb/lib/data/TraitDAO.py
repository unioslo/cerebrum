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
        for key, value in entity.get_traits().items():
            dto = DTO()
            dto.name = key.str
            target_id = value['target_id']
            dto.target = EntityDAO.get(target_id)
            dto.number = value['numval']
            dto.string = value['strval']
            dto.date = value['date']
            traits.append(dto)
        return traits
