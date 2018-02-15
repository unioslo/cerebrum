# -*- coding: utf-8 -*-
# Copyright 2004-2014 University of Oslo, Norway
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

import re
import pickle
from os.path import join as join_paths
from collections import defaultdict

import cereconf

from Cerebrum.modules.no.OrgLDIF import norEduLDIFMixin
from Cerebrum.modules.OrgLDIF import postal_escape_re
from Cerebrum.modules.LDIFutils import (
    ldapconf, normalize_string, hex_escape_match)
from Cerebrum.Utils import make_timer

# Replace these characters with spaces in OU RDNs.
ou_rdn2space_re = re.compile('[#\"+,;<>\\\\=\0\\s]+')


class OrgLDIFUiOMixin(norEduLDIFMixin):
    """Mixin class for norEduLDIFMixin(OrgLDIF) with UiO modifications."""

    from cereconf import LDAP_PERSON
    if not LDAP_PERSON['dn'].startswith('ou='):
        def __init__(self, db, logger):
            self.__super.__init__(db, logger)
            self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']
            self.attr2syntax['uioVisiblePrivateMobile'] = \
                self.attr2syntax['mobile']
    else:
        # Hacks for old LDAP structure
        def __init__(self, db, logger):
            self.__super.__init__(db, logger)
            self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']
            self.attr2syntax['uioVisiblePrivateMobile'] = \
                self.attr2syntax['mobile']
            # Used by make_ou_dn() for for migration to ny-ldap.uio.no:
            self.used_new_DNs = {}
            self.ou_quarantined = {}
            self.dn2new_structure = {'ou=organization,dc=uio,dc=no':
                                     'cn=organization,dc=uio,dc=no',
                                     'ou=--,ou=organization,dc=uio,dc=no':
                                     'cn=organization,dc=uio,dc=no'}

    def init_ou_dump(self):
        self.__super.init_ou_dump()
        self.get_ou_quarantines()
        ou2parent = dict((c, p)
                         for p, ous in self.ou_tree.items()
                         for c in ous)

        class Id2ou(dict):
            # For missing id2ous, cache and return nearest parent or None
            def __missing__(self, key):
                val = self[key] = self[ou2parent.get(key)]
                return val

        self.ou_id2ou_uniq_id = Id2ou(self.ou_id2ou_uniq_id)
        self.ou_id2ou_uniq_id.setdefault(None, None)

    def test_omit_ou(self):
        return (not self.ou.has_spread(self.const.spread_ou_publishable)) or \
            self.ou_quarantined.get(self.ou.entity_id, False)

    def get_ou_quarantines(self):
        for row in self.ou.list_entity_quarantines(
                entity_types=self.const.entity_ou,
                quarantine_types=self.const.quarantine_ou_notvalid,
                only_active=True):
            self.ou_quarantined[int(row['entity_id'])] = True

    def make_ou_dn(self, entry, parent_dn):
        # Change from superclass:
        # Replace special characters with spaces instead of escaping them.
        # Replace multiple whitespace with a single space.  strip() the result.
        # Add fake attributes as info to migration scripts at ny-ldap.uio.no,
        # which needs to undo the above hacks: '#dn' with the new DN, and
        # '#remove: ou' for OU values that are added by this method.
        new_structure_dn = self.__super.make_ou_dn(
            entry, self.dn2new_structure[parent_dn])
        norm_new_dn = normalize_string(new_structure_dn)
        if norm_new_dn in self.used_new_DNs:
            new_structure_dn = "%s=%s+%s" % (
                self.FEIDE_attr_ou_id, entry[self.FEIDE_attr_ou_id][0],
                new_structure_dn)
        self.used_new_DNs[norm_new_dn] = True
        entry['#dn'] = (new_structure_dn,)
        rdn_ou = ou_rdn2space_re.sub(' ', entry['ou'][0]).strip()
        entry['ou'] = self.attr_unique(entry['ou'], normalize_string)
        ou_count = len(entry['ou'])
        entry['ou'].insert(0, rdn_ou)
        entry['ou'] = self.attr_unique(entry['ou'], normalize_string)
        if len(self.attr_unique(entry['ou'], normalize_string)) > ou_count:
            entry['#remove: ou'] = (rdn_ou,)
        dn = self.__super.make_ou_dn(entry, parent_dn)
        self.dn2new_structure.setdefault(dn, new_structure_dn)
        return dn

    def init_attr2id2contacts(self):
        # Change from superclass: Include 'mobile' as well.
        contact_source = getattr(self.const,
                                 cereconf.LDAP['contact_source_system'])
        contacts = [(attr, self.get_contacts(
            contact_type=contact_type,
            source_system=source_system,
            convert=self.attr2syntax[attr][0],
            verify=self.attr2syntax[attr][1],
            normalize=self.attr2syntax[attr][2]))
            for attr, source_system, contact_type in (
                ('telephoneNumber', contact_source, self.const.contact_phone),
                ('mobile', contact_source, self.const.contact_mobile_phone),
                ('uioVisiblePrivateMobile', contact_source,
                 self.const.contact_private_mobile_visible),
                ('facsimileTelephoneNumber', contact_source,
                 self.const.contact_fax),
                ('labeledURI', None, self.const.contact_url))]

        self.id2labeledURI = contacts[-1][1]
        self.attr2id2contacts = [v for v in contacts if v[1]]

    def make_address(self, sep,
                     p_o_box, address_text, postal_number, city, country):
        # Changes from superclass:
        # Weird algorithm for when to use p_o_box.
        # Append "Blindern" to postbox.
        if country:
            country = self.const.Country(country).country
        if (p_o_box and int(postal_number or 0) / 100 == 3):
            address_text = "Pb. %s - Blindern" % p_o_box
        else:
            address_text = (address_text or "").strip()
        post_nr_city = None
        if city or (postal_number and country):
            post_nr_city = " ".join(filter(None, (postal_number,
                                                  (city or "").strip())))
        val = "\n".join(filter(None, (address_text, post_nr_city, country)))
        if sep == '$':
            val = postal_escape_re.sub(hex_escape_match, val)
        return val.replace("\n", sep)

    def init_person_course(self):
        """Populate dicts with a person's course information."""
        timer = make_timer(self.logger, 'Processing person courses...')
        self.ownerid2urnlist = pickle.load(file(
            join_paths(ldapconf(None, 'dump_dir'), "ownerid2urnlist.pickle")))
        timer("...person courses done.")

    def init_person_groups(self):
        """Populate dicts with a person's group information."""
        timer = make_timer(self.logger, 'Processing person groups...')
        self.person2group = pickle.load(file(
            join_paths(ldapconf(None, 'dump_dir'), "personid2group.pickle")))
        timer("...person groups done.")

    def init_person_dump(self, use_mail_module):
        """Supplement the list of things to run before printing the
        list of people."""
        self.__super.init_person_dump(use_mail_module)
        self.init_person_course()
        self.init_person_groups()
        self.init_person_office365_consents()

    def init_person_titles(self):
        # Change from original: Search titles first by system_lookup_order,
        # then within each system let personal title override work title.
        timer = make_timer(self.logger, 'Fetching personal titles...')
        titles = defaultdict(dict)
        for name_type in (self.const.personal_title, self.const.work_title):
            for row in self.person.search_name_with_language(
                    entity_type=self.const.entity_person,
                    name_variant=name_type,
                    name_language=self.languages):
                titles[int(row['entity_id'])].setdefault(
                    int(row['name_language']), row['name'])
        self.person_titles = dict([(p_id, t.items())
                                   for p_id, t in titles.items()])
        timer("...personal titles done.")

    def make_uioPersonScopedAffiliation(self, p_id, pri_aff, pri_ou):
        # [primary|secondary]:<affiliation>@<status>/<stedkode>
        ret = []
        pri_aff_str, pri_status_str = pri_aff
        for aff, status, ou in self.affiliations[p_id]:
            # populate the caches
            if aff in self.aff_cache:
                aff_str = self.aff_cache[aff]
            else:
                aff_str = str(self.const.PersonAffiliation(aff))
                self.aff_cache[aff] = aff_str
            if status in self.status_cache:
                status_str = self.status_cache[status]
            else:
                status_str = str(self.const.PersonAffStatus(status).str)
                self.status_cache[status] = status_str
            p = 'secondary'
            if (aff_str == pri_aff_str
                    and status_str == pri_status_str and ou == pri_ou):
                p = 'primary'
            ou = self.ou_id2ou_uniq_id[ou]
            if ou:
                ret.append(''.join((p, ':', aff_str, '/', status_str, '@', ou)))
        return ret

    def make_person_entry(self, row, person_id):
        """ Extend with UiO functionality. """
        dn, entry, alias_info = self.__super.make_person_entry(row, person_id)
        if not dn:
            return dn, entry, alias_info

        # Add or extend entitlements
        if person_id in self.ownerid2urnlist:
            urnlist = self.ownerid2urnlist[person_id]
            if 'eduPersonEntitlement' in entry:
                entry['eduPersonEntitlement'].update(urnlist)
            else:
                entry['eduPersonEntitlement'] = set(urnlist)

        # Add person ID
        entry['uioPersonID'] = str(person_id)

        # Add group memberships
        if person_id in self.person2group:
            # TODO: remove member and uioPersonObject after transition period
            entry['uioMemberOf'] = entry['member'] = \
                self.person2group[person_id]
            entry['objectClass'].extend(('uioMembership', 'uioPersonObject'))

        # Add scoped affiliations
        pri_edu_aff, pri_ou, pri_aff = self.make_eduPersonPrimaryAffiliation(
            person_id)
        entry['uioPersonScopedAffiliation'] = \
            self.make_uioPersonScopedAffiliation(person_id, pri_aff, pri_ou)

        # Add the uioPersonObject class if missing
        if 'uioPersonObject' not in entry['objectClass']:
            entry['objectClass'].extend(('uioPersonObject',))

        # Check if there exists «avvikende» (deviant) addresses.
        # If so, export them instead.
        addrs = self.addr_info.get(person_id)
        post = addrs and addrs.get(int(self.const.address_other_post))
        if post:
            a_txt, p_o_box, p_num, city, country = post
            post = self.make_address("$", p_o_box, a_txt, p_num, city, country)
            if post:
                entry['postalAddress'] = (post,)
        street = addrs and addrs.get(int(self.const.address_other_street))
        if street:
            a_txt, p_o_box, p_num, city, country = street
            street = self.make_address(", ", None, a_txt, p_num, city, country)
            if street:
                entry['street'] = (street,)

        # Add Office 365 consents
        if person_id in self.office365_consents:
            entry['uioOffice365consent'] = 'TRUE'

        return dn, entry, alias_info

    def _calculate_edu_OUs(self, p_ou, s_ous):
        return s_ous

    def init_person_selections(self, *args, **kwargs):
        """ Extend with UiO settings for person selections.

        This is especially for `no.uio.OrgLDIF.is_person_visible()`, as UiO has
        some special needs in how to interpret visibility of persons due to
        affiliations for reservation and consent, which behaves differently in
        SAPUiO and FS.

        """
        self.__super.init_person_selections(*args, **kwargs)
        # Set what affiliations that should be checked for visibility from SAP
        # and FS. The default is to set the person to NOT visible, which happens
        # for all persons that doesn't have _any_ of the affiliations defined
        # here.
        self.visible_sap_affs = (int(self.const.affiliation_ansatt),)
        tilkn_aff = int(self.const.affiliation_tilknyttet)
        self.visible_sap_statuses = (
            (tilkn_aff, int(self.const.affiliation_tilknyttet_ekst_stip)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_frida_reg)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_innkjoper)),
            (tilkn_aff, int(self.const.
                            affiliation_tilknyttet_assosiert_person)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_ekst_forsker)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_emeritus)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_gjesteforsker)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_bilag)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_ekst_partner)),
        )
        student = int(self.const.affiliation_student)
        self.fs_aff_statuses = (
            (student, int(self.const.affiliation_status_student_aktiv)),
            (student, int(self.const.affiliation_status_student_drgrad)))
        self.sap_res = self.init_person_group("SAP-elektroniske-reservasjoner")
        self.fs_samtykke = self.init_person_group("FS-aktivt-samtykke")

    def is_person_visible(self, person_id):
        """ Override with UiO specific visibility.

        At UiO, visibility is controlled differently depending on what source
        system the person is from. SAPUiO has reservations, while FS has active
        consents. Since we don't fetch source systems per affiliation from
        Cerebrum in `OrgLDIF`, we only guess.

        The reason for this override, is to support priority. SAP has priority
        over FS, which can't be implemented through the configuration as of
        today.

        Note that the settings in `cereconf.LDAP_PERSON['visible_selector']` is
        ignored by this override. The list of affiliations are hardcoded in the
        method `init_person_selections`.

        """
        # TODO: this could be changed to check the trait 'reserve_public'
        # later, so we don't have to check group memberships.
        #
        # The trait behaves in the following manner:
        # Every person should be 'invisible', except if:
        #  * The person has a trait of the type 'reserve_public', and
        #  * The trait's numval is set to 0
        # This means that a missing trait should be considered as a reservation.

        p_affs = self.affiliations[person_id]
        # If there is an affiliation from SAP then consider
        # reservations/permissions from SAP only.
        for (aff, status, ou) in p_affs:
            if aff in self.visible_sap_affs:
                return person_id not in self.sap_res
            if (aff, status) in self.visible_sap_statuses:
                return person_id not in self.sap_res
        # Otherwise, if there is an affiliaton STUDENT/<aktiv or drgrad>,
        # check for permission from FS to make the person visible.
        for (aff, status, ou) in p_affs:
            if (aff, status) in self.fs_aff_statuses:
                return person_id in self.fs_samtykke
        # Otherwise hide the person.
        return False

    def init_person_office365_consents(self):
        """Fetch the IDs of persons who have consented
        to being exported to Office 365."""
        timer = make_timer(self.logger, 'Fetching Office 365 consents...')
        consents = self.person.list_consents(
            consent_code=self.const.consent_office365)
        self.office365_consents = set([c['entity_id'] for c in consents])
        timer('...Office 365 consents done.')
