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

import os
import time

import cereconf

import Cerebrum.modules.printutils.bofhd_misc_print_passwords as base
from Cerebrum import Errors
from Cerebrum.modules.bofhd.errors import CerebrumError


class BofhdExtension(base.BofhdExtension):

    """ Alter how password letters are printed at UiA. """

    def _template_filename(self, operator, tpl):
        u""" Generate a filename for the template. """
        op = self._get_account(operator.get_entity_id(), idtype='id')
        now = time.strftime("%Y-%m-%d-%H%M%S", time.localtime())
        return "%s-%s-%s.%s" % (
            op.account_name, now, os.getpid(), tpl.get('fmt', 'file'))

    def _get_printer(self, session, template):
        """ Get printer preset.

        UIA doesn't actually print the files, but copies them onto a file
        exchange server. We just need a placeholder printer name here to
        prevent the misc_print_passwords from asking.

        """
        return getattr(cereconf, 'PRINT_PRINTER', 'no_printer')

    def _get_mappings(self, account, tpl):
        """ Get mappings for a given template. """
        mapping = dict()

        if account.owner_type == self.const.entity_group:
            grp = self._get_group(account.owner_id, idtype='id')
            mapping['fullname'] = 'group:%s' % grp.group_name
            mapping['birthdate'] = account.created_at.strftime('%Y-%m-%d')
        elif account.owner_type == self.const.entity_person:
            person = self._get_person('entity_id', account.owner_id)
            mapping['fullname'] = person.get_name(self.const.system_cached,
                                                  self.const.name_full)
            mapping['birthdate'] = person.birth_date.strftime('%Y-%m-%d')
        else:
            raise CerebrumError(
                "Unsupported owner type. Please use `misc list_passwords'")

        if tpl.get('lang', '').endswith("letter"):
            mapping['barcode'] = 'barcode_%s.eps' % account.entity_id
            mapping.update(
                dict.fromkeys(('address_line1', 'address_line2',
                               'address_line3', 'zip', 'city', 'country'), ''))

            if account.owner_type == self.const.entity_person:
                address = None
                for source, kind in (
                        (self.const.system_sap, self.const.address_post),
                        (self.const.system_fs, self.const.address_post),
                        (self.const.system_fs,
                         self.const.address_post_private)):
                    address = person.get_entity_address(source=source,
                                                        type=kind)
                    if address:
                        break
                if address:
                    mapping['address_line1'] = mapping.get('fullname', '')
                    address = address[0]
                    if address['address_text']:
                        alines = address['address_text'].split("\n")+[""]
                        mapping['address_line2'] = alines[0]
                        mapping['address_line3'] = alines[1]
                    mapping['zip'] = address['postal_number']
                    mapping['city'] = address['city']
                    mapping['country'] = address['country']
            try:
                mapping['emailadr'] = account.get_primary_mailaddress()
            except Errors.NotFoundError:
                mapping['emailadr'] = ''

        return mapping
