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
""" This module contains a password print command for UiA. """
from __future__ import unicode_literals
import cereconf

import Cerebrum.modules.printutils.bofhd_misc_print_passwords as base
from Cerebrum import Errors
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.templates import mappers


class BofhdExtension(base.BofhdExtension):
    def _get_printer(self, session, template):
        """ Get printer preset.

        UIA doesn't actually print the files, but copies them onto a file
        exchange server. We just need a placeholder printer name here to
        prevent the misc_print_passwords from asking.

        """
        return getattr(cereconf, 'PRINT_PRINTER', 'no_printer')

    def _get_group_account_mappings(self, account, tmpl_type):
        grp = self._get_group(account.owner_id, idtype='id')
        mapping = dict()
        if tmpl_type == 'letter':
            mapping.update(dict.fromkeys(
                ('address_line2', 'address_line3', 'zip', 'city', 'country'),
                ''
            ))
        mapping['fullname'] = 'group:%s' % grp.group_name
        mapping['birthdate'] = account.created_at.strftime('%Y-%m-%d')
        return mapping

    def _get_person_account_mappings(self, account, tmpl_type):
        person = self._get_person('id', account.owner_id)
        mappings = mappers.get_person_info(person, self.const)

        if tmpl_type == 'letter':
            address_lookups = (
                (self.const.system_sap, self.const.address_post),
                (self.const.system_fs, self.const.address_post),
                (self.const.system_fs, self.const.address_post_private)
            )
            address = mappers.get_person_address(person, address_lookups)
            mappings.update(mappers.get_address_mappings(address))
            try:
                mappings['email_adr'] = account.get_primary_mailaddress()
            except Errors.NotFoundError:
                mappings['email_adr'] = ''
        return mappings

    def _get_mappings(self, account, password, tpl):
        """ Get mappings for a given template. """
        mappings = super(BofhdExtension, self)._get_mappings(
            account, password, tpl
        )

        if account.owner_type == self.const.entity_group:
            mappings.update(self._get_group_account_mappings(account,
                                                             tpl['type']))
        elif account.owner_type == self.const.entity_person:
            mappings.update(self._get_person_account_mappings(account,
                                                              tpl['type']))
        else:
            raise CerebrumError(
                "Unsupported owner type. Please use `misc list_passwords'")

        return mappings
