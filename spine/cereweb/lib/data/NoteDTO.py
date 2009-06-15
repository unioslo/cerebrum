from lib.data.DTO import DTO
from lib.data.AccountDAO import AccountDAO
from lib.data.ConstantsDAO import ConstantsDAO

class NoteDTO(DTO):
    def __init__(self, note=None, db=None):
        if db is None or note is None:
            return
        
        co = ConstantsDAO(db)
        ac = AccountDAO(db)

        cid = note['creator_id']
        creator = ac.shallow_get(cid)

        self.creator = creator

        self.id = note['note_id']
        self.description = note['description']
        self.create_date = note['create_date']
        self.subject = note['subject']
        self.description = note['description']

    __slots__ = [
        'id',
        'create_date',
        'creator',
        'subject',
        'description',
    ]
