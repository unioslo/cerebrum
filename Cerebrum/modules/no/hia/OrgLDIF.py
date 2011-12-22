# -*- coding: iso-8859-1 -*-
# Copyright 2004-2010 University of Oslo, Norway
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

from Cerebrum.modules.LDIFutils import verify_printableString, normalize_string

from Cerebrum.modules.no.OrgLDIF import *

class OrgLDIFHiAMixin(norEduLDIFMixin):
    """Mixin class for norEduLDIFMixin(OrgLDIF) with HiA modifications."""

    def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']
        self.attr2syntax['roomNumber'] = (None, verify_printableString,
                                          normalize_string)

    def init_attr2id2contacts(self):
        self.__super.init_attr2id2contacts()
        source = getattr(self.const, cereconf.LDAP['contact_source_system'])

        attr = 'mobile'
        syntax = self.attr2syntax[attr]
        c = self.get_contacts(
            contact_type  = self.const.contact_mobile_phone,
            source_system = source,
            convert       = syntax[0],
            verify        = syntax[1],
            normalize     = syntax[2])
        if c:
            self.attr2id2contacts.append((attr, c))

        # roomNumber
        # Some employees have registered their office addresses in SAP. We store
        # this as co.contact_office. The roomNumber is the alias.
        attr = 'roomNumber'
        syntax = self.attr2syntax[attr]
        c = self.get_contact_aliases(
            contact_type  = self.const.contact_office,
            source_system = source,
            convert       = syntax[0],
            verify        = syntax[1],
            normalize     = syntax[2])
        if c:
            c = dict((key, c[key][0][1]) for key in c if c[key][0])
            self.attr2id2contacts.append((attr, c))

    def get_contact_aliases(self, entity_id=None, contact_type=None,
            source_system=None, convert=None, verify=None, normalize=None):
        """Return a list of contact values and aliases for the specified
        parameters, or if entity_id is None, a dict {entity_id: [contact
        values]}. Note that each contact value has the form (contact_value,
        alias).
        
        The verify method is called upon both contact_address and contact_alias.
        A new parameter might be needed for verifying aliases?"""
        entity = Entity.EntityContactInfo(self.db)
        cont_tab = {}
        if not convert:
            convert = str
        for row in entity.list_contact_info(entity_id     = entity_id,
                                            source_system = source_system,
                                            contact_type  = contact_type):
            c_list = (convert(str(row['contact_value'])), str(row['contact_alias']))
            cont_tab.setdefault(row['entity_id'], []).append(c_list)

        for key, c_list in cont_tab.iteritems():
            cont_tab[key] = self.attr_unique(
                    filter(lambda x: verify(x[0]) and verify(x[1]),
                           [c for c in c_list if c[0] not in ('', '0')]),
                    normalize = normalize)
        if entity_id is None:
            return cont_tab
        else:
            return (cont_tab.values() or ((),))[0]

    if False:
      # ??? This was unused ???

      def init_person_dump(self, use_mail_module):
        self.__super.init_person_dump(use_mail_module)
        self.primary_affiliation = (
            int(self.const.affiliation_ansatt),
            int(self.const.affiliation_status_ansatt_primaer))

      def person_dn_primaryOU(self, entry, row, person_id):
        # Change from superclass:
        # If person has affiliation ANSATT/primær, use it for the primary OU.
        for aff in self.affiliations.get(person_id, ()):
            if aff[:2] == self.primary_affiliation:
                ou_id = aff[2]
                break
        else:
            ou_id = int(row['ou_id'])
        primary_ou_dn = self.ou2DN.get(ou_id)
        return ",".join(("uid=" + entry['uid'][0],
                         (self.person_dn_suffix
                          or primary_ou_dn
                          or self.person_default_parent_dn))), primary_ou_dn

# arch-tag: f7098a5b-0019-4466-b4d7-becffc95a421
