import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules import Email

from lib.data.DTO import DTO
from lib.data.HostDTO import HostDTO
from lib.data.EmailTargetDTO import EmailTargetDTO

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")
Host = Utils.Factory.get("Host")

class HostDAO(object):
    def __init__(self, db=None):
        self.db = db or Database()
        self.constants = Constants(self.db)
        self.host = Host(self.db)

    def get_host(self, host_id):
        self.host.clear()
        self.host.find(host_id)

        dto = DTO()
        dto.id = host_id
        dto.name = self.host.name
        dto.type_name = self._get_type_name()
        dto.description = self.host.description
        return dto

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

        try:
            es.find(et.email_server_id)
        except NotFoundError, e:
            return []

        epa.find(et.entity_id)
        ea.find(epa.email_primaddr_id)
        target_type = self.constants.EmailTarget(et.email_target_type)
        target = EmailTargetDTO(et)
        target.type = target_type.str + "@" + es.name
        target.address = ea.get_address()
        return [target]

    def get_hosts(self):
        return self.search()

    def search(self, name=None, description=None):
        # The data set is small enough that we search within the strings.
        if name:
            name = "*" + name.strip("*") + "*"
        if description:
            description = "*" + description.strip("*") + "*"
        kwargs = {
            'name': name or None,
            'description': description or None,
        }

        hosts = []
        for host in self.host.search(**kwargs):
            dto = DTO.from_row(host)
            dto.id = dto.host_id
            dto.type_name = self._get_type_name()
            hosts.append(dto)
        return hosts

    def _get_type_name(self):
         return str(self.constants.entity_host)
