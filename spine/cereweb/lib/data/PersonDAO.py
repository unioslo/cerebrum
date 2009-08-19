import cerebrum_path
from mx import DateTime
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")
Person = Utils.Factory.get("Person")

from lib.data.AccountDAO import AccountDAO
from lib.data.AffiliationDAO import AffiliationDAO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.EntityDAO import EntityDAO
from lib.data.QuarantineDAO import QuarantineDAO
from lib.data.NoteDAO import NoteDAO
from lib.data.TraitDAO import TraitDAO
from lib.data.EntityDTO import EntityDTO
from lib.data.DTO import DTO

class PersonDAO(EntityDAO):
    def __init__(self, db=None):
        super(PersonDAO, self).__init__(db, Person)

    def get(self, id, include_extra=False):
        person = self._find(id)

        return self._create_dto(person, include_extra)

    def get_accounts(self, id):
        person = self._find(id)
        account_ids = [a.account_id for a in person.get_accounts()]
        account_dtos = AccountDAO(self.db).get_accounts(*account_ids)
        primary_id = person.get_primary_account()
        for dto in account_dtos:
            dto.is_primary = dto.id == primary_id

        return account_dtos

    def get_affiliations(self, id):
        try:
            person = self._find(id)
        except NotFoundError, e:
            return []

        return self._get_affiliations(person)

    def create(self, dto):
        entity = self.entity
        entity.clear()
        entity.populate(
            dto.birth_date,
            self.constants.Gender(dto.gender.id),
            dto.description)
        entity.affect_names(
            self.constants.system_manual,
            self.constants.name_first,
            self.constants.name_last)
        entity.populate_name(
            self.constants.name_first,
            dto.first_name)
        entity.populate_name(
            self.constants.name_last,
            dto.last_name)
        entity.write_db()

        dto.id = entity.entity_id
           
    def delete(self, person_id):
        person = self._find(person_id)
        dto = self._create_dto(person, False)
        person.delete()
        return dto

    def add_affiliation_status(self, person_id, ou, status):
        person = self._find(person_id)
        source = self.constants.AuthoritativeSystem("Manual")
        status = self.constants.PersonAffStatus(status)
        person.add_affiliation(ou, status.affiliation, source, status)
        person.write_db()

    def remove_affiliation_status(self, person_id, ou, status, ss):
        person = self._find(person_id)
        source = self.constants.AuthoritativeSystem(ss)
        status = self.constants.PersonAffStatus(status)
        person.delete_affiliation(ou, status.affiliation, source)
        person.write_db()

    def add_birth_no(self, person_id, birth_no):
        person = self._find(person_id)
        source_system = self.constants.AuthoritativeSystem("Manual")
        const = self.constants.EntityExternalId("NO_BIRTHNO")
        person.affect_external_id(source_system, const)
        person.populate_external_id(source_system, const, birth_no)

        person.write_db()

    def add_name(self, person_id, name_type, name):
        entity = self._find(person_id)

        name_type = self.constants.PersonName(name_type)

        entity.affect_names(self.constants.system_manual, name_type)
        entity.populate_name(name_type, name)
        entity.write_db()

    def remove_name(self, person_id, name_type, source_system):
        entity = self._find(person_id)

        name_type = self.constants.PersonName(name_type)
        source = self.constants.AuthoritativeSystem(source_system)

        entity._delete_name(source, name_type)
        
    def save(self, dto):
        entity = self._find(dto.id)
        entity.gender = self.constants.Gender(dto.gender.id)
        entity.birth_date = dto.birth_date
        entity.description = dto.description
        entity.deceased_date = dto.deceased_date

        entity.write_db()

    def _get_affiliations(self, entity):
        return AffiliationDAO(self.db).create_from_person_affiliations(entity.get_affiliations(include_deleted=True))

    def _get_name(self, entity):
        return entity.get_name(self.constants.system_cached, self.constants.name_full)

    def _get_names(self, entity):
        names = {}

        for name in entity.get_all_names():
            key = "%s:%s" % (name.name_variant, name.name)
            if not key in names:
                dto = DTO()
                dto.value = name.name
                dto.variant = ConstantsDAO(self.db).get_name_type(name.name_variant)
                dto.source_systems = []
                names[key] = dto

            dto = names[key]
            source_system = ConstantsDAO(self.db).get_source_system(name.source_system)
            if not source_system in dto.source_systems:
                dto.source_systems.append(source_system)
        return names.values()

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

    def _get_type_name(self):
        return self.constants.entity_person.str

    def _get_type_id(self):
        return int(self.constants.entity_person)

    def _create_dto(self, person, include_extra):
        dto = DTO()
        self._populate(dto, person)
        if include_extra:
            dto.quarantines = QuarantineDAO(self.db).create_from_entity(person)
            dto.affiliations = self._get_affiliations(person)
            dto.names = self._get_names(person)
            dto.external_ids = self._get_external_ids(person)
            dto.contacts = self._get_contacts(person)
            dto.addresses = self._get_addresses(person)
            dto.notes = NoteDAO(self.db).create_from_entity(person)
            dto.traits = TraitDAO(self.db).create_from_entity(person)

        return dto

    def _populate(self, dto, person):
        dto.id = person.entity_id
        dto.name = self._get_name(person)
        dto.description = person.description
        dto.type_name = self._get_type_name()
        dto.type_id = self._get_type_id()
        dto.gender = self._get_gender(person)
        dto.birth_date = person.birth_date
        dto.deceased_date = person.deceased_date
        dto.is_deceased = self._is_deceased(person)

    def _is_deceased(self, person):
        if not person.deceased_date: return False
        return person.deceased_date < DateTime.now()

    def _get_gender(self, person):
        return ConstantsDAO(self.db).get_gender(person.gender)
