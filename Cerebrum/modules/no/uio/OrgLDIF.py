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

# Replace these characters with spaces in OU RDNs.
ou_rdn2space_re = re.compile('[#\"+,;<>\\\\=\0\\s]+')

class OrgLDIFUiOMixin(norEduLDIFMixin):
    """Mixin class for norEduLDIFMixin(OrgLDIF) with UiO modifications."""

    def __init__(self, db, logger):
        self.__super.__init__(db, logger)
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
            new_structure_dn = "norEduOrgUnitUniqueNumber=%s+%s" % (
                entry['norEduOrgUnitUniqueNumber'][0],
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

    def make_address(sep, p_o_box, address_text, postal_number, city, country):
        # Changes from superclass:
        # Weird algorithm for when to use p_o_box.
        # Append "Blindern" to postbox.
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
    make_address = staticmethod(make_address)

# arch-tag: e13d2650-dd88-4cac-a5fb-6a7cc6884914
