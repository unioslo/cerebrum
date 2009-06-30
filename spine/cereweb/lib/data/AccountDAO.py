import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

from lib.data.AccountDTO import AccountDTO
from lib.data.AffiliationDAO import AffiliationDAO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.DTO import DTO
from lib.data.EntityDAO import EntityDAO
from lib.data.GroupDAO import GroupDAO
from lib.data.TraitDAO import TraitDAO

Database = Utils.Factory.get("Database")
Account = Utils.Factory.get("Account")
Person = Utils.Factory.get("Person")
PosixUser = Utils.Factory.get("PosixUser")

class AccountDAO(EntityDAO):
    def __init__(self, db=None):
        super(AccountDAO, self).__init__(db, Account)

    def get(self, id, include_extra=True):
        account = self._find(id)

        return self._create_dto(account, include_extra)

    def get_by_name(self, name):
        account = self._find_by_name(name)

        return self._create_dto(account)

    def _create_dto(self, account, include_extra=True):
        dto = AccountDTO()
        self._populate(dto, account)
        self._populate_posix(dto, account, include_extra)
        dto.groups = self._get_groups(account)

        if include_extra:
            self._populate_owner(dto, account)
            self._populate_creator(dto, account)
            dto.affiliations = self._get_affiliations(account)
            dto.authentications = self._get_authentications(account)
            dto.homes = self._get_homes(account)
            dto.spreads = self._get_spreads(account)
            dto.traits = self._get_traits(account)

        return dto

    def _populate(self, dto, account):
        dto.id = account.entity_id
        dto.name = self._get_name(account)
        dto.type_name = self._get_type_name()
        dto.expire_date = account.expire_date
        dto.create_date = account.create_date

    def _populate_posix(self, dto, account, include_extra=True):
        dto.is_posix = False

        try:
            paccount = self._get_posix_account(account.entity_id)
        except NotFoundError, e:
            return

        dto.is_posix = True
        dto.posix_uid = paccount.posix_uid
        dto.gecos = paccount.get_gecos()
        shell = ConstantsDAO(self.db).get_shell(paccount.shell)
        dto.shell = shell.name
        
        if include_extra:
            self._populate_posix_group(dto, paccount)

    def _populate_posix_group(self, dto, account):
        group_id = account.gid_id
        group_type = self.constants.entity_group
        dto.primary_group = EntityDAO(self.db).get(group_id, group_type)

    def _get_groups(self, account):
        return GroupDAO(self.db).get_groups_for(account.entity_id)

    def _populate_owner(self, dto, account):
        owner_id = account.owner_id
        owner_type = account.owner_type
        dto.owner = EntityDAO(self.db).get(owner_id, owner_type)
        
    def _populate_creator(self, dto, account):
        creator_id = account.creator_id
        dto.creator = EntityDAO(self.db).get(creator_id)
        
    def _get_affiliations(self, account):
        return AffiliationDAO(self.db).create_from_account_types(account.get_account_types())

    def _get_authentications(self, account):
        auths = []
        for auth in account.get_account_authentication_methods():
            dto = DTO()
            method = self.constants.Authentication(auth.method)
            dto.methodname = method.str
            auths.append(dto)
        return auths

    def _get_homes(self, account):
        homes = []

        for home in account.get_homes():
            dto = DTO()
            dto.spread = DTO()
            spread = self.constants.Spread(home.spread)
            dto.spread.name = spread.str
            dto.path = home.home
            dto.disk = None
            status = self.constants.AccountHomeStatus(home.status)
            dto.status = DTO()
            dto.status.description = status.description
            homes.append(dto)
        return homes

    def _get_spreads(self, account):
        spreads = []
        for (spread_id,) in account.get_spread():
            spread = self.constants.Spread(spread_id)
            dto = DTO()
            dto.name = spread.str
            dto.description = spread.description
            spreads.append(dto)
        return spreads

    def _get_traits(self, account):
        return TraitDAO(self.db).create_from_entity(account)

    def _get_posix_account(self, id):
        paccount = PosixUser(self.db)
        paccount.find(id)
        return paccount

    def _get_name(self, entity):
        return entity.get_name(self.constants.account_namespace)

    def _get_type_name(self):
        return self.constants.entity_account.str
