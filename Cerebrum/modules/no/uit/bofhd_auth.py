# -*- coding: utf-8 -*-
#
# Copyright 2003-2019 University of Oslo, Norway
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
""" Site specific auth.py for UiT. """
import cereconf

from Cerebrum.Errors import NotFoundError
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_contact_info import BofhdContactAuth
from Cerebrum.modules.bofhd_requests.bofhd_requests_auth import RequestsAuth
from Cerebrum.modules.bofhd.bofhd_email import BofhdEmailAuth
from Cerebrum.modules.bofhd import bofhd_access
from Cerebrum.modules.bofhd.errors import PermissionDenied


class UitContactAuthMixin(BofhdContactAuth):
    """ uio specific contact auth. """

    def can_get_contact_info(self, operator,
                             entity=None,
                             contact_type=None,
                             query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return True
        if (hasattr(cereconf, 'BOFHD_VOIP_ADMINS') and
                self.is_group_member(operator, cereconf.BOFHD_VOIP_ADMINS)):
                return True
        return super(UitContactAuthMixin, self).can_get_contact_info(
            operator,
            entity=entity,
            contact_type=contact_type,
            query_run_any=query_run_any)


class UitAuth(UitContactAuthMixin, BofhdAuth):
    """Defines methods that are used by bofhd to determine wheter
    an operator is allowed to perform a given action.

    This class only contains special cases for UiT.
    """

    # Temporary owner group is specified in trait_uit_guest_owner trait,
    # and members of owner groups should be allowed to change password
    # for their guest users
    def _is_guest_owner(self, operator, account):
        """ Return if the operator is the owner of *guest* account. """
        owner_uit = owner_personal = None

        # Personal guest account owner
        if hasattr(self.const, 'trait_guest_owner'):
            owner_personal = account.get_trait(
                getattr(self.const, 'trait_guest_owner'))
        if owner_personal:
            if operator == owner_personal['target_id']:
                return True

        # Old uit guest account owner
        if hasattr(self.const, 'trait_uit_guest_owner'):
            owner_uit = account.get_trait(
                getattr(self.const, 'trait_uit_guest_owner'))
        if owner_uit:
            grp = Factory.get("Group")(self._db)
            try:
                grp.find(owner_uit['target_id'])
            except NotFoundError:
                return False
            return self.is_group_member(operator, grp.group_name)
        return False

    def can_set_password(self, operator, account=None,
                         query_run_any=False):
        if query_run_any:
            return True
        if self._is_guest_owner(operator, account):
            return True
        return super(UitAuth, self).can_set_password(operator, account,
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

    def can_show_history(self, operator, entity=None, query_run_any=False):
        """UiT-specific history-specific authentication rules."""
        if (entity and entity.entity_type == self.const.entity_email_target and
                self.is_postmaster(operator)):
            return True
        return super(UitAuth, self).can_show_history(
            operator, entity, query_run_any)

    def can_email_forward_info(self, operator, query_run_any=False):
        """Allow access to superusers, postmasters and CERT."""
        if self.is_superuser(operator):
            return True
        if self.is_postmaster(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_email_forward_info):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Restricted access')


class UitContactAuth(UitAuth):
    # can_get_contact_info is included in UioAuth, because it is used by
    # person_info
    # TODO: verify this?
    pass


class UitEmailAuth(UitAuth, BofhdEmailAuth):

    def can_email_address_delete(self, operator_id,
                                 account=None,
                                 domain=None,
                                 query_run_any=False):
        """Checks if the operator can delete an address in a given domain.

        Superusers and postmasters are always allowed, but normal users are
        also allowed to delete their own addresses if it is not registered to
        one of their users' active affiliations' OU.
        """
        if self.is_superuser(operator_id):
            return True
        if query_run_any:
            return True
        try:
            return self._is_local_postmaster(
                operator_id, self.const.auth_email_delete, account, domain,
                query_run_any)
        except PermissionDenied:
            pass
        if operator_id != account.entity_id:
            raise PermissionDenied("Can only change e-mail addresses that "
                                   "belongs to your account")
        if domain.entity_id in account.get_prospect_maildomains():
            raise PermissionDenied(
                "Can't delete e-mail addresses from domains the account is "
                "affiliated with")
        return True

    def can_email_forward_info(self, operator, query_run_any=False):
        """Allow access to superusers, postmasters and CERT."""
        if self.is_superuser(operator):
            return True
        if self.is_postmaster(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator,
                self.const.auth_email_forward_info):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Restricted access')

    def can_email_mod_name(self, operator, person=None, firstname=None,
                           lastname=None, query_run_any=False):
        """If someone is allowed to modify a person's name. """
        if self.is_superuser(operator, query_run_any):
            return True
        if self.is_postmaster(operator, query_run_any):
            return True
        if query_run_any:
            return True

        # Operator can only modify name if owner
        account = Factory.get('Account')(self._db)
        account.find(operator)
        if person.entity_id != account.owner_id:
            raise PermissionDenied('Cannot modify name for other persons')

        all_names = person.get_names()

        # Last name must match one of the registered last names
        last_names = [x['name'] for x in all_names
                      if x['name_variant'] == self.const.name_last]
        if lastname not in last_names:
            raise PermissionDenied("Invalid family name")

        # All parts of the given name must exist somewhere
        first_names = sum([x['name'].split(' ') for x in all_names
                          if x['name_variant'] == self.const.name_first], [])
        for n in firstname.split(' '):
            if n not in first_names:
                raise PermissionDenied('Invalid given name: {}'.format(n))
        return True

    def can_email_move(self, operator, account=None, query_run_any=False):
        if self.is_postmaster(operator, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")


class UitBofhdRequestsAuth(UitAuth, RequestsAuth):
    pass


class UitAccessAuth(UitAuth, bofhd_access.BofhdAccessAuth):
    pass
