# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

import cerebrum_path
import mx.DateTime
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.bofhd.errors import PermissionDenied

from lib.data.AccountDTO import AccountDTO
from lib.data.AffiliationDAO import AffiliationDAO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.DTO import DTO
from lib.data.DiskDAO import DiskDAO
from lib.data.EntityDAO import EntityDAO
from lib.data.GroupDAO import GroupDAO
from lib.data.TraitDAO import TraitDAO
from lib.data.NoteDAO import NoteDAO
from lib.data.QuarantineDAO import QuarantineDAO

Database = Utils.Factory.get("Database")
Account = Utils.Factory.get("Account")
Person = Utils.Factory.get("Person")
Group = Utils.Factory.get("Group")
PosixUser = Utils.Factory.get("PosixUser")

def first_or_none(fn, items):
    for item in items:
        if fn(item): return item
    return None

class AccountDAO(EntityDAO):
    EntityType = Account
    
    def get(self, id, include_extra=True):
        account = self._find(id)
        if not self.auth.can_read_account(self.db.change_by, account):
            raise PermissionDenied("Not authorized to view account")

        return self._create_dto(account, include_extra)

    def search(self, name):
        name = name.strip("*") + '*'
        account = self._get_cerebrum_obj()
        return [self._create_from_search(r)
                for r in account.search(name=name,
                                        expire_start=None)]

    def get_by_owner_ids(self, *owner_ids):
        account = self._get_cerebrum_obj()
        return [self._create_from_search(r)
                for r in account.search(owner_id=owner_ids,
                                        expire_start=None)]

    def get_by_name(self, name, include_extra=True):
        account = self._find_by_name(name)
        if not self.auth.can_read_account(self.db.change_by, account):
            raise PermissionDenied("Not authorized to view account")

        return self._create_dto(account, include_extra)

    def get_owner(self, account_id):
        dto = DTO()
        account = self._find(account_id)
        self._populate_owner(dto, account)
        return dto.owner

    def get_accounts(self, *account_ids):
        dtos = []
        for account_id in account_ids:
            dto = self.get(account_id, False)
            dtos.append(dto)
        return dtos

    def get_posix_groups(self, account_id):
        groups = self.get_groups(account_id)
        return [g for g in groups if g.is_posix]

    def get_groups(self, account_id):
        groups = GroupDAO(self.db).get_groups_for(account_id)

        paccount = self._get_posix_account(account_id)
        primary_group_id = paccount and paccount.gid_id

        for group in groups:
            group.is_primary = group.id == primary_group_id

        return groups

    def get_free_uid(self):
        paccount = PosixUser(self.db)
        return paccount.get_free_uid()

    def get_default_shell(self):
        shells = ConstantsDAO(self.db).get_shells()
        for shell in shells: return shell

    def suggest_usernames(self, entity):
        fname, lname = self._split_name(entity.name)

        account = self._get_cerebrum_obj()
        return account.suggest_unames(
            self.constants.account_namespace,
            fname,
            lname,
            maxlen=8)

    def get_md5_password_hash(self, account_id):
        """This method is used for tests to verify that we have changed the
        password."""
        account = self._find(account_id)
        if not self.auth.is_superuser(self.db.change_by):
            raise PermissionDenied("Not authorized to get password hash")

        t = self.constants.auth_type_md5_crypt
        return account.get_account_authentication(t)

    def set_password(self, account_id, new_password):
        account = self._find(account_id)
        if not self.auth.can_set_password(self.db.change_by, account):
            raise PermissionDenied("Not authorized to set password")

        account.set_password(new_password)
        account.write_db()

    def promote_posix(self, account_id, primary_group_id):
        account = self._find(account_id)
        if not self.auth.can_edit_account(self.db.change_by, account):
            raise PermissionDenied("Not authorized to edit account")

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
        if not self.auth.can_edit_account(self.db.change_by, paccount):
            raise PermissionDenied("Not authorized to edit account")

        paccount.delete_posixuser()

    def delete(self, account_id):
        account = self._find(account_id)
        if not self.auth.can_delete_account(self.db.change_by, account):
            raise PermissionDenied("Not authorized to delete account")

        if self.is_posix(account_id):
            self.demote_posix(account_id)

        group_dao = GroupDAO(self.db)
        for group in group_dao.get_groups_for(account_id):
            group_dao.remove_member(group.id, account_id)

        account.delete()

    def _create_from_search(self, result):
        dto = DTO()
        dto.id = result.fields.account_id
        dto.name = result.fields.name
        dto.type = self._get_type()
        dto.type_name = self._get_type_name()
        dto.owner_id = result.fields.owner_id
        dto.owner_type = self.constants.EntityType(result.fields.owner_type)
        return dto

    def _get_owner(self, dto):
        if dto.owner.type_id == self.constants.entity_person:
            owner = Person(self.db)
        elif dto.owner.type_id == self.constants.entity_group:
            owner = Group(self.db)
        else:
            raise ProgrammingError(
                "Can't get owner of unknown type (%s)" % dto.owner.type_id)

        owner.find(dto.owner.id)
        return owner

    def create(self, dto):
        owner = self._get_owner(dto)
        if not self.auth.can_create_account(self.db.change_by, owner):
            raise PermissionDenied("Not authorized to create account")

        account = Account(self.db)
        account.populate(
            dto.name,
            dto.owner.type_id,
            dto.owner.id,
            dto.np_type,
            self.db.change_by,
            dto.expire_date)
        account.write_db()
        # Inherit all affiliations from owner.
        # Perhaps this should come from populate of initial write_db()?
        if hasattr(owner, "get_affiliations"):
            for aff in owner.get_affiliations():
                account.set_account_type(aff['ou_id'], aff['affiliation'])

        return self._create_dto(account)

    def save(self, dto):
        account = self._find(dto.id)
        if not self.auth.can_edit_account(self.db.change_by, account):
            raise PermissionDenied("Not authorized to edit account")

        account.expire_date = dto.expire_date

        self._save_posix(dto)

        account.write_db()
            
    def add_affiliation(self, account_id, ou_id, affiliation_id, priority):
        account = self._find(account_id)
        if not self.auth.can_edit_affiliation(self.db.change_by, account, ou_id, affiliation_id):
            raise PermissionDenied("Not authorized to edit affiliation of account")

        account.set_account_type(ou_id, affiliation_id, priority)
        account.write_db()

    def remove_affiliation(self, account_id, ou_id, affiliation_id):
        account = self._find(account_id)
        if not self.auth.can_edit_affiliation(self.db.change_by, account, ou_id, affiliation_id):
            raise PermissionDenied("Not authorized to edit affiliation of account")

        account.del_account_type(ou_id, affiliation_id)
        account.write_db()

    def set_home(self, account_id, spread_id, disk_id=-1, path=-1):
        account = self._find(account_id)
        if not self.auth.can_edit_homedir(self.db.change_by, account, spread_id):
            raise PermissionDenied("Not authorized to edit homedir of account")

        kw = {
            'status': self.constants.home_status_not_created
        }

        if disk_id != -1:
            kw['disk_id'] = disk_id
        
        if path != -1:
            kw['home'] = path

        homedir_id = self._get_homedir_id_or_not_set(account, spread_id)
        if homedir_id is not None:
            kw['current_id'] = homedir_id

        homedir_id = account.set_homedir(**kw)

        account.set_home(spread_id, homedir_id)
        account.write_db()

    def remove_home(self, account_id, spread_id):
        account = self._find(account_id)
        if not self.auth.can_edit_homedir(self.db.change_by, account, spread_id):
            raise PermissionDenied("Not authorized to edit homedir of account")

        account.clear_home(spread_id)
        account.write_db()

    def _get_homedir_id_or_not_set(self, account, spread_id):
        try:
            home = account.get_home(spread_id)
            return home['homedir_id']
        except NotFoundError, e:
            return None
    
    def _save_posix(self, dto):
        paccount = self._get_posix_account(dto.id)
        if paccount is None: return

        paccount.shell = self.constants.PosixShell(dto.shell)
        paccount.gecos = dto.gecos
        paccount.gid_id = dto.primary_group.id

        paccount.write_db()

    def _split_name(self, name):
        names = name.split(" ", 1)
        if len(names) == 1:
            names.insert(0, "")
        return names

    def _create_dto(self, account, include_extra=True):
        dto = AccountDTO()
        self._populate(dto, account)
        dto.groups = self.get_groups(account.entity_id)
        dto.primary_group = first_or_none(lambda x: x.is_primary, dto.groups)
        self._populate_posix(dto, account, include_extra)

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
            dto.np_type = account.np_type
            dto.np_type_name = self._get_np_type_name(account)
        return dto

    def _populate(self, dto, account):
        dto.id = account.entity_id
        dto.name = self._get_name(account)
        dto.owner_id = account.owner_id
        dto.owner_type = account.owner_type
        dto.type_name = self._get_type_name()
        dto.type_id = self._get_type_id()
        dto.expire_date = account.expire_date
        dto.create_date = account.create_date
        dto.is_expired = mx.DateTime.now() > account.expire_date

    def _populate_posix(self, dto, account, include_extra=True):
        paccount = self._get_posix_account(account.entity_id)
        dto.is_posix = paccount is not None

        if not dto.is_posix:
            return

        dto.posix_uid = paccount.posix_uid
        dto.gecos = paccount.get_gecos()
        shell = ConstantsDAO(self.db).get_shell(paccount.shell)
        dto.shell = shell.name
        
    def _populate_owner(self, dto, account):
        owner_id = account.owner_id
        owner_type = account.owner_type
        from lib.data.EntityFactory import EntityFactory
        dto.owner = EntityFactory(self.db).get_entity(owner_id, account.owner_type)
        
    def _populate_creator(self, dto, account):
        creator_id = account.creator_id
        from lib.data.EntityFactory import EntityFactory
        dto.creator = EntityFactory(self.db).get_entity(creator_id)
        
    def _get_affiliations(self, account):
        return AffiliationDAO(self.db).create_from_account_types(account.get_account_types())

    def _get_authentications(self, account):
        auths = []
        auth_dao = ConstantsDAO(self.db)
        for auth in account.get_account_authentication_methods():
            dto = auth_dao.get_authentication_method(auth['method'])
            auths.append(dto)
        return auths

    def _get_homes(self, account):
        homes = []

        for home in account.get_homes():
            dto = self._create_home_dto(home)
            homes.append(dto)
        return homes

    def _create_home_dto(self, home):
        dto = DTO()
        dto.spread = ConstantsDAO(self.db).get_spread(home['spread'])
        dto.path = home['home']
        dto.disk = home['disk_id'] and DiskDAO(self.db).get(home['disk_id'])
        status = self.constants.AccountHomeStatus(home['status'])
        dto.status = DTO()
        dto.status.description = status.description
        return dto

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

    def is_posix(self, entity_id):
        return self._get_posix_account(entity_id) is not None

    def _get_name(self, entity):
        return entity.get_name(self.constants.account_namespace)

    def _get_type(self):
        return self.constants.entity_account

    def _get_np_type_name(self, account):
        if account.np_type:
            np_type = int(account.np_type)
            return self.constants.Account(np_type).description
        return None
