# -*- coding: utf-8 -*-
# Copyright 2004-2010 University of Oslo, Norway
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
import os.path
import string

import cereconf

from Cerebrum import Entity
from Cerebrum.modules.feide.service import FeideService
from Cerebrum.modules.OrgLDIF import OrgLDIF
from Cerebrum.modules.LDIFutils import (ldapconf,
                                        normalize_string,
                                        verify_IA5String,
                                        verify_emailish,
                                        normalize_IA5String,
                                        hex_escape_match,
                                        dn_escape_re)
from Cerebrum.Utils import make_timer


class norEduLDIFMixin(OrgLDIF):
    """Mixin class for OrgLDIF, adding FEIDE attributes to the LDIF output.

    Adds object classes norEdu<Org,OrgUnit,Person> from the FEIDE schema:
    <http://www.feide.no/ldap-schema-feide>.

    cereconf.py setup:

    Add 'Cerebrum.modules.no.Person/PersonFnrMixin' to cereconf.CLASS_PERSON.

    Either add 'Cerebrum.modules.no.Stedkode/Stedkode' to cereconf.CLASS_OU
    or override get_orgUnitUniqueID() in a cereconf.CLASS_ORGLDIF mixin.

    cereconf.LDAP['FEIDE_schema_version']: '1.5' (current default) to '1.5.1'.
    If it is a sequence of two versions, use the high version but
    include obsolete attributes from the low version.  This may be
    useful in a transition stage between schema versions.

    Note that object class extensibleObject, which if the server
    supports it allows any attribute, is used instead of norEduObsolete
    and federationFeideSchema.  This avoids a FEIDE schema bug.
    cereconf.LDAP['use_extensibleObject'] = False disables this.
    """

    extensibleObject = (cereconf.LDAP.get('use_extensibleObject', True) and
                        'extensibleObject') or None

    FEIDE_schema_version = cereconf.LDAP.get('FEIDE_schema_version', '1.5')
    FEIDE_obsolete_version = cereconf.LDAP.get('FEIDE_obsolete_schema_version')

    if isinstance(FEIDE_schema_version, (tuple, list)):
        FEIDE_obsolete_version = min(*FEIDE_schema_version)
        FEIDE_schema_version = max(*FEIDE_schema_version)

    FEIDE_attr_org_id = 'norEduOrgUniqueIdentifier'
    FEIDE_attr_ou_id = 'norEduOrgUnitUniqueIdentifier'

    FEIDE_class_obsolete = None
    if FEIDE_obsolete_version:
        FEIDE_class_obsolete = 'norEduObsolete'

    def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        try:
            orgnum = int(cereconf.DEFAULT_INSTITUSJONSNR)
            self.norEduOrgUniqueID = ("000%05d" % orgnum,)
        except (AttributeError, TypeError):
            self.norEduOrgUniqueID = None
        self.FEIDE_ou_common_attrs = {}
        # '@<security domain>' for the eduPersonPrincipalName attribute.
        self.homeOrg = cereconf.INSTITUTION_DOMAIN_NAME
        self.ou_uniq_id2ou_id = {}
        self.ou_id2ou_uniq_id = {}
        self.primary_aff_traits = {}
        # For caching strings of affiliations, int(aff) -> str(aff).
        self.aff_cache = {}
        # For caching strings of statuses, int(st) -> str(st).
        self.status_cache = {}
        logger.debug("OrgLDIF norEduOrgUniqueIdentifier: %s",
                     self.norEduOrgUniqueID)
        logger.debug("OrgLDIF schacHomeOrganization: %s",
                     self.homeOrg)
        logger.debug("OrgLDIF FEIDE schema version: %s",
                     self.FEIDE_schema_version)
        logger.debug("OrgLDIF FEIDE obsolete version: %s",
                     self.FEIDE_obsolete_version)
        if not self.homeOrg and self.FEIDE_schema_version >= '1.6':
            # Is this neccessary? We should have this for everyone anyway.
            raise ValueError("HomeOrg is mandatory in schema ver 1.6")

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
        entry['norEduOrgSchemaVersion'] = (self.FEIDE_schema_version,)
        uri = entry.get('labeledURI') or entry.get('eduOrgHomePageURI')
        if uri:
            entry.setdefault('eduOrgHomePageURI', uri)
            if entry.setdefault('labeledURI', uri):
                entry['objectClass'].append('labeledURIObject')

    def test_omit_ou(self):
        """'Available' OUs have the proper spread."""
        return not self.ou.has_spread(self.const.spread_ou_publishable)

    def get_orgUnitUniqueID(self):
        # Make norEduOrgUnitUniqueIdentifier attribute from the current OU.
        # Requires 'Cerebrum.modules.no.Stedkode/Stedkode' in CLASS_OU.
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
            'cn':                  (ldapconf('OU', 'dummy_name'),),
            self.FEIDE_attr_ou_id: (ldap_ou_id,)})
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
        ou_id = self.ou.entity_id
        for attr, id2contact in self.attr2id2contacts:
            contact = id2contact.get(ou_id)
            if contact:
                entry[attr] = contact

        def verify_email(email):
            return verify_IA5String(email) and verify_emailish(email)

        entry['mail'] = self.get_contacts(
            entity_id=ou_id,
            contact_type=int(self.const.contact_email),
            verify=verify_email,
            normalize=normalize_IA5String)
        post_string, street_string = self.make_entity_addresses(
            self.ou, self.system_lookup_order)
        if post_string:
            entry['postalAddress'] = (post_string,)
        if street_string:
            entry['street'] = (street_string,)

    def make_ou_entry(self, ou_id, parent_dn):
        # Changes from superclass:
        # Add object class norEduOrgUnit and its attributes norEduOrgAcronym,
        # cn, norEduOrgUnitUniqueIdentifier, norEduOrgUniqueIdentifier.
        # If a DN is not unique, prepend the norEduOrgUnitUniqueIdentifier.
        self.ou.clear()
        self.ou.find(ou_id)
        if self.test_omit_ou():
            return parent_dn, None

        name_variants = (self.const.ou_name_acronym,
                         self.const.ou_name_short,
                         self.const.ou_name,
                         self.const.ou_name_display)
        var2pref = dict([(v, i) for i, v in enumerate(name_variants)])
        ou_names = {}
        for row in self.ou.search_name_with_language(
                entity_id=self.ou.entity_id,
                name_language=self.languages,
                name_variant=name_variants):
            name = row["name"].strip()
            if name:
                pref = var2pref[int(row['name_variant'])]
                lnames = ou_names.setdefault(pref, [])
                lnames.append((int(row['name_language']), name))
        if not ou_names:
            self.logger.warn("No names could be located for ou_id=%s", ou_id)
            return parent_dn, None

        ldap_ou_id = self.get_orgUnitUniqueID()
        self.ou_uniq_id2ou_id[ldap_ou_id] = ou_id
        self.ou_id2ou_uniq_id[ou_id] = ldap_ou_id
        entry = {
            'objectClass': ['top', 'organizationalUnit', 'norEduOrgUnit'],
            self.FEIDE_attr_ou_id: (ldap_ou_id,)}
        if 0 in ou_names:
            self.add_lang_names(entry, 'norEduOrgAcronym', ou_names[0])
        ou_names = [names for ou_pref, names in sorted(ou_names.items())]
        for names in ou_names:
            self.add_lang_names(entry, 'ou', names)
        self.add_lang_names(entry, 'cn', ou_names[-1])
        entry.update(self.FEIDE_ou_common_attrs)
        if self.FEIDE_class_obsolete:
            entry['objectClass'].append(self.FEIDE_class_obsolete)
            if self.norEduOrgUniqueID:
                entry['norEduOrgUniqueNumber'] = self.norEduOrgUniqueID
            entry['norEduOrgUnitUniqueNumber'] = (ldap_ou_id,)
        dn = self.make_ou_dn(entry, parent_dn or self.ou_dn)
        if not dn:
            return parent_dn, None

        for attr in entry.keys():
            if attr == 'ou' or attr.startswith('ou;'):
                entry[attr] = self.attr_unique(entry[attr], normalize_string)
        self.fill_ou_entry_contacts(entry)
        self.update_ou_entry(entry)
        return dn, entry

    def make_person_entry(self, row, person_id):
        """Override to add Feide specific functionality."""
        dn, entry, alias_info = self.__super.make_person_entry(row, person_id)
        if not dn:
            return dn, entry, alias_info
        pri_edu_aff, pri_ou, pri_aff = self.make_eduPersonPrimaryAffiliation(
            person_id)
        if pri_edu_aff:
            entry['eduPersonPrimaryAffiliation'] = pri_edu_aff
            entry['eduPersonPrimaryOrgUnitDN'] = (
                self.ou2DN.get(int(pri_ou)) or self.dummy_ou_dn)
        if (ldapconf('PERSON', 'entitlements_pickle_file') and
                person_id in self.person2entitlements):
            entry['eduPersonEntitlement'] = set(self.person2entitlements[person_id])

        entry['objectClass'].append('schacContactLocation')
        entry['schacHomeOrganization'] = self.homeOrg

        return dn, entry, alias_info

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

    def make_eduPersonPrimaryAffiliation(self, p_id):
        """Ad hoc solution for eduPersonPrimaryAffiliation.

        This function needs an element in cereconf.LDAP_PERSON that looks like:

           'eduPersonPrimaryAffiliation_selector': {
               'ANSATT': {'bilag': (250, 'employee'),
                          'vitenskapelig': (50, 'faculty'),
                          'tekadm' :(60, 'staff'),
                          },
                ...

        The given person's affiliation which in the config gets the *lowest*
        value is returned.

        @rtype: tuple
        @return: What is considered the person's primary affiliation, according
            to config and primary_aff trait. The tuple's elements:

                (<aff_str from config>, <ou_id>, (<aff>, <status>))

            Example:

                ('employee', 1234, ('ANSATT', 'bilag'))

        """
        def lookup_cereconf(aff, status):
            selector = cereconf.LDAP_PERSON.get(
                'eduPersonPrimaryAffiliation_selector')
            if selector and aff in selector and status in selector[aff]:
                return selector[aff][status]
            return (None, None)

        if p_id not in self.affiliations:
            return None
        pri_aff = None
        pri = None
        pri_ou = None
        pri_edu_aff = None
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
            # if a trait is set to override the general rule, we return that.
            if p_id in self.primary_aff_traits:
                if (aff_str, status_str, ou) == self.primary_aff_traits[p_id]:
                    p, a = lookup_cereconf(aff_str, status_str)
                    if p:
                        return a, ou, (aff_str, status_str)
            p, a = lookup_cereconf(aff_str, status_str)
            if p and (pri is None or p < pri):
                pri = p
                pri_aff = (aff_str, status_str)
                pri_ou = ou
                pri_edu_aff = a
        if pri_aff is None:
            self.logger.warn(
                "Person '%s' did not get eduPersonPrimaryAffiliation. "
                "Check his/her affiliations "
                "and eduPersonPrimaryAffiliation_selector in cereconf.", p_id)
        return pri_edu_aff, pri_ou, pri_aff

    def init_person_basic(self):
        self.__super.init_person_basic()
        self._get_primary_aff_traits()

    def _get_primary_aff_traits(self):
        """Fill L{self.primary_aff_traits} with override traits for selecting
        what affiliation that should be the person's primary aff.

        Used to override what should be in eduPersonPrimaryAffiliation.

        """
        if not hasattr(self.const, 'trait_primary_aff'):
            return
        timer = make_timer(self.logger, 'Fetching primary aff traits...')
        for row in self.person.list_traits(code=self.const.trait_primary_aff):
            p_id = row['entity_id']
            val = row['strval']
            m = re.match(r"(\w+)\/(\w+)@(\w+)", val)
            if m and m.group(3) in self.ou_uniq_id2ou_id:
                self.primary_aff_traits[p_id] = (
                    m.group(1), m.group(2), self.ou_uniq_id2ou_id[m.group(3)])
        timer("...primary aff traits done.")

    def init_person_dump(self, use_mail_module):
        self.__super.init_person_dump(use_mail_module)
        if ldapconf('PERSON', 'entitlements_pickle_file'):
            self.init_person_entitlements()
        self.init_person_fodselsnrs()
        self.init_person_birth_dates()

    def init_person_entitlements(self):
        """Populate dicts with a person's entitlement information."""
        timer = make_timer(self.logger, 'Processing person entitlements...')
        self.person2entitlements = pickle.load(file(
            os.path.join(
                ldapconf(None, 'dump_dir'),
                ldapconf('PERSON', 'entitlements_pickle_file'))))
        timer("...person entitlements done.")

    def init_person_fodselsnrs(self):
        # Set self.fodselsnrs = dict {person_id: str or instance with fnr}
        # str(fnr) will return the person's "best" fodselsnr, or ''.
        timer = make_timer(self.logger, 'Fetching fodselsnrs...')
        self.fodselsnrs = self.person.getdict_fodselsnr()
        timer("...fodselsnrs done.")

    def init_person_birth_dates(self):
        # Set self.birth_dates = dict {person_id: birth date}
        timer = make_timer(self.logger, 'Fetching birth dates...')
        self.birth_dates = birth_dates = {}
        for row in self.person.list_persons(person_id=self.persons):
            birth_date = row['birth_date']
            if birth_date:
                birth_dates[int(row['person_id'])] = birth_date
        timer("...birth dates done.")

    def update_person_entry(self, entry, row, person_id):
        # Changes from superclass:
        # If possible, add object class norEduPerson and its attributes
        # norEduPersonNIN, norEduPersonBirthDate, eduPersonPrincipalName.
        self.__super.update_person_entry(entry, row, person_id)
        uname = entry.get('uid')
        fnr = self.fodselsnrs.get(person_id)
        birth_date = self.birth_dates.get(person_id)

        # uid is mandatory for norEduPerson
        if not uname:
            return

        entry['eduPersonPrincipalName'] = '%s@%s' % (uname[0], self.homeOrg)

        # Prior to norEdu 1.5.1, fnr is mandatory for norEduPerson
        if fnr or self.FEIDE_schema_version >= '1.5.1':
            entry['objectClass'].append('norEduPerson')
            entry['displayName'] = entry['norEduPersonLegalName'] = entry['cn']

            if birth_date:
                entry['norEduPersonBirthDate'] = ("%04d%02d%02d" % (
                    birth_date.year, birth_date.month, birth_date.day),)

            if fnr:
                entry['norEduPersonNIN'] = (str(fnr),)

            # norEdu 1.6 introduces two-factor auth:
            if self.FEIDE_schema_version >= '1.6':
                self.update_person_authn(entry, person_id)

    @property
    def person_authn_selection(self):
        u""" Returns norEduPersonAuthnMethod_selector with constants.

        Returns the LDAP_PERSON[norEduPersonAuthnMethod_selector] setting with
        all strings replaced with their corresponding constant.

        """
        if not hasattr(self, '_person_authn_selection'):
            self._person_authn_selection = dict()

            def get_const(name, cls):
                constant = self.const.human2constant(name, cls)
                if not constant:
                    self.logger.warn(
                        "LDAP_PERSON[norEduPersonAuthnMethod_selector]: "
                        "Unknown %s %r", cls.__name__, name)
                return constant

            for aff, selections in ldapconf('PERSON',
                                            'norEduPersonAuthnMethod_selector',
                                            {}).iteritems():
                aff = get_const(aff, self.const.PersonAffiliation)
                if not aff:
                    continue
                for system, c_type in selections:
                    system = get_const(system, self.const.AuthoritativeSystem)
                    c_type = get_const(c_type, self.const.ContactInfo)
                    if (not system) or (not c_type):
                        continue
                    self._person_authn_selection.setdefault(aff, []).append(
                        (system, c_type))
        return self._person_authn_selection

    @property
    def person_authn_methods(self):
        """ Returns a contact info mapping for update_person_authn.

        Initializes self.person_authn_methods with a dict that maps person
        entity_id to a list of dicts with contact info:

            person_id: [ {'contact_type': <const>,
                          'source_system': <const>,
                          'value': <str>, },
                         ... ],
            ...

        """
        if not hasattr(self, '_person_authn_methods'):
            timer = make_timer(self.logger,
                               'Fetching authentication methods...')
            entity = Entity.EntityContactInfo(self.db)
            self._person_authn_methods = dict()

            # Find the unique systems and contact types for filtering
            source_systems = set(
                (v[0] for s in self.person_authn_selection.itervalues()
                 for v in s))
            contact_types = set(
                (v[1] for s in self.person_authn_selection.itervalues()
                 for v in s))

            if not source_systems or not contact_types:
                # No authn methods to cache
                return self._person_authn_methods

            # Cache contact info
            count = 0
            for row in entity.list_contact_info(
                    entity_type=self.const.entity_person,
                    source_system=list(source_systems),
                    contact_type=list(contact_types)):
                c_type = self.const.ContactInfo(row['contact_type'])
                system = self.const.AuthoritativeSystem(row['source_system'])
                self._person_authn_methods.setdefault(
                    int(row['entity_id']), list()).append(
                        {'value': str(row['contact_value']),
                         'contact_type': c_type,
                         'source_system': system, })
                count += 1
            timer("...authentication methods done.")
        return self._person_authn_methods

    @property
    def person_authn_levels(self):
        """ Returns a authentication level mapping for update_person_authn.

        Initializes self.person_authn_levels with a dict that maps person
        entity_id to a set of service authentication levels:

            person_id: set([ (feide_service_id, authentication_level),
                         ... ]),
            ...

        """
        if not hasattr(self, '_person_authn_levels'):
            supported = ldapconf('PERSON', 'norEduPersonAuthnMethod_selector',
                                 {})
            if not supported:
                self._person_authn_levels = {}
                return self._person_authn_levels
            timer = make_timer(self.logger,
                               'Fetching authentication levels...')
            fse = FeideService(self.db)
            self._person_authn_levels = fse.get_person_to_authn_level_map()
            timer("...authentication levels done.")
        return self._person_authn_levels

    def update_person_authn(self, entry, person_id):
        """ Add authentication info to the entry.

        This method should be overridden to provide the LDAP attributes
        'norEduPersonAuthnMethod' and 'norEduPersonServiceAuthnLevel', which
        was introduced in the norEdu 1.6 specification.

        :param dict entry: The person entry to update
        :param int person_id: The Cerebrum entity_id of the person.

        """
        person_affs = [aff for aff, _s, _ou in self.affiliations[person_id]]
        template = string.Template('urn:mace:feide.no:auth:method:sms $value '
                                   'label=${source_system}%20${contact_type}')

        # Add populated template to norEduPersonAuthnMethod for each configured
        # method, if the contact data exists
        authn_methods = list()
        for authn_entry in self.person_authn_methods.get(person_id, []):
            for aff, selection in self.person_authn_selection.iteritems():
                if (aff in person_affs and
                        (authn_entry['source_system'],
                         authn_entry['contact_type']) in selection):
                    authn_methods.append(
                        template.substitute(authn_entry))
        entry['norEduPersonAuthnMethod'] = self.attr_unique(
            authn_methods, normalize=normalize_string)

        # Add norEduPersonServiceAuthnLevel entries
        authn_levels = self.person_authn_levels.get(person_id, [])
        if not authn_levels:
            return
        authn_level_template = string.Template(
            'urn:mace:feide.no:spid:${feide_id} '
            'urn:mace:feide.no:auth:level:fad08:${level}')
        authn_level_entries = []
        for feide_id, level in authn_levels:
            authn_level_entries.append(
                authn_level_template.substitute({
                    'feide_id': feide_id,
                    'level': level
                }))
        entry['norEduPersonServiceAuthnLevel'] = self.attr_unique(
            authn_level_entries, normalize=normalize_string)
