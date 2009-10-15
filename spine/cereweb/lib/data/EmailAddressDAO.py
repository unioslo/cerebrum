import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd.errors import PermissionDenied

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")

from lib.data.DTO import DTO
from lib.data.EntityDAO import EntityDAO
from lib.data.EmailDomainDAO import EmailDomainDAO

class EmailAddressDAO(EntityDAO):
    EntityType = Email.EmailAddress
    NullObject = DTO()
    NullObject.id = None
    NullObject.local = "[no address]"
    NullObject.domain = "[no domain]"
    NullObject.address = "[no address]"
    NullObject.is_primary = False
    NullObject.expire = None

    def get(self, address_id):
        address = self._find(address_id)
        return self._create_dto(address)

    def delete(self, address_id):
        address = self._find(address_id)
        if not self.auth.can_delete_email_address(self.db.change_by, address):
            raise PermissionDenied("Not authorized to delete email address")

        address.delete()

    def create(self, target_id, domain_id, local_part, expire_date):
        target = Email.EmailTarget(self.db)
        domain = Email.EmailDomain(self.db)
        target.find(target_id)
        domain.find(domain_id)

        if not self.auth.can_create_email_address(self.db.change_by, target, domain):
            raise PermissionDenied("Not authorized to create email address")

        address = self._get_cerebrum_obj()
        address.populate(local_part, domain_id, target_id, expire_date)
        address.write_db()

    def search(self, domain_id=None):
        address = self._get_cerebrum_obj()
        return [self._create_dto_from_search(r) for r in address.search(domain_id=domain_id)]

    def _create_dto_from_search(self, row):
        dto = DTO.from_row(row)
        dto.id = dto.address_id
        dto.type_name = self._get_type_name()
        dto.type_id = self._get_type_id()
        dto.local = dto.local_part
        dto.domain = DTO()
        dto.domain.name = row.fields.domain
        dto.domain.id = row.fields.domain_id
        dto.address = "@".join((dto.local, dto.domain.name))
        dto.name = dto.address
        return dto

    def get_addresses(self, *address_ids):
        return [self.get(id_) for id_ in address_ids]

    def _create_dto(self, address):
        dto = DTO()
        dto.id = address.entity_id
        dto.local = address.get_localpart()
        dto.domain = self._get_domain(address)
        dto.address = "@".join((dto.local, dto.domain.name))
        dto.is_primary = self._is_primary(address)
        dto.expire = address.email_addr_expire_date
        return dto

    def _is_primary(self, address):
        primary = Email.EmailPrimaryAddressTarget(self.db)
        try:
            primary.find(address.email_addr_target_id)
        except NotFoundError, e:
            return False
        return primary.email_primaddr_id == address.entity_id

    def _get_domain(self, address):
        dao = EmailDomainDAO(self.db)
        return dao.get(address.get_domain_id())

    def _get_type(self):
        return self.constants.entity_email_address
