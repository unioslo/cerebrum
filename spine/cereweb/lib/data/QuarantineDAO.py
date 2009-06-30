import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

Database = Utils.Factory.get("Database")

from lib.data.DTO import DTO
from lib.data.EntityDAO import EntityDAO
from lib.data.ConstantsDAO import ConstantsDAO

class QuarantineDAO(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()
        self.db = db
        self.co = ConstantsDAO(self.db)
        self.dao = EntityDAO(self.db)

    def create_dto(self, quarantine):
        cid = quarantine['creator_id']
        qid = quarantine['quarantine_type']
    
        creator = self.dao.get(cid, "account")
        quarantine_type = self.co.get_quarantine(qid)

        dto = DTO()
        dto.creator = creator
        dto.type_name = quarantine_type.name
        dto.type_description = quarantine_type.description

        dto.description = quarantine['description']
        dto.create_date = quarantine['create_date']
        dto.start_date = quarantine['start_date']
        dto.end_date = quarantine['end_date']
        dto.disable_until = quarantine['disable_until']
        return dto
