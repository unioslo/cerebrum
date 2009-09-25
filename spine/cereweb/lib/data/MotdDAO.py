import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.Cereweb import CerewebMotd

Database = Utils.Factory.get("Database")

from lib.data.DTO import DTO
from lib.data.EntityDAO import EntityDAO

class MotdDAO(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()
        self.db = db
        self.dao = EntityDAO(self.db)

    def get(self, eid):
        motd = CerewebMotd(self.db)
        motd.find(eid)
        dto = DTO.from_obj(motd)
        dto.creator = self.dao.get(dto.creator, 'account')
        dto.id = dto.motd_id
        return dto

    def get_latest(self, num=None):
        motds = CerewebMotd(self.db).list_motd()
        motds.sort(key=lambda x: x.create_date, reverse=True)
        if num:
            motds = motds[:num]

        result = []
        for motd in motds:
            dto = DTO.from_row(motd)
            dto.id = dto.motd_id
            dto.creator = self.dao.get(dto.creator, 'account')
            result.append(dto)
        return result
