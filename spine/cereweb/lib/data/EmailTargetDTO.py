from lib.data.DTO import DTO

class EmailTargetDTO(DTO):
    def __init__(self, et=None):
        if et is None:
            return

        self.id = et.entity_id
        self.alias = et.email_target_alias

    __slots__ = [
        'id',
        'type',
        'alias',
        'address',
    ]
