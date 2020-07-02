# -*- coding: utf-8 -*-
#
# Copyright 2004-2020 University of Oslo, Norway
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
import logging
from collections import defaultdict

from six import text_type

from Cerebrum import Entity
from Cerebrum.modules.no.OrgLDIF import OrgLdifEntitlementsMixin
from Cerebrum.modules.LDIFutils import (
    attr_unique,
    normalize_string,
)
from Cerebrum.Utils import make_timer

logger = logging.getLogger(__name__)


class OrgLDIFHiAMixin(OrgLdifEntitlementsMixin):
    """Mixin class for norEduLDIFMixin(OrgLDIF) with HiA modifications."""

    def __init__(self, *args, **kwargs):
        super(OrgLDIFHiAMixin, self).__init__(*args, **kwargs)
        self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']
        self.attr2syntax['roomNumber'] = (None, None, normalize_string)

    def init_attr2id2contacts(self):
        # Changes from the original:
        # - Get phone and fax from system_manual, others from system_sap.
        # - Add mobile and roomNumber.
        sap, manual = self.const.system_sap, self.const.system_manual

        contacts = [
            (attr, self.get_contacts(contact_type=contact_type,
                                     source_system=source_system,
                                     convert=self.attr2syntax[attr][0],
                                     verify=self.attr2syntax[attr][1],
                                     normalize=self.attr2syntax[attr][2]))
            for attr, source_system, contact_type in (
                ('telephoneNumber', manual, self.const.contact_phone),
                ('facsimileTelephoneNumber', manual, self.const.contact_fax),
                ('mobile', sap, self.const.contact_mobile_phone),
                ('labeledURI', None, self.const.contact_url))]

        self.id2labeledURI = contacts[-1][1]
        self.attr2id2contacts = [v for v in contacts if v[1]]

        # roomNumber
        # Some employees have registered their office addresses in SAP.
        # We store this as co.contact_office. The roomNumber is the alias.
        attr = 'roomNumber'
        syntax = self.attr2syntax[attr]
        contacts = self.get_contact_aliases(
            contact_type=self.const.contact_office,
            source_system=self.const.system_sap,
            convert=syntax[0],
            verify=syntax[1],
            normalize=syntax[2])
        if contacts:
            self.attr2id2contacts.append((attr, contacts))

    def get_contact_aliases(self, contact_type=None, source_system=None,
                            convert=None, verify=None, normalize=None):
        """Return a dict {entity_id: [list of contact aliases]}."""
        # The code mimics a reduced modules/OrgLDIF.py:get_contacts().
        entity = Entity.EntityContactInfo(self.db)
        cont_tab = defaultdict(list)
        if not convert:
            convert = text_type
        if not verify:
            verify = bool
        for row in entity.list_contact_info(source_system=source_system,
                                            contact_type=contact_type):
            alias = convert(text_type(row['contact_alias']))
            if alias and verify(alias):
                cont_tab[int(row['entity_id'])].append(alias)

        return dict((key, attr_unique(values, normalize=normalize))
                    for key, values in cont_tab.iteritems())

    def init_person_titles(self):
        """Extends the person_titles dict with employment titles available via
        the PersonEmployment module."""
        super(OrgLDIFHiAMixin, self).init_person_titles()

        timer = make_timer(logger,
                           'Fetching personal employment titles...')
        employments = self.person.search_employment(main_employment=True)
        for emp in employments:
            if emp['person_id'] not in self.person_titles:
                title = [(self.const.language_nb, emp['description'])]
                self.person_titles[emp['person_id']] = title
        timer("...personal employment titles done.")
