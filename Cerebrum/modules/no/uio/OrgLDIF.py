# -*- coding: iso-8859-1 -*-
# Copyright 2004, 2006 University of Oslo, Norway
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

import pickle
from Cerebrum.modules.no.OrgLDIF import *

# Replace these characters with spaces in OU RDNs.
ou_rdn2space_re = re.compile('[#\"+,;<>\\\\=\0\\s]+')

class OrgLDIFUiOMixin(norEduLDIFMixin):
    """Mixin class for norEduLDIFMixin(OrgLDIF) with UiO modifications."""

    from cereconf import LDAP_PERSON
    if not LDAP_PERSON['dn'].startswith('ou='):

      def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']

    else:
      # Hacks for old LDAP structure

      def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']
        # Used by make_ou_dn() for for migration to ny-ldap.uio.no:
        self.used_new_DNs = {}
        self.dn2new_structure = {'ou=organization,dc=uio,dc=no':
                                 'cn=organization,dc=uio,dc=no',
                                 'ou=--,ou=organization,dc=uio,dc=no':
                                 'cn=organization,dc=uio,dc=no'}

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
        s = getattr(self.const, cereconf.LDAP['contact_source_system'])
        c = [(a, self.get_contacts(contact_type  = t,
                                   source_system = s,
                                   convert       = self.attr2syntax[a][0],
                                   verify        = self.attr2syntax[a][1],
                                   normalize     = self.attr2syntax[a][2]))
             for a,s,t in (('telephoneNumber', s, self.const.contact_phone),
                           ('mobile', s, self.const.contact_mobile_phone),
                           ('facsimileTelephoneNumber',
                            s, self.const.contact_fax),
                           ('labeledURI', None, self.const.contact_url))]
        self.id2labeledURI    = c[-1][1]
        self.attr2id2contacts = [v for v in c if v[1]]

    def update_person_entry(self, entry, row):
        # Temporary hack for backwards compatibility with data from LT:
        # Append attribute value 'mobile' to 'telephoneNumber'.
        self.__super.update_person_entry(entry, row)
        if 'mobile' in entry:
            entry['telephoneNumber'] = self.attr_unique(
                entry.get('telephoneNumber', []) + entry['mobile'],
                normalize=normalize_phone)

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
        return iso2utf(val.replace("\n", sep))

    def init_person_course(self):
        """Populate dicts with a person's course information."""
        timer = self.make_timer("Processing person courses...")
        fn = "/cerebrum/dumps/LDAP/ownerid2urnlist.pickle"
        self.ownerid2urnlist = pickle.load(file(fn))
        timer("...person courses done.") 

    def init_person_groups(self):
        """Populate dicts with a person's group information."""
        timer = self.make_timer("Processing person groups...")
        fn = "/cerebrum/dumps/LDAP/personid2group.pickle"
        self.person2group = pickle.load(file(fn))
        timer("...person groups done.") 

    def init_person_dump(self, use_mail_module):
        """Suplement the list of things to run before printing the
        list of people."""
        self.__super.init_person_dump(use_mail_module)
        self.init_person_course()
        self.init_person_groups()

    def init_person_titles(self):
        # Change from original: Search titles first by system_lookup_order,
        # then within each system let personal title override work title.
        timer = self.make_timer("Fetching personal titles...")
        self.person_title = person_title = {}
        for source in self.system_lookup_order:
            for name_type in (int(self.const.name_personal_title),
                              int(self.const.name_work_title)):
                for row in self.person.list_persons_name(source_system=source,
                                                         name_type=name_type):
                    person_title.setdefault(int(row['person_id']), row['name'])
        timer("...personal titles done.")

    def make_person_entry(self, row):
        """Add data from person_course to a person entry."""
        dn, entry, alias_info = self.__super.make_person_entry(row)
        p_id = int(row['person_id'])
        if not dn:
            return dn, entry, alias_info
        if self.ownerid2urnlist.has_key(p_id):
            entry['eduPersonEntitlement'] = self.ownerid2urnlist[p_id]
        if self.person2group.has_key(p_id):
            entry['member'] = self.person2group[p_id]
            entry['objectClass'].append('uioPersonObject')
                
        return dn, entry, alias_info
# arch-tag: e13d2650-dd88-4cac-a5fb-6a7cc6884914
