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

import six
from flask_restx import abort

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.Entity import EntityContactInfo
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.no.uio.voip.voipService import VoipService
from Cerebrum.modules.no.uio.voip.voipAddress import VoipAddress
from Cerebrum.modules.no.uio.voip.voipClient import VoipClient
from Cerebrum.modules.no.uio.voip.bofhd_voip_cmds import find_available_voip_extension



def get_voip_service(db, designation):
    """
    Locate a specific voip_service by ID or description.

    :param db: Database connection
    :param designation: Service entity ID or description
    :return: VoipService instance
    :raises: 404 if not found
    """
    service = VoipService(db)

    # Try entity_id first
    if isinstance(designation, six.integer_types) or (
        isinstance(designation, six.string_types) and designation.isdigit()
    ):
        try:
            service.find(int(designation))
            return service
        except Errors.NotFoundError:
            abort(404, message="No voip_service with id={}".format(designation))

    # Try exact description match
    ids = service.search_voip_service_by_description(designation, exact_match=True)
    if len(ids) == 1:
        service.find(ids[0]["entity_id"])
        return service

    abort(404, message="Could not find voip_service: {}".format(designation))


def get_ou(db, designation):
    """
    Locate an organizational unit by ID or stedkode.

    :param db: Database connection
    :param designation: OU entity ID or stedkode
    :return: OU instance
    :raises: 404 if not found
    """
    ou = Factory.get("OU")(db)

    if six.text_type(designation).isdigit():
        # Try both ou_id and stedkode
        for key in ("ou_id", "stedkode"):
            try:
                if key == "ou_id":
                    ou.find(int(designation))
                else:
                    ou.find_stedkode(int(designation))
                return ou
            except (Errors.NotFoundError, ValueError):
                pass

    abort(404, message="Could not find OU: {}".format(designation))


def get_constant(db, designation, const_type):
    """
    Fetch a constant by designation.

    :param db: Database connection
    :param designation: Constant name or code
    :param const_type: Constant type class
    :return: Constant instance
    :raises: 400 if not found
    """
    const = Factory.get('Constants')(db)
    cnst = const.fetch_constants(const_type, designation)
    if len(cnst) == 0:
        abort(400, message="Unknown {} constant: {}".format(
            six.text_type(const_type), designation))
    return cnst[0]


def assert_unused_service_description(db, description):
    """
    Check that a description is not in use by any voip_service.

    :param db: Database connection
    :param description: Description to check
    :raises: 400 if description is in use
    """
    vs = VoipService(db)
    services = vs.search_voip_service_by_description(description, exact_match=True)
    if services:
        abort(400, message="Description must be unique. In use by id={}".format(
            services[0]['entity_id']))


def typeset_ou(db, ou_id):
    """
    Return a human-friendly description of an OU.

    :param db: Database connection
    :param ou_id: OU entity ID
    :return: String like '33-15-20 (USIT)'
    """
    const = Factory.get('Constants')(db)
    ou = get_ou(db, int(ou_id))

    acronym = ou.get_name_with_language(
        const.ou_name_acronym, const.language_nb, None)
    short_name = ou.get_name_with_language(
        const.ou_name_short, const.language_nb, None)
    ou_name = acronym or short_name

    location = "%02d-%02d-%02d (%s)" % (
        ou.fakultet, ou.institutt, ou.avdeling, ou_name)
    return location


def typeset_traits(db, trait_sequence):
    """
    Return a human-friendly version of entity traits.

    :param db: Database connection
    :param trait_sequence: Sequence of trait codes
    :return: List of trait names
    """
    const = Factory.get('Constants')(db)
    traits = []
    for et in trait_sequence:
        traits.append(six.text_type(const.EntityTrait(et)))
    return traits


def get_voip_address_by_owner_entity_id(db, designation):
    """
    Return voip_address by owner entity_id.

    :param db: Database connection
    :param designation: Owner entity ID
    :return: List of VoipAddress instances
    """
    if not (isinstance(designation, six.integer_types) or (
        isinstance(designation, six.string_types) and designation.isdigit()
    )):
        return []

    value = int(designation)
    try:
        va = VoipAddress(db)
        va.find_by_owner_id(value)
        return [va]
    except Errors.NotFoundError:
        return []


def get_voip_address_by_entity_id(db, designation):
    """
    Return voip_address by entity_id.

    :param db: Database connection
    :param designation: Address entity ID
    :return: List of VoipAddress instances
    """
    if not (isinstance(designation, six.integer_types) or (
        isinstance(designation, six.string_types) and designation.isdigit()
    )):
        return []

    value = int(designation)
    try:
        va = VoipAddress(db)
        va.find(value)
        return [va]
    except Errors.NotFoundError:
        return []


def get_voip_address_by_contact_info(db, designation):
    """
    Return voip_addresses by contact info value.

    :param db: Database connection
    :param designation: Contact value
    :return: List of VoipAddress instances
    """
    const = Factory.get('Constants')(db)
    try:
        eci = EntityContactInfo(db)
        ids = set()
        for row in eci.list_contact_info(
            source_system=const.system_voip,
            contact_value=designation
        ):
            ids.add(row["entity_id"])
        for row in eci.list_contact_info(
            source_system=const.system_voip,
            contact_alias=designation
        ):
            ids.add(row["entity_id"])

        result = []
        for entity_id in ids:
            result.extend(get_voip_address_by_owner_entity_id(db, entity_id))
        return result
    except Errors.NotFoundError:
        return []


def get_voip_address(db, designation, all_matches=False):
    """
    Collect voipAddress instance(s) matching designation.

    Searches in order:
    1. By entity_id
    2. By owner_entity_id
    3. By contact_info

    :param db: Database connection
    :param designation: Search parameter
    :param all_matches: If True, return all matches; if False, return first unique match
    :return: VoipAddress instance (if all_matches=False) or list of instances
    :raises: 404 if no matches found
    """
    search_funcs = [
        get_voip_address_by_entity_id,
        get_voip_address_by_owner_entity_id,
        get_voip_address_by_contact_info,
    ]

    result = []
    collected_ids = set()

    for func in search_funcs:
        addrs = func(db, designation)
        result.extend(x for x in addrs if x.entity_id not in collected_ids)
        collected_ids.update(x.entity_id for x in addrs)

        if not all_matches and len(addrs) == 1:
            return addrs[0]

    if len(result) == 0:
        abort(404, message="No voip_address matches: {}".format(designation))

    if not all_matches and len(result) > 1:
        abort(400, message="Cannot uniquely determine voip_address from: {}. "
              "Matching ids: {}".format(
                  designation, ", ".join(str(int(x.entity_id)) for x in result)))

    return result


def get_contact_info(db, value):
    """
    Return entity_contact_info entries for the specified contact value.

    :param db: Database connection
    :param value: Contact value to search for
    :return: List of contact info dicts
    """
    const = Factory.get('Constants')(db)
    result = []
    eci = EntityContactInfo(db)

    for row in eci.list_contact_info(
        source_system=const.system_voip,
        contact_value=value
    ):
        result.append(dict(row))

    for row in eci.list_contact_info(
        source_system=const.system_voip,
        contact_alias=value
    ):
        result.append(dict(row))

    return result


def get_voip_owner(db, designation):
    """
    Locate the owner of a voip address (Person or VoipService).

    :param db: Database connection
    :param designation: Owner identifier
    :return: Person or VoipService instance
    :raises: 404 if not found
    """
    # Try person first
    person = Factory.get("Person")(db)
    if isinstance(designation, six.integer_types) or (
        isinstance(designation, six.string_types) and designation.isdigit()
    ):
        try:
            person.find(int(designation))
            return person
        except Errors.NotFoundError:
            pass

    # Try service
    try:
        return get_voip_service(db, designation)
    except:
        pass

    abort(404, message="Cannot locate person/voip-service: {}".format(designation))


def find_available_extension(db):
    """
    Find an available 5-digit extension and construct a valid full number.

    Wrapper around the XMLRPC/bofhd implementation.

    :param db: Database connection
    :return: Tuple (contact_full, contact_alias) where contact_full is
             the complete phone number (+47XXXXXXXX) and contact_alias is the
             5-digit extension
    :raises: 400 if no available extension can be found
    """
    const = Factory.get('Constants')(db)

    try:
        return find_available_voip_extension(db, const)
    except CerebrumError as e:
        abort(400, message=str(e))
