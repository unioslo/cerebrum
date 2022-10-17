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
Parsing, normalization and data extraction utils for legacy ou import objects.

In the old ou import, we used system2parser/xml2object + object2cerebrum in
order to parse and update Cerberum.  This is quite similar to our new approach
for imports:

- A system-specific datasource for parsing and normalizing input data
- A mapper to extract and select relevant data for Cerebrum.
- An importer/syncer that stores the output "object" from the mapper.

With this legacy mapper, we can hook the existing OU import into our
py:mod:`.ou_sync` module.
"""
import datetime
import logging

from Cerebrum.modules.xmlutils import xml2object
from Cerebrum.utils.date_compat import get_date
from .ou_model import OrgUnitMapper

logger = logging.getLogger(__name__)


def format_id(value, required=True):
    if required and not value:
        raise ValueError('missing id')
    elif not value:
        return None
    return 'sko:{}'.format(value)


class LegacyObjectMapper(OrgUnitMapper):
    """
    A legacy mapper for py:class:`Cerebrum.modules.xmlutils.xml2object.DataOU`
    objects.

    This mapper extracts data more-or-less in the same way as the old
    py:mod:`Cerebrum.modules.xmlutils.object2cerebrum` did.

    All functions take a ``DataOU`` object as ``ou_data``.
    """

    def get_id(self, ou_data):
        """ id to use when building org tree. """
        return format_id(self.get_location_code(ou_data), required=True)

    def get_parent_id(self, ou_data):
        """ parent id to use when building org tree. """
        return format_id(ou_data.parent, required=False)

    def get_location_code(self, ou_data):
        """ Get stedkode (if present) from ou_data.

        :param dict ou_data: an ou data structure

        :returns str: Returns a location code, or None if no stedkode exists.
        """
        ids = dict(ou_data.iterids())
        return ids.get(xml2object.DataOU.NO_SKO)

    def get_external_ids(self, ou_data):
        """ Get external_id identifiers from ou_data.

        :param dict ou_data: an ou data structure

        :rtype: generator
        :returns:
            zero or more tuples with (id_type, external_id)
        """
        for key, value in ou_data.iterids():
            if key == xml2object.DataOU.NO_DFO:
                yield ('DFO_OU_ID', value)
            elif key == xml2object.DataOU.NO_ORGREG:
                yield ('ORGREG_OU_ID', value)
            else:
                logger.debug('unknown id type: %s', repr(key))

    def get_names(self, ou_data):
        """ Get localized names from ou_data.

        :param dict ou_data: an ou data structure

        :rtype: generator
        :returns:
            zero or more tuples with (name_variant, name_lang, name)

        .. note::
           It is an error to return a name type that is not listed by
           `.name_types`.
        """
        for kind, names in ou_data.iternames():
            if kind == xml2object.DataOU.NAME_ACRONYM:
                name_types = ('OU acronym',)
            elif kind == xml2object.DataOU.NAME_SHORT:
                name_types = ('OU short',)
            elif kind == xml2object.DataOU.NAME_LONG:
                name_types = ('OU name', 'OU display')
            else:
                logger.debug('unknown name type: %s', repr(kind))

            for name in names:
                for name_type in name_types:
                    yield (name_type, name.language, name.value)

    def get_contact_info(self, ou_data):
        """ Get contact info from ou_data.

        :param dict ou_data: an ou data structure

        :rtype: generator
        :returns:
            zero or more tuples with (contact_type strval, contact_value)
        """
        for contact in ou_data.itercontacts():
            if not contact.value:
                logger.debug('empty value for: %s', repr(contact.kind))
                continue

            if contact.kind == xml2object.DataContact.CONTACT_PHONE:
                yield ('PHONE', contact.value)
            elif contact.kind == xml2object.DataContact.CONTACT_FAX:
                yield ('FAX', contact.value)
            elif contact.kind == xml2object.DataContact.CONTACT_URL:
                yield ('URL', contact.value)
            elif contact.kind == xml2object.DataContact.CONTACT_EMAIL:
                yield ('EMAIL', contact.value)
            else:
                logger.debug('unknown contact: %s', repr(contact.kind))

    def get_addresses(self, ou_data):
        """ Get address info from ou_data.

        :param dict ou_data: an ou data structure

        :rtype: generator
        :returns:
            zero or more tuples with (address_type strval, address_column dict)

            Accepted address columns are:
             - address_text
             - p_o_box
             - postal_number
             - city
             - country
        """
        for addr_kind, addr in ou_data.iteraddress():
            if addr_kind == xml2object.DataAddress.ADDRESS_BESOK:
                addr_type = 'STREET'
            elif addr_kind == xml2object.DataAddress.ADDRESS_POST:
                addr_type = 'POST'
            else:
                logger.debug('unknown address type: %s', repr(addr_kind))
                continue

            addr_d = {
                'address_text': addr.street,
                'postal_number': addr.zip,
                'city': addr.city,
                'country': None,
            }
            yield (addr_type, addr_d)

    def is_valid(self, ou_data, _today=None):
        """ If this org unit is an valid/active org unit. """
        today = _today or datetime.date.today()
        valid_from = get_date(ou_data.start_date)
        valid_to = get_date(ou_data.end_date)
        return ((valid_from is None or today >= valid_from)
                and (valid_to is None or today <= valid_to))

    def is_visible(self, ou_data):
        """ If this org unit should be included in public views. """
        if not self.is_valid(ou_data):
            # Expired org units are *soft deleted* and are never published.
            return False
        return getattr(ou_data, "publishable", False)

    def get_usage(self, ou_data):
        """ Usage codes for this org unit.

        Known usage codes are defined in ``cereconf.OU_USAGE_SPREAD``, and are
        used to map various tags and properties from the source system to
        automatic spreads.
        """
        if not self.is_valid(ou_data):
            return ()
        return tuple(ou_data.iter_usage_codes())
