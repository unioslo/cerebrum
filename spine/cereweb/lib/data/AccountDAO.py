from lib.data.MemberDAO import MemberDAO
from lib.data.MemberDTO import MemberDTO
import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")
Account = Utils.Factory.get("Account")

def get(id):
    return AccountDAO().get(id)

def get_by_name(name):
    return AccountDAO().get_by_name(name)

class AccountDAO(MemberDAO):
    def __init__(self, db=None):
        if db is None:
            db = Database()
        super(AccountDAO, self).__init__(db)
        self.member = Account(self.db)

    def shallow_get(self, id):
        member = self._find(id)
        return MemberDTO(member, self.constants)

    def get(self, id):
        member = self._find(id)
        data = MemberDTO(member, self.constants)

        data.owner = self.get_owner(member)
        data.has_owner = data.owner is not None

        return data

    def get_by_name(self, name):
        self.member.find_by_name(name)
        return MemberDTO(self.member, self.constants)

    def get_owner(self, member):
        member_id = member.owner_id
        member_type = member.owner_type
        dao = self.get_dao(member_type)
        return dao.get(member_id)

