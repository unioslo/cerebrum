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

assert False, "Not finished.  Decide what variable TODO should be."

from Cerebrum.modules.OrgLDIF import *

class norEduLDIFMixin(OrgLDIF):
    """Mixin class for OrgLDIF, adding FEIDE attributes to the LDIF output.

    Adds object classes norEdu<Org,OrgUnit,Person> from the FEIDE schema:
    <http://www.feide.no/feide-prosjektet/dokumenter/ldap/FEIDEldap.html>.

    Expects:
    'Cerebrum.modules.no.Stedkode/Stedkode'     in cereconf.CLASS_OU,
    'Cerebrum.modules.no.Person/PersonFnrMixin' in cereconf.CLASS_PERSON."""

    def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.norEduOrgUniqueNumber = ("000%05d"  # Note: 000 = Norway in FEIDE.
                                      % cereconf.DEFAULT_INSTITUSJONSNR,)
        # '@<security domain>' for the eduPersonPrincipalName attribute.
        self.eduPPN_domain = '@' + cereconf.INSTITUTION_DOMAIN_NAME

    def update_base_object_entry(self, entry):
        # Changes from superclass:
        # Add object class norEduOrg and its attribute norEduOrgUniqueNumber,
        # and optionally eduOrgHomePageURI, labeledURI and labeledURIObject.
        entry['objectClass'].append('norEduOrg')
        entry['norEduOrgUniqueNumber'] = self.norEduOrgUniqueNumber
        uri = entry.get('labeledURI') or entry.get('eduOrgHomePageURI')
        if uri:
            entry.setdefault('eduOrgHomePageURI', uri)
            if entry.setdefault('labeledURI', uri):
                entry['objectClass'].append('labeledURIObject')

    def get_orgUnitUniqueNumber(self):
        # Make norEduOrgUnitUniqueNumber attribute from the current OU.
        return "%02d%02d%02d" % \
               (self.ou.fakultet, self.ou.institutt, self.ou.avdeling)

    def update_dummy_ou_entry(self, entry):
        # Changes from superclass:
        # If root_ou_id is set is found, add object class norEduOrgUnit and
        # its attributes cn, norEduOrgUnitUniqueNumber, norEduOrgUniqueNumber.
        if self.root_ou_id is None:
            return
        self.ou.clear()
        self.ou.find(self.root_ou_id)
        entry.update({
            'objectClass': ['top', 'organizationalUnit', 'norEduOrgUnit'],
            'cn':                        (cereconf.LDAP_DUMMY_OU_NAME,),
            'norEduOrgUnitUniqueNumber': (self.get_orgUnitUniqueNumber(),),
            'norEduOrgUniqueNumber':     self.norEduOrgUniqueNumber})

    def fill_ou_entry_contacts(self, entry):
        # Changes from superclass:
        # Add mail attribute (allowed by the norEdu* object classes).
        # Do not add labeledURIObject; either object class norEduOrgUnit
        # or the update_base_object_entry routine will allow labeledURI.
        ou_id = self.ou.ou_id
        for attr, id2contact in self.attr2id2contacts:
            contact = id2contact.get(ou_id)
            if contact:
                entry[attr] = contact
        entry['mail'] = self.get_contacts(
            entity_id    = ou_id,
            contact_type = int(self.const.contact_email),
            verify       = verify_IA5String,
            normalize    = normalize_IA5String)
        post_string, street_string = self.make_entity_addresses(
            self.ou, self.system_lookup_order)
        if post_string:
            entry['postalAddress'] = (post_string,)
        if street_string:
            entry['street'] = (street_string,)

    def make_ou_entry(self, ou_id, parent_dn):
        # Changes from superclass:
        # Only output OUs with katalog_merke == 'T'.
        # Add object class norEduOrgUnit and its attributes norEduOrgAcronym,
        # cn, norEduOrgUnitUniqueNumber, norEduOrgUniqueNumber.
        # If a DN is not unique, prepend the norEduOrgUnitUniqueNumber.
        self.ou.clear()
        self.ou.find(ou_id)
        if self.ou.katalog_merke != 'T':
            return parent_dn, None
        ou_names = [iso2utf((n or '').strip()) for n in (self.ou.acronym,
                                                         self.ou.short_name,
                                                         self.ou.display_name)]
        acronym  = ou_names[0]
        ou_names = filter(None, ou_names)
        entry = {
            'objectClass': ['top', 'organizationalUnit', 'norEduOrgUnit'],
            'norEduOrgUnitUniqueNumber': (self.get_orgUnitUniqueNumber(),),
            'norEduOrgUniqueNumber':     self.norEduOrgUniqueNumber,
            'ou': ou_names,
            'cn': ou_names[-1:]}
        if acronym:
            entry['norEduOrgAcronym'] = (acronym,)
        dn = self.make_ou_dn(entry, parent_dn or self.org_dn)
        if not dn:
            return parent_dn, None
        entry['ou'] = self.attr_unique(entry['ou'], normalize_string)
        self.fill_ou_entry_contacts(entry)
        self.update_ou_entry(entry)
        return dn, entry

    def make_ou_dn(self, entry, parent_dn):
        # Change from superclass:
        # If the preferred DN is already used, include
        # norEduOrgUnitUniqueNumber in the RDN as well.
        dn = "ou=%s,%s" % (
            dn_escape_re.sub(hex_escape_match, entry['ou'][0]), parent_dn)
        if dn in self.used_DNs:
            dn = "norEduOrgUnitUniqueNumber=%s+%s" % (
                dn_escape_re.sub(hex_escape_match,
                                 entry['norEduOrgUnitUniqueNumber'][0]),
                dn)
        return dn

    def init_person_dump(self, use_mail_module):
        self.__super.init_person_dump(use_mail_module)
        timer = self.make_timer("Fetching fodselsnrs...")
        self.fodselsnrs = self.person.getdict_fodselsnr()
        timer("...fodselsnrs done.")

    def list_persons(self):
        # Change from superclass:
        # Include birth dates.
        return TODO.list_LDAP_persons_bdate(self.person_spread)

    def update_person_entry(self, entry, row):
        # Changes from superclass:
        # If possible, add object class norEduPerson and its attributes
        # norEduPersonNIN, norEduPersonBirthDate, eduPersonPrincipalName.
        self.__super.update_person_entry(entry, row)
        uname = entry.get('uid')
        fnr = self.fodselsnrs.get(int(row['person_id']))
        if uname and fnr:
            entry['objectClass'].append('norEduPerson')
            entry['eduPersonPrincipalName'] = (uname[0] + self.eduPPN_domain,)
            entry['norEduPersonNIN'] = (str(fnr),)
            birth_date = row['birth_date']
            if birth_date:
                entry['norEduPersonBirthDate'] = (birth_date.replace('-', ''),)
