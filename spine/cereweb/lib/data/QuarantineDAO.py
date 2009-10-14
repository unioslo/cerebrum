import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

Database = Utils.Factory.get("Database")

from lib.data.DTO import DTO
from lib.data.ConstantsDAO import ConstantsDAO

class QuarantineDAO(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()
        self.db = db
        self.co = ConstantsDAO(self.db)
        from lib.data.EntityFactory import EntityFactory
        self.factory = EntityFactory(self.db)

    def create_from_entity(self, entity):
        quarantines = []
        for q in entity.get_entity_quarantine():
            dto = self.create_dto(q)
            dto.entity_id = entity.entity_id
            quarantines.append(dto)
        return quarantines

    def create_dto(self, quarantine):
        cid = quarantine['creator_id']
        qid = quarantine['quarantine_type']
    
        creator = self.factory.get_entity(cid, "account")
        quarantine_type = self.co.get_quarantine(qid)

        dto = DTO()
        dto.creator = creator
        dto.type_id = qid
        dto.type_name = quarantine_type.name
        dto.type_description = quarantine_type.description

        dto.description = quarantine['description']
        dto.create_date = quarantine['create_date']
        dto.start_date = quarantine['start_date']
        dto.end_date = quarantine['end_date']
        dto.disable_until = quarantine['disable_until']
        return dto
