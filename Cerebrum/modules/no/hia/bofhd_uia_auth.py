# -*- coding: utf-8 -*-
#
# Copyright 2003, 2018 University of Oslo, Norway
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

"""
Site specific auth.py for UiA

"""

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_contact_info import BofhdContactAuth
from Cerebrum.modules.bofhd.bofhd_email import BofhdEmailAuth
from Cerebrum.modules.bofhd.bofhd_access import BofhdAccessAuth
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.no.bofhd_note_cmds import EntityNoteBofhdAuth


class UiaAuth(EntityNoteBofhdAuth, BofhdAuth):
    """Defines methods that are used by bofhd to determine wheter
    an operator is allowed to perform a given action.

    This class only contains special cases for UiA.
    """

    def can_set_trait(self, operator, trait=None, ety=None, target=None,
                      query_run_any=False):
        # this should not be necessary, we have to agree on the way
        # to use personal traits in order to avoid duplication and
        # double work
        if query_run_any:
            return True
        if self.is_superuser(operator):
            return True
        # persons can set some of their own traits
        if ety and trait in (self.const.trait_accept_nondisc,
                             self.const.trait_reject_nondisc,
                             self.const.trait_accept_rules):
            account = Factory.get('Account')(self._db)
            account.find(operator)
            if ety.entity_id == account.owner_id:
                return True
        elif ety and trait in (self.const.trait_reservation_sms_password,):
            if ety.entity_id == operator:
                return True
        raise PermissionDenied("Not allowed to set trait")

    def can_remove_trait(self, operator, trait=None, ety=None, target=None,
                         query_run_any=False):
        if query_run_any:
            return True
        if self.is_superuser(operator):
            return True
        # persons can remove some of their own traits
        if ety and trait in (self.const.trait_reject_nondisc,):
            account = Factory.get('Account')(self._db)
            account.find(operator)
            if ety.entity_id == account.owner_id:
                return True
        raise PermissionDenied("Not allowed to remove trait")

    def can_send_welcome_sms(self, operator, query_run_any=False):
        # Superusers can see and run command
        if self.is_superuser(operator):
            return True
        # Group members can see and run command
        if self.is_group_member(operator, 'cerebrum-password'):
            return True
        # Hide command if not in the above groups
        if query_run_any:
            return False
        raise PermissionDenied("Not allowed to send Welcome SMS")


class UiaContactAuth(UiaAuth, BofhdContactAuth):

    def can_add_contact_info(self, operator,
                             entity=None,
                             contact_type=None,
                             query_run_any=False):
        # Superusers can see and run command
        if self.is_superuser(operator):
            return True

        # Users with auth_add_contactinfo can see and run command
        if self._has_operation_perm_somewhere(
                operator,
                self.const.auth_add_contactinfo):
            # Only allow phone numbers to be added
            if contact_type is not None and contact_type not in (
                    self.const.contact_phone,
                    self.const.contact_phone_private,
                    self.const.contact_mobile_phone,
                    self.const.contact_private_mobile):
                raise PermissionDenied(
                    "You are only allowed to add phone numbers")
            return True
        # Hide command if not in the above groups
        if query_run_any:
            return False
        raise PermissionDenied("Not allowed to add contact info")

    def can_remove_contact_info(self, operator,
                                entity=None,
                                contact_type=None,
                                source_system=None,
                                query_run_any=False):
        # Superusers can see and run command
        if self.is_superuser(operator):
            return True
        # Users with auth_rem_contactinfo can see and run command
        if self._has_operation_perm_somewhere(
                operator,
                self.const.auth_remove_contactinfo):
            return True
        # Hide command if not in the above groups
        if query_run_any:
            return False
        raise PermissionDenied("Not allowed to remove contact info")


class UiaEmailAuth(UiaAuth, BofhdEmailAuth):

    def can_email_move(self, operator, account=None, query_run_any=False):
        if self.is_postmaster(operator, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")


class UiaAccessAuth(UiaAuth, BofhdAccessAuth):
    """Nih specific authentication checks

    Used for overriding default behavior

    """
    pass
