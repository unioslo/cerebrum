# -*- coding: utf-8 -*-
#
# Copyright 2016-2024 University of Oslo, Norway
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

from flask_restx import fields as base_fields
from Cerebrum.rest.api import fields


def create_models(api):
    """Create and return API models."""

    VoipService = api.model('VoipService', {
        'entity_id': base_fields.Integer(
            description='Service entity ID',
        ),
        'service_type': base_fields.String(
            description='Service type',
        ),
        'description': base_fields.String(
            description='Service description',
        ),
        'ou_id': base_fields.Integer(
            description='Organizational unit ID',
        ),
        'location': base_fields.String(
            description='Location (OU representation)',
        ),
        'traits': base_fields.List(
            base_fields.String,
            description='Entity traits',
        ),
    })

    VoipServiceList = api.model('VoipServiceList', {
        'services': base_fields.List(
            base_fields.Nested(VoipService),
            description='List of voip services',
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

    VoipAddress = api.model('VoipAddress', {
        'entity_id': base_fields.Integer(
            description='Address entity ID',
        ),
        'owner_entity_id': base_fields.Integer(
            description='Owner entity ID',
        ),
        'owner_entity_type': base_fields.String(
            description='Owner entity type',
        ),
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
        'traits': base_fields.List(
            base_fields.String,
            description='Entity traits',
        ),
        'clients': base_fields.List(
            base_fields.String,
            description='Associated client IDs',
        ),
    })

    VoipAddressList = api.model('VoipAddressList', {
        'addresses': base_fields.List(
            base_fields.Nested(VoipAddress),
            description='List of voip addresses',
        ),
    })

    VoipAddressNumber = api.model('VoipAddressNumber', {
        'contact_type': base_fields.String(
            required=True,
            description='Contact type code',
        ),
        'contact_value': base_fields.String(
            required=True,
            description='Full phone number',
        ),
        'priority': base_fields.Integer(
            description='Priority (optional, auto-assigned if not provided)',
        ),
    })

    return {
        'VoipService': VoipService,
        'VoipServiceList': VoipServiceList,
        'VoipServiceCreate': VoipServiceCreate,
        'VoipServiceUpdate': VoipServiceUpdate,
        'VoipAddress': VoipAddress,
        'VoipAddressList': VoipAddressList,
        'VoipAddressNumber': VoipAddressNumber,
    }
