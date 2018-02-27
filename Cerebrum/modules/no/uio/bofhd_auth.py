# -*- coding: utf-8 -*-
#
# Copyright 2003-2017 University of Oslo, Norway
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
""" Site specific auth.py for UiO. """

import cereconf
from Cerebrum import Constants
from Cerebrum.Errors import NotFoundError
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import auth
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode


class Constants(Constants.Constants):
    auth_set_password_important = _AuthRoleOpCode(
        'set_password_imp', 'Set password for important/critical accounts')


class BofhdAuth(auth.BofhdAuth):
    """Defines methods that are used by bofhd to determine wheter
    an operator is allowed to perform a given action.

    This class only contains special cases for UiO.
    """

    # Temporary owner group is specified in trait_uio_guest_owner trait,
    # and members of owner groups should be allowed to change password
    # for their guest users
    def _is_guest_owner(self, operator, account):
        """ Return if the operator is the owner of *guest* account. """
        owner_uio = owner_personal = None

        # Personal guest account owner
        if hasattr(self.const, 'trait_guest_owner'):
            owner_personal = account.get_trait(
                getattr(self.const, 'trait_guest_owner'))
        if owner_personal:
            if operator == owner_personal['target_id']:
                return True

        # Old uio guest account owner
        if hasattr(self.const, 'trait_uio_guest_owner'):
            owner_uio = account.get_trait(
                getattr(self.const, 'trait_uio_guest_owner'))
        if owner_uio:
            grp = Factory.get("Group")(self._db)
            try:
                grp.find(owner_uio['target_id'])
            except NotFoundError:
                return False
            return self.is_group_member(operator, grp.group_name)
        return False

    def _is_important_account(self, operator, account):
        """If an account is considered important."""
        # Accounts owned by a group, i.e. system account
        # is_account_owner() will allow this if operator is a group member
        if account.owner_type == self.const.entity_group:
            return True
        # Tagged sysadmin accounts
        if account.get_trait(self.const.trait_sysadm_account):
            return True
        return super(BofhdAuth, self)._is_important_account(operator, account)

    def can_set_password(self, operator, account=None,
                         query_run_any=False):
        if query_run_any:
            return True
        if self._is_guest_owner(operator, account):
            return True
        return super(BofhdAuth, self).can_set_password(operator, account,
                                                       query_run_any)

    def can_clear_name(self, operator, person=None, source_system=None,
                       query_run_any=False):
        """If operator is allowed to remove a person's name from a given source
        system."""
        if self.is_superuser(operator, query_run_any):
            return True
        if self.is_postmaster(operator, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not allowed to clear name')

    def can_set_trait(self, operator, trait=None, ety=None, target=None,
                      query_run_any=False):
        if query_run_any:
            return True
        if self.is_superuser(operator):
            return True
        # users can set some of their own traits
        if ety and trait in (self.const.trait_reservation_sms_password,):
            if ety.entity_id == operator:
                return True
        # persons can set some of their own traits
        if ety and trait in (self.const.trait_primary_aff,):
            account = Factory.get('Account')(self._db)
            account.find(operator)
            if ety.entity_id == account.owner_id:
                return True
        # permission can be given via opsets
        if trait and self._has_target_permissions(
                operator=operator, operation=self.const.auth_set_trait,
                target_type=self.const.auth_target_type_host,
                target_id=ety.entity_id, victim_id=ety.entity_id,
                operation_attr=str(trait)):
            return True
        raise PermissionDenied("Not allowed to set trait")

    def can_get_contact_info(self, operator, person=None, contact_type=None,
                             query_run_any=False):
        """If an operator is allowed to see contact information for a given
        person, i.e. phone numbers."""
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return True
        account = Factory.get('Account')(self._db)
        account.find(operator)
        if person.entity_id == account.owner_id:
            return True
        if (hasattr(cereconf, 'BOFHD_VOIP_ADMINS') and
                self.is_group_member(operator, cereconf.BOFHD_VOIP_ADMINS)):
                return True
        return super(BofhdAuth, self).can_get_contact_info(operator, person,
                                                           contact_type,
                                                           query_run_any)


    def can_create_sysadm(self, operator, query_run_any=False):
        """Allow sysadmins to create sysadmin accounts.

        Note that we don't check for OU or disk or anything. This is to avoid
        edge cases that requires manual work, and no security benefits. If one
        sysadmin creates a sysadmin account on a different OU, there is most
        likely a reason for that.

        """
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(operator,
                                              self.const.auth_create_user):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not allowed to create sysadmin accounts')
