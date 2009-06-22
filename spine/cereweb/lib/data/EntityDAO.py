import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

Database = Utils.Factory.get("Database")
Entity = Utils.Factory.get("Entity")

from lib.data.EntityDTO import EntityDTO
from lib.data.MemberFactory import MemberFactory

def get(id):
    return EntityDAO().get(id)

class EntityDAO(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()

        self.db = db

    def get(self, id):
        entity = Entity(self.db)
        entity.find(id)
        
        data = MemberFactory(self.db).get(entity.entity_type, id)
        dto = EntityDTO()
        dto.id = data.id
        dto.name = data.name
        dto.type_name = data.type_name
        return dto
        

