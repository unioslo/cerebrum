#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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
This module contains the functionality for building a dict consistent
with the CIM-WS schema, based on data from a Cerebrum person object.
"""

import phonenumbers
from Cerebrum.Utils import Factory
from Cerebrum.Errors import NotFoundError
from Cerebrum.utils.funcwrap import memoize


class CIMDataSource(object):
    """Fetches data and formats it for CIM."""
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self.co = Factory.get('Constants')(self.db)
        self.pe = Factory.get('Person')(self.db)
        self.ac = Factory.get('Account')(self.db)
        self.ou = Factory.get('OU')(self.db)
        self.authoritative_system = self.co.AuthoritativeSystem(
            str(self.config.authoritative_system))
        self.ou_perspective = self.co.OUPerspective(
            str(self.config.ou_perspective))

    def is_eligible(self, person_id):
        """Decide whether a person should be exported to CIM.

        :return: Export?
        :rtype: bool
        """
        self.pe.clear()
        self.pe.find(person_id)
        affs = [aff['affiliation'] for aff in self.pe.get_affiliations()]
        return self.co.affiliation_ansatt in affs

    def get_person_data(self, person_id):
        """
        Builds a dict according to the CIM-WS schema, using info stored in
        Cerebrums database about the given person.

        :param int person_id: The person's entity_id in Cerebrum
        :return: A dict with person data, with entries adhering to the
                 CIM-WS-schema.
        :rtype: dict
        """
        self.pe.clear()
        self.ac.clear()
        self.pe.find(person_id)
        self.ac.find(self.pe.get_primary_account())

        person = {}
        person['username'] = self.ac.get_account_name()

        # Get and add first and last names from authoritative system
        pe_names = self.pe.get_all_names()
        names = self._attr_filter(
            'source_system', self.authoritative_system, pe_names)
        first_name_list = self._attr_filter(
            'name_variant', self.co.name_first, names)
        last_name_list = self._attr_filter(
            'name_variant', self.co.name_last, names)
        person['firstname'] = first_name_list[0]['name']
        person['lastname'] = last_name_list[0]['name']

        # Get and add phone entries
        contact_info = self.pe.get_contact_info()
        person.update(self._get_phone_entries(contact_info))

        # Get and add email address
        try:
            person['email'] = self.ac.get_primary_mailaddress()
        except NotFoundError:
            pass

        # Get and add company info
        affs = self._attr_filter(
            'source_system',
            self.authoritative_system,
            self.pe.get_affiliations())
        primary_aff_ou_id = affs[0]['ou_id']
        person.update(self._get_org_structure(primary_aff_ou_id))

        # Get and add job title if present
        try:
            person['job_title'] = self.pe.get_name_with_language(
                name_variant=self.co.work_title,
                name_language=self.co.language_nb)
        except NotFoundError:
            pass

        return person

    def _attr_filter(self, attr_name, constant, unfiltered):
        """
        Takes a list of tuples, and returns a list of only the tuples where the
        attr with attr_name is equal to the input parameter constant.

        :param str attr_name: An attribute name.
        :param _CerebrumCode constant: A Cerebrum constant
        :param list unfiltered: An unfiltered list of tuples
        :return: A filtered list, containing only tuples with valid matches. If
                 no matches are found, the list will be empty.
        :rtype: list
        """
        return filter(lambda x: x[attr_name] == constant, unfiltered)

    def _format_phone_number(self, phone_number):
        """
        Takes a phone number, and adds a default country prefix to it if
        missing. It is assumed that phone numbers lacking a prefix, is from
        the default region defined in the configuration.

        :param unicode phone_number: A phone number
        :return: A phone number with a country prefix, or None
        :rtype: unicode
        """
        try:
            parsed_nr = phonenumbers.parse(
                number=phone_number,
                region=self.config.phone_country_default)
            if phonenumbers.is_valid_number(parsed_nr):
                return phonenumbers.format_number(
                    numobj=parsed_nr,
                    num_format=phonenumbers.PhoneNumberFormat.E164)
            return None
        except phonenumbers.NumberParseException:
            return None

    def _get_phone_entries(self, contact_info):
        """
        Based on the mappings in the configuration, extracts relevant phone
        numbers.

        :param list contact_info:
            A list of tuples with Cerebrum contact_info entries
        :return:
            The phone numbers to include in the person data.
        :rtype: dict
        """
        contact_info = self._attr_filter(
            'source_system',
            self.authoritative_system,
            contact_info)
        phones = {}
        for contact_entry in self.config.phone_mappings:
            entries = self._attr_filter(
                'contact_type',
                self.co.ContactInfo(
                    str(self.config.phone_mappings[contact_entry])),
                contact_info)
            if entries:
                parsed_number = self._format_phone_number(
                    entries[0]['contact_value'])
                if parsed_number:
                    phones[contact_entry] = parsed_number
        return phones

    @memoize
    def _get_org_structure(self, from_ou_id):
        """
        Makes an organization structure (company/department/sub-department)
        by traversing upwards in the OU hierarchy from a given OU.

        :param int from_ou_id:
            The entity ID of the OU to start traversing from.
        :return:
            The organizational units to include in the person data.
        :rtype: dict
        """
        self.ou.clear()
        self.ou.find(from_ou_id)

        ou_roots = set([x['ou_id'] for x in self.ou.root()])
        ous = []
        structure = {}
        current_ou_id = self.ou.entity_id
        current_ou_name = None

        while current_ou_id not in ou_roots:
            self.ou.clear()
            self.ou.find(current_ou_id)
            current_ou_name = self.ou.get_name_with_language(
                name_variant=self.co.ou_name_acronym,
                name_language=self.co.language_nb)
            ous.append(current_ou_name)
            current_ou_id = self.ou.get_parent(self.ou_perspective)
            if not current_ou_id:
                break

        ous.reverse()
        for i, ou_entry in enumerate(ous):
            if i == len(self.config.company_hierarchy):
                # No more room in schema
                break
            structure[self.config.company_hierarchy[i]] = ou_entry
        return structure
