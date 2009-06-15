from lib.data.MemberDAO import MemberDAO
from lib.data.MemberDTO import MemberDTO
import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")
Person = Utils.Factory.get("Person")

def get(id):
    db = Database()
    dao = PersonDAO(db)
    return dao.get(id)

class PersonDAO(MemberDAO):
    def __init__(self, db):
        super(PersonDAO, self).__init__(db)
        self.member = Person(self.db)

    def get(self, id):
        member = self._find(id)
        data = MemberDTO()
        data.id = member.entity_id
        data.name = member.get_name(self.constants.system_cached, self.constants.name_full)
        data.type_name = self.constants.entity_person.str
        data.has_owner = False
        return data
