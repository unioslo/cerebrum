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

from Cerebrum.modules.no.OrgLDIF import *
from Cerebrum.Utils import Factory
from Cerebrum import Errors

class HiNeOrgLDIFMixin(OrgLDIF):
    def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.db = Factory.get('Database')()
        self.ac = Factory.get('Account')(db)
        self.pe = Factory.get('Person')(db)
        self.co = Factory.get('Constants')(db)

    def test_omit_ou(self):
        # Not using Stedkode, so all OUs are available (there is no need to
        # look for special spreads).
        return False

    # Fetch mail addresses from entity_contact_info of accounts, not persons.
    person_contact_mail = False

    def update_person_entry(self, entry, row):
        self.__super.update_person_entry(entry, row)
        self.ac.clear()
        self.ac.find_by_name(entry['uid'])
        self.pe.clear()
        self.pe.find(self.ac.owner_id)
        addrs = self.pe.get_contact_info(source=self.co.system_fs,
                                         type=self.co.contact_email)
        if addrs and 'student' in entry['eduPersonAffiliation'] and \
                not 'employee' in entry['eduPersonAffiliation']:
            entry['mail'] = addrs.pop()['contact_value']

        # Add MD4 hash, an objectClass which allows it in the LDAP schema,
        # and an unused dummy sambaSID which that objectClass requires.
        try:
            pw4 = self.ac.get_account_authentication(self.const.auth_type_md4_nt)
        except Errors.NotFoundError:
            pass
        else:
            entry['sambaNTPassword'] = (pw4,)
            entry['sambaSID'] = ('-1',)
            entry['objectClass'].append('sambaSamAccount')
        
