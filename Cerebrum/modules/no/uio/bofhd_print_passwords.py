#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2018 University of Oslo, Norway
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
""" This module contains a password print command for UiO. """
from __future__ import unicode_literals
import cereconf

import Cerebrum.modules.printutils.bofhd_misc_print_passwords as base
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.templates import mappers


class BofhdExtension(base.BofhdExtension):

    """ Alter how password letters are printed at UiO. """

    def _get_default_printer(self, session):
        """ Get a default printer for the prompt. """
        previous = super(BofhdExtension, self)._get_default_printer(session)
        return previous or 'pullprint'

    def _get_printer(self, session, template):
        """ Get printer preset. """
        if template.get('type', '') == 'letter':
            return cereconf.PRINT_PRINTER
        return 'pullprint'

    def _can_set_spool_user(self, session, template):
        """ Can spool user be set? """
        return self._get_printer(session, template) == 'pullprint'

    def _get_group_account_mappings(self, account):
        group = self._get_group(account.owner_id, idtype='id')
        return mappers.get_group_mappings(group)

    def _get_person_account_mappings(self, account, tmpl_type):
        person = self._get_person('id', account.owner_id)
        mappings = mappers.get_person_info(person, self.const)

        if tmpl_type == 'letter':
            address_lookups = (
                (self.const.system_sap, self.const.address_post),
                (self.const.system_fs, self.const.address_post),
                (self.const.system_sap, self.const.address_post_private),
                (self.const.system_fs, self.const.address_post_private)
            )

            address = mappers.get_person_address(person, address_lookups)
            if not address:
                raise CerebrumError(
                    "Couldn't get authoritative address for {}"
                    .format(account.account_name)
                )
            mappings.update(mappers.get_address_mappings(address, self.const))
        return mappings

    def _get_mappings(self, account, password, tpl):
        """ Get mappings for a given template.

        :param Cerebrum.Account account: The account to generate mappings for
        :param str password: The account's password
        :param dict tpl: The template to generate mappings for

        :return dict: A dictionary of mappings for the TemplateHandler.

        """
        if tpl['type'] == 'letter' and \
           account.owner_type != self.const.entity_person:
            raise CerebrumError(
                "Cannot make letter to non-personal account {}"
                .format(account.account_name)
            )

        mappings = mappers.get_account_mappings(account, password)

        if account.owner_type == self.const.entity_group:
            mappings.update(self._get_group_account_mappings(account))
        elif account.owner_type == self.const.entity_person:
            mappings.update(self._get_person_account_mappings(account,
                                                              tpl['type']))
        else:
            raise CerebrumError("Unsupported account owner type %s"
                                .format(account.owner_type))
        return mappings
