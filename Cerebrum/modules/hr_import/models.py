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


class HRPerson(object):
    """
    Main class for holding all information that Cerebrum should need
    about a person from an HR system
    """

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

        self.leader_groups = set()  # set of int (group ids)
        self.external_ids = set()   # set of HRExternalID
        self.contact_infos = set()  # set of HRContactInfo
        self.adddresses = set()     # set of HRAddress
        self.titles = set()         # set of HRTitle
        self.affiliations = set()   # set of HRAffiliation
        self.account_types = set()  # set of HRAccountType


class ComparableObject(object):
    """General class that implements __eq__ and __ne__"""

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return False

    def __ne__(self, other):
        return not self.__eq__(other)


class HRContactInfo(object):
    """Class with contact info matching entity_contact_info"""

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

    def __hash__(self):
        return hash(
            (self.contact_type, self.contact_pref, self.contact_value)
        )


class HRAddress(ComparableObject):
    """Class with info about an address matching, entity_address"""

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

    def __hash__(self):
        return hash(
            (self.address_type, self.city, self.postal_code, self.address_text)
        )


class HRExternalID(ComparableObject):
    """Class with info about an external_id, matching entity_external_id"""

    def __init__(self, id_type, external_id):
        """
        :param id_type: External_id type constant code.
        :param external_id: The ID. e.g. passport number or birth number
        """
        self.id_type = id_type
        self.external_id = external_id

    def __hash__(self):
        return hash(
            (self.id_type, self.external_id)
        )


class HRTitle(ComparableObject):
    """Class with info about a title, matching entity_language_name"""

    def __init__(self, name_variant, name_language, name):
        """
        :param name_variant: Entity name code constant value
        :param name_language: Language code constant value
        :param name: The name of the title
        """
        self.name_variant = name_variant
        self.name_language = name_language
        self.name = name

    def __hash__(self):
        return hash(
            (self.name_variant, self.name_language, self.name)
        )


class HRAffiliation(ComparableObject):
    """
    Class with info about an affiliation, matching person_affiliation_source
    (and person_affiliation)
    """

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

    def __hash__(self):
        return hash(
            (self.ou_id, self.affiliation, self.status, self.precedence)
        )


 class HRAccountType(HRAffiliation):
    """Class with info about an account type, matching account_type"""

    def __init__(self, ou_id, affiliation):
        """
        :param ou_id: ID of the ou where the affiliation belongs
        :param affiliation: Person affiliation code constant
        """
        super(self, HRAccountType).__init__(ou_id, affiliation, None, None)
