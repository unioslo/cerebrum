# -*- coding: utf-8 -*-
#
# Copyright 2006-2020 University of Oslo, Norway
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
from __future__ import unicode_literals

import json
from collections import defaultdict

from six import text_type

from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.OrgLDIF import OrgLDIF
from Cerebrum.modules.LDIFutils import normalize_string
from Cerebrum.modules.no.nmh import StudentStudyProgramCache


# TODO: NmhOrgLDIFMixin

class nmhOrgLDIFMixin(OrgLDIF):  # noqa: N801

    # Fetch mail addresses from entity_contact_info of accounts, not persons.
    person_contact_mail = False

    def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']
        self.attr2syntax['roomNumber'] = (None, None, normalize_string)
        self.person = Factory.get('Person')(self.db)
        self.pe2fagomr = self.get_fagomrade()
        self.pe2fagmiljo = self.get_fagmiljo()
        self.pe2study_program = self.get_study_programs()

    def test_omit_ou(self):
        """Not using Stedkode, so all OUs are available (there is no need to
        look for special spreads).
        """
        return False

    def get_fagomrade(self):
        """
        NMH wants 'fagomrade' exported, which consists one or more 'fagfelt'.

        This field is stored in a trait for each person. The trait string value
        is a JSON-serialized list of strings.
        """
        person2fagfelt = dict()

        for row in self.person.list_traits(self.const.trait_fagomrade_fagfelt):
            try:
                fagfelt = json.loads(row['strval'])
            except Exception, exc:
                self.logger.warn(
                    "Could not JSON-deserialize trait_fagomrade_fagfelt "
                    "for person:%s, %s",
                    row['entity_id'], exc)
                continue

            person2fagfelt[row['entity_id']] = fagfelt

        return person2fagfelt

    def get_fagmiljo(self):
        """
        Returns a dict mapping from person_id to 'fagmiljø'.

        NMH wants 'fagmiljø' exported, which is retrieved from SAP as 'utvalg'
        and stored in a trait for each person. We blindly treat them as
        plaintext.
        """
        return dict(
            (row['entity_id'], row['strval'])
            for row in self.person.list_traits(self.const.trait_fagmiljo))

    def get_study_programs(self):
        """Returns a dict mapping from person_id to 'studienivakode'
        and 'arstall_kull'."""
        sspc = StudentStudyProgramCache.StudentStudyProgramCache(
            db=self.db, logger=self.logger, max_age={'hours': 12})
        if sspc.data is None:
            raise Exception('Unable to load student study program cache')
        return sspc.data

    def init_attr2id2contacts(self):
        """Override to include more, local data from contact info."""
        sap, fs = self.const.system_sap, self.const.system_fs
        c = [(a, self.get_contacts(contact_type=t,
                                   source_system=s,
                                   convert=self.attr2syntax[a][0],
                                   verify=self.attr2syntax[a][1],
                                   normalize=self.attr2syntax[a][2]))
             for a, s, t in (
                 ('telephoneNumber', sap, self.const.contact_phone),
                 ('mobile', (sap, fs), self.const.contact_mobile_phone),
                 ('facsimileTelephoneNumber', sap, self.const.contact_fax),
                 ('labeledURI', None, self.const.contact_url))]
        self.id2labeledURI = c[-1][1]
        self.attr2id2contacts = [v for v in c if v[1]]

        # roomNumber
        # Some employees have registered their office addresses in SAP.
        # We store this as co.contact_office. The roomNumber is the alias.
        attr = 'roomNumber'
        syntax = self.attr2syntax[attr]
        c = self.get_contact_aliases(
            contact_type=self.const.contact_office,
            source_system=self.const.system_sap,
            convert=syntax[0],
            verify=syntax[1],
            normalize=syntax[2])
        if c:
            self.attr2id2contacts.append((attr, c))

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

        return dict((key, self.attr_unique(values, normalize=normalize))
                    for key, values in cont_tab.iteritems())

    def make_person_entry(self, row, person_id):
        """Override the production of a person entry to output.

        NMH needs more data for their own use, e.g. to be used by their web
        pages."""
        dn, entry, alias_info = self.__super.make_person_entry(row, person_id)
        if dn:
            urns = entry.setdefault('eduPersonEntitlement', set())
            # Add fagomrade/fagfelt, if registered for the person:
            fagf = self.pe2fagomr.get(person_id, [])
            for f in fagf:
                urns.add('urn:mace:feide.no:nmh.no:fagomrade:{}'.format(f))
            # Add fagmiljø:
            fagm = self.pe2fagmiljo.get(person_id)
            if fagm:
                urns.add('urn:mace:feide.no:nmh.no:fagmiljo:{}'.format(fagm))
            # Add study programs
            study_programs = self.pe2study_program.get(person_id, [])
            urn_format = 'urn:mace:feide.no:nmh.no:studies/studyprogram/{}/{}'
            for program in study_programs:
                urn = urn_format.format(program['studieprogramkode'],
                                        program['arstall_kull'])
                urns.add(urn)
        return dn, entry, alias_info
