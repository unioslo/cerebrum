import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.no.uio.bofhd_auth import BofhdAuth

from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.DTO import DTO
from lib.data.EntityDTO import EntityDTO

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")
Entity = Utils.Factory.get("Entity")

class EntityDAO(object):
    def __init__(self, db=None, EntityType=None):
        if db is None:
            db = Database()

        self.db = db
        self.constants = Constants(self.db)
        self.auth = BofhdAuth(self.db)
        
        if EntityType is not None:
            self.entity = EntityType(self.db)

    def get(self, entity_id, entity_type=None):
        if entity_type is None:
            entity = Entity(self.db)
            entity.find(entity_id)
            entity_type = entity.entity_type
        
        from lib.data.EntityFactory  import EntityFactory
        return EntityFactory(self.db).create(entity_type, entity_id)

    def get_by_name(self, name):
        raise NotImplementedError("This method should be overloaded.")

    def get_entity(self, entity_id):
        entity = self._find(entity_id)
        return self._create_entity_dto(entity)

    def get_entity_by_name(self, name):
        entity = self._find_by_name(name)
        return self._create_entity_dto(entity)

    def exists(self, entity_id):
        try:
            self.get(entity_id)
        except NotFoundError, e:
            return False
        return True

    def add_external_id(self, entity_id, external_id, external_id_type):
        source = self.constants.AuthoritativeSystem("Manual")
        id_type = self.constants.EntityExternalId(external_id_type)

        entity = self._find(entity_id)
        entity.affect_external_id(source, id_type)
        entity.populate_external_id(source, id_type, external_id)
        entity.write_db()

    def remove_external_id(self, entity_id, external_id_type):
        source = self.constants.AuthoritativeSystem("Manual")
        id_type = self.constants.EntityExternalId(external_id_type)

        entity = self._find(entity_id)
        entity._delete_external_id(source, id_type)

    def add_spread(self, entity_id, spread):
        spread_type = self.constants.Spread(spread)

        entity = self._find(entity_id)
        entity.add_spread(spread_type)
        entity.write_db()

    def remove_spread(self, entity_id, spread):
        spread_type = self.constants.Spread(spread)

        entity = self._find(entity_id)
        entity.delete_spread(spread_type)
        entity.write_db()

    def suggest_usernames(self, entity_id):
        """FIXME: Where should I be?"""

    def _get_name(self, entity):
        return "Unknown"

    def _get_type_id(self):
        raise NotImplementedError, "This method must be overloaded."

    def _get_type_name(self):
        return 'entity'

    def _find(self, entity_id):
        if not hasattr(self, 'entity'):
            raise ProgrammingException(
                "Can't access entity attribute.  Most likely you're not using a valid subclass of EntityDAO.")
        self.entity.clear()
        self.entity.find(entity_id)
        return self.entity

    def _find_by_name(self, name):
        self.entity.clear()
        self.entity.find_by_name(name)
        return self.entity

    def _create_entity_dto(self, entity):
        dto = EntityDTO()
        dto.id = entity.entity_id
        dto.name = self._get_name(entity)
        dto.type_name = self._get_type_name()
        dto.type_id = self._get_type_id()
        return dto

    def _get_contacts(self, entity):
        contacts = {}

        for contact in entity.get_contact_info():
            key = "%s:%s" % (contact.contact_type, contact.contact_value)
            if not key in contacts:
                dto = DTO()
                dto.value = contact.contact_value
                dto.variant = ConstantsDAO(self.db).get_contact_type(contact.contact_type)
                dto.source_systems = []
                contacts[key] = dto

            dto = contacts[key]
            source_system = ConstantsDAO(self.db).get_source_system(contact.source_system)
            source_system.preferance = contact.contact_pref
            if not source_system in dto.source_systems:
                dto.source_systems.append(source_system)
        return contacts.values()

    def _get_addresses(self, entity):
        addresses = {}

        for address in entity.get_entity_address():
            key = "%s:%s.%s.%s.%s.%s" % (
                address.address_type,
                address.address_text,
                address.p_o_box,
                address.postal_number,
                address.city,
                address.country)
            if not key in addresses:
                dto = DTO()
                dto.value = DTO()
                dto.value.address_text = address.address_text
                dto.value.p_o_box = address.p_o_box
                dto.value.postal_number = address.postal_number
                dto.value.city = address.city
                dto.value.country = address.country
                dto.variant = ConstantsDAO(self.db).get_address_type(address.address_type)
                dto.source_systems = []
                addresses[key] = dto

            dto = addresses[key]
            source_system = ConstantsDAO(self.db).get_source_system(address.source_system)
            if not source_system in dto.source_systems:
                dto.source_systems.append(source_system)
        return addresses.values()

    def _get_external_ids(self, entity):
        external_ids = {}

        for external_id in entity.list_external_ids(entity_id=entity.entity_id):
            key = "%s:%s" % (external_id.id_type, external_id.external_id)
            if not key in external_ids:
                dto = DTO()
                dto.value = external_id.external_id
                dto.variant = ConstantsDAO(self.db).get_external_id_type(external_id.id_type)
                dto.source_systems = []
                external_ids[key] = dto

            dto = external_ids[key]
            source_system = ConstantsDAO(self.db).get_source_system(external_id.source_system)
            if not source_system in dto.source_systems:
                dto.source_systems.append(source_system)
        return external_ids.values()

    def _get_spreads(self, entity):
        spreads = []
        spread_dao = ConstantsDAO(self.db)
        for (spread_id,) in entity.get_spread():
            dto = spread_dao.get_spread(spread_id)
            spreads.append(dto)
        return spreads

