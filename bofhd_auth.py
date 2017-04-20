# -*- coding: iso-8859-1 -*-
#
# Copyright 2003-2014 University of Oslo, Norway
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
from Cerebrum.modules.bofhd import auth
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules import Email


class BofhdAuth(auth.BofhdAuth):
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
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return True
        if operator == account.entity_id:
            return True
        if self._no_account_home(operator, account):
            return True
        if self._is_guest_owner(operator, account):
            return True
        return self.is_account_owner(operator, self.const.auth_set_password,
                                     account)

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

    def can_email_address_delete(self, operator_id, account=None, domain=None,
                                 query_run_any=False):
        """Checks if the operator can delete an address in a given domain.
        Superusers and postmasters are always allowed, but normal users are also
        allowed to delete their own addresses if it is not registered to one of
        their users' active affiliations' OU."""
        if self.is_superuser(operator_id):
            return True
        if query_run_any:
            return True
        try:
            return self._is_local_postmaster(operator_id,
                    self.const.auth_email_delete, account, domain,
                    query_run_any)
        except PermissionDenied:
            pass
        if operator_id != account.entity_id:
            raise PermissionDenied("Can only change e-mail addresses that "
                                   "belongs to your account")
        if domain.entity_id in account.get_prospect_maildomains():
            raise PermissionDenied("Can't delete e-mail addresses from domains "
                                   "the account is affiliated with")
        return True

    def can_email_mod_name(self, operator_id, person=None, firstname=None,
                           lastname=None, query_run_any=False):
        """If someone is allowed to modify a person's name. Only postmasters are
        allowed to do this by default, but persons can change their name after
        some criterias."""
        if self.is_superuser(operator_id, query_run_any):
            return True
        if self.is_postmaster(operator_id, query_run_any):
            return True
        if query_run_any:
            return True

        # last name must match primary one
        # TBD: only _primary_ family name, or can others be accepted?
        found = False
        for sys in cereconf.SYSTEM_LOOKUP_ORDER:
            try:
                if lastname != person.get_name(getattr(self.const, sys),
                                               self.const.name_last):
                    raise PermissionDenied("Invalid family name")
                found = True
                break
            except NotFoundError:
                continue
        if not found:
            raise PermissionDenied('No family name registered')

        # check that all names already exists
        names = []
        for row in person.get_all_names():
            if row['name_variant'] != self.const.name_first:
                continue
            names.extend(row['name'].split(' '))
        if not names:
            raise PermissionDenied('No given names registered')
        for n in firstname.split(' '):
            if n not in names:
                raise PermissionDenied('Unregistered name: %s' % n)
        return True

    def can_show_history(self, operator, entity=None, query_run_any=False):
        """UiT-specific history-specific authentication rules."""
        if (entity and entity.entity_type == self.const.entity_email_target and
                self.is_postmaster(operator)):
            return True
        return super(BofhdAuth, self).can_show_history(
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
