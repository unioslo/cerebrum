from lib.data.HostDTO import HostDTO
from lib.data.EmailTargetDTO import EmailTargetDTO
import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")
from Cerebrum.modules import Email

class HostDAO(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()

        self.db = db
        self.co = Constants(db)

    def get_email_servers(self):
        email = Email.EmailServer(self.db)
        for server in email.list_email_server_ext():
            yield HostDTO(server)
    
    def get_email_targets(self, entity_id):
        et = Email.EmailTarget(self.db)
        epa = Email.EmailPrimaryAddressTarget(self.db)
        ea = Email.EmailAddress(self.db)
        es = Email.EmailServer(self.db)

        try:
            et.find_by_target_entity(entity_id)
        except NotFoundError, e:
            return []

        es.find(et.email_server_id)
        epa.find(et.entity_id)
        ea.find(epa.email_primaddr_id)
        target_type = self.co.EmailTarget(et.email_target_type)
        target = EmailTargetDTO(et)
        target.type = target_type.str + "@" + es.name
        target.address = ea.get_address()
        return [target]
