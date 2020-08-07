# -*- coding: utf-8 -*-
# Copyright 2020 University of Oslo, Norway
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
This module contains classes for holding information about a person from
an HR system.
"""

class HRPerson:

    def __init__(self, hr_id, first_name, last_name, date_of_birth,
                 gender, reserved, source_system):
        """
        :param hr_id: The persos's ID in the source system
        :param first_name: First name of the person
        :param last_name: Last name of the person
        :param date_of_birth: Date the person was born
        :param gender: Gender of the person (M/F/None)
        :param reserved: If the person is reserved from public display
        :param source_system: Authorative system code constant
        """
        self.hr_id = hr_id
        self.first_name = first_name
        self.last_name = last_name
        self.date_of_birth = date_of_birth
        self.gender = gender
        self.reserved = reserved
        self.source_system = source_system

        self.leader_groups = []  # list of int (group ids)
        self.external_ids = []   # list of HRExternalID
        self.contact_infos = []  # list of HRContactInfo
        self.adddresses = []     # list of HRAddress
        self.roles = []          # list of HRRole
        self.titles = []         # list of HRTitle
        self.affiliations = []   # list of HRAffiliation


class HRContactInfo:

    def __init__(self, contact_type, contact_pref,
                 contact_value):
        """
        :param contact_type: Contact type constant code.
        :param contact_pref: Contact preference
        :param contact_value: The actual contact info. e.g. a phonenumber
        """
        self.contact_type = contact_type
        self.contact_pref = contact_pref
        self.contact_value = contact_value


class HRAddress:

    def __init__(self, address_type, city, postal_code, address_text):
        """
        :param address_type: Address type constant code.
        :param city: City name.
        :param postal_code: Postal code of address.
        :param address_text: The rest of the address. Typically street
                             name and house number.
        """
        self.address_type = address_type
        self.city = city
        self.postal_code = postal_code
        self.address_text = address_text


class HRExternalID:

    def __init__(self, id_type, external_id):
        """
        :param id_type: External_id type constant code.
        :param external_id: The ID. e.g. passport number or birth number
        """
        self.id_type = id_type
        self.external_id = external_id


class HRTitle:

    def __init__(self, name_variant, name_language, name):
        """
        :param name_variant: Entity name code constant value
        :param name_language: Language code constant value
        :param name: The name of the title
        """
        self.name_variant = name_variant
        self.name_language = name_language
        self.name = name


class HRAffiliation:

    def __init__(self, ou_id, affiliation, status, precedence):
        """
        :param ou_id: ID of the ou where the affiliation belongs
        :param affiliation: Person affiliation code constant
        :param status: Status code constant
        :param precedence: Precedence for the affiliation
        """
        self.ou_id = ou_id
        self.affiliation = affiliation
        self.status = status
        self.precedence = precedence


class HRRole(HRAffiliation):

    def __init__(self, ou_id, affiliation, status):
        """
        :param ou_id: ID of the ou where the role belongs
        :param affiliation: Person affiliation code constant
        :param status: Status code constant
        """
        super(HRRole, self).__init__(ou_id, affiliation, status, None)
