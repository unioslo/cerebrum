import cerebrum_path
from Cerebrum import Utils
Constants = Utils.Factory.get("Constants")
Database = Utils.Factory.get("Database")
Entity = Utils.Factory.get("Entity")

from lib.data.AccountDAO import AccountDAO
from lib.data.GroupDAO import GroupDAO
from lib.data.OuDAO import OuDAO
from lib.data.PersonDAO import PersonDAO
from lib.data.HostDAO import HostDAO
from lib.data.DiskDAO import DiskDAO
from lib.data.EmailDomainDAO import EmailDomainDAO
from lib.data.EmailTargetDAO import EmailTargetDAO
from lib.data.EmailAddressDAO import EmailAddressDAO

class EntityFactory(object):
    def __init__(self, db=None):
        self.db = db or Database()
        self.c = Constants(self.db)

    def get_dao(self, type_id):
        if isinstance(type_id, self.c.EntityType):
            entity_type = type_id
        else:
            entity_type = self.c.EntityType(type_id)

        if entity_type == self.c.entity_group:
            return GroupDAO(self.db)
        if entity_type == self.c.entity_account:
            return AccountDAO(self.db)
        if entity_type == self.c.entity_ou:
            return OuDAO(self.db)
        if entity_type == self.c.entity_person:
            return PersonDAO(self.db)
        if entity_type == self.c.entity_host:
            return HostDAO(self.db)
        if entity_type == self.c.entity_disk:
            return DiskDAO(self.db)
        if entity_type == self.c.entity_email_target:
            return EmailTargetDAO(self.db)
        if entity_type == self.c.entity_email_domain:
            return EmailDomainDAO(self.db)
        if entity_type == self.c.entity_email_address:
            return EmailAddressDAO(self.db)
        raise NotImplementedError("I do not know how to create DAO for type %s" % entity_type)

    def get_dao_by_entity_id(self, entity_id):
        entity_type = self._get_type(entity_id)
        return self.get_dao(entity_type)

    def get_entity(self, entity_id, type_id=None):
        if type_id:
            dao = self.get_dao(type_id)
        else:
            dao = self.get_dao_by_entity_id(entity_id)

        return dao.get_entity(entity_id)

    def get_entity_by_name(self, type_name, entity_name):
        dao = self.get_dao(type_name)
        return dao.get_entity_by_name(entity_name)

    def _get_type(self, entity_id):
        entity = Entity(self.db)
        entity.find(entity_id)
        return entity.entity_type

