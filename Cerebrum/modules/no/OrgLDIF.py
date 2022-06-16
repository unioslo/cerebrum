# -*- coding: utf-8 -*-
#
# Copyright 2004-2022 University of Oslo, Norway
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
"""
Mixins for adding norEdu* attributes to `Cerebrum.modules.OrgLDIF`.

This module implements the main Feide schema and norEdu attributes, as well as
mixins for certain norEdu attribtues/features.

py:class:`.NorEduOrgLdifMixin`
    Common Feide (norEduPerson ++) mixin.

py:class:`.OrgLdifCourseMixin`
    Mixin to provide ``eduPersonEntitlement`` from a pickle-file of course
    participation/role URNs.

py:class:`.OrgLdifEntitlementsMixin`
    Mixin to provide ``eduPersonEntitlement`` from a JSON-file of
    person-id -> entitlement-list mappings.

py:class:`.NorEduSmsAuthnMixin`
    Mixin to provide `norEduPersonAuthnMethod` from EntityContactInfo (mobile
    numbers for SMS one time codes).

py:class:`.NorEduAzureAuthnMixin`
    Mixin to enable Azure-AD authentication in Feide.
"""
from __future__ import unicode_literals

import io
import json
import logging
import os
import pickle
import re

import six
from six.moves.urllib.parse import quote

from Cerebrum.Entity import EntityContactInfo
from Cerebrum.modules.OrgLDIF import OrgLDIF
from Cerebrum.modules.LDIFutils import (attr_unique,
                                        normalize_string,
                                        verify_IA5String,
                                        verify_emailish,
                                        normalize_IA5String,
                                        hex_escape_match,
                                        dn_escape_re)
from Cerebrum.Utils import make_timer

logger = logging.getLogger(__name__)


class NorEduOrgLdifMixin(OrgLDIF):
    """
    Mixin class for OrgLDIF, adding FEIDE attributes to the LDIF output.

    Adds object classes norEdu<Org,OrgUnit,Person> from the FEIDE schema:
    <http://www.feide.no/ldap-schema-feide>.

    cereconf.py setup:

    Add 'Cerebrum.modules.no.Person/PersonFnrMixin' to cereconf.CLASS_PERSON.

    Either add 'Cerebrum.modules.no.Stedkode/Stedkode' to cereconf.CLASS_OU
    or override get_unique_ou_id() in a cereconf.CLASS_ORGLDIF mixin.

    cereconf.LDAP['FEIDE_schema_version']: '1.5' (current default) to '1.5.1'.
    If it is a sequence of two versions, use the high version but
    include obsolete attributes from the low version.  This may be
    useful in a transition stage between schema versions.
    """

    FEIDE_schema_version = '1.6'
    FEIDE_obsolete_version = None
    FEIDE_class_obsolete = None

    def __init__(self, *args, **kwargs):
        super(NorEduOrgLdifMixin, self).__init__(*args, **kwargs)

        root = self.config.org.parent
        schema_v = root.get('FEIDE_schema_version', default=None)
        obsolete_v = root.get('FEIDE_obsolete_schema_version', default=None)
        if isinstance(schema_v, (tuple, list)):
            schema_v, obsolete_v = max(*schema_v), min(*schema_v)

        if schema_v:
            self.FEIDE_schema_version = schema_v

        if obsolete_v:
            self.FEIDE_obsolete_version = obsolete_v
            self.FEIDE_class_obsolete = 'norEduObsolete'
        logger.debug("FEIDE schema version: %s", self.FEIDE_schema_version)
        logger.debug("FEIDE obsolete version: %s", self.FEIDE_obsolete_version)

        if self.config.org_id is None:
            self.norEduOrgUniqueID = None
        else:
            self.norEduOrgUniqueID = ("000%05d" % self.config.org_id,)
        logger.debug("norEduOrgUniqueIdentifier: %s", self.norEduOrgUniqueID)

        # '@<security domain>' for the eduPersonPrincipalName attribute.
        self.homeOrg = self.config.domain_name
        logger.debug("schacHomeOrganization: %s", self.homeOrg)

        self.FEIDE_ou_common_attrs = {}
        self.ou_uniq_id2ou_id = {}
        self.ou_id2ou_uniq_id = {}
        self.primary_aff_traits = {}
        # For caching strings of affiliations, int(aff) -> str(aff).
        self.aff_cache = {}
        # For caching strings of statuses, int(st) -> str(st).
        self.status_cache = {}
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
            entry['norEduOrgUniqueIdentifier'] = self.norEduOrgUniqueID
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

    def get_unique_ou_id(self):
        # Make norEduOrgUnitUniqueIdentifier attribute from the current OU.
        # Requires 'Cerebrum.modules.no.Stedkode/Stedkode' in CLASS_OU.
        return "%02d%02d%02d" % (self.ou.fakultet,
                                 self.ou.institutt,
                                 self.ou.avdeling)

    def update_dummy_ou_entry(self, entry):
        # Changes from superclass:
        # If root_ou_id is set is found, add object class norEduOrgUnit and its
        # attrs cn, norEduOrgUnitUniqueIdentifier, norEduOrgUniqueIdentifier.
        if self.root_ou_id is None:
            return
        self.ou.clear()
        self.ou.find(self.root_ou_id)
        ldap_ou_id = self.get_unique_ou_id()
        entry.update({
            'objectClass': ['top', 'organizationalUnit', 'norEduOrgUnit'],
            'cn': (self.config.ou.get('dummy_name'),),
            'norEduOrgUnitUniqueIdentifier': (ldap_ou_id,),
        })
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
            logger.warn("No names could be located for ou_id=%s", ou_id)
            return parent_dn, None

        ldap_ou_id = self.get_unique_ou_id()
        self.ou_uniq_id2ou_id[ldap_ou_id] = ou_id
        self.ou_id2ou_uniq_id[ou_id] = ldap_ou_id
        entry = {
            'objectClass': ['top', 'organizationalUnit', 'norEduOrgUnit'],
            'norEduOrgUnitUniqueIdentifier': (ldap_ou_id,)}
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
                entry[attr] = attr_unique(entry[attr], normalize_string)
        self.fill_ou_entry_contacts(entry)
        self.update_ou_entry(entry)
        return dn, entry

    def make_person_entry(self, row, person_id):
        """Override to add Feide specific functionality."""
        dn, entry, alias_info = super(NorEduOrgLdifMixin,
                                      self).make_person_entry(row, person_id)
        if not dn:
            return dn, entry, alias_info
        pri_edu_aff, pri_ou, pri_aff = self.make_edu_person_primary_aff(
            person_id)
        if pri_edu_aff:
            entry['eduPersonPrimaryAffiliation'] = pri_edu_aff
            entry['eduPersonPrimaryOrgUnitDN'] = (
                self.ou2DN.get(int(pri_ou)) or self.dummy_ou_dn)

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
            ldap_ou_id = entry['norEduOrgUnitUniqueIdentifier'][0]
            dn = "%s=%s+%s" % (
                'norEduOrgUnitUniqueIdentifier',
                dn_escape_re.sub(hex_escape_match, ldap_ou_id),
                dn)
        return dn

    def make_edu_person_primary_aff(self, p_id):
        """
        Ad hoc solution for eduPersonPrimaryAffiliation.

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
        def lookup_selector(aff, status):
            selector = self.config.person.get(
                'eduPersonPrimaryAffiliation_selector', default=None)
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
                    p, a = lookup_selector(aff_str, status_str)
                    if p:
                        return a, ou, (aff_str, status_str)
            p, a = lookup_selector(aff_str, status_str)
            if p and (pri is None or p < pri):
                pri = p
                pri_aff = (aff_str, status_str)
                pri_ou = ou
                pri_edu_aff = a
        if pri_aff is None:
            logger.warn(
                "Person '%s' did not get eduPersonPrimaryAffiliation. "
                "Check his/her affiliations "
                "and eduPersonPrimaryAffiliation_selector.", p_id)
        return pri_edu_aff, pri_ou, pri_aff

    def init_person_basic(self):
        super(NorEduOrgLdifMixin, self).init_person_basic()
        self._get_primary_aff_traits()

    def _get_primary_aff_traits(self):
        """Fill L{self.primary_aff_traits} with override traits for selecting
        what affiliation that should be the person's primary aff.

        Used to override what should be in eduPersonPrimaryAffiliation.

        """
        if not hasattr(self.const, 'trait_primary_aff'):
            return
        timer = make_timer(logger, 'Fetching primary aff traits...')
        for row in self.person.list_traits(code=self.const.trait_primary_aff):
            p_id = row['entity_id']
            val = row['strval']
            m = re.match(r"(\w+)\/(\w+)@(\w+)", val)
            if m and m.group(3) in self.ou_uniq_id2ou_id:
                self.primary_aff_traits[p_id] = (
                    m.group(1), m.group(2), self.ou_uniq_id2ou_id[m.group(3)])
        timer("...primary aff traits done.")

    def init_person_dump(self, use_mail_module):
        super(NorEduOrgLdifMixin, self).init_person_dump(use_mail_module)
        self.init_person_fodselsnrs()
        self.init_person_birth_dates()

    def init_person_fodselsnrs(self):
        # Set self.fodselsnrs = dict {person_id: str or instance with fnr}
        # str(fnr) will return the person's "best" fodselsnr, or ''.
        timer = make_timer(logger, 'Fetching fodselsnrs...')
        self.fodselsnrs = self.person.getdict_fodselsnr()
        timer("...fodselsnrs done.")

    def init_person_birth_dates(self):
        # Set self.birth_dates = dict {person_id: birth date}
        timer = make_timer(logger, 'Fetching birth dates...')
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
        super(NorEduOrgLdifMixin, self).update_person_entry(entry, row,
                                                            person_id)
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


class NorEduSmsAuthnMixin(NorEduOrgLdifMixin):
    """
    Mixin to provide MFA-attributes for one time codes by SMS to Feide.

    This mixin will add mobile numbers to the ``norEduPersonAuthnMethod``
    attribute, if supported for the given person.

    The ``cereconf.LDAP_PERSON['norEduPersonAuthnMethod_selector']`` setting
    controls which phone numbers can be used for this purpose, and for which
    persons.
    """

    feide_authn_method_sms_fmt = (
        'urn:mace:feide.no:auth:method:sms {value} label={label}')

    # Replaced by `_set_sms_authn_label` and labels from config by default.
    # To hard-code labels - override `_set_sms_authn_label with a no-op and
    # override this dict with (aff, source, type) -> label mappings.
    feide_authn_method_sms_labels = {}

    def _set_sms_authn_label(self, affiliation, source_system, contact_type,
                             label):
        """
        Set label for a given sms authn method.

        This is called by py:meth:`.person_authn_selection` - which reads
        labels from ``cereconf.LDAP_PERSON[norEduPersonAuthnMethod_selector]``.

        Labels from config are cached in
        py:attr:`.feide_authn_method_sms_labels` for later use by
        py:meth:`._get_sms_authn_label`

        :type affiliation: Cerebrum.Constants._PersonAffiliationCode
        :type source_system: Cerebrum.Constants._AuthoritativeSystemCode
        :type contact_type: Cerebrum.Constants._ContactInfoCode
        :type label: six.text_type
        """
        if not label:
            return
        key = (
            six.text_type(affiliation),
            six.text_type(source_system),
            six.text_type(contact_type),
        )
        if not hasattr(self, 'feide_authn_method_sms_labels'):
            self.feide_authn_method_sms_labels = dict()
        self.feide_authn_method_sms_labels[key] = six.text_type(label)

    def _get_sms_authn_label(self, affiliation, source_system,
                             contact_type, contact_value):
        """
        Get label for a given sms authn method.

        This method may be overridden to provide e.g. partial phone numbers in
        the auth method labels, or to change how labels are generated e.g. by
        affiliation.

        :type affiliation: Cerebrum.Constants._PersonAffiliationCode
        :type source_system: Cerebrum.Constants._AuthoritativeSystemCode
        :type contact_type: Cerebrum.Constants._ContactInfoCode
        :type contact_value: six.text_type

        :returns:
            A properly quoted label for the given authn method.
        """
        key = (
            six.text_type(affiliation),
            six.text_type(source_system),
            six.text_type(contact_type),
        )
        if key in self.feide_authn_method_sms_labels:
            label = self.feide_authn_method_sms_labels[key]
            return quote(label.encode('utf-8'))
        else:
            # fallback, e.g. 'PRIVATEMOBILE from SAP'
            return quote('{2} from {1}'.format(*key).encode('utf-8'))

    def _format_sms_authn_entry(self, affiliation, source_system, contact_type,
                                contact_value):
        """
        Format a norEduPersonAuthnMethod entry from contact info.

        :type affiliation: Cerebrum.Constants._PersonAffiliationCode
        :type source_system: Cerebrum.Constants._AuthoritativeSystemCode
        :type contact_type: Cerebrum.Constants._ContactInfoCode
        :type contact_value: six.text_type

        :rtype: six.text_type
        """
        return self.feide_authn_method_sms_fmt.format(
            # TODO: We really *should* sanitize/normalize value
            value=contact_value,
            label=self._get_sms_authn_label(
                affiliation,
                source_system,
                contact_type,
                contact_value,
            ),
        )

    @property
    def person_authn_selection(self):
        """ Normalized norEduPersonAuthnMethod_selector.

        Returns the ``LDAP_PERSON[norEduPersonAuthnMethod_selector]``
        mapping/setting with all strings replaced with their corresponding
        constant:

            <PersonAffiliation> -> [
              (<AuthoritativeSystem>, <ContactInfo>),
              ...
            ]
        """
        if not hasattr(self, '_person_authn_selection'):
            self._person_authn_selection = dict()

            def get_const(name, cls):
                constant = self.const.human2constant(name, cls)
                if not constant:
                    logger.warning(
                        "LDAP_PERSON[norEduPersonAuthnMethod_selector]: "
                        "Unknown %s %r", cls.__name__, name)
                return constant

            for aff, selections in self.config.person.get(
                    'norEduPersonAuthnMethod_selector',
                    default={}).items():
                aff = get_const(aff, self.const.PersonAffiliation)
                if not aff:
                    continue
                for selector, label in selections.items():
                    system, c_type = selector
                    system = get_const(system, self.const.AuthoritativeSystem)
                    c_type = get_const(c_type, self.const.ContactInfo)
                    if (not system) or (not c_type):
                        continue
                    self._set_sms_authn_label(aff, system, c_type, label)
                    self._person_authn_selection.setdefault(aff, []).append(
                        (system, c_type))
        return self._person_authn_selection

    @property
    def person_authn_methods(self):
        """ Phone numbers to use for MFA with SMS one time codes.

        Initializes self.person_authn_methods with a dict that maps person
        entity_id to a list of dicts with contact info:

            person_id -> [
              {
                'contact_type': <ContactInfo>,
                'source_system': <AuthoritativeSystem>,
                'value': <str>,
              },
              ...
            ],

        """
        if not hasattr(self, '_person_authn_methods'):
            timer = make_timer(logger,
                               'Fetching authentication methods...')
            entity = EntityContactInfo(self.db)
            cache = self._person_authn_methods = {}

            # Find the unique systems and contact types for filtering
            source_systems = set(
                (v[0] for s in self.person_authn_selection.values()
                 for v in s))
            contact_types = set(
                (v[1] for s in self.person_authn_selection.values()
                 for v in s))

            if not source_systems or not contact_types:
                # No authn methods to cache
                return cache

            # Cache contact info
            count = 0
            for row in entity.list_contact_info(
                    entity_type=self.const.entity_person,
                    source_system=list(source_systems),
                    contact_type=list(contact_types)):
                person_cache = cache.setdefault(int(row['entity_id']), [])
                c_type = self.const.ContactInfo(row['contact_type'])
                system = self.const.AuthoritativeSystem(row['source_system'])
                person_cache.append({
                    'value': six.text_type(row['contact_value']),
                    'contact_type': c_type,
                    'source_system': system,
                })
                count += 1
            logger.info('cached %d authn methods from contact info', count)
            timer("...authentication methods done.")
        return self._person_authn_methods

    def _get_sms_authn_methods(self, person_id):
        """
        Get norEduPersonAuthnMethod sms values for a person.

        :returns list: values for the norEduPersonAuthnMethod attribute
        """
        # Note: 'self.affiliations' comes from 'init_person_affiliations' -
        # default implementation in 'Cererbum.modules.OrgLDIF'
        person_affs = [aff for aff, _, _ in self.affiliations[person_id]]

        # TODO: We should probably label a little bit better, and only include
        # *one* of each phone number, even if the same number exists in more
        # than one selection.
        authn_methods = []
        for authn_entry in self.person_authn_methods.get(person_id, []):
            for aff, selection in self.person_authn_selection.items():
                if aff not in person_affs:
                    # This person doesn't have an aff that allows this authn
                    # method
                    continue
                if ((authn_entry['source_system'], authn_entry['contact_type'])
                        not in selection):
                    # This contact info type doesn't apply to this selection
                    continue

                value = self._format_sms_authn_entry(
                    aff,
                    authn_entry['source_system'],
                    authn_entry['contact_type'],
                    authn_entry['value'])
                authn_methods.append(value)

        return attr_unique(authn_methods, normalize=normalize_string)

    def update_person_entry(self, entry, row, person_id):
        super(NorEduSmsAuthnMixin, self).update_person_entry(entry, row,
                                                             person_id)

        # norEdu 1.6 introduces two-factor auth:
        if self.FEIDE_schema_version < '1.6':
            return

        # If parents didn't add the norEduPerson class, we can't add
        # norEduPerson attributes
        if 'norEduPerson' not in entry['objectClass']:
            return

        sms_methods = self._get_sms_authn_methods(person_id)

        # there *shouldn't* be any value collisions here, as SMS methods use a
        # distinct urn - if we ever make a new mixin that *also* produce
        # norEduPersonAuthnMethod values with the same urn this should be
        # re-done
        if sms_methods and entry.get('norEduPersonAuthnMethod'):
            entry['norEduPersonAuthnMethod'].extend(sms_methods)
        elif sms_methods:
            entry['norEduPersonAuthnMethod'] = sms_methods


class OrgLdifCourseMixin(NorEduOrgLdifMixin):
    """
    Mixin to provide eduPersonEntitlement from a pickle-file of URNs.

    The pickle file typically contains references to Course-objects in
    kurs.ldif (see generate_kurs_ldif.py).
    """

    # TODO: Implement enable/disable
    # TODO: Implement kwargs for providing filename
    # TODO: This mixin probably belongs alongside the code that generates the
    #       pickle data

    def __init__(self, *args, **kwargs):
        super(OrgLdifCourseMixin, self).__init__(*args, **kwargs)
        # TODO: add LDAP_PERSON entry/default and fetch using
        #       config.person.get_filename()
        self.person_course_filename = os.path.join(
            self.config.person.get('dump_dir', inherit=True),
            "ownerid2urnlist.pickle")

    def _init_person_course(self):
        """Populate dicts with a person's course information."""
        timer = make_timer(logger, 'Processing person courses...')
        self._person2urnlist = pickle.load(file(self.person_course_filename))
        timer("...person courses done.")

    def init_person_dump(self, *args, **kwargs):
        # API-method, init person data
        super(OrgLdifCourseMixin, self).init_person_dump(*args, **kwargs)
        self._init_person_course()

    def make_person_entry(self, row, person_id):
        # API-method, generate person object
        dn, entry, alias_info = super(OrgLdifCourseMixin,
                                      self).make_person_entry(row, person_id)

        # Add or extend entitlements
        if dn and person_id in self._person2urnlist:
            urnlist = self._person2urnlist[person_id]
            if 'eduPersonEntitlement' in entry:
                entry['eduPersonEntitlement'].update(urnlist)
            else:
                entry['eduPersonEntitlement'] = set(urnlist)

        return dn, entry, alias_info


class OrgLdifEntitlementsMixin(NorEduOrgLdifMixin):
    """
    Mixin to provide eduPersonEntitlement from a file.

    This class populates a eduPersonEntitlement for persons from a json file.
    The file is typically generated by
    ``contrib/no/generate_person_entitlements.py``.
    """

    def __init__(self, *args, **kwargs):
        super(OrgLdifEntitlementsMixin, self).__init__(*args, **kwargs)

        entitlements_file = self.config.person.get_filename(
            'entitlements_file', default=None)

        if entitlements_file:
            self.entitlements_file = entitlements_file
        else:
            self.entitlements_file = None

    def _init_person_entitlements(self):
        """ Load person entitlements file. """
        if hasattr(self, '_person_entitlements'):
            logger.warning('Person entitlements already loaded!')
            return

        timer = make_timer(logger, 'Loading person entitlements...')
        with io.open(self.entitlements_file, encoding='utf-8') as stream:
            e_dict = json.loads(stream.read())
        self._person_entitlements = {int(p_id): e_list
                                     for p_id, e_list in e_dict.items()}
        timer("...person entitlements done.")

    def init_person_dump(self, *args, **kwargs):
        # API-method: Init person data
        super(OrgLdifEntitlementsMixin, self).init_person_dump(*args, **kwargs)
        if self.entitlements_file:
            self._init_person_entitlements()

    def make_person_entry(self, row, person_id):
        # API-method: Generate person object
        dn, entry, alias_info = super(OrgLdifEntitlementsMixin,
                                      self).make_person_entry(row, person_id)

        # Add or extend entitlements
        if (self.entitlements_file and dn and
                person_id in self._person_entitlements):
            entitlements = self._person_entitlements[person_id]
            if 'eduPersonEntitlement' in entry:
                entry['eduPersonEntitlement'].update(entitlements)
            else:
                entry['eduPersonEntitlement'] = set(entitlements)

        return dn, entry, alias_info


class NorEduAzureAuthnMixin(NorEduOrgLdifMixin):
    """
    Mixin to enable/disable Azure-AD authentication in Feide.

    If this mixin is used, all valid norEduPerson objects *will* have:
    ::

        norEduPersonAuthnMethod: urn:mace:feide.no:auth:method:azuread -
    """
    feide_authn_method_azuread = 'urn:mace:feide.no:auth:method:azuread -'

    def update_person_entry(self, entry, row, person_id):
        super(NorEduAzureAuthnMixin, self).update_person_entry(entry, row,
                                                               person_id)

        # norEdu 1.6 introduces two-factor auth:
        if self.FEIDE_schema_version < '1.6':
            return

        # If parents didn't add the norEduPerson class, we can't add
        # norEduPerson attributes
        if 'norEduPerson' not in entry['objectClass']:
            return

        # there *shouldn't* be any value collisions here, as the "enable
        # azure-ad" value use a distinct urn - if we ever make a new mixin that
        # *also* produce norEduPersonAuthnMethod values with the same urn this
        # should be re-done
        values = attr_unique([self.feide_authn_method_azuread],
                             normalize=normalize_string)
        if values and entry.get('norEduPersonAuthnMethod'):
            entry['norEduPersonAuthnMethod'].extend(values)
        elif values:
            entry['norEduPersonAuthnMethod'] = values
