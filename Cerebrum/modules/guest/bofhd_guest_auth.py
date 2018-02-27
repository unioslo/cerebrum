#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014 University of Oslo, Norway
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

""" This is an auth module for use with bofhd_guest_cmds.

This module controls access to the guest commands.

"""
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import auth
from Cerebrum.modules.bofhd.errors import PermissionDenied


class BofhdAuth(auth.BofhdAuth):
    """ Methods to control command access. """

    def _is_guest_account(self, guest):
        """ Check if account object is guest. """
        if guest.np_type != self.const.account_guest:
            return False
        try:
            guest.get_trait(self.const.trait_guest_owner)['target_id']
            guest.get_trait(self.const.trait_guest_name)['strval']
        except:
            return False
        return True

    def _is_employee(self, operator):
        """ Check if operator is an employee. """
        ac = Factory.get('Account')(self._db)
        ac.find(operator)
        if ac.owner_type == self.const.entity_person:
            pe = Factory.get('Person')(self._db)
            for row in pe.list_affiliations(
                    person_id=ac.owner_id,
                    affiliation=self.const.affiliation_ansatt):
                return True
        return False

    def _is_personal_guest_owner(self, operator, guest):
        """ Check if operator is the owner of guest. """
        if not self._is_guest_account(guest):
            return False
        if operator == guest.entity_id:
            return True
        # Check if operator is the owner registered in the trait
        if not self._is_employee(operator):
            return False
        try:
            real_owner = guest.get_trait(
                self.const.trait_guest_owner)['target_id']
            if real_owner == operator:
                return True
        except:
            pass
        return False

    def can_view_personal_guest(self, operator,
                                guest=None, query_run_any=False):
        """ If the operator can see guest info. """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            # Employees should have access to the command
            if self._is_employee(operator):
                return True
            # The guest should have access to the command
            ac = Factory.get('Account')(self._db)
            ac.find(operator)
            if self._is_guest_account(ac):
                return True
            return False
        if self._is_personal_guest_owner(operator, guest):
            return True
        raise PermissionDenied(
            "You are not the owner of %s" % guest.account_name)

    def can_create_personal_guest(self, operator, query_run_any=False):
        """ If the operator can create a personal guest user. """
        if self.is_superuser(operator):
            return True
        if self._is_employee(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied(
            "Guest accounts are only available to employees.")

    def can_reset_guest_password(self, operator,
                                 guest=None, query_run_any=False):
        """ If the operator can re-set the password for a guest. """
        return self.can_remove_personal_guest(operator, guest=guest,
                                              query_run_any=query_run_any)
        raise PermissionDenied("")  # Not reached

    def can_remove_personal_guest(self, operator, guest=None,
                                  query_run_any=False):
        """ If the operator can remove a personal guest user. """
        if query_run_any:
            if self.is_superuser(operator):
                return True
            return self._is_employee(operator)

        # The account _must_ be a guest, regardless of op
        if not self._is_guest_account(guest):
            raise PermissionDenied(
                "Account %s is not a guest account" % guest.account_name)

        if self.is_superuser(operator):
            return True

        if not self._is_employee(operator):
            return False

        if self._is_personal_guest_owner(operator, guest):
            return True

        raise PermissionDenied(
            "You're not the owner of guest %s" % guest.account_name)
