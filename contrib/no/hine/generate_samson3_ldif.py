#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2012 University of Oslo, Norway
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

import cerebrum_path, cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules import LDIFutils
from Cerebrum.QuarantineHandler import QuarantineHandler

class Samson3LDIF(object):
    """This class builds an LDIF with username, password, email address,
       given name and last name, for import to Samson3"""
    def load_quaratines(self):
        # Collect all quarantines
        self.quarantines = {}
        for row in self.account.list_entity_quarantines(
                entity_types=self.const.entity_account, only_active=True):
            self.quarantines.setdefault(int(row['entity_id']), []).append(
                int(row['quarantine_type']))

    def make_auths(self, auth_type, old=None):
        # Collect authentication information
        auth = old or {}
        for row in self.account.list_account_authentication(auth_type):
            auth[int(row['account_id'])] = (row['entity_name'],
                                            row['auth_data'])
        return auth

    def __init__(self):
        # Init a lot of the things we need
        self.samson3_dn = LDIFutils.ldapconf('SAMSON3', 'dn', None)
        self.db = Factory.get('Database')()
        self.const = Factory.get('Constants')(self.db)
        self.account = Factory.get('Account')(self.db)
        self.person = Factory.get('Person')(self.db)

        # Collect password hashes..
        self.auth = self.make_auths(self.const.auth_type_md5_crypt)
        # ..and quarantines..
        self.load_quaratines()
        # ..and define a place to store the catalogobjects before writing LDIF.
        self.entries = []

    def prep(self):
        # This function collects the information that should be exported.
        # It also enforces quarantines.

        aff_to_select = [self.const.PersonAffiliation(x) for x in \
                         cereconf.LDAP_SAMSON3['affiliation']]

        # We select all persons with a specific affiliation:
        for ac in self.account.list_accounts_by_type(
                affiliation = aff_to_select):
            # We get the account name and password hash
            self.account.clear()
            self.account.find(ac.account_id)
            auth = self.auth[self.account.entity_id]
            auth = '{crypt}' + auth[1]
            
            # Set the hash to None if the account is quarantined.
            if ac.account_id in self.quarantines:
                # FIXME: jsama, 2012-03-21:
                # Commenting out these lines is a quick fix. Spreads might not
                # be totally sane as of this writing, so if anyone has a
                # quarantine, don't export the password hash. We don't care
                # about them rules defined in cereconf.

                #qh = QuarantineHandler(self.db, self.quarantines[ac.account_id],
                #                       spreads=[self.const.spread_ldap_account])
                #if qh.should_skip():
                #    continue
                #if qh.is_locked():
                #     auth = None
                auth = None

            # Get the persons names
            self.person.clear()
            self.person.find(self.account.owner_id)
            surname = self.person.get_name(self.const.system_cached,
                                             self.const.name_last)
            given_name = self.person.get_name(self.const.system_cached,
                                              self.const.name_first)
            common_name = self.person.get_name(self.const.system_cached,
                                               self.const.name_full)
           
            # We convert to utf
            surname = LDIFutils.iso2utf(surname)
            given_name = LDIFutils.iso2utf(given_name)
            common_name = LDIFutils.iso2utf(common_name)
            username = LDIFutils.iso2utf(self.account.account_name)

            # Get the email address
            email = self.account.get_primary_mailaddress()

            # Construct the distinguished name
            dn = ','.join(('uid=' + username, self.samson3_dn))
            # Stuff all data in a dict
            entry = {
                    'uid': username,
                    'mail': email,
                    'cn': common_name,
                    'sn': surname,
                    'givenName': given_name,
                    'objectClass': 'inetOrgPerson',
                    }
            if auth: # Export password attribute unless quarantine
                entry['userPassword'] = auth
            # Put the DN and dict in a list, to be written to file later.
            self.entries.append({'dn': dn, 'entry': entry})

    def dump(self):
        # This function uses LDIFWriter to properly format an LDIF file.
        fd = LDIFutils.LDIFWriter('SAMSON3', cereconf.LDAP_SAMSON3['file'])
        fd.write_container()
        for e in self.entries:
            fd.write(LDIFutils.entry_string(e['dn'], e['entry'], False))
        fd.close()

# Main function responsible for running stuff.
# Instantiate, prepare data, and dump them
def main():
    s = Samson3LDIF()
    s.prep()
    s.dump()

if __name__ == '__main__':
    main()
