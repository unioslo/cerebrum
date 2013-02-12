# -*- coding: iso-8859-1 -*-
# Copyright 2006-2007 University of Oslo, Norway
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

from Cerebrum.Utils import Factory
from Cerebrum.modules.no.OrgLDIF import *

class nmhOrgLDIFMixin(OrgLDIF):
    def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']
        self.person = Factory.get('Person')(self.db)
        self.pe2fagomr = self.get_fagomrade()

    def test_omit_ou(self):
        # Not using Stedkode, so all OUs are available (there is no need to
        # look for special spreads).
        return False

    def get_fagomrade(self):
        """NMH wants 'fagomrade' exported, which consists of 'fagfelt' and
        'instrument'. Both fields are stored in traits for each person.

        """
        fagfelts = dict((row['entity_id'], row['strval']) for row in
                    self.person.list_traits(self.const.trait_fagomrade_fagfelt))
        instr = dict((row['entity_id'], row['strval']) for row in
                 self.person.list_traits(self.const.trait_fagomrade_instrument))
        return fagfelts, instr

    def init_attr2id2contacts(self):
        """Override to include 'mobile' data from contact info."""
        sap, fs = self.const.system_sap, self.const.system_fs
        c = [(a, self.get_contacts(contact_type  = t,
                                   source_system = s,
                                   convert       = self.attr2syntax[a][0],
                                   verify        = self.attr2syntax[a][1],
                                   normalize     = self.attr2syntax[a][2]))
             for a,s,t in (('telephoneNumber', fs, self.const.contact_phone),
                           ('mobile', sap, self.const.contact_mobile_phone),
                           ('facsimileTelephoneNumber', sap,
                                                        self.const.contact_fax),
                           ('labeledURI', None, self.const.contact_url))]
        self.logger.info("in nmh's init_attr2id2contacts!!!!!!!")
        self.id2labeledURI    = c[-1][1]
        self.attr2id2contacts = [v for v in c if v[1]]

        # TODO: roomNumbers

    def make_person_entry(self, row):
        """Override the production of a person entry to output.
        
        NMH needs more data for their own use, e.g. to be used by their web
        pages."""
        dn, entry, alias_info = self.__super.make_person_entry(row)
        if dn:
            p_id = int(row['person_id'])
            # Add fagfelt and instrument, if registered for the person:
            fagf = self.pe2fagomr[0].get(p_id, '')
            inst = self.pe2fagomr[1].get(p_id, '')
            if fagf or inst:
                urn = 'urn:mace:uio.no:nmh.no:fagomrade:%s,%s' % (fagf, inst)
                entry.setdefault('eduPersonEntitlement', []).append(urn)
        return dn, entry, alias_info

    # Fetch mail addresses from entity_contact_info of accounts, not persons.
    person_contact_mail = False
