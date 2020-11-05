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
"""
Site specific auth.py for UiA
"""
from Cerebrum.Utils import Factory
from Cerebrum.modules.apikeys import bofhd_apikey_cmds
from Cerebrum.modules.audit import bofhd_history_cmds
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_contact_info import BofhdContactAuth
from Cerebrum.modules.bofhd.bofhd_email import BofhdEmailAuth
from Cerebrum.modules.bofhd_requests.bofhd_requests_auth import RequestsAuth
from Cerebrum.modules.bofhd.bofhd_access import BofhdAccessAuth
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.no.bofhd_note_cmds import EntityNoteBofhdAuth
from Cerebrum.modules.bofhd import bofhd_user_create_unpersonal


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

    def can_add_affiliation(self, operator, person=None, ou=None, aff=None,
                            aff_status=None, query_run_any=False):
        # Restrict affiliation types
        if not query_run_any and aff in (
                self.const.affiliation_ansatt,
                self.const.affiliation_student):
            raise PermissionDenied(
                "Affiliations STUDENT/ANSATT can only be set by "
                "automatic imports")
        return super(UiaAuth, self).can_add_affiliation(
            operator, person=person, ou=ou, aff=aff, aff_status=aff_status,
            query_run_any=query_run_any)

    def can_alter_group(self, operator, group=None, query_run_any=False):
        """Checks if the operator has permission to add/remove group members
        for the given group.

        @type operator: int
        @param operator: The entity_id of the user performing the operation.

        @type group: An entity of EntityType Group
        @param group: The group to add/remove members to/from.

        @type query_run_any: True or False
        @param query_run_any: Check if the operator has permission *somewhere*

        @return: True or False
        """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            # query_run_any and operator is admin for *any* groups
            if self._is_admin(operator):
                return True
        else:
            # operator is admin for this specific group
            if self._is_admin(operator, group.entity_id):
                return True
        return super(UiaAuth, self).can_alter_group(operator, group,
                                                    query_run_any)


class ContactAuth(UiaAuth, BofhdContactAuth):

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


class EmailAuth(UiaAuth, BofhdEmailAuth):

    def can_email_move(self, operator, account=None, query_run_any=False):
        if self.is_postmaster(operator, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")


class BofhdRequestsAuth(UiaAuth, RequestsAuth):
    pass


class AccessAuth(UiaAuth, BofhdAccessAuth):
    pass


class ApiKeyAuth(UiaAuth, bofhd_apikey_cmds.BofhdApiKeyAuth):
    pass


class CreateUnpersonalAuth(UiaAuth,
                           bofhd_user_create_unpersonal.BofhdUnpersonalAuth):
    pass


class HistoryAuth(UiaAuth, bofhd_history_cmds.BofhdHistoryAuth):
    pass
