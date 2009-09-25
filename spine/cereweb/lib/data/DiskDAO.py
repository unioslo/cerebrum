import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

from lib.data.DTO import DTO
from lib.data.HostDAO import HostDAO

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")
Disk = Utils.Factory.get("Disk")

class DiskDAO(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()

        self.db = db
        self.disk = Disk(self.db)
        self.host_dao = HostDAO(self.db)
        self.constants = Constants(self.db)

    def get_disk(self, disk_id):
        self.disk.clear()
        self.disk.find(disk_id)

        dto = DTO()
        dto.id = disk_id
        dto.type_name = self._get_type_name()
        dto.description = self.disk.description
        dto.path = self.disk.path
        dto.host = self.host_dao.get_host(self.disk.host_id)
        return dto

    def get_disks(self):
        return self.search()

    def search(self, path=None, description=None):
        # The data set is small enough that we search within the strings.
        if path:
            path = "*" + path.strip("*") + "*"
        if description:
            description = "*" + description.strip("*") + "*"

        kwargs = {
            'path': path or None,
            'description': description or None,
        }

        disks = []
        for disk in self.disk.search(**kwargs):
            dto = self.get_disk(disk.disk_id)
            disks.append(dto)
        return disks
        
    def _get_type_name(self):
         return str(self.constants.entity_disk)
