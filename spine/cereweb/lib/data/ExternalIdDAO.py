import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.bofhd.errors import PermissionDenied

Database = Utils.Factory.get("Database")

from lib.data.DTO import DTO
from lib.data.EntityDAO import EntityDAO

class ExternalIdDAO(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()
        self.db = db
        self.dao = EntityDAO(self.db)

    def create_from_entity(self, entity):
        external_ids = {}

        for external_id in entity.list_external_ids(entity_id=entity.entity_id):
            key = "%s:%s" % (external_id.id_type, external_id.external_id)

            if self.auth.can_read_external_id(self.db.change_by, entity, external_id.id_type):
                value = external_id.external_id
            else:
                value = "[No access]"

            if not key in external_ids:
                dto = DTO()
                dto.value = value
                dto.variant = ConstantsDAO(self.db).get_external_id_type(external_id.id_type)
                dto.source_systems = []
                external_ids[key] = dto

            dto = external_ids[key]
            source_system = ConstantsDAO(self.db).get_source_system(external_id.source_system)
            if not source_system in dto.source_systems:
                dto.source_systems.append(source_system)

        return external_ids.values()
