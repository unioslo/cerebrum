from lib.data.DTO import DTO
from lib.data.AccountDAO import AccountDAO
from lib.data.ConstantsDAO import ConstantsDAO

class QuarantineDTO(DTO):
    def __init__(self, quarantine=None, db=None):
        if db is None or quarantine is None:
            return
        
        co = ConstantsDAO(db)
        ac = AccountDAO(db)

        cid = quarantine['creator_id']
        qid = quarantine['quarantine_type']
    
        creator = ac.shallow_get(cid)
        quarantine_type = co.get_quarantine(qid)

        self.creator = creator

        self.type_name = quarantine_type.name
        self.type_description = quarantine_type.description

        self.description = quarantine['description']
        self.create_date = quarantine['create_date']
        self.start_date = quarantine['start_date']
        self.end_date = quarantine['end_date']
        self.disable_until = quarantine['disable_until']

    __slots__ = [
        'type_name',
        'type_description',
        'description',
        'creator',
        'create_date',
        'start_date',
        'end_date',
        'disable_until',
    ]
