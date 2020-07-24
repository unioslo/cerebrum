# -*- coding: utf-8 -*-

# Copyright 2020 University of Oslo
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
Interface for phone number parsing, validation, and formatting.

Region code strings must be provided using CLDR two-letter region
code format in upper case.  You may peruse a list of available codes
here:
http://www.iso.org/iso/country_codes/iso_3166_code_lists/country_names_and_code_elements.htm

Exposes a subset of Google's phonenumbers library:
https://github.com/daviddrysdale/python-phonenumbers/
"""

from warnings import warn

import phonenumbers
import six

import cereconf


class NumberParseException(Exception):
    """Raised when failing to parse a putative phone number."""

    INVALID_COUNTRY_CODE = 0
    NOT_A_NUMBER = 1
    TOO_SHORT_AFTER_IDD = 2
    TOO_SHORT_NSN = 3
    TOO_LONG = 4

    def __init__(self, original):
        assert isinstance(original, phonenumbers.NumberParseException)
        self.error_type = original.error_type
        super(NumberParseException, self).__init__(str(original))


E164 = phonenumbers.PhoneNumberFormat.E164
INTERNATIONAL = phonenumbers.PhoneNumberFormat.INTERNATIONAL
NATIONAL = phonenumbers.PhoneNumberFormat.NATIONAL
RFC3966 = phonenumbers.PhoneNumberFormat.RFC3966


class PhoneNumber(object):
    """Represents an international phone number."""

    def __init__(self, numobj):
        self._inner = numobj

    @property
    def country_code(self):
        return self._inner.country_code

    @property
    def national_number(self):
        return self._inner.national_number

    def __eq__(self, other):
        return self._inner.__eq__(other._inner)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return six.text_type(
            "{}("
            "country_code={},"
            "national_number={})"
        ).format(
            type(self).__name__,
            self._inner.country_code,
            self._inner.national_number,
        )


def parse(number, region=None):
    """
    Parse a phone number string.

    The number to parse can be provided with or without a country
    code ("+47 <number>" or "0047 <number>").  When an international
    phone number format is not recognised, the phone number is
    assumed to originate from the geographical location given by
    the ``region`` parameter.

    :type number: str
    :param number:
        Potential phone number to parse.  Can be with or without
        formatting, using such separation characters as "+" and "-".

    :type region: str
    :param region:
        Region is used to derive :func:`PhoneNumber.country_code`
        when ``number`` is not written in the international phone
        number format with a leading country code such as "+47 <number>".

    :rtype: PhoneNumber

    :raises NumberParseException:
        If string is not considered a viable phone number.

        If no region was supplied.

        If region is supplied, but not a valid upper case, two-letter
        CLDR region code.
    """
    try:
        numobj = phonenumbers.parse(number, region=region)
        return PhoneNumber(numobj)
    except phonenumbers.NumberParseException as e:
        raise NumberParseException(e)


def is_valid(numobj):
    """Tests whether a phone number matches a valid pattern."""
    return phonenumbers.is_valid_number(numobj._inner)


def format(numobj, format=E164):
    """Formats a phone number in the specified format."""
    return phonenumbers.format_number(numobj._inner, format)


# TODO(andretol):
# We wouldn't need this function if ../modules/no/access_FS.py:/_phone_to_country
# didn't implement an insane number validation algorithm of its own.
def country2region(country_code):
    """
    Returns the CLDR two-letter region codes that matches the country
    calling code.

    :rtype: Tuple[str]
    :return:
        Set of regions that have ``country_code`` as their calling code.
        If no regions match the result is empty.
    """
    warn("Consider parsing phone number with a specific region instead")
    return phonenumbers.region_codes_for_country_code(country_code)
