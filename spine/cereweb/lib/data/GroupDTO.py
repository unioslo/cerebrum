from lib.data.DTO import DTO
from lib.data.MemberDTO import MemberDTO

class GroupDTO(DTO):
    def __init__(self, group=None, constants=None):
        self.notes = []
        self.spreads = []
        self.quarantines = []
        self.type_name = 'group'

        if group is None or constants is None:
            return

        self.id = group.entity_id
        self.description = group.description
        self.name = group.get_name(constants.group_namespace)
        self.description = group.description
        self.type_name = constants.entity_group.str
        self.is_expired = group.is_expired()
        self.create_date = group.create_date
        self.expire_date = group.expire_date

    __slots__ = [
        'id',
        'name',
        'description',
        'type_name',
        'is_expired',
        'is_posix',
        'posix_gid',
        'create_date',
        'expire_date',
        'members',
        'visibility_name',
        'visibility_value',
        'quarantines',
        'notes',
        'spreads',
        'history',
    ]
