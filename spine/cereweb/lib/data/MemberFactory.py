import cerebrum_path
from Cerebrum import Utils
Constants = Utils.Factory.get("Constants")

from lib.data.AccountDAO import AccountDAO
from lib.data.GroupDAO import GroupDAO
from lib.data.PersonDAO import PersonDAO

class MemberFactory(object):
    def __init__(self, db):
        self.db = db
        self.c = Constants(db)

    def get_dao(self, type_id):
        if type_id == self.c.entity_group:
            return GroupDAO(self.db)
        if type_id == self.c.entity_account:
            return AccountDAO(self.db)
        if type_id == self.c.entity_person:
            return PersonDAO(self.db)
            
        return None
