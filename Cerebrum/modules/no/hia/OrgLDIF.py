# -*- coding: iso-8859-1 -*-
# Copyright 2004-2012 University of Oslo, Norway
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

from collections import defaultdict

from Cerebrum.modules.LDIFutils import verify_printableString, normalize_string

from Cerebrum.modules.no.OrgLDIF import *

class OrgLDIFHiAMixin(norEduLDIFMixin):
    """Mixin class for norEduLDIFMixin(OrgLDIF) with HiA modifications."""

    def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']
        self.attr2syntax['roomNumber'] = (iso2utf, None, normalize_string)

    def init_attr2id2contacts(self):
        # Changes from the original:
        # - Get phone and fax from system_manual, others from system_sap.
        # - Add mobile and roomNumber.
        sap, manual = self.const.system_sap, self.const.system_manual

        c = [(a, self.get_contacts(contact_type  = t,
                                   source_system = s,
                                   convert       = self.attr2syntax[a][0],
                                   verify        = self.attr2syntax[a][1],
                                   normalize     = self.attr2syntax[a][2]))
             for a,s,t in (('telephoneNumber', manual, self.const.contact_phone),
                           ('facsimileTelephoneNumber',
                            manual, self.const.contact_fax),
                           ('mobile', sap, self.const.contact_mobile_phone),
                           ('labeledURI', None, self.const.contact_url))]
        self.id2labeledURI    = c[-1][1]
        self.attr2id2contacts = [v for v in c if v[1]]

        # roomNumber
        # Some employees have registered their office addresses in SAP. We store
        # this as co.contact_office. The roomNumber is the alias.
        attr = 'roomNumber'
        syntax = self.attr2syntax[attr]
        c = self.get_contact_aliases(
            contact_type  = self.const.contact_office,
            source_system = self.const.system_sap,
            convert       = syntax[0],
            verify        = syntax[1],
            normalize     = syntax[2])
        if c:
            self.attr2id2contacts.append((attr, c))

    def get_contact_aliases(self, contact_type=None,
            source_system=None, convert=None, verify=None, normalize=None):
        """Return a dict {entity_id: [list of contact aliases]}."""
        # The code mimics a reduced modules/OrgLDIF.py:get_contacts().
        entity = Entity.EntityContactInfo(self.db)
        cont_tab = defaultdict(list)
        if not convert:
            convert = str
        if not verify:
            verify = bool
        for row in entity.list_contact_info(source_system = source_system,
                                            contact_type  = contact_type):
            alias = convert(str(row['contact_alias']))
            if alias and verify(alias):
                cont_tab[int(row['entity_id'])].append(alias)

        return dict((key, self.attr_unique(values, normalize=normalize))
                    for key, values in cont_tab.iteritems())
