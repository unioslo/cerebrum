# -*- coding: utf-8 -*-
#
# Copyright 2016-2026 University of Oslo, Norway
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
Utility functions for VOIP API.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from flask import url_for
from flask_restx import abort

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.Entity import EntityContactInfo
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.no.uio.voip.voipClient import VoipClient
from Cerebrum.modules.no.uio.voip.voipService import VoipService
from Cerebrum.modules.no.uio.voip.voipAddress import VoipAddress
from Cerebrum.modules.no.uio.voip.voipAddress import is_valid_voip_number
from Cerebrum.modules.no.uio.voip.voipService import search_voip_service
from Cerebrum.modules.no.uio.voip.bofhd_voip_cmds import (
    find_available_voip_extension,
)
from Cerebrum.rest.api import utils as api_utils
from Cerebrum.rest.api import db


#
# Simple entity lookups
#

def get_voip_service_by_id(service_id, _error=404):
    """ Get VoipService entity by entity id. """
    service = VoipService(db.connection)
    try:
        service.find(int(service_id))
        return service
    except (Errors.NotFoundError, ValueError, TypeError):
        abort(
            _error,
            message="No voip service with id={}".format(repr(service_id)),
        )


def get_voip_address_by_id(address_id, _error=404):
    """ Get VoipService entity by entity id. """
    addr = VoipAddress(db.connection)
    try:
        addr.find(int(address_id))
        return addr
    except (Errors.NotFoundError, ValueError, TypeError):
        abort(
            _error,
            message="No voip address with id={}".format(repr(address_id)),
        )


def get_ou_by_id(ou_id, _error=404):
    ou = Factory.get("OU")(db.connection)
    try:
        ou.find(int(ou_id))
        return ou
    except (Errors.NotFoundError, ValueError, TypeError):
        abort(
            _error,
            message="No ou with id={}".format(repr(ou_id)),
        )


def get_ou_by_location(ou_id, _error=404):
    ou = Factory.get("OU")(db.connection)
    try:
        ou.find_sko(format(int(ou_id), '06d'))
        return ou
    except (Errors.NotFoundError, ValueError, TypeError):
        abort(
            _error,
            message="No ou with location={}".format(repr(ou_id)),
        )


def get_person_by_id(person_id, _error=404):
    pe = Factory.get("Person")(db.connection)
    try:
        pe.find(int(person_id))
        return pe
    except (Errors.NotFoundError, ValueError, TypeError):
        abort(
            _error,
            message="No person with id={}".format(repr(person_id)),
        )


#
# Simple constant lookups
#

def get_service_type(strval, _error=400):
    const = db.const
    try:
        return const.get_constant(const.VoipServiceTypeCode, strval)
    except LookupError:
        abort(
            _error,
            message="Unknown service type={}".format(repr(strval)),
        )


def get_entity_type(strval, _error=400):
    const = db.const
    try:
        return const.get_constant(const.EntityType, strval)
    except LookupError:
        abort(
            _error,
            message="Unknown entity type={}".format(repr(strval)),
        )


def get_contact_type(strval, _error=400):
    const = db.const
    try:
        return const.get_constant(const.ContactInfo, strval)
    except LookupError:
        abort(
            _error,
            message="Unknown contact type={}".format(repr(strval)),
        )


#
# Other helpers
#

def assert_unused_service_description(description, _error=400):
    """
    Check that a description is not in use by any voip_service.

    :param db: Database connection
    :param description: Description to check
    :raises: 400 if description is in use
    """
    services = search_voip_service(db.connection,
                                   description=description,
                                   fetchall=True, limit=1)
    if services:
        in_use_by = services[0]['entity_id']
        abort(
            _error,
            message=(
                "Description already in use by id={} (must be unique)"
            ).format(in_use_by),
        )


def find_owner_ids_from_contact(value):
    """
    Return voip_addresses by contact info value.

    :param db: Database connection
    :param designation: Contact value
    :return: List of VoipAddress instances
    """
    const = db.const
    eci = EntityContactInfo(db.connection)
    ids = set()
    for row in eci.list_contact_info(
        source_system=const.system_voip,
        contact_type=const.contact_voip_extension,
        contact_value=value,
    ):
        ids.add(row["entity_id"])
    for row in eci.list_contact_info(
        source_system=const.system_voip,
        contact_type=const.contact_voip_extension,
        contact_alias=value,
    ):
        ids.add(row["entity_id"])
    return ids


def get_contact_info(value, owner_id=None):
    """
    Return entity_contact_info entries for the specified contact value.

    :param value: Contact value to search for
    :return: List of contact info dicts
    """
    const = db.const
    result = []
    eci = EntityContactInfo(db.connection)

    for row in eci.list_contact_info(
        source_system=const.system_voip,
        contact_type=const.contact_voip_extension,
        entity_id=owner_id,
        contact_value=value
    ):
        result.append(dict(row))

    for row in eci.list_contact_info(
        source_system=const.system_voip,
        contact_type=const.contact_voip_extension,
        entity_id=owner_id,
        contact_alias=value
    ):
        result.append(dict(row))

    return result


def get_voip_owner(owner_id, _error=400):
    """
    Locate the owner of a voip address (Person or VoipService).

    :param designation: Owner identifier
    :return: Person or VoipService instance
    :raises: 404 if not found
    """
    entity = Factory.get("Entity")(db.connection)
    try:
        entity.find(int(owner_id))
    except Errors.NotFoundError:
        abort(
            _error,
            message="No entity with id={}".format(repr(owner_id)),
        )

    if entity.entity_type == db.const.entity_person:
        return get_person_by_id(entity.entity_id, _error=500)
    elif entity.entity_type == db.const.entity_voip_service:
        return get_voip_service_by_id(entity.entity_id, _error=500)
    else:
        entity_type = get_entity_type(entity.entity_type, _error=500)
        abort(
            _error,
            message="Invalid owner type={} for id={}".format(
                entity_type,
                entity.entity_id,
            ),
        )


def find_available_extension():
    """
    Find an available 5-digit extension and construct a valid full number.

    Wrapper around the XMLRPC/bofhd implementation.

    :return: Tuple (contact_full, contact_alias) where contact_full is
             the complete phone number (+47XXXXXXXX) and contact_alias is the
             5-digit extension
    :raises: 400 if no available extension can be found
    """
    try:
        return find_available_voip_extension(
            db.connection,
            db.const,
        )
    except CerebrumError as e:
        abort(400, message=str(e))


def build_owner_data(owner_type, owner_id, owner_name=None):
    if owner_type == db.const.entity_voip_service:
        owner_href = url_for('.voip-service',
                             service_id=owner_id)
    else:
        owner_href = api_utils.href_from_entity_type(
            entity_type=owner_type,
            entity_id=owner_id,
            entity_name=owner_name,
        )

    return {
        "id": owner_id,
        "type": owner_type,
        "name": owner_name,
        "href": owner_href,
    }


def get_number_entry(owner, number):
    existing = list(
        owner.list_contact_info(
            entity_id=int(owner.entity_id),
            source_system=db.const.system_voip,
            contact_type=db.const.contact_voip_extension,
            contact_value=number,
        )
    )
    if len(existing) > 1:
        abort(
            500,
            message="Multiple entries",
        )
    if len(existing) == 1:
        return dict(existing[0])
    return None


def validate_number_pair(number, extension=None, _error=400):
    if not is_valid_voip_number(number, alias=extension):
        abort(
            _error,
            message=(
                "Invalid number/extension pair ({}, {})"
            ).format(repr(number), repr(extension)),
        )


def validate_number_is_free(number, is_extension=False, _error=400):
    eci = EntityContactInfo(db.connection)
    const = db.const
    if is_extension:
        value_args = {'contact_alias': number}
        hint = "extension"
    else:
        value_args = {'contact_value': number}
        hint = "number"

    for _ in eci.list_contact_info(
                source_system=const.system_voip,
                contact_type=const.contact_voip_extension,
                **value_args):
        abort(
            _error,
            message="Invalid {} - {} is in use".format(hint, repr(number)),
        )


def get_next_priority(owner):
    so_far = owner.list_contact_info(
        entity_id=owner.entity_id,
        source_system=db.const.system_voip,
        contact_type=db.const.contact_voip_extension,
    )
    if so_far:
        priority = max(x["contact_pref"] for x in so_far) + 1
    else:
        priority = 1
    return priority


def get_client_ids_from_address(address):
    client = VoipClient(db.connection)
    return sorted([
        x["entity_id"]
        for x in client.search(voip_address_id=int(address.entity_id))
    ])
