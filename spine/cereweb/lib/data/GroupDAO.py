import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
Database = Utils.Factory.get("Database")
Group = Utils.Factory.get("Group")
PosixGroup = Utils.Factory.get("PosixGroup")

from lib.data.ConstantsDTO import ConstantsDTO
from lib.data.DTO import DTO
from lib.data.EntityDAO import EntityDAO
from lib.data.EntityDTO import EntityDTO
from lib.data.GroupDTO import GroupDTO
from lib.data.NoteDAO import NoteDAO
from lib.data.QuarantineDAO import QuarantineDAO
from lib.data.TraitDAO import TraitDAO

class GroupDAO(EntityDAO):
    def __init__(self, db=None):
        super(GroupDAO, self).__init__(db, Group)

    def get(self, id, include_extra=False):
        group = self._find(id)

        return self._create_dto(group, include_extra)

    def get_by_name(self, name, include_extra=False):
        group = self._find_by_name(name)
        
        return self._create_dto(group, include_extra)

    def get_shallow(self, id):
        group = self._find(id)

        dto = GroupDTO()
        self._populate(dto, group)
        self._populate_posix(dto, group)
        self._populate_visibility(dto, group)
        return dto

    def get_entities_for_account(self, account_id):
        for row in self.entity.search(member_id=account_id):
            dto = EntityDTO()
            dto.id = row.group_id
            dto.name = row.name
            dto.type_name = self._get_type_name()
            yield dto

    def get_groups_for(self, member_id):
        groups = []
        direct_groups = self.entity.search(member_id=member_id)
        for group in self.entity.search(member_id=member_id, indirect_members=True):
            dto = self._create_dto_from_search(group)
            dto.direct = group in direct_groups
            groups.append(dto)
        return groups

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

    def _get_name(self, entity):
        return entity.get_name(self.constants.group_namespace)

    def _get_type_name(self):
         return self.constants.entity_group.str

    def _create_dto(self, group, include_extra=False):
        dto = GroupDTO()
        self._populate(dto, group)
        self._populate_posix(dto, group)
        self._populate_visibility(dto, group)

        if include_extra:
            dto.members = self._get_members(group)
            dto.quarantines = self._get_quarantines(group)
            dto.notes = self._get_notes(group)
            dto.spreads = self._get_spreads(group)
            dto.traits = self._get_traits(group)
            
        return dto

    def _create_dto_from_search(self, result):
        dto = DTO()
        dto.id = result.group_id
        dto.name = result.name
        dto.type_name = self._get_type_name()
        dto.description = result.description
        dto.is_posix = self._is_posix(result.group_id)
        
        return dto

    def _populate(self, dto, group):
        dto.id = group.entity_id
        dto.description = group.description
        dto.name = self._get_name(group)
        dto.description = group.description
        dto.type_name = self._get_type_name()
        dto.is_expired = group.is_expired()
        dto.create_date = group.create_date
        dto.expire_date = group.expire_date

    def _is_posix(self, group_id):
        return self._get_posix_group(group_id) is not None
        
    def _populate_posix(self, dto, group):
        pgroup = self._get_posix_group(group.entity_id)
        dto.is_posix = pgroup is not None
        dto.posix_gid = pgroup and pgroup.posix_gid or -1

    def _populate_visibility(self, dto, group):
        code = self.constants.GroupVisibility(group.visibility)
        dto.visibility_name = code.description
        dto.visibility_value = code.str

    def _save_posix(self, dto):
        if not dto.is_posix:
            return

        pgroup = self._get_posix_group(dto.id)
        pgroup.posix_gid = dto.posix_gid
        pgroup.write_db()

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
        from lib.data.EntityFactory  import EntityFactory
        return EntityFactory(self.db).create(member_type, member_id)

    def _get_quarantines(self, group):
        quarantine_dao = QuarantineDAO(self.db)
        quarantines = []
        for q in group.get_entity_quarantine():
            dto = quarantine_dao.create_dto(q)
            quarantines.append(dto)
        return quarantines

    def _get_notes(self, group):
        note_dao = NoteDAO(self.db)
        notes = []
        for note in group.get_notes():
            dto = note_dao.create_dto(note)
            notes.append(dto)
        return notes

    def _get_spreads(self, group):
        spreads = []
        for data in group.get_spread():
            sid = data['spread']
            spread_const = self.constants.Spread(sid)
            spread = ConstantsDTO(spread_const)
            spreads.append(spread)
        return spreads

    def _get_traits(self, group):
        return TraitDAO(self.db).create_from_entity(group)
