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

import datetime


class ReprMixin(object):

    repr_fields = ()

    def __iter_repr_fields(self):
        for attr in self.repr_fields:
            value = getattr(self, attr, None)
            if value:
                yield attr, value

    def __repr__(self):
        # Note: no infinite recursion protection
        fields = ', '.join(
            '{k}={v}'.format(k=k, v=repr(v))
            for k, v in self.__iter_repr_fields())
        return '<{cls.__name__}{fields}>'.format(
            cls=type(self),
            fields=(' ' + fields) if fields else '',
        )


class HRPerson(ReprMixin):
    """
    Main class for holding all information that Cerebrum should need
    about a person from an HR system
    """

    repr_fields = ('hr_id',)

    def __init__(self,
                 hr_id,
                 first_name,
                 last_name,
                 birth_date,
                 gender):
        """
        :param str hr_id: The person's ID in the source system
        :param str first_name: First name of the person
        :param str last_name: Last name of the person
        :param date birth_date: Date the person was born
        :param str gender: Gender of the person ('M'/'F'/None)
        """
        self.hr_id = hr_id
        self.first_name = first_name
        self.last_name = last_name
        self.birth_date = birth_date
        self.gender = gender

        self.external_ids = set()  # set of HRExternalID
        self.contact_infos = set()  # set of HRContactInfo
        self.titles = set()         # set of HRTitle
        self.affiliations = set()   # set of HRAffiliation

    def has_active_affiliations(self, start_grace, end_grace):
        """
        Check if any of the persons affiliations is active.

        :param datetime.timedelta start_grace: Grace period for start date
        :param datetime.timedelta end_grace: Grace period for end date
        :return boolean: True if active any affiliations are active.
        """
        return any([x.is_active(start_grace, end_grace)
                    for x in self.affiliations])


class ComparableObject(object):
    """General class that implements __eq__ and __ne__

    One should never mutate instances of this class or subclasses once created!
    """

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        """Retrieves ``self._hash`` if it exists, otherwise create it"""
        if hasattr(self, '_hash'):
            return self._hash
        self._hash = self.get_hash()
        return self._hash

    def get_hash(self):
        """Create a hash for the object"""
        def helper():
            yield self.__class__.__name__
            for k, v in sorted(self.__dict__.items()):
                yield hash(tuple((k, hash(v))))

        return hash(tuple(helper()))


class HRContactInfo(ComparableObject, ReprMixin):
    """Class with contact info matching entity_contact_info"""

    repr_fields = ('contact_type',)

    def __init__(self, contact_type, contact_pref, contact_value):
        """
        :param str contact_type: Contact type code
        :param int contact_pref: Contact preference (default 50)
        :param str contact_value: The actual contact info. e.g. a phonenumber
        """
        self.contact_type = contact_type
        self.contact_pref = contact_pref
        self.contact_value = contact_value


class HRExternalID(ComparableObject, ReprMixin):
    """Class with info about an external_id, matching entity_external_id"""

    repr_fields = ('id_type',)

    def __init__(self, id_type, external_id):
        """
        :param str id_type: External_id type.
        :param str external_id: The ID. e.g. passport number or birth number
        """
        self.external_id = external_id
        self.id_type = id_type


class HRTitle(ComparableObject, ReprMixin):
    """Class with info about a title, matching entity_language_name"""

    repr_fields = ('name_variant', 'name_language')

    def __init__(self, name_variant, name_language, name):
        """
        :param str name_variant: Entity name code
        :param str name_language: Language code
        :param str name: The name of the title
        """
        self.name_variant = name_variant
        self.name_language = name_language
        self.name = name


class HRAffiliation(ComparableObject, ReprMixin):
    """
    Class with info about an affiliation, matching person_affiliation_source
    (and person_affiliation)
    """

    repr_fields = ('affiliation', 'ou_id')

    def __init__(self, ou_id, affiliation, status, precedence,
                 start_date=None, end_date=None):
        """
        :param str ou_id: id for the ou, either an external id or stedkode
        :param str affiliation: Affiliation code
        :param str status: Status code
        :param int or None precedence: Precedence for the affiliation
        :param date or None start_date: Date from which the affiliation is
                                        active
        :param date or None end_date: End date of the affiliation
        """
        self.ou_id = ou_id
        self.affiliation = affiliation
        self.status = status
        self.precedence = precedence
        self.start_date = start_date
        self.end_date = end_date

    def __hash__(self):
        return hash(
            (self.ou_id, self.affiliation)
        )

    def is_active(self, start_grace, end_grace):
        """
        Check if the affiliation is currently active.

        self.start_date - start_grace <= today <= self.end_date + end_grace
        :param datetime.timedelta start_grace: Grace period for start date
        :param datetime.timedelta end_grace: Grace period for end date
        :return boolean: True if active
        """

        today = datetime.date.today()
        if self.start_date and self.end_date:
            if (self.start_date - start_grace <= today
                    <= self.end_date + end_grace):
                return True
        elif self.start_date:
            if self.start_date - start_grace <= today:
                return True
        return False
