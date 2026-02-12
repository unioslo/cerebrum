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
VOIP Services API.

Endpoints for managing voip services.
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
from Cerebrum.modules.no.uio.voip.voipService import VoipService
from Cerebrum.rest.api import db, auth
from . import utils
from . import models as model_module

api = Namespace('services', description='VOIP service operations')

# Create models
models = model_module.create_models(api)


@api.route('/', endpoint='services-list')
class VoipServiceListResource(Resource):
    """Resource for voip service creation and search."""

    service_search_parser = api.parser()
    service_search_parser.add_argument(
        'search',
        type=str,
        required=False,
        help='Search parameter (entity_id, description, ou_id, or stedkode)',
    )

    @auth.require()
    @api.marshal_with(models['VoipServiceList'])
    @api.doc(expect=[service_search_parser])
    def get(self):
        """
        Search for voip services.

        Search by entity_id, description, ou_id, or stedkode.
        """
        args = self.service_search_parser.parse_args()
        designation = args.get('search', '').strip()

        if not designation:
            abort(400, message="Search parameter is required")

        collect = dict()
        vs = VoipService(db.connection)

        # Try by-id lookup first
        if designation.isdigit():
            try:
                vs.find(int(designation))
                collect[vs.entity_id] = (
                    vs.description, vs.service_type, vs.ou_id)
            except Errors.NotFoundError:
                pass

        # Try by description
        for exact_match in (True, False):
            results = vs.search_voip_service_by_description(
                designation, exact_match=exact_match)
            for row in results:
                collect[row["entity_id"]] = (
                    row["description"], row["service_type"], row["ou_id"])

        # Try by OU
        try:
            ou = utils.get_ou(db.connection, designation)
            for row in vs.search(ou_id=ou.entity_id):
                collect[row["entity_id"]] = (
                    row["description"], row["service_type"], row["ou_id"])
        except:
            pass

        answer = []
        for entity_id in collect:
            description, service_type, ou_id = collect[entity_id]
            const = db.const
            service_type_const = const.VoipServiceTypeCode(service_type)
            answer.append({
                "entity_id": entity_id,
                "description": description,
                "service_type": six.text_type(service_type_const),
                "ou_id": ou_id,
                "location": utils.typeset_ou(db.connection, ou_id),
                "traits": [],
            })

        return {'services': answer}

    @auth.require()
    @api.expect(models['VoipServiceCreate'])
    @api.response(201, 'Service created')
    @db.autocommit
    def post(self):
        """Create a new voip service."""
        data = api.payload

        service_type_str = data.get('service_type')
        ou_id = data.get('ou_id')
        description = data.get('description')

        if not all([service_type_str, ou_id, description]):
            abort(400, message="Missing required fields")

        utils.assert_unused_service_description(db.connection, description)

        service = VoipService(db.connection)
        ou = utils.get_ou(db.connection, ou_id)
        service_type = utils.get_constant(
            db.connection, service_type_str, db.const.VoipServiceTypeCode)

        service.populate(description, service_type, ou.entity_id)
        service.write_db()

        # Create a corresponding voip_address
        from Cerebrum.modules.no.uio.voip.voipAddress import VoipAddress
        address = VoipAddress(db.connection)
        address.populate(service.entity_id)
        address.write_db()

        # Create default softphone client
        from Cerebrum.modules.no.uio.voip.voipClient import VoipClient
        client = VoipClient(db.connection)
        if not client.search(
            voip_address_id=address.entity_id,
            client_type=db.const.voip_client_type_softphone
        ):
            client.populate(
                address.entity_id,
                db.const.voip_client_type_softphone,
                True,
                None,
                db.const.voip_client_info_softphone
            )
            client.write_db()
            client.set_auth_data(
                db.const.voip_auth_sip_secret,
                client.generate_sip_secret()
            )

        return {
            'entity_id': service.entity_id,
            'message': 'Created voip_service with id={}'.format(service.entity_id)
        }, 201


@api.route('/<int:service_id>', endpoint='service')
@api.doc(params={'service_id': 'Service entity ID'})
class VoipServiceResource(Resource):
    """Resource for a single voip service."""

    @auth.require()
    @api.marshal_with(models['VoipService'])
    def get(self, service_id):
        """Get voip service information."""
        service = utils.get_voip_service(db.connection, service_id)

        service_type = db.const.VoipServiceTypeCode(service.service_type)
        return {
            'entity_id': service.entity_id,
            'service_type': six.text_type(service_type),
            'description': service.description,
            'ou_id': service.ou_id,
            'location': utils.typeset_ou(db.connection, service.ou_id),
            'traits': utils.typeset_traits(db.connection, service.get_traits()),
        }

    @auth.require()
    @api.expect(models['VoipServiceUpdate'])
    @api.response(200, 'Service updated')
    @db.autocommit
    def put(self, service_id):
        """Update voip service information."""
        service = utils.get_voip_service(db.connection, service_id)
        data = api.payload

        description = data.get('description')
        service_type_str = data.get('service_type')
        ou_id = data.get('ou_id')

        if description and service.description != description:
            utils.assert_unused_service_description(db.connection, description)
            service.description = description

        if service_type_str:
            service_type = utils.get_constant(
                db.connection, service_type_str, db.const.VoipServiceTypeCode)
            if service.service_type != service_type:
                service.service_type = service_type

        if ou_id:
            ou = utils.get_ou(db.connection, ou_id)
            if service.ou_id != ou.entity_id:
                service.ou_id = ou.entity_id

        service.write_db()

        return {
            'entity_id': service.entity_id,
            'message': 'Updated voip_service with id={}'.format(service.entity_id)
        }

    @auth.require()
    @api.response(200, 'Service deleted')
    @db.autocommit
    def delete(self, service_id):
        """Delete a voip service."""
        service = utils.get_voip_service(db.connection, service_id)

        entity_id = service.entity_id
        description = service.description

        service.delete()

        return {
            'entity_id': entity_id,
            'message': 'Deleted voip_service id={}, {}'.format(
                entity_id, description)
        }
