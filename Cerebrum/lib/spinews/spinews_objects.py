class Group(object): 
    def __init__(self):
        self.quarantines = []
        self.members = []
        self.name = None
        self.posix_gid = None

class Account(object):
    def __init__(self):
        self.quarantines = []
        self.name = None
        self.passwd = None
        self.homedir = None
        self.home = None
        self.disk_path = None
        self.disk_host = None
        self.gecos = None
        self.full_name = None
        self.shell = None
        self.shell_name = None
        self.posix_uid = None
        self.posix_gid = None
        self.primary_group = None
        self.owner_id = None
        self.owner_group_name = None
        self.primary_affiliation = None
        self.primary_ou_id = None

class Ou(object):
    def __init__(self):
        self.quarantines = []
        self.id = None
        self.name = None
        self.acronym = None
        self.short_name = None
        self.display_name = None
        self.sort_name = None
        self.parent_id = None
        self.email = None
        self.url = None
        self.phone = None
        self.post_address = None
        self.stedkode = None
        self.parent_stedkode = None
        
class Alias(object):
    def __init__(self):
        self.local_part = None
        self.domain = None
        self.primary_address_local_part = None
        self.primary_address_domain = None
        self.address_id = None
        self.primary_address_id = None
        self.server_name = None
        self.account_id = None
        self.account_name = None

class Homedir(object):
    def __init__(self):
        self.homedir_id = None
        self.disk_path = None
        self.home = None
        self.homedir = None
        self.account_name = None
        self.posix_uid = None
        self.posix_gid = None

class Person(object):
    def __init__(self):
        self.quarantines = []
        self.affiliations = []
        self.traits = []
        self.id = None
        self.export_id = None
        self.type = None
        self.birth_date = None
        self.nin = None
        self.first_name = None
        self.last_name = None
        self.full_name = None
        self.display_name = None
        self.work_title = None
        self.primary_account = None
        self.primary_account_name = None
        self.primary_account_password = None
        self.email = None
        self.address_text = None
        self.city = None
        self.postal_number = None
        self.phone = None
        self.url = None

