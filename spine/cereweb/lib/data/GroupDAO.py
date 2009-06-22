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

def get(id, include_members=False):
    return GroupDAO().get(id, include_members)

def get_by_name(name, include_members=False):
    return GroupDAO().get_by_name(name, include_members)

def add_member(member_id, group_id):
    return GroupDAO().add_member(member_id, group_id)

class GroupDAO(MemberDAO):
    def __init__(self, db=None):
        if db is None:
            db = Database()

        super(GroupDAO, self).__init__(db)
        self.member = Group(db)

    def get(self, id, include_members=False):
        group = self._find(id)

        return self._create_dto(group, include_members)

    def populate(self, dto, group):
        dto.id = group.entity_id
        dto.description = group.description
        dto.name = group.get_name(self.constants.group_namespace)
        dto.description = group.description
        dto.type_name = self.constants.entity_group.str
        dto.is_expired = group.is_expired()
        dto.create_date = group.create_date
        dto.expire_date = group.expire_date
        
    def populate_posix(self, dto):
        pgroup = self._get_posix_group(dto.id)
        dto.is_posix = pgroup is not None
        dto.posix_gid = pgroup and pgroup.posix_gid or -1

    def populate_visibility(self, dto, group):
        code = self.constants.GroupVisibility(group.visibility)
        dto.visibility_name = code.description
        dto.visibility_value = code.str

    def get_shallow(self, id):
        group = self._find(id)

        data = GroupDTO()
        self.populate(data, group)
        self.populate_posix(data)
        self.populate_visibility(data, group)
        return data

    def get_by_name(self, name, include_members=False):
        self.member.clear()
        self.member.find_by_name(name)
        
        return self._create_dto(self.member, include_members)

    def add_member(self, member_id, group_id):
        group = self._find(group_id)
        if not group.has_member(member_id):
            group.add_member(member_id)

    def remove_member(self, group_id, member_id):
        group = self._find(group_id)
        if group.has_member(member_id):
            group.remove_member(member_id)


    def promote_posix(self, id):
        group = self._find(id)
        pgroup = PosixGroup(self.db)
        pgroup.populate(parent=group)
        pgroup.write_db()

    def demote_posix(self, id):
        pgroup = self._get_posix_group(id)
        pgroup.delete()

    def save(self, dto):
        group = self._find(dto.id)

        group.group_name = dto.name
        group.description = dto.description
        group.expire_date = dto.expire_date or None
        group.visibility = self.constants.GroupVisibility(dto.visibility_value)
        
        self._save_posix(dto)
        group.write_db()

    def delete(self, id):
        group = self._find(id)
        group.delete()

    def add(self, dto):
        group = Group(self.db)
        group.populate(
            self.db.change_by,
            self.constants.group_visibility_all,
            dto.name,
            dto.description,
            expire_date=dto.expire_date or None)
        group.write_db()
        dto.id = group.entity_id

    def _save_posix(self, dto):
        if not dto.is_posix:
            return

        pgroup = self._get_posix_group(dto.id)
        pgroup.posix_gid = dto.posix_gid
        pgroup.write_db()

    def _create_dto(self, group, include_members=False):
        data = GroupDTO()
        self.populate(data, group)
        self.populate_posix(data)
        self.populate_visibility(data, group)

        if include_members:
            data.members = self._get_members(group)
        data.quarantines = self._get_quarantines(group)
        data.notes = self._get_notes(group)
        data.spreads = self._get_spreads(group)
            
        return data

    def _get_posix_group(self, id):
        pgroup = PosixGroup(self.db)

        try:
            pgroup.find(id)
        except NotFoundError, e:
            return None

        return pgroup
        
    def _get_members(self, group):
        members = []
        for cerebrum_member in group.search_members(group_id=group.entity_id):
            member = self._get_member(cerebrum_member)
            members.append(member)
        return members

    def _get_member(self, cerebrum_member):
        member_id = cerebrum_member['member_id']
        member_type = cerebrum_member['member_type']
        dao = self.get_dao(member_type)
        return dao.get(member_id)

    def _get_quarantines(self, group):
        quarantines = []
        for q in group.get_entity_quarantine():
            quarantines.append(QuarantineDTO(q, self.db))
        return quarantines

    def _get_notes(self, group):
        notes = []
        for note in group.get_notes():
            notes.append(NoteDTO(note, self.db))
        return notes

    def _get_spreads(self, group):
        spreads = []
        for data in group.get_spread():
            sid = data['spread']
            spread_const = self.constants.Spread(sid)
            spread = ConstantsDTO(spread_const)
            spreads.append(spread)
        return spreads
