from lib.data.DTO import DTO

class EmailTargetDTO(DTO):
    def __init__(self, et=None):
        self.id = -1
        self.type = 'not set'
        self.alias = 'not set'
        self.address = 'not set'

        if et is None:
            return

        self.id = et.entity_id
        self.alias = et.email_target_alias
