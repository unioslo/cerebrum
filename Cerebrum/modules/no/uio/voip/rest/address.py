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

import six
import cereconf
from flask_restx import Namespace, Resource, abort

from Cerebrum import Errors
from Cerebrum.Entity import EntityContactInfo
from Cerebrum.modules.no.uio.voip.voipAddress import VoipAddress
from Cerebrum.modules.no.uio.voip.voipClient import VoipClient
from Cerebrum.rest.api import db, auth
from . import utils
from . import models as model_module

api = Namespace('addresses', description='VOIP address operations')

# Create models
models = model_module.create_models(api)


@api.route('/', endpoint='addresses-list')
class VoipAddressListResource(Resource):
    """Resource for voip address search."""

    address_search_parser = api.parser()
    address_search_parser.add_argument(
        'search',
        type=str,
        required=False,
        help='Search parameter (entity_id, owner_id, contact info)',
    )

    @auth.require()
    @api.response(200, 'Address found')
    @api.marshal_with(models['VoipAddressList'])
    @api.doc(expect=[address_search_parser])
    def get(self):
        """
        Search for voip addresses.

        Search by entity_id, owner_entity_id, or contact info.
        """
        args = self.address_search_parser.parse_args()
        designation = args.get('search', '').strip()

        if not designation:
            abort(400, message="Search parameter is required")

        voip_addresses = utils.get_voip_address(db.connection, designation, all_matches=True)

        answer = []
        for address in voip_addresses:
            voip_attrs = address.get_voip_attributes()
            answer.append({
                "entity_id": address.entity_id,
                "owner_entity_id": address.owner_entity_id,
                "owner_entity_type": six.text_type(voip_attrs["owner_type"]),
                "cn": voip_attrs["cn"],
                "sip_uri": voip_attrs.get("voipSipUri", ""),
                "sip_primary_uri": voip_attrs.get("voipSipPrimaryUri", ""),
                "e164_uri": voip_attrs.get("voipE164Uri", ""),
                "extension_uri": voip_attrs.get("voipExtensionUri", ""),
                "traits": [],
                "clients": [],
            })

        return {'addresses': answer}


@api.route('/<int:address_id>', endpoint='address')
@api.doc(params={'address_id': 'Address entity ID or owner ID'})
class VoipAddressResource(Resource):
    """Resource for a single voip address."""

    @auth.require()
    @api.response(200, 'Address found')
    @api.marshal_with(models['VoipAddress'])
    def get(self, address_id):
        """Get voip address information."""
        address = utils.get_voip_address(db.connection, address_id)
        owner = address.get_owner()

        client = VoipClient(db.connection)
        client_ids = sorted([
            six.text_type(x["entity_id"])
            for x in client.search(voip_address_id=address.entity_id)
        ])

        attrs = address.get_voip_attributes()
        return {
            'entity_id': address.entity_id,
            'owner_entity_id': owner.entity_id,
            'owner_entity_type': six.text_type(
                db.const.EntityType(owner.entity_type)),
            'cn': attrs["cn"],
            'sip_uri': attrs["voipSipUri"],
            'sip_primary_uri': attrs["voipSipPrimaryUri"],
            'e164_uri': attrs["voipE164Uri"],
            'extension_uri': attrs["voipExtensionUri"],
            'traits': utils.typeset_traits(db.connection, address.get_traits()),
            'clients': client_ids,
        }

    @auth.require()
    @api.response(204, 'Address deleted')
    @db.autocommit
    def delete(self, address_id):
        """Delete a voip address."""
        address = utils.get_voip_address(db.connection, address_id)

        # Check if there are clients associated
        client = VoipClient(db.connection)
        clients = list(client.search(voip_address_id=address.entity_id))
        if clients:
            abort(400, message="Cannot delete address id={}: "
                  "it has {} voip_client(s)".format(
                      address.entity_id, len(clients)))

        address_id = address.entity_id
        owner = address.get_owner()
        address.delete()


@api.route('/<int:address_id>/numbers', endpoint='address-numbers')
@api.doc(params={'address_id': 'Address entity ID or owner ID'})
class VoipAddressNumberResource(Resource):
    """Resource for managing phone numbers on a voip address."""

    @auth.require()
    @api.expect(models['VoipAddressNumber'])
    @api.response(201, 'Number added')
    @db.autocommit
    def post(self, address_id):
        """Add a phone number to a voip address.

        If contact_type is contact_voip_extension and contact_value is empty
        or not provided, an available extension will be automatically assigned.
        """
        import logging
        logger = logging.getLogger(__name__)

        data = api.payload

        contact_type_str = data.get('contact_type')
        contact_full = data.get('contact_value')
        priority = data.get('priority')

        # Get or create the address
        owner = utils.get_voip_owner(db.connection, address_id)

        # Check if address already exists
        address = VoipAddress(db.connection)
        try:
            address.find_by_owner_id(owner.entity_id)
        except Errors.NotFoundError:
            # Create new address
            address.populate(owner.entity_id)
            address.write_db()

        # Determine contact type
        if contact_type_str:
            contact_type = utils.get_constant(
                db.connection, contact_type_str, db.const.ContactInfo)
        else:
            contact_type = db.const.contact_voip_extension

        # Auto-assign extension if contact_full is empty and type is extension
        if (contact_type == db.const.contact_voip_extension
                and (not contact_full or contact_full == "")):
            contact_full, contact_alias = utils.find_available_extension(db.connection)
            logger.info("Auto-assigned extension %s (full: %s) for owner id=%s",
                        contact_alias, contact_full, owner.entity_id)
        else:
            if not contact_full:
                abort(400, message="contact_value is required")

            # Check that the number is not in use
            if utils.get_contact_info(db.connection, contact_full):
                abort(400, message="Number {} already in use".format(contact_full))

            # Deduce 5-digit alias if appropriate
            contact_alias = None
            if contact_type == db.const.contact_voip_extension:
                contact_alias = contact_full[-5:]

        # Validate the numbers
        if not address.contact_is_valid(contact_type, contact_full, contact_alias):
            abort(400, message="({}, {}) is not a valid number pair".format(
                contact_full, contact_alias))

        # Check if already registered to this owner
        def owner_has_contact(owner, contact_value):
            entity_ids = [
                x["entity_id"] for x in utils.get_contact_info(
                    db.connection, contact_value)]
            return owner.entity_id in entity_ids

        if (owner_has_contact(owner, contact_full) or
                (contact_alias and owner_has_contact(owner, contact_alias))):
            abort(400, message="{} or {} has already been registered for {}".format(
                contact_full, contact_alias, owner.entity_id))

        # Determine priority
        if priority is None:
            so_far = owner.list_contact_info(
                entity_id=owner.entity_id,
                source_system=db.const.system_voip)
            priority = 1
            if so_far:
                priority = max(x["contact_pref"] for x in so_far) + 1
        else:
            priority = int(priority)
            if priority <= 0:
                abort(400, message="Priority must be larger than 0")

        # Add the contact info
        owner.add_contact_info(
            db.const.system_voip,
            contact_type,
            contact_full,
            pref=priority,
            alias=contact_alias
        )

        warn = ""
        if contact_alias and not contact_full.endswith(contact_alias):
            warn = " (Warning: Short number does not match full number)"

        return {
            'message': 'Associated {}/{} with owner id={}{}'.format(
                contact_full, contact_alias, owner.entity_id, warn),
            'contact_full': contact_full,
            'contact_alias': contact_alias,
        }, 201


@api.route('/<int:address_id>/numbers/<string:number>', endpoint='address-number')
@api.doc(params={
    'address_id': 'Address entity ID or owner ID',
    'number': 'Phone number to delete'
})
class VoipAddressNumberDeleteResource(Resource):
    """Resource for deleting a specific phone number."""

    number_delete_parser = api.parser()
    number_delete_parser.add_argument(
        'owner_id',
        type=int,
        required=False,
        help='Optional owner entity ID if number is ambiguous',
    )

    @auth.require()
    @api.response(204, 'Number deleted')
    @api.response(404, 'Number not found')
    @api.doc(expect=[number_delete_parser])
    @db.autocommit
    def delete(self, address_id, number):
        """Delete a phone number from a voip address."""
        args = self.number_delete_parser.parse_args()
        owner_id = args.get('owner_id')

        contacts = utils.get_contact_info(db.connection, number)
        if not contacts:
            return '', 404
        owner = None
        if owner_id is not None:
            owner = utils.get_voip_owner(db.connection, owner_id)

        if len(contacts) > 1 and owner is None:
            abort(400, message="Multiple entities have {} registered. "
                  "You must specify owner_id".format(number))

        eci = EntityContactInfo(db.connection)

        for d in contacts:
            if owner and owner.entity_id != d["entity_id"]:
                continue

            eci.clear()
            eci.find(d["entity_id"])
            eci.delete_contact_info(
                d["source_system"],
                d["contact_type"],
                d["contact_pref"]
            )
