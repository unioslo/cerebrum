# -*- coding: iso-8859-1 -*-
# Copyright 2004 University of Oslo, Norway
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

from Cerebrum.modules.no.OrgLDIF import *

class OrgLDIFHiAMixin(norEduLDIFMixin):
    """Mixin class for norEduLDIFMixin(OrgLDIF) with HiA modifications."""

    def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']

    def init_attr2id2contacts(self):
        self.__super.init_attr2id2contacts()
        attr = 'mobile'
        source = getattr(self.const, cereconf.LDAP['contact_source_system'])
        syntax = self.attr2syntax[attr]
        c = self.get_contacts(
            contact_type  = self.const.contact_phone_cellular,
            source_system = source,
            convert       = syntax[0],
            verify        = syntax[1],
            normalize     = syntax[2])
        if c:
            self.attr2id2contacts.append((attr, c))

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
