# -*- coding: utf-8 -*-
#
# Copyright 2022 University of Oslo, Norway
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
Parsing and normalization utils for org unit data from Orgreg.

Really only provides *one* useful function: py:func:`.parse_org_unit`.  This
function should be used to turn org unit info (/ou/{id} json response from the
Orgreg API) into a dict with only the relevant bits.  It will:

1. Validate certain data fields, e.g. require `ouId` to be non-empty, require
    any date fields to be valid ISO-8601 dates (if given)

2. Normalize wanted data, e.g. turn ISO8601 date strings into `datetime.date`
    objects, normalize text data to Unicode NFC

3. Filter out unwanted data and re-organize data structure, e.g. remove
    `order`, `startDate`, and other unused fields
"""
from __future__ import absolute_import, unicode_literals

import logging

from Cerebrum.utils import date as date_utils
from Cerebrum.utils import textnorm


logger = logging.getLogger(__name__)


def parse_orgreg_date(value, allow_empty=False):
    """ Get a date object from an Orgreg date string. """
    if not value or not value.strip():
        if allow_empty:
            return None
        else:
            raise ValueError('empty date')
    return date_utils.parse_date(value)


def normalize_text(value, allow_empty=False):
    r"""
    Normalize plaintext strings.

    >>> normalize_text("a\N{COMBINED RING ABOVE}")
    '\xc5'  # "\N{LATIN SMALL LETTER A WITH RING ABOVE}"
    """
    if not value or not value.strip():
        if allow_empty:
            return None
        else:
            raise ValueError('empty text')
    return textnorm.normalize(value.strip())


def parse_orgreg_address(d):
    """
    Parse an Orgreg (org unit) address object.

    Examples:

    >>> parse_orgreg_address({})  # None
    >>> parse_orgreg_address({'street': ''})  # None
    >>> parse_orgreg_address({'street': 'foo'})
    {'street': 'foo', 'city': None, ...}
    """
    if not d:
        return None
    addr = {
        'street': normalize_text(d.get('street'), allow_empty=True),
        'extended': normalize_text(d.get('extended'), allow_empty=True),
        'postalCode': normalize_text(d.get('postalCode'), allow_empty=True),
        'city': normalize_text(d.get('city'), allow_empty=True),
        # state/province is not really used in Cerebrum
        # 'province': normalize_text(d.get('stateOrProvinceName'),
        #                            allow_empty=True),
        'country': normalize_text(d.get('country'), allow_empty=True),
    }
    if not any(addr.values()):
        return None
    return addr


# Orgreg three-letter language code to Cerebrum two-letter language code.  We
# only need to include languages we want available to the mapper.  The language
# codes seems to match ISO-639-2 and ISO-639-1, but who knows if that holds
# true if more languages are ever added...
#
# This language code mapping and filtering should *probably* be done in a
# mapper, but this is easaier.
LANGUAGE_MAP = {
    'eng': 'en',
    'nno': 'nn',
    'nob': 'nb',
}


def parse_localized_data(d):
    """
    Parse and and extract localized texts from an orgreg object.

    Examples:

    >>> parse_localized_data(None)
    {'nb': None, 'nn': None, 'en': None}

    >>> parse_localized_data({'nob': 'hei', 'eng': 'hi',
    ...                       'foo': 'bar', 'baz': 'quux'})
    {'no': 'hei', 'en': 'hi', 'nn': None}
    """
    d = d or {}
    known = {}
    for long, short in LANGUAGE_MAP.items():
        known[short] = normalize_text(d.get(long), allow_empty=True)
    return known


def parse_external_id(d):
    """ Normalize external ids from an orgreg object. """
    return {
        'type': normalize_text(d['type']),
        'sourceSystem': normalize_text(d['sourceSystem']),
        'value': normalize_text(d['value']),
    }


def parse_org_unit(d):
    """
    Validate and normalize an org unit from Orgreg.
    """
    return {
        'ouId': int(d['ouId']),
        'hierarchy': normalize_text(d['hierarchy']),
        # NOTE: parent == 0 for root org units.  Let's make that a bit more
        # explicit by setting `None` to represent "no parent".
        'parent': int(d['parent']) or None,
        'children': tuple(int(c) for c in d['children']),

        # identifiers and other metadata
        'externalKeys': tuple(parse_external_id(i) for i in d['externalKeys']),
        'note': normalize_text(d.get('note'), allow_empty=True),
        'tags': tuple(t for t in d['tags']),
        'validFrom': parse_orgreg_date(d['validFrom']),
        'validTo': parse_orgreg_date(d.get('validTo'), allow_empty=True),

        # contact info
        'email': normalize_text(d.get('email'), allow_empty=True),
        'fax': normalize_text(d.get('fax'), allow_empty=True),
        'phone': normalize_text(d.get('phone'), allow_empty=True),

        # addresses - either non-empty dicts or None
        'postalAddress': parse_orgreg_address(d.get('postalAddress')),
        'visitAddress': parse_orgreg_address(d.get('visitAddress')),

        # localized data / names - always non-empty dicts with keys en/nb/nn
        'homepage': parse_localized_data(d.get('homepage')),
        'acronym': parse_localized_data(d.get('acronym')),
        'shortName': parse_localized_data(d.get('shortName')),
        'name': parse_localized_data(d.get('name')),
        'longName': parse_localized_data(d.get('longName')),
    }
