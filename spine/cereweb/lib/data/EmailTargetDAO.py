import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd.errors import PermissionDenied

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")

from lib.data.DTO import DTO
from lib.data.EntityDAO import EntityDAO
from lib.data.HostDAO import HostDAO
from lib.data.EmailAddressDAO import EmailAddressDAO

class EmailTargetDAO(EntityDAO):
    EntityType = Email.EmailTarget

    def get(self, target_id):
        target = self._find(target_id)
        return self._create_dto(target)

    def create(self, entity_id, target_type, host_id):
        if not self.auth.can_create_email_target(
                self.db.change_by, entity_id, target_type, host_id):
            raise PermissionDenied("Not authorized to create email target")

        from lib.data.EntityFactory import EntityFactory
        dao = EntityFactory(self.db).get_dao_by_entity_id(entity_id)
        entity = dao.get_entity(entity_id)

        using_uid = None
        if entity.type_name == 'account' and dao.is_posix(entity_id):
            using_uid = entity_id

        target = self._get_cerebrum_obj()
        target.populate(
            target_type,
            target_entity_id=entity.id,
            target_entity_type=entity.type_id,
            alias=None,
            using_uid=using_uid,
            server_id=host_id)
        target.write_db()

    def save(self, target_id, entity_id, target_type, alias):
        target = self._find(target_id)
        if not self.auth.can_edit_email_target(self.db.change_by, target):
            raise PermissionDenied("Not authorized to edit email target")

        if target.email_target_entity_id != entity_id:
            from lib.data.EntityFactory import EntityFactory
            dao = EntityFactory(self.db).get_dao_by_entity_id(entity_id)
            entity = dao.get_entity(entity_id)

            target.email_target_entity_id = entity_id
            target.email_target_entity_type = entity.type_id

            target.email_target_using_uid = None
            if entity.type_name == 'account' and dao.is_posix(entity_id):
                target.email_target_using_uid = entity_id

        target.email_target_type = target_type
        target.email_target_alias = alias or None
        target.write_db()

    def delete(self, target_id):
        target = self._find(target_id)

        if not self.auth.can_delete_email_target(self.db.change_by, target):
            raise PermissionDenied("Not authorized to delete email target")

        address_dao = EmailAddressDAO(self.db)
        for address in target.get_addresses():
            address_dao.delete(address.fields.address_id)

        target.delete()

    def set_primary_address(self, target_id, address_id):
        target = self._find(target_id)

        if not self.auth.can_edit_email_target(self.db.change_by, target):
            raise PermissionDenied("Not authorized to edit email target")

        address = Email.EmailAddress(self.db)
        address.find(address_id)

        if address.get_target_id() != target.entity_id:
            raise NotFoundError('The given address does not have this target as its target.')

        primary_target = Email.EmailPrimaryAddressTarget(self.db)
        try:
            primary_target.find(target_id)
            primary_target.email_primaddr_id = address_id
        except NotFoundError, e:
            primary_target.populate(address_id, target_id)
        primary_target.write_db()

    def get_from_entity(self, entity_id):
        target = self._get_cerebrum_obj()

        try:
            target.find_by_target_entity(entity_id)
        except NotFoundError, e:
            return None

        return self._create_dto(target)

    def _create_dto(self, target):
        dto = DTO()
        dto.id = target.entity_id
        dto.type_name = self._get_type_name()
        dto.type_id = self._get_type_id()
        dto.alias = target.email_target_alias
        target_type = self._get_target_type(target)
        dto.target_type = str(target_type)
        dto.target_type_id = int(target_type)
        dto.owner = self._get_owner(target)
        dto.server = self._get_server(target)
        dto.name = self._get_name(target, dto)
        dto.primary = self._get_primary(target)
        dto.addresses = self._get_addresses(target)
        return dto

    def _get_type(self):
        return self.constants.entity_email_target

    def _get_name(self, entity, dto=None):
        if dto:
            server = dto.server
        else:
            server = self._get_server(entity)

        target_type = str(self._get_target_type(entity))
        return target_type + "@" + server.name

    def _get_server(self, target):
        dao = HostDAO(self.db)
        entity_id = target.get_server_id()
        if not entity_id:
            dto = DTO()
            dto.id = -1
            dto.name = "[no server]"
            dto.type_name = dao._get_type_name()
            return dto
        return dao.get_entity(entity_id)

    def _get_target_type(self, target):
        return self.constants.EmailTarget(target.email_target_type)

    def _get_owner(self, target):
        from lib.data.EntityFactory import EntityFactory
        factory = EntityFactory(self.db)

        entity_id = target.email_target_entity_id
        entity_type_id = target.email_target_entity_type
        return factory.get_entity(entity_id, entity_type_id)

    def _get_primary(self, target):
        address_dao = EmailAddressDAO(self.db)

        primary = Email.EmailPrimaryAddressTarget(self.db)
        try:
            primary.find(target.entity_id)
        except NotFoundError, e:
            return address_dao.NullObject

        entity_id = primary.get_address_id()
        return address_dao.get(entity_id)

    def _get_addresses(self, target):
        address_ids = [x.fields.address_id for x in target.get_addresses()]
        address_dao = EmailAddressDAO(self.db)
        return address_dao.get_addresses(*address_ids)

