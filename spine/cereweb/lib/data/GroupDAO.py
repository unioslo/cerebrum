import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
Database = Utils.Factory.get("Database")
Group = Utils.Factory.get("Group")
PosixGroup = Utils.Factory.get("PosixGroup")
Constants = Utils.Factory.get("Constants")

from lib.data.MemberDAO import MemberDAO
from lib.data.GroupDTO import GroupDTO
from lib.data.QuarantineDTO import QuarantineDTO
from lib.data.NoteDTO import NoteDTO
from lib.data.ConstantsDTO import ConstantsDTO

def get(id):
    db = Database()
    dao = GroupDAO(db)
    return dao.get(id)

class GroupDAO(MemberDAO):
    def __init__(self, db):
        super(GroupDAO, self).__init__(db)
        self.member = Group(db)

    def get(self, id):
        group = self._find(id)
        data = GroupDTO(group, self.constants)
        data.is_posix = self.is_posix(group)
        data.posix_gid = self.get_posix_gid(group)
        data.visibility_name, data.visibility_value = self.get_visibility(group)
        data.members = self.get_members(group)
        data.quarantines = self.get_quarantines(group)
        data.notes = self.get_notes(group)
        data.spreads = self.get_spreads(group)
            
        return data

    def is_posix(self, group):
        pgroup = PosixGroup(self.db)

        try:
            pgroup.find(group.entity_id)
        except NotFoundError, e:
            pgroup = False

        self.pgroup = pgroup
        return pgroup and True

    def get_posix_gid(self, group):
        g = self.pgroup

        return g and g.posix_gid or -1
    
    def get_members(self, group):
        members = []
        for cerebrum_member in group.search_members(group_id=group.entity_id):
            member = self.get_member(cerebrum_member)
            members.append(member)
        return members

    def get_member(self, cerebrum_member):
        member_id = cerebrum_member['member_id']
        member_type = cerebrum_member['member_type']
        dao = self.get_dao(member_type)
        return dao.get(member_id)

    def get_visibility(self, group):
        code = self.constants.GroupVisibility(group.visibility)
        return code.description, code.str

    def get_quarantines(self, group):
        quarantines = []
        for q in group.get_entity_quarantine():
            quarantines.append(QuarantineDTO(q, self.db))
        return quarantines

    def get_notes(self, group):
        notes = []
        for note in group.get_notes():
            notes.append(NoteDTO(note, self.db))
        return notes

    def get_spreads(self, group):
        spreads = []
        for data in group.get_spread():
            sid = data['spread']
            spread_const = self.constants.Spread(sid)
            spread = ConstantsDTO(spread_const)
            spreads.append(spread)
        return spreads
