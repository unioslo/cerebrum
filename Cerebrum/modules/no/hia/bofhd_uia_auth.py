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
from Cerebrum.modules.bofhd import auth
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.no.bofhd_note_cmds import EntityNoteBofhdAuth


class BofhdAuth(EntityNoteBofhdAuth, auth.BofhdAuth):
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
