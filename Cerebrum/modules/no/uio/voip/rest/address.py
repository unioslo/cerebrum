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
VOIP Addresses API.

Endpoints for managing voip addresses.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from flask_restx import Resource, abort

from Cerebrum import Errors
from Cerebrum.modules.no.uio.voip.voipAddress import VoipAddress
from Cerebrum.rest.api import db, auth
from Cerebrum.rest.api import utils as api_utils
from . import utils
from . import models

api = models.api
logger = logging.getLogger(__name__)


ARG_ADDRESS_ID = "VoIP address id"
ARG_NUMBER = "VoIP phone number"


def search_voip_addrs(owner_id=None, owner_type=None, contact_value=None):
    if contact_value is not None:
        owner_ids = utils.find_owner_ids_from_contact(contact_value)
    else:
        owner_ids = None

    if owner_id is not None:
        if owner_ids is None:
            owner_ids = set((owner_id,))
        else:
            owner_ids = owner_ids & set((owner_id,))

    va = VoipAddress(db.connection)
    results = []
    for row in va.search(owner_entity_id=owner_ids,
                         owner_entity_type=owner_type):
        # search is ordered by entity-id
        results.append({
            'address_id': row['entity_id'],
            'owner_id': row['owner_entity_id'],
            'owner_type': row['owner_entity_type'],
        })
    return results


def _build_address_response(address):
    """ Build a VoipAddress model from a VoipAddress entity. """
    owner = address.get_owner()
    client_ids = utils.get_client_ids_from_address(address)
    attrs = address.get_voip_attributes()
    owner_name = api_utils.get_entity_name(owner)
    return {
        'address_id': address.entity_id,
        'owner': utils.build_owner_data(
            owner_id=owner.entity_id,
            owner_type=owner.entity_type,
            owner_name=owner_name,
        ),
        'cn': attrs["cn"],
        'sip_uri': attrs["voipSipUri"],
        'sip_primary_uri': attrs["voipSipPrimaryUri"],
        'e164_uri': attrs["voipE164Uri"],
        'extension_uri': attrs["voipExtensionUri"],
        'clients': client_ids,
    }


@api.route("/addresses/", endpoint="voip-address-list")
class VoipAddressListResource(Resource):
    """Resource for voip address search."""

    address_search_parser = api.parser()
    address_search_parser.add_argument(
        'owner_id',
        type=int,
        required=False,
        help='Filter addresses by owner id',
    )
    address_search_parser.add_argument(
        'owner_type',
        type=str,
        required=False,
        help='Filter addresses by owner type',
    )
    # TODO: separate number and extension?
    address_search_parser.add_argument(
        'contact_value',
        type=str,
        required=False,
        help='Filter addresses by contact value',
    )

    @auth.require()
    @api.response(200, 'Address found')
    @api.response(400, 'Missing required search parameter')
    @api.marshal_with(models.VoipAddressList)
    @api.doc(expect=[address_search_parser])
    def get(self):
        """
        Search for voip addresses.

        Search by entity_id, owner_entity_id, or contact info.
        """
        args = self.address_search_parser.parse_args()

        if args['owner_type'] is None:
            owner_type = None
        else:
            owner_type = utils.get_entity_type(args['owner_type'])

        voip_addresses = search_voip_addrs(owner_id=args['owner_id'],
                                           owner_type=owner_type,
                                           contact_value=args['contact_value'])

        answer = []
        for row in voip_addresses:
            answer.append({
                "address_id": row['address_id'],
                "owner": utils.build_owner_data(
                    owner_id=row['owner_id'],
                    owner_type=row['owner_type'],
                ),
            })

        return {'addresses': answer}

    address_new_parser = api.parser()
    address_new_parser.add_argument(
        'owner_id',
        type=int,
        required=True,
        help='Address owner',
    )

    @auth.require()
    @api.expect(address_new_parser)
    @api.response(200, 'Address created')
    @api.response(400, 'Invalid address data')
    @api.marshal_with(models.VoipAddress)
    @db.autocommit
    def post(self):
        """ Create a new VoipAddress for a given owner. """
        args = self.address_new_parser.parse_args()

        # Find owner
        owner_id = args['owner_id']
        owner = utils.get_voip_owner(owner_id)

        # Check if address already exists
        address = VoipAddress(db.connection)
        try:
            address.find_by_owner_id(owner.entity_id)
            abort(
                400,
                message=(
                    "Address exists for owner id={}"
                ).format(repr(owner_id)),
            )
        except Errors.NotFoundError:
            # Create new address
            address.clear()
            address.populate(owner.entity_id)
            address.write_db()

        return _build_address_response(address)


@api.route("/addresses/<int:address_id>", endpoint="voip-address")
@api.doc(params={'address_id': ARG_ADDRESS_ID})
class VoipAddressResource(Resource):
    """Resource for a single voip address."""

    @auth.require()
    @api.response(200, 'Address found')
    @api.marshal_with(models.VoipAddress)
    def get(self, address_id):
        """Get voip address information."""
        address = utils.get_voip_address_by_id(address_id)
        return _build_address_response(address)

    @auth.require()
    @api.response(204, 'Address deleted')
    @api.response(400, 'Address with VOIP clients not deleted')
    @db.autocommit
    def delete(self, address_id):
        """Delete a voip address."""
        address = utils.get_voip_address_by_id(address_id)

        # Check if there are clients associated
        clients = utils.get_client_ids_from_address(address)
        if clients:
            abort(
                400,
                message=(
                    "Cannot delete address id={}: "
                    "it has {} voip_client(s)"
                ).format(address.entity_id, len(clients)),
            )

        address_id = address.entity_id
        address.get_owner()
        address.delete()
        return None, 204


@api.route("/addresses/<int:address_id>/numbers",
           endpoint="voip-address-number-list")
@api.doc(params={'address_id': ARG_ADDRESS_ID})
class VoipNumberCollectionResource(Resource):
    """Resource for managing phone numbers on a voip address."""

    @auth.require()
    @api.response(201, 'Number added')
    @api.response(400, 'Number not added')
    @api.marshal_with(models.VoipNumber)
    @db.autocommit
    def post(self, address_id):
        """Generate and add a phone number to a voip address. """

        address = utils.get_voip_address_by_id(address_id)
        owner = address.get_owner()

        # Auto-assign extension if not given
        contact_value, contact_alias = utils.find_available_extension()
        utils.validate_number_pair(contact_value, contact_alias)
        utils.validate_number_is_free(contact_value, is_extension=False)
        utils.validate_number_is_free(contact_alias, is_extension=True)

        logger.info(
            "Auto-assigned extension %s (number: %s) for owner id=%s",
            contact_alias, contact_value, owner.entity_id)

        priority = utils.get_next_priority(owner)

        # Add the contact info
        owner.add_contact_info(
            db.const.system_voip,
            db.const.contact_voip_extension,
            contact_value,
            pref=priority,
            alias=contact_alias
        )
        return {
            'number': contact_value,
            'extension': contact_alias,
            'priority': priority,
        }, 201

    @auth.require()
    @api.response(200, 'Address found')
    @api.response(400, 'Missing required search parameter')
    @api.marshal_with(models.VoipNumberList)
    def get(self, address_id):
        """Get voip numbers for a given address."""
        address = utils.get_voip_address_by_id(address_id)
        owner = address.get_owner()
        results = []
        for row in owner.list_contact_info(
                source_system=db.const.system_voip,
                contact_type=db.const.contact_voip_extension,
                entity_id=owner.entity_id):
            results.append({
                'number': row['contact_value'],
                'extension': row['contact_alias'],
                'priority': row['contact_pref'],
            })
        results.sort(key=lambda d: (d['priority'], d['number']))
        return {'numbers': results}


@api.route("/addresses/<int:address_id>/numbers/<string:number>",
           endpoint="voip-address-number")
@api.doc(params={'address_id': ARG_ADDRESS_ID, 'number': ARG_NUMBER})
class VoipNumberResource(Resource):
    """Resource for adding or deleting a specific phone number."""

    @auth.require()
    @api.response(200, 'Number found')
    @api.response(404, 'Address or number not found')
    @api.marshal_with(models.VoipNumber)
    def get(self, address_id, number):
        """ Add number or update extension for the given address. """
        address = utils.get_voip_address_by_id(address_id)
        owner = address.get_owner()

        row = utils.get_number_entry(owner, number)
        if not row:
            abort(
                404,
                message="Number not found",
            )

        return {
            'number': row['contact_value'],
            'extension': row['contact_alias'],
            'priority': row['contact_pref'],
        }

    number_parser = api.parser()
    number_parser.add_argument(
        'extension',
        type=str,
        required=False,
        help="Extension number to add (will auto-generate if empty)",
    )
    number_parser.add_argument(
        'priority',
        type=int,
        required=False,
        help='Optional priority value - should normally be omitted',
    )

    @auth.require()
    @api.expect(number_parser)
    @api.response(200, 'Number updated')
    @api.response(201, 'Number added')
    @api.response(400, 'Invalid request')
    @api.response(404, 'Address not found')
    @api.marshal_with(models.VoipNumber)
    @db.autocommit
    def put(self, address_id, number):
        """ Add number or update extension for the given address. """
        address = utils.get_voip_address_by_id(address_id)
        owner = address.get_owner()

        args = self.number_parser.parse_args()
        contact_value = number
        contact_alias = args['extension']
        priority = args['priority']
        if priority is not None:
            priority = int(priority)
            if priority <= 0:
                abort(400, message="Priority must be larger than 0")

        row = utils.get_number_entry(owner, contact_value)
        if row:
            # update
            old_pri = row['contact_pref']
            old_alias = row['contact_alias']
            if ((not priority or old_pri == priority)
                    and (not contact_alias or old_alias == contact_alias)):
                # no change
                return {
                    'number': contact_value,
                    'extension': old_alias,
                    'priority': old_pri,
                }, 200
            # update extension and/or priority
            if contact_alias:
                utils.validate_number_is_free(contact_alias, is_extension=True)
                utils.validate_number_pair(contact_value, contact_alias)
            else:
                contact_alias = old_alias
            if not priority:
                priority = old_pri

            owner.delete_contact_info(
                db.const.system_voip,
                db.const.contact_voip_extension,
                old_pri,
            )
            http_code = 200
        else:
            # new number
            utils.validate_number_pair(contact_value, contact_alias)
            utils.validate_number_is_free(contact_value, is_extension=False)
            utils.validate_number_is_free(contact_alias, is_extension=True)
            if not priority:
                priority = utils.get_next_priority(owner)
            http_code = 201

        # Add the contact info
        owner.add_contact_info(
            db.const.system_voip,
            db.const.contact_voip_extension,
            contact_value,
            pref=priority,
            alias=contact_alias
        )
        return {
            'number': contact_value,
            'extension': contact_alias,
            'priority': priority,
        }, http_code

    @auth.require()
    @api.response(204, 'Number deleted')
    @api.response(404, 'Number not found')
    @db.autocommit
    def delete(self, address_id, number):
        """Delete a phone number from a voip address."""
        address = utils.get_voip_address_by_id(address_id)
        owner = address.get_owner()
        row = utils.get_number_entry(owner, number)
        if not row:
            abort(
                404,
                message="Number not found",
            )
        owner.delete_contact_info(
            row["source_system"],
            row["contact_type"],
            row["contact_pref"],
        )
        return None, 204
