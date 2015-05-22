# -*- coding: utf-8 -*-
# Copyright 2013 University of Oslo, Norway
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

# kbj005 2015.02.16: copied from /cerebrum/lib/python2.7/site-packages/Cerebrum/modules/no/hih

"""Mixin for OrgLDIF for UiT."""

from collections import defaultdict

from Cerebrum.Utils import Factory
from Cerebrum.modules.no.OrgLDIF import *

class OrgLDIFUiTMixin(OrgLDIF):
    def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']

    def init_attr2id2contacts(self):
        """Override to include more, local data from contact info."""
        self.__super.init_attr2id2contacts()
        sap, fs = self.const.system_sap, self.const.system_fs
        c = [(a, self.get_contacts(contact_type  = t,
                                   source_system = s,
                                   convert       = self.attr2syntax[a][0],
                                   verify        = self.attr2syntax[a][1],
                                   normalize     = self.attr2syntax[a][2]))
             for a,s,t in (('mobile', fs, self.const.contact_mobile_phone),)]
        self.attr2id2contacts.extend((v for v in c if v[1]))

    def update_org_object_entry(self, entry):
        # Changes from superclass:
        # Add attributes needed by UiT.
        self.__super.update_org_object_entry(entry)
  
        if entry.has_key('o'):
            entry['o'].append(['University of Tromsoe','Universitetet i Tromso'])
        else:
            entry['o'] = (['University of Tromsoe','Universitetet i Tromso'])
  
        if entry.has_key('eduOrgLegalName'):
            entry['eduOrgLegalName'].append(['Universitetet i Tromso','University of Tromsoe'])
        else:
            entry['eduOrgLegalName'] = (['Universitetet i Tromso','University of Tromsoe'])
        
        entry['norEduOrgNIN'] = (['NO970422528'])


    def update_ou_entry(self, entry):
        # Changes from superclass:
        # Add object class norEduOrg and its attr norEduOrgUniqueIdentifier
        entry['objectClass'].append('norEduOrg')
        entry['norEduOrgUniqueIdentifier'] = self.norEduOrgUniqueID

        # ?? Are these needed?
        # entry['objectClass'].append('eduOrg')
        # entry['objectClass'].append('norEduObsolete')
    
    def generate_person(self, outfile, alias_outfile, use_mail_module):
        """Output person tree and aliases if cereconf.LDAP_PERSON['dn'] is set.

        Aliases are only output if cereconf.LDAP_PERSON['aliases'] is true.

        If use_mail_module is set, persons' e-mail addresses are set to
        their primary users' e-mail addresses.  Otherwise, the addresses
        are taken from contact info registered for the individual persons."""

        # Changes from superclass:
        # - Persons with affiliation_ansatt_sito or affiliation_manuell_gjest_u_konto are ignored.
        # - system object is added.
        
        if not self.person_dn:
            return
        self.init_person_dump(use_mail_module)
        if self.person_parent_dn not in (None, self.org_dn):
            outfile.write(container_entry_string('PERSON'))
        timer       = self.make_timer("Processing persons...")
        round_timer = self.make_timer()
        round       = 0
        for row in self.list_persons():
            if(row[2] in [int(self.const.affiliation_ansatt_sito)]):
                # this person does not qualify to be listed in the FEIDE tree on the ldap server.
                #self.logger.warn("sito person. Not to be included")
                continue
            if (row[2] in [int(self.const.affiliation_manuell_gjest_u_konto)]):
                #self.logger.warn("person withouth account. not to be included")
                continue
            if round % 10000 == 0:
                round_timer("...rounded %d rows..." % round)
            round += 1
            dn, entry, alias_info = self.make_person_entry(row)
            if dn:
                if dn in self.used_DNs:
                    self.logger.warn("Omitting person_id %d: duplicate DN '%s'"
                                     % (row['person_id'], dn))
                else:
                    self.used_DNs[dn] = True
                    outfile.write(entry_string(dn, entry, False))
                    if self.aliases and alias_info:
                        self.write_person_alias(alias_outfile,
                                                dn, entry, alias_info)
        timer("...persons done.")
        self.generate_system_object(outfile)

    def generate_system_object(self,outfile):
        entry= {'objectClass':['top','uioUntypedObject']}
        self.ou_dn = "cn=system,dc=uit,dc=no"
        outfile.write(entry_string(self.ou_dn,entry))

