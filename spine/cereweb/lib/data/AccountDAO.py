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
from lib.data.NoteDAO import NoteDAO
from lib.data.QuarantineDAO import QuarantineDAO

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

    def set_password(self, account_id, new_password):
        account = self._find(account_id)
        account.set_password(new_password)
        account.write_db()

    def get_md5_password_hash(self, account_id):
        account = self._find(account_id)
        t = self.constants.auth_type_md5_crypt
        return account.get_account_authentication(t)

    def get_posix_groups(self, account_id):
        groups = self.get_groups(account_id)
        return [g for g in groups if g.is_posix]

    def get_groups(self, account_id):
        return GroupDAO(self.db).get_groups_for(account_id)

    def suggest_usernames(self, entity):
        fname, lname = self._split_name(entity.name)

        return self.entity.suggest_unames(
            self.constants.account_namespace,
            fname,
            lname,
            maxlen=8)

    def promote_posix(self, account_id, primary_group_id):
        account = self._find(account_id)
        paccount = PosixUser(self.db)
        paccount.populate(
            self.get_free_uid(),
            primary_group_id,
            gecos = None,
            shell = self.get_default_shell().id,
            parent=account)
        paccount.write_db()

    def demote_posix(self, account_id):
        paccount = PosixUser(self.db)
        paccount.find(account_id)
        paccount.delete_posixuser()

    def delete(self, account_id):
        if self._is_posix(account_id):
            self.demote_posix(account_id)

        account = self._find(account_id)
        account.delete()

    def get_free_uid(self):
        paccount = PosixUser(self.db)
        return paccount.get_free_uid()

    def get_default_shell(self):
        shells = ConstantsDAO(self.db).get_shells()
        for shell in shells: return shell

    def create(self, dto):
        account = Account(self.db)
        account.populate(
            dto.name,
            dto.owner.type_id,
            dto.owner.id,
            dto.np_type,
            self.db.change_by,
            dto.expire_date)
        account.write_db()

        return self._create_dto(account)
            
    def _split_name(self, name):
        names = name.split(" ", 1)
        if len(names) == 1:
            names.insert(0, "")
        return names

    def _create_dto(self, account, include_extra=True):
        dto = AccountDTO()
        self._populate(dto, account)
        self._populate_posix(dto, account, include_extra)
        dto.groups = self.get_groups(account.entity_id)

        if include_extra:
            self._populate_owner(dto, account)
            self._populate_creator(dto, account)
            dto.affiliations = self._get_affiliations(account)
            dto.authentications = self._get_authentications(account)
            dto.homes = self._get_homes(account)
            dto.spreads = self._get_spreads(account)
            dto.traits = self._get_traits(account)
            dto.notes = self._get_notes(account)
            dto.quarantines = self._get_quarantines(account)

        return dto

    def _populate(self, dto, account):
        dto.id = account.entity_id
        dto.name = self._get_name(account)
        dto.type_name = self._get_type_name()
        dto.type_id = self._get_type_id()
        dto.expire_date = account.expire_date
        dto.create_date = account.create_date

    def _populate_posix(self, dto, account, include_extra=True):
        paccount = self._get_posix_account(account.entity_id)
        dto.is_posix = paccount is not None

        if not dto.is_posix:
            return

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

    def _get_notes(self, account):
        return NoteDAO(self.db).create_from_entity(account)

    def _get_quarantines(self, account):
        return QuarantineDAO(self.db).create_from_entity(account)

    def _get_posix_account(self, id):
        paccount = PosixUser(self.db)

        try:
            paccount.find(id)
        except NotFoundError, e:
            return None

        return paccount

    def _is_posix(self, group_id):
        return self._get_posix_account(group_id) is not None

    def _get_name(self, entity):
        return entity.get_name(self.constants.account_namespace)

    def _get_type_name(self):
        return self.constants.entity_account.str

    def _get_type_id(self):
        return int(self.constants.entity_account)
