import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.no.ntnu.bofhd_auth import BofhdAuth

Database = Utils.Factory.get("Database")
Entity = Utils.Factory.get("Entity")

from lib.data.DTO import DTO

class NoteDAO(object):
    def __init__(self, db=None):
        self.db = db or Database()
        self.auth = BofhdAuth(self.db)
        from lib.data.EntityFactory import EntityFactory
        self.factory = EntityFactory(self.db)

    def get(self, entity_id):
        entity = Entity(self.db)
        entity.find(entity_id)
        return self.create_from_entity(entity)

    def create_from_entity(self, entity):
        notes = []
        for note in entity.get_notes():
            dto = self.create_dto(note)
            notes.append(dto)
        return notes
        
    def create_dto(self, note):
        dto = DTO()

        cid = note['creator_id']
        creator = self.factory.get_entity(cid, 'account')

        dto.creator = creator

        dto.id = note['note_id']
        dto.description = note['description']
        dto.create_date = note['create_date']
        dto.subject = note['subject']
        dto.description = note['description']
        return dto
    
    def add(self, entity_id, subject, body=None):
        if not self.auth.can_add_note(self.db.change_by, entity_id):
            raise PermissionDenied("Not authorized to add note")

        entity = Entity(self.db)
        entity.find(entity_id)
        entity.add_note(self.db.change_by, subject, body)
    

    def delete(self, entity_id, note_id):
        if not self.auth.can_delete_note(self.db.change_by, entity_id):
            raise PermissionDenied("Not authorized to delete note")

        entity = Entity(self.db)
        entity.find(entity_id)
        entity.delete_note(self.db.change_by, note_id)
