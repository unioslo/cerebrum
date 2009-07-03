import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

Database = Utils.Factory.get("Database")

from lib.data.DTO import DTO
from lib.data.EntityDAO import EntityDAO

class NoteDAO(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()
        self.db = db
        self.dao = EntityDAO(self.db)

    def create_from_entity(self, entity):
        notes = []
        for note in entity.get_notes():
            dto = self.create_dto(note)
            notes.append(dto)
        return notes
        
    def create_dto(self, note):
        dto = DTO()

        cid = note['creator_id']
        creator = self.dao.get(cid, 'account')

        dto.creator = creator

        dto.id = note['note_id']
        dto.description = note['description']
        dto.create_date = note['create_date']
        dto.subject = note['subject']
        dto.description = note['description']
        return dto
