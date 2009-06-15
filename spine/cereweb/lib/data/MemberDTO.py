from lib.data.DTO import DTO

class MemberDTO(DTO):
    def __init__(self, member=None, constants=None):
        if member is None or constants is None:
            return

        self.id = member.entity_id
        self.name = member.get_name(constants.account_namespace)
        self.type_name = constants.entity_account.str
        
    __slots__ = [
        'id',
        'name',
        'type_name',
        'has_owner',
        'owner',
    ]
