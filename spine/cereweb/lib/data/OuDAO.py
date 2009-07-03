import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

Database = Utils.Factory.get("Database")
OU = Utils.Factory.get("OU")

from lib.data.EntityDAO import EntityDAO

class OuDAO(EntityDAO):
    def __init__(self, db=None):
        super(OuDAO, self).__init__(db, OU)

    def _get_type_name(self):
        return self.constants.entity_ou.str

    def _get_type_id(self):
        return int(self.constants.entity_ou)

    def _get_name(self, entity):
        return entity.name
