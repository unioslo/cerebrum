import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")
Person = Utils.Factory.get("Person")

from lib.data.AffiliationDAO import AffiliationDAO
from lib.data.EntityDAO import EntityDAO
from lib.data.EntityDTO import EntityDTO

class PersonDAO(EntityDAO):
    def __init__(self, db=None):
        super(PersonDAO, self).__init__(db, Person)

    def get(self, id):
        raise NotImplementedError("TODO: This method hasn't been implemented yet.")

    def get_affiliations(self, id):
        try:
            person = self._find(id)
        except NotFoundError, e:
            return []

        return AffiliationDAO(self.db).create_from_person_affiliations(person.get_affiliations())

    def _get_name(self, entity):
        return entity.get_name(self.constants.system_cached, self.constants.name_full)

    def _get_type_name(self):
        return self.constants.entity_person.str
