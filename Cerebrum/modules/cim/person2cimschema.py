#!/usr/bin/env python
# -*- encoding: utf-8 -*-
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

import cereconf
import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum.Errors import NotFoundError
from . import config


def get_cim_person_data(entity_id):
    """
    Builds a dict according to the CIM-WS schema, using info stored in
    Cerebrums database about the given person.

    :param entity_id: The person's entity_id in Cerebrum
    :type entity_id: int
    :return: A dict with person data, with entries adhering to the
             CIM-WS-schema.
    :rtype: dict
    """
    db = Factory.get('Database')()
    pe = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)
    authoritative_system = config.authoritative_system

    person_dict = {}
    try:
        pe.find(entity_id)
    except NotFoundError:
        raise

    # Get username
    primary_ac_id = pe.get_primary_account()
    ac.find(primary_ac_id)
    person_dict['username'] = ac.get_account_name()

    # Get and add first and last names from authoritative system
    pe_names = pe.get_all_names()
    names = _attr_filter('source_system', authoritative_system, pe_names)
    first_name_list = _attr_filter('name_variant', co.name_first, names)
    last_name_list = _attr_filter('name_variant', co.name_last, names)
    person_dict['firstname'] = first_name_list[0]['name']
    person_dict['lastname'] = last_name_list[0]['name']

    # Get and add phone entries
    pe_contact_info = pe.get_contact_info()
    _add_phone_entries(pe_contact_info, person_dict)

    # Get and add email address
    try:
        person_dict['email'] = ac.get_primary_mailaddress()
    except NotFoundError:
        pass

    # Get and add company info
    pe_affs = pe.get_affiliations()
    _add_company_info(pe_affs, person_dict)

    # Get and add job title if present
    try:
        person_dict['job_title'] = pe.get_name_with_language(co.work_title,
                                                             co.language_nb)
    except NotFoundError:
        pass

    return person_dict


def _attr_filter(attr_name, constant, input_list):
    """
    Takes a list of tuples, and returns a list of only the tuples where the
    attr with attr_name is equal to the input parameter constant.

    :param attr_name: An attribute name.
    :type attr_name: str
    :param constant: A Cerebrum constant
    :type constant: _CerebrumCode
    :param input_list: A list of tuples
    :type input_list: list
    :return: A filtered list, containing only tuples with valid matches. If
             no matches are found, the list will be empty.
    :rtype: list
    """
    return filter(lambda x: x[attr_name] == constant, input_list)


def _format_phone_number(phone_number):
    """
    Takes a phone number, and adds a default country prefix to it if missing.
    If a prefix is already present, it returns the phone number as is. It is
    assumed that phone numbers lacking a prefix, is not of a foreign
    nationality, and we will therefore always add the default prefix from the
    configuration.
    :param phone_number: A phone number
    :type phone_number: str
    :return: A phone number with a country prefix
    """
    if phone_number.startswith('+'):
        return phone_number

    # Add country-prefix if missing, as this is required by CIM
    prefixed_number = ''.join([config.country_phone_prefix, phone_number])
    return prefixed_number


def _add_phone_entries(pe_contact_info, person_dict):
    """
    Adds relevant phone attributes to the given person_dict, based on values
    found in contact_info, and the mappings found in the module configuration.

    :param pe_contact_info: A list of tuples with Cerebrum contact_info entries
    :type pe_contact_info: list
    :param person_dict: A dict with person data according to the CIM-WS-schema
    :type person_dict: dict
    """
    contact_info = _attr_filter('source_system',
                                config.authoritative_system,
                                pe_contact_info)
    for contact_entry in config.phone_entry_mappings:
        entry_list = _attr_filter('contact_type',
                                  config.phone_entry_mappings[contact_entry],
                                  contact_info)
        if entry_list:
                person_dict[contact_entry] = _format_phone_number(
                    entry_list[0]['contact_value']
                )


def _add_company_info(pe_affs, person_dict):
    """
    Adds the relevant OU entries regarding company/department/sub-department
    to the given person_dict, by traversing upwards in the OU hierarchy,
    starting with the person's primary OU affiliation stated by the system
    set as authoritative in the module configuration.
    :param pe_affs:
    :param person_dict: A dict with person data according to the CIM-WS-schema
    :type person_dict: dict
    :return:
    """
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ou = Factory.get('OU')(db)

    affs = _attr_filter('source_system', config.authoritative_system, pe_affs)

    try:
        ou.find(affs[0]['ou_id'])
    except NotFoundError:
        raise

    ou_list = []
    current_ou_id = ou.entity_id
    current_ou_name = None

    while current_ou_name != config.company_name:
        ou.clear()
        ou.find(current_ou_id)
        current_ou_name = ou.get_name_with_language(co.ou_name,
                                                    co.language_nb)
        ou_list.append(current_ou_name)
        current_ou_id = ou.get_parent(config.system_perspective)

    ou_list.reverse()
    for i, ou_entry in enumerate(ou_list):
        if i == len(config.company_hierarchy):  # No more room in schema
            return
        person_dict[config.company_hierarchy[i]] = ou_entry
