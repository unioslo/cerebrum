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
Data models for VOIP API.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from flask_restx import Namespace
from flask_restx import fields as base_fields
from Cerebrum.rest.api import fields
from Cerebrum.rest.api.v1 import models


api = Namespace(
    "voip",
    description="VoIP service and address namespace",
)


# Basic VoipService reference item (basic info)
VoipServiceListItem = api.model('VoipServiceListItem', {
    'href': fields.href(
        '.voip-service',
        description='URL to this service',
    ),
    'service_id': base_fields.Integer(
        description='Service entity ID',
        example=101,
    ),
    'service_type': base_fields.String(
        description='Service type',
        example="voip_service_teknisk",
    ),
    'description': base_fields.String(
        description='Service description',
        example="Vakttelefon, eksempel",
    ),
    'ou': fields.base.Nested(
        models.OU,
        description='Organizational unit',
        example={
            "href": "/path/to/ous/110",
            "id": 110,
        },
    ),
})


# A list of VoipServiceListItem values
VoipServiceList = api.model('VoipServiceList', {
    'services': base_fields.List(
        base_fields.Nested(VoipServiceListItem),
        description='List of voip services',
    ),
})


VoipService = api.inherit('VoipService', VoipServiceListItem, {
    'location': base_fields.String(
        description='Location (OU representation)',
    ),
})

VoipServiceCreate = api.model('VoipServiceCreate', {
    'service_type': base_fields.String(
        required=True,
        description='Service type code',
        example="voip_service_teknisk",
    ),
    'description': base_fields.String(
        required=True,
        description='Service description (must be unique)',
        example="Vakttelefon, eksempel",
    ),
    'ou_id': base_fields.Integer(
        required=True,
        description='Organizational unit ID',
        example=110,
    ),
})

VoipServiceUpdate = api.model('VoipServiceUpdate', {
    'service_type': base_fields.String(
        description='New service type code',
        example="voip_service_teknisk",
    ),
    'description': base_fields.String(
        description='New service description',
        example="Vakttelefon, eksempel",
    ),
    'ou_id': base_fields.Integer(
        description='New organizational unit ID',
        example=110,
    ),
})


# Basic VoipAddress reference item (basic info)
VoipAddressListItem = api.model('VoipAddressListItem', {
    'href': fields.href(
        '.voip-address',
        description='URL to this address',
    ),
    'address_id': base_fields.Integer(
        description='Address entity ID',
        example=102,
    ),
    'owner': fields.base.Nested(
        models.EntityOwner,
        description='Entity owner',
        example={
            'id': 112,
            'type': "person",
            'href': "/path/to/persons/112",
            'name': None,
        },
    ),
})


VoipAddressList = api.model('VoipAddressList', {
    'addresses': base_fields.List(
        base_fields.Nested(VoipAddressListItem),
        description='List of voip addresses',
    ),
})


VoipAddress = api.inherit('VoipAddress', VoipAddressListItem, {
    'cn': base_fields.String(
        description='Common name',
    ),
    'sip_uri': base_fields.List(
        base_fields.String,
        description='SIP URI',
        example=[
            "sip:+68051234@example.org", "sip:51234@exmaple.org",
            "sip:username@example.org", "sip:first.last@example.org",
        ],
    ),
    'sip_primary_uri': base_fields.String(
        description='Primary SIP URI',
        example="sip:first.last@example.org",
    ),
    'e164_uri': base_fields.String(
        description='E.164 URI',
        example="sip:68051234@example.org",
    ),
    'extension_uri': base_fields.String(
        description='Extension URI',
        example="sip:51234@example.org",
    ),
    'clients': base_fields.List(
        base_fields.Integer,
        description='Associated client IDs',
        example=[103, 104],
    ),
})


VoipNumber = api.model('VoipNumber', {
    'number': base_fields.String(
        description='VoIP phone number',
        example="+4768051234",
    ),
    'extension': base_fields.String(
        description='VoIP phone extension',
        example="51234",
    ),
    'priority': base_fields.Integer(
        description='Contact priority',
        example=1,
    ),
})


VoipNumberList = api.model('VoipNumberList', {
    'numbers': base_fields.List(
        base_fields.Nested(VoipNumber),
        description='List of voip numbers',
    ),
})
