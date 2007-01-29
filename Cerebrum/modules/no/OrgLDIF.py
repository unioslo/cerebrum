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

from Cerebrum.modules.OrgLDIF import *

class norEduLDIFMixin(OrgLDIF):
    """Mixin class for OrgLDIF, adding FEIDE attributes to the LDIF output.

    Adds object classes norEdu<Org,OrgUnit,Person> from the FEIDE schema:
    <http://www.feide.no/feide-prosjektet/dokumenter/ldap/FEIDEldap.html>.

    cereconf.py setup:

    Add 'Cerebrum.modules.no.Person/PersonFnrMixin' to cereconf.CLASS_PERSON.

    Either add 'Cerebrum.modules.no.Stedkode/Stedkode' to cereconf.CLASS_OU
    or override get_orgUnitUniqueID() in a cereconf.CLASS_ORGLDIF mixin.

    cereconf.LDAP['FEIDE_schema_version']: '1.1' (current default) to '1.3'.
    If it is a sequence of two versions, use the high version but
    include obsolete attributes from the low version.  This may be
    useful in a transition stage between schema versions.

    Note that object class extensibleObject, which if the server
    supports it allows any attribute, is used instead of norEduObsolete
    and federationFeideSchema.  This avoids a FEIDE schema bug.
    cereconf.LDAP['use_extensibleObject'] = False disables this.
    """

    extensibleObject = (cereconf.LDAP.get('use_extensibleObject', True)
                        and 'extensibleObject') or None

    FEIDE_schema_version = cereconf.LDAP.get('FEIDE_schema_version', '1.1')
    FEIDE_obsolete_version = cereconf.LDAP.get('FEIDE_obsolete_schema_version')
    if isinstance(FEIDE_schema_version, (tuple, list)):
        FEIDE_obsolete_version = min(*FEIDE_schema_version)
        FEIDE_schema_version   = max(*FEIDE_schema_version)
    FEIDE_attr_org_id, FEIDE_attr_ou_id = {
        '1.1': ('norEduOrgUniqueNumber',     'norEduOrgUnitUniqueNumber'),
        '1.3': ('norEduOrgUniqueIdentifier', 'norEduOrgUnitUniqueIdentifier'),
        '1.4': ('norEduOrgUniqueIdentifier', 'norEduOrgUnitUniqueIdentifier'),
        }[FEIDE_schema_version]
    FEIDE_class_obsolete = None
    if FEIDE_obsolete_version:
        if FEIDE_schema_version >= '1.4':
            FEIDE_class_obsolete = 'norEduObsolete'
        elif FEIDE_obsolete_version <= '1.1' < FEIDE_schema_version:
            FEIDE_class_obsolete = extensibleObject
        if not FEIDE_class_obsolete:
            raise ValueError(
                "cereconf.LDAP: "
                "'FEIDE_schema_version' of '1.3' needs 'use_extensibleObject'")

    def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        try:
            orgnum = int(cereconf.DEFAULT_INSTITUSJONSNR)
        except (AttributeError, TypeError):
            self.norEduOrgUniqueID = None
            if self.FEIDE_schema_version < '1.4':
                raise
        else:
            # Note: 000 = Norway in FEIDE.
            self.norEduOrgUniqueID = ("000%05d" % orgnum,)
        self.FEIDE_ou_common_attrs = {}
        if self.FEIDE_schema_version == '1.1':
            self.FEIDE_ou_common_attrs = {
                self.FEIDE_attr_org_id: self.norEduOrgUniqueID}
        # '@<security domain>' for the eduPersonPrincipalName attribute.
        self.eduPPN_domain = '@' + cereconf.INSTITUTION_DOMAIN_NAME

    def update_org_object_entry(self, entry):
        # Changes from superclass:
        # Add object class norEduOrg and its attr norEduOrgUniqueIdentifier,
        # and optionally eduOrgHomePageURI, labeledURI and labeledURIObject.
        # Also add attribute federationFeideSchemaVersion if appropriate.
        entry['objectClass'].append('norEduOrg')
        if self.norEduOrgUniqueID:
            entry[self.FEIDE_attr_org_id] = self.norEduOrgUniqueID
        if self.FEIDE_class_obsolete:
            entry['objectClass'].append(self.FEIDE_class_obsolete)
            if self.norEduOrgUniqueID:
                entry['norEduOrgUniqueNumber'] = self.norEduOrgUniqueID
        if self.FEIDE_schema_version >= '1.4':
            entry['norEduOrgSchemaVersion'] = (self.FEIDE_schema_version,)
        elif self.FEIDE_schema_version > '1.1' and self.extensibleObject:
            entry['objectClass'].append(self.extensibleObject)
            entry['federationFeideSchemaVersion']= (self.FEIDE_schema_version,)
        uri = entry.get('labeledURI') or entry.get('eduOrgHomePageURI')
        if uri:
            entry.setdefault('eduOrgHomePageURI', uri)
            if entry.setdefault('labeledURI', uri):
                entry['objectClass'].append('labeledURIObject')

    def get_orgUnitUniqueID(self):
        # Make norEduOrgUnitUniqueIdentifier attribute from the current OU.
        return "%02d%02d%02d" % \
               (self.ou.fakultet, self.ou.institutt, self.ou.avdeling)

    def update_dummy_ou_entry(self, entry):
        # Changes from superclass:
        # If root_ou_id is set is found, add object class norEduOrgUnit and its
        # attrs cn, norEduOrgUnitUniqueIdentifier, norEduOrgUniqueIdentifier.
        if self.root_ou_id is None:
            return
        self.ou.clear()
        self.ou.find(self.root_ou_id)
        ldap_ou_id = self.get_orgUnitUniqueID()
        entry.update({
            'objectClass': ['top', 'organizationalUnit', 'norEduOrgUnit'],
            self.FEIDE_attr_ou_id:  (ldap_ou_id,)})
        if self.FEIDE_schema_version != '1.4':
            entry['cn'] = (ldapconf('OU', 'dummy_name'),)
        entry.update(self.FEIDE_ou_common_attrs)
        if self.FEIDE_class_obsolete:
            entry['objectClass'].append(self.FEIDE_class_obsolete)
            if self.norEduOrgUniqueID:
                entry['norEduOrgUniqueNumber'] = self.norEduOrgUniqueID
            entry['norEduOrgUnitUniqueNumber'] = (ldap_ou_id,)

    def fill_ou_entry_contacts(self, entry):
        # Changes from superclass:
        # Add mail attribute (allowed by the norEdu* object classes).
        # Do not add labeledURIObject; either object class norEduOrgUnit
        # or the update_org_object_entry routine will allow labeledURI.
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

    def test_skip_ou(self):
        # Return true if self.ou should be skipped.
        return getattr(self.ou, 'katalog_merke', 'T') != 'T'

    def make_ou_entry(self, ou_id, parent_dn):
        # Changes from superclass:
        # If Stedkode is used, only output OUs with katalog_merke == 'T'.
        # Add object class norEduOrgUnit and its attributes norEduOrgAcronym,
        # cn, norEduOrgUnitUniqueIdentifier, norEduOrgUniqueIdentifier.
        # If a DN is not unique, prepend the norEduOrgUnitUniqueIdentifier.
        self.ou.clear()
        self.ou.find(ou_id)
        if self.test_skip_ou():
            return parent_dn, None
        ou_names = [iso2utf((n or '').strip()) for n in (self.ou.acronym,
                                                         self.ou.short_name,
                                                         self.ou.display_name)]
        acronym  = ou_names[0]
        ou_names = filter(None, ou_names)
        ldap_ou_id = self.get_orgUnitUniqueID()
        entry = {
            'objectClass': ['top', 'organizationalUnit', 'norEduOrgUnit'],
            self.FEIDE_attr_ou_id:  (ldap_ou_id,),
            'ou': ou_names}
        if self.FEIDE_schema_version != '1.4':
            entry['cn'] = ou_names[-1:]
        entry.update(self.FEIDE_ou_common_attrs)
        if self.FEIDE_class_obsolete:
            entry['objectClass'].append(self.FEIDE_class_obsolete)
            if self.norEduOrgUniqueID:
                entry['norEduOrgUniqueNumber'] = self.norEduOrgUniqueID
            entry['norEduOrgUnitUniqueNumber'] = (ldap_ou_id,)
        if acronym and self.FEIDE_schema_version != '1.4':
            entry['norEduOrgAcronym'] = (acronym,)
        dn = self.make_ou_dn(entry, parent_dn or self.ou_dn)
        if not dn:
            return parent_dn, None
        entry['ou'] = self.attr_unique(entry['ou'], normalize_string)
        self.fill_ou_entry_contacts(entry)
        self.update_ou_entry(entry)
        return dn, entry

    def make_ou_dn(self, entry, parent_dn):
        # Change from superclass:
        # If the preferred DN is already used, include
        # norEduOrgUnitUniqueIdentifier in the RDN as well.
        dn = "ou=%s,%s" % (
            dn_escape_re.sub(hex_escape_match, entry['ou'][0]), parent_dn)
        if normalize_string(dn) in self.used_DNs:
            ldap_ou_id = entry[self.FEIDE_attr_ou_id][0]
            dn = "%s=%s+%s" % (
                self.FEIDE_attr_ou_id,
                dn_escape_re.sub(hex_escape_match, ldap_ou_id),
                dn)
        return dn

    def init_person_dump(self, use_mail_module):
        self.__super.init_person_dump(use_mail_module)
        self.init_person_fodselsnrs()
        self.init_person_birth_dates()

    def init_person_fodselsnrs(self):
        # Set self.fodselsnrs = dict {person_id: str or instance with fnr}
        # str(fnr) will return the person's "best" fodselsnr, or ''.
        timer = self.make_timer("Fetching fodselsnrs...")
        self.fodselsnrs = self.person.getdict_fodselsnr()
        timer("...fodselsnrs done.")

    def init_person_birth_dates(self):
        # Set self.birth_dates = dict {person_id: birth date}
        timer = self.make_timer("Fetching birth dates...")
        self.birth_dates = birth_dates = {}
        for row in self.person.list_persons():
            birth_date = row['birth_date']
            if birth_date:
                birth_dates[int(row['person_id'])] = birth_date
        timer("...birth dates done.")

    def update_person_entry(self, entry, row):
        # Changes from superclass:
        # If possible, add object class norEduPerson and its attributes
        # norEduPersonNIN, norEduPersonBirthDate, eduPersonPrincipalName.
        self.__super.update_person_entry(entry, row)
        uname = entry.get('uid')
        person_id = int(row['person_id'])
        fnr = self.fodselsnrs.get(person_id)
        if uname and fnr:
            entry['objectClass'].append('norEduPerson')
            entry['eduPersonPrincipalName'] = (uname[0] + self.eduPPN_domain,)
            entry['norEduPersonNIN'] = (str(fnr),)
            birth_date = self.birth_dates.get(person_id)
            if birth_date:
                entry['norEduPersonBirthDate'] = ("%04d%02d%02d" % (
                    birth_date.year, birth_date.month, birth_date.day),)

# arch-tag: f895ee98-7185-40df-83bb-96aa506d8b21
