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

    def get_disks(self):
        hosts = self._get_hosts()
        disks = []
        disk_obj = self.disk
        for disk in disk_obj.search():
            disk_obj.clear()
            disk_obj.find(disk.disk_id)
            host = hosts[disk_obj.host_id]

            dto = DTO()
            dto.id = disk.disk_id
            dto.description = disk.description
            dto.path = disk.path
            dto.hostname = host.name
            disks.append(dto)
        return disks

    def _get_hosts(self):
        hosts = {}
        for host in self.host.search():
            hosts[host.host_id] = host
        return hosts

