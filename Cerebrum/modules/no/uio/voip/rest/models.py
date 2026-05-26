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
import textwrap

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
    ),
    'service_type': base_fields.String(
        description='Service type',
    ),
    'description': base_fields.String(
        description='Service description',
    ),
    'ou': fields.base.Nested(
        models.OU,
        description='Organizational unit',
    ),
})


# A list of VoipServiceListItem values
VoipServiceList = api.model('VoipServiceList', {
    'services': base_fields.List(
        base_fields.Nested(VoipServiceListItem),
        description='List of voip services',
    ),
})


VoipService = VoipServiceListItem.inherit('VoipService', {
    'location': base_fields.String(
        description='Location (OU representation)',
    ),
})

VoipServiceCreate = api.model('VoipServiceCreate', {
    'service_type': base_fields.String(
        required=True,
        description='Service type code',
    ),
    'ou_id': base_fields.Integer(
        required=True,
        description='Organizational unit ID',
    ),
    'description': base_fields.String(
        required=True,
        description='Service description (must be unique)',
    ),
})

VoipServiceUpdate = api.model('VoipServiceUpdate', {
    'description': base_fields.String(
        description='New service description',
    ),
    'service_type': base_fields.String(
        description='New service type code',
    ),
    'ou_id': base_fields.Integer(
        description='New organizational unit ID',
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
    ),
    'owner': fields.base.Nested(
        models.EntityOwner,
        description='Entity owner',
    ),
})


VoipAddressList = api.model('VoipAddressList', {
    'addresses': base_fields.List(
        base_fields.Nested(VoipAddressListItem),
        description='List of voip addresses',
    ),
})


VoipAddress = VoipAddressListItem.inherit('VoipAddress', {
    'cn': base_fields.String(
        description='Common name',
    ),
    'sip_uri': base_fields.String(
        description='SIP URI',
    ),
    'sip_primary_uri': base_fields.String(
        description='Primary SIP URI',
    ),
    'e164_uri': base_fields.String(
        description='E.164 URI',
    ),
    'extension_uri': base_fields.String(
        description='Extension URI',
    ),
    'clients': base_fields.List(
        base_fields.Integer,
        description='Associated client IDs',
    ),
})


VoipNumber = api.model('VoipNumber', {
    'number': base_fields.String(
        description='VoIP phone number',
    ),
    'extension': base_fields.String(
        description='VoIP phone extension',
    ),
    'priority': base_fields.Integer(
        description='Contact priority',
    ),
})


VoipNumberList = api.model('VoipNumberList', {
    'numbers': base_fields.List(
        base_fields.Nested(VoipNumber),
        description='List of voip numbers',
    ),
})
