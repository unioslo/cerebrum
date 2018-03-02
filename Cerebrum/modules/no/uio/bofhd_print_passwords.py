#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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
from six import text_type

import cereconf

import Cerebrum.modules.printutils.bofhd_misc_print_passwords as base
from Cerebrum.modules.bofhd.errors import CerebrumError


class BofhdExtension(base.BofhdExtension):

    """ Alter how password letters are printed at UiO. """

    def _get_default_printer(self, session):
        """ Get a default printer for the prompt. """
        previous = super(BofhdExtension, self)._get_default_printer(session)
        return previous or 'pullprint'

    def _get_printer(self, session, template):
        """ Get printer preset. """
        if template.get('lang', '').endswith("letter"):
            return cereconf.PRINT_PRINTER
        return 'pullprint'

    def _can_set_spool_user(self, session, template):
        """ Can spool user be set? """
        return self._get_printer(session, template) == 'pullprint'

    def _get_mappings(self, account, tpl):
        """ Get mappings for a given template.

        :param Cerebrum.Account account: The account to generate mappings for
        :param dict tpl: The template to generate mappings for

        :return dict: A dictionary of mappings for the TemplateHandler.

        """
        mapping = dict()

        # Add account owner info to mappings
        owner_type = self.const.EntityType(account.owner_type)
        if owner_type == self.const.entity_group:
            group = self._get_group(account.owner_id, idtype='id')
            mapping['group'] = group.group_name
        elif owner_type == self.const.entity_person:
            person = self._get_person('id', account.owner_id)
            mapping['fullname'] = person.get_name(self.const.system_cached,
                                                  self.const.name_full)
        else:
            raise CerebrumError("Unsupported account owner type %s" %
                                text_type(owner_type))

        # TODO: Replace with template system from CRB-2443
        # TODO: Too much business logic is tied up to the template 'language'
        if tpl.get('lang', '').endswith('letter'):
            if account.owner_type != self.const.entity_person:
                raise CerebrumError(
                    ("Cannot make letter to non-personal account %s " %
                     account.account_name))

            # Barcode
            mapping['barcode'] = 'barcode_%d.eps' % account.entity_id

            # Address
            address = None
            for source, kind in (
                    (self.const.system_sap, self.const.address_post),
                    (self.const.system_fs, self.const.address_post),
                    (self.const.system_sap, self.const.address_post_private),
                    (self.const.system_fs, self.const.address_post_private)):
                address = person.get_entity_address(source=source, type=kind)
                if address:
                    break
            if not address:
                raise CerebrumError(
                    "Couldn't get authoritative address for %s" %
                    account.account_name)
            address = address[0]
            alines = address['address_text'].split("\n")+[""]
            mapping['address_line1'] = mapping['fullname']
            if alines:
                mapping['address_line2'] = alines[0]
                mapping['address_line3'] = alines[1]
            else:
                mapping['address_line2'] = ""
                mapping['address_line3'] = ""
            mapping['zip'] = address['postal_number']
            mapping['city'] = address['city']
            mapping['country'] = address['country']
            mapping['birthdate'] = person.birth_date.strftime('%Y-%m-%d')

        # latex template expects UTF-8
        for k, v in mapping.items():
            if not v:
                continue
            mapping[k] = v.encode('UTF-8')

        return mapping
