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
from flask_restx import Resource, abort

from Cerebrum.modules.no.uio.voip.voipAddress import VoipAddress
from Cerebrum.modules.no.uio.voip.voipClient import VoipClient
from Cerebrum.modules.no.uio.voip.voipService import VoipService
from Cerebrum.modules.no.uio.voip.voipService import search_voip_service
from Cerebrum.rest.api import db, auth
from . import utils
from . import models

api = models.api


@api.route("/services/", endpoint="voip-service-list")
class VoipServiceListResource(Resource):
    """ VoIP service collection resource - list, search, or create service. """

    service_search_parser = api.parser()
    service_search_parser.add_argument(
        "ou-id",
        type=int,
        required=False,
        help="Only include services for the given org unit id (ou entity-id)",
    )
    service_search_parser.add_argument(
        "location",
        type=int,
        required=False,
        help="Only include services by org unit location code (stedkode)",
    )
    service_search_parser.add_argument(
        "description",
        type=str,
        required=False,
        help=(
            "Only include services with the given description"
            " (supports case-sensitive glob-like patterns)"
        ),
    )

    @auth.require()
    @api.marshal_with(models.VoipServiceList)
    @api.response(200, 'Service found')
    @api.doc(expect=[service_search_parser])
    def get(self):
        """ List or search for voip services. """
        args = self.service_search_parser.parse_args()

        # Sanity check our ou-id + location args
        # (i.e. translate to a single ou_id)
        ou_ids = set()
        if args['ou-id'] is not None:
            ou = utils.get_ou_by_id(args['ou-id'])
            ou_ids.add(ou.entity_id)
        if args['location'] is not None:
            ou = utils.get_ou_by_location(args['location'])
            ou_ids.add(ou.entity_id)
        if len(ou_ids) > 1:
            # TODO: We *could* support OR-ing the ou-id and location
            # parameters, but it really doesn't make sense
            # We could also logically AND them, i.e. return an empty result.
            abort(400, message="conflicting ou identifiers")
        if len(ou_ids) < 1:
            ou_ids = None

        description = args['description']

        matches = []
        svc_type_cls = db.const.VoipServiceTypeCode
        for row in search_voip_service(db.connection, ou_id=ou_ids,
                                       description_like=description):
            service_type = svc_type_cls(row['service_type'])
            matches.append({
                "service_id": row['entity_id'],
                "service_type": six.text_type(service_type),
                "description": row['description'],
                "ou": {'id': row['ou_id']},
            })
        return {'services': matches}

    @auth.require()
    @api.expect(models.VoipServiceCreate)
    @api.response(201, 'Service created')
    @api.response(400, 'Service not created')
    @db.autocommit
    def post(self):
        """Create a new voip service."""
        data = api.payload

        service_type_str = data.get('service_type')
        ou_id = data.get('ou_id')
        description = data.get('description')

        if not all([service_type_str, ou_id, description]):
            abort(400, message="Missing required fields")

        utils.assert_unused_service_description(description)

        service = VoipService(db.connection)
        ou = utils.get_ou_by_id(ou_id, _error=400)
        service_type = utils.get_service_type(service_type_str)

        service.populate(description, service_type, ou.entity_id)
        service.write_db()

        # Create a corresponding voip_address
        address = VoipAddress(db.connection)
        address.populate(service.entity_id)
        address.write_db()

        # Create default softphone client
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
            'service_id': service.entity_id,
        }, 201


def _build_service_response(service):
    """Build a VoipService model from a VoipService entity. """
    service_type = utils.get_service_type(service.service_type, _error=500)
    return {
        'service_id': service.entity_id,
        'service_type': six.text_type(service_type),
        'description': service.description,
        'ou': {
            'id': service.ou_id,
        },
        'location': utils.typeset_ou(service.ou_id),
    }


@api.route("/services/<int:service_id>", endpoint="voip-service")
@api.doc(params={'service_id': 'Service entity ID'})
class VoipServiceResource(Resource):
    """Resource for a single voip service."""

    @auth.require()
    @api.response(200, 'Service found')
    @api.response(404, 'Service not found')
    @api.marshal_with(models.VoipService)
    def get(self, service_id):
        """Get voip service information."""
        service = utils.get_voip_service_by_id(service_id)
        return _build_service_response(service)

    @auth.require()
    @api.expect(models.VoipServiceUpdate)
    @api.marshal_with(models.VoipService)
    @api.response(200, 'Service updated')
    @api.response(400, 'Invalid service_type, description, or ou_id')
    @api.response(404, 'Service not found')
    @db.autocommit
    def put(self, service_id):
        """Update voip service information."""
        service = utils.get_voip_service_by_id(service_id)
        data = api.payload

        description = data.get('description')
        service_type_str = data.get('service_type')
        ou_id = data.get('ou_id')

        if description and service.description != description:
            utils.assert_unused_service_description(description)
            service.description = description

        if service_type_str:
            service_type = utils.get_service_type(service_type_str)
            if service.service_type != service_type:
                service.service_type = service_type

        if ou_id:
            ou = utils.get_ou_by_id(ou_id, _error=400)
            if service.ou_id != ou.entity_id:
                service.ou_id = ou.entity_id

        service.write_db()
        return _build_service_response(service)

    @auth.require()
    @api.response(204, 'Service deleted')
    @api.response(404, 'Service not found')
    @db.autocommit
    def delete(self, service_id):
        """Delete a voip service."""
        service = utils.get_voip_service_by_id(service_id)
        service.delete()
        return None, 204
