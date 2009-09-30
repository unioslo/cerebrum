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
        self.host_dao = HostDAO(self.db)
        self.constants = Constants(self.db)

    def get(self, disk_id):
        disk = Disk(self.db)
        disk.find(disk_id)

        dto = DTO()
        dto.id = disk_id
        dto.type_name = self._get_type_name()
        dto.description = disk.description
        dto.path = disk.path
        dto.name = disk.path
        dto.host = self.host_dao.get(disk.host_id)

        return dto

    def search(self, path=None, description=None, host_id=None):
        # The data set is small enough that we search within the strings.
        if path:
            path = "*" + path.strip("*") + "*"
        if description:
            description = "*" + description.strip("*") + "*"

        kwargs = {
            'path': path or None,
            'description': description or None,
            'host_id': host_id or None,
        }

        disks = []
        for disk in Disk(self.db).search(**kwargs):
            dto = self.get(disk.fields.disk_id)
            disks.append(dto)
        return disks
        
    def _get_type_name(self):
         return str(self.constants.entity_disk)
