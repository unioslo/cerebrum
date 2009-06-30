from lib.data.DTO import DTO

class AccountDTO(DTO):
    def __init__(self):
        self.id = -1
        self.name = ""
        self.type_name = 'account'

        self.owner = None
        self.creator = None
        self.create_date = None

        self.is_quarantined = False

        self.expire_date = None
        self.is_expired = False

        self.is_posix = False
        self.posix_uid = -1
        self.primary_group = None
        self.groups = []
        self.gecos = None
        self.shell = None

        self.affiliations = []
        self.quarantines = []
        self.spreads = []
        self.notes = []
