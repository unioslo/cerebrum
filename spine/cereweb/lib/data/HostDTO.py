from lib.data.DTO import DTO

class HostDTO(DTO):
    def __init__(self, host=None):
        if host is not None:
            self.id = host.server_id
            self.name = host.name
            self.server_type = host.server_type

    __slots__ = [
        'id',
        'name',
        'server_type',
    ]
