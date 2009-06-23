from lib.data.DTO import DTO
from lib.data.MemberDTO import MemberDTO

class GroupDTO(DTO):
    def __init__(self):
        self.name = ""
        self.description = ""
        self.notes = []
        self.spreads = []
        self.quarantines = []
        self.members = []
        self.type_name = 'group'
        self.has_owner = False
        self.expire_date = None

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
        'has_owner',
    ]
