from lib.data.DTO import DTO

class GroupDTO(DTO):
    def __init__(self):
        self.name = ""
        self.description = ""
        self.notes = []
        self.spreads = []
        self.traits = []
        self.quarantines = []
        self.members = []
        self.type_name = 'group'
        self.has_owner = False
        self.expire_date = None
