# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
Greg datasource for guest imports.

This module contains to convert and validate relevant objects from Grag.  Its
main parts are:

py:func:`.parse_message`
    Convert an event payload to a simple dict with only relevant items (event
    id, source, type, references)

py:func:`.parse_person`
    Convert and normalize person info (/persons/{id} json response from the
    Greg API) into a dict with only the relevant bits.
"""
from __future__ import unicode_literals

import json
import logging

import six

from Cerebrum.modules.hr_import.datasource import (
    AbstractDatasource,
    DatasourceInvalid,
    RemoteObject,
)
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import textnorm


logger = logging.getLogger(__name__)


# Generic convert/normalize utils


def normalize_id(greg_id):
    """ normalize greg reference values. """
    return six.text_type(int(greg_id))


def parse_greg_date(value, allow_empty=False):
    """ Get a date object from a Greg date string. """
    if not value and allow_empty:
        return None
    return date_utils.parse_date(value)


def parse_greg_dt(value, allow_empty=False):
    """ Get a tz-aware datetime from a Greg datetime string. """
    if not value and allow_empty:
        return None
    dt = date_utils.parse_datetime_tz(value)
    return date_utils.to_timezone(dt)


def normalize_text(value, allow_empty=False):
    if not value or not value.strip():
        if allow_empty:
            return None
        else:
            raise ValueError('empty text')
    return textnorm.normalize(value.strip())


# Event message utils


def _get_msg_id(d):
    """ parse 'id' field from message dict. """
    return normalize_id(d['id'])


def _get_msg_data(d):
    """ key/value fields. """
    for key, value in d.get('data', {}).items():
        norm_key = normalize_text(key)
        if norm_key.endswith('_id'):
            norm_value = normalize_id(value)
        else:
            norm_value = normalize_text(value)
        yield (norm_key, norm_value)


def parse_message(msg_text):
    """ Parse Greg message.

    :param str msg_text: json encoded message

    :rtype: dict
    :return:
        Returns a dict with message fields:

        - id (str): event id (e.g. "3")
        - type (str): event type (e.g. "person.update")
        - source (str): source system (e.g. "greg:uio:prod")
        - data (dict): event payload (e.g. {"person_id": "2"})
    """
    # TODO: Does all messages follow the same format?
    # Will all data in the 'data' portion of a message be on the form of
    # *datatype* -> *id*?
    try:
        msg_data = json.loads(msg_text)
        return {
            'id': normalize_id(msg_data['id']),
            'type': normalize_text(msg_data['type']),
            'source': normalize_text(msg_data['source']),
            # 'version': msg_data['specversion'],
            'data': dict(_get_msg_data(msg_data)) or {},
        }
    except Exception as e:
        # this is likely a KeyError (missing field) or ValueError (invalid
        # field value)
        logger.debug('invalid message: %s (%r)', e, msg_text)
        raise DatasourceInvalid('invalid message')


# API endpoint object utils


def _parse_person_consent(d):
    """ Parse/convert/filter/flatten consent object values. """
    td = d['type']
    return {
        'consent_type': normalize_text(td['identifier']),
        # 'valid_from': parse_greg_date(td['valid_from']),
        # 'user_allowed_to_change': bool(td['user_allowed_to_change']),
        'consent_given_at': parse_greg_date(d['consent_given_at'],
                                            allow_empty=False),
    }


def _parse_person_id(d):
    """ Parse/convert/filter identity object values. """
    return {
        'id': normalize_id(d['id']),
        'person': normalize_id(d['person']),
        # 'source': normalize_text(d['source']),
        'type': normalize_text(d['type']),
        'value': normalize_text(d['value'], allow_empty=True),
        'verified': normalize_text(d['verified'], allow_empty=True),
        # 'verified_at': parse_greg_dt(d['verified_at']),
        # 'verified_by': normalize_id(d['verified_by']),
        # 'created': parse_greg_dt(d['created']),
        # 'updated': parse_greg_dt(d['updated']),
    }


def _parse_person_role(d):
    """ Parse/convert/filter role object values. """
    return {
        'id': normalize_id(d['id']),
        'type': normalize_text(d['type']),
        # TODO: The 'orgunit' field will probably change into an object, which
        # includes both the internal greg orgunit id, as well as the orgreg id
        'orgunit_id': normalize_id(d['orgunit']),
        # 'sponsor_id': normalize_id(d['sponsor_id']),
        'start_date': parse_greg_date(d['start_date']),
        'end_date': parse_greg_date(d['end_date']),
        # 'created': parse_greg_dt(d['created']),
        # 'updated': parse_greg_dt(d['updated']),
    }


def parse_person(d):
    """ Sanitize and normalize guest (person) data. """
    return {
        'id': normalize_id(d['id']),
        'first_name': normalize_text(d['first_name'], allow_empty=True),
        'last_name': normalize_text(d['last_name'], allow_empty=True),
        'date_of_birth': parse_greg_date(d['date_of_birth']),
        'registration_completed_date': parse_greg_date(
            d['registration_completed_date'],
            allow_empty=True,
        ),
        # 'token': normalize_text(d['token'], allow_empty=True),
        'identities': tuple(_parse_person_id(i) for i in d['identities']),
        'roles': tuple(_parse_person_role(r) for r in d['roles']),
        'consents': tuple(_parse_person_consent(c) for c in d['consents']),
    }


# Main objects


class GregPerson(RemoteObject):
    """
    Container for cleaned up person data from the Greg API.

    This object works much like a read-only dict, but will additionally carry
    the reference (the person.id/greg_pid) used to fetch the data.
    """
    pass


class GregDatasource(AbstractDatasource):
    """
    Datasource implementation for Greg guests.

    TODO: Do we really need this object?  Should we maybe *not* re-use this
    part of the hr_import?
    """

    def __init__(self, client):
        self.client = client

    def get_reference(self, event):
        """ Extract reference from message body """
        # TODO: We don't really need this method, but we made it an
        # abc.abstractmethod in the superclass.  We should either revise this
        # system (or just inherit from object?).
        raise NotImplementedError()

    def get_object(self, reference):
        """ Fetch data from sap (employee data, assignments, roles). """
        greg_pid = normalize_id(reference)

        raw = self.client.get_person(greg_pid)
        if raw:
            greg_data = parse_person(raw)
        else:
            logger.warning('no result for person-id %r', greg_pid)
            greg_data = {}

        return GregPerson('greg', greg_pid, greg_data)
