from lib.data.MemberDTO import MemberDTO
import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
Constants = Utils.Factory.get("Constants")
Entity = Utils.Factory.get("Entity")

class MemberDAO(object):
    def __init__(self, db):
        self.db = db
        self.constants = Constants(self.db)

    def _find(self, id):
        member = self.member
        member.clear()

        member.find(id)
        self.needs_reset = True
        return member

    def get(self, id):
        member = Entity(self.db)
        member.find(id)
        data = MemberDTO()
        data.id = member.entity_id
        return data

    def get_dao(self, type_id):
        if not hasattr(self, 'member_factory'):
            from lib.data.MemberFactory import MemberFactory
            self.member_factory = MemberFactory(self.db)

        return self.member_factory.get_dao(type_id)
