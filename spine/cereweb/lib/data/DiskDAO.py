import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

from lib.data.DTO import DTO

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")
Disk = Utils.Factory.get("Disk")
Host = Utils.Factory.get("Host")

class DiskDAO(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()

        self.db = db
        self.disk = Disk(self.db)
        self.host = Host(self.db)

    def get_disk(self, disk_id):
        self.disk.clear()
        self.disk.find(disk_id)

        dto = DTO()
        dto.id = disk_id
        dto.description = self.disk.description
        dto.path = self.disk.path
        dto.host = self._get_host(self.disk.host_id)
        return dto

    def get_disks(self):
        disks = []
        disk_obj = self.disk
        for disk in disk_obj.search():
            dto = self.get_disk(disk.disk_id)
            disks.append(dto)
        return disks

    def _get_host(self, host_id):
        self.host.clear()
        self.host.find(host_id)

        dto = DTO()
        dto.id = host_id
        dto.name = self.host.name
        dto.description = self.host.description
        return dto
        
    def _get_hosts(self):
        hosts = {}
        for host in self.host.search():
            hosts[host.host_id] = host
        return hosts

