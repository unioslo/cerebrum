#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2018 University of Oslo, Norway
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
""" OrgUnit API. """

from __future__ import unicode_literals

from flask_restx import Namespace, Resource, abort

from Cerebrum.rest.api import db, auth, fields
from Cerebrum.rest.api.v1 import models

from Cerebrum.Utils import Factory
from Cerebrum import Errors

api = Namespace('ous', description='Organizational unit operations')


def find_ou(ou_id):
    ou = Factory.get('OU')(db.connection)
    try:
        ou.find(ou_id)
    except Errors.NotFoundError:
        abort(404, message="No such OU with entity_id={}".format(ou_id))
    return ou


def format_ou(ou):
    if isinstance(ou, (int, long)):
        ou = find_ou(ou)

    data = {
        'id': ou.entity_id,
        'contexts': [row['spread'] for row in ou.get_spread()],
        'contact': ou.get_contact_info(),
        'names': ou.search_name_with_language(entity_id=ou.entity_id),
    }

    # Extend with data from the stedkode mixin if available
    try:
        data.update({
            'landkode': ou.landkode,
            'fakultet': ou.fakultet,
            'institutt': ou.institutt,
            'avdeling': ou.avdeling,
            'institusjon': ou.institusjon,
            'stedkode': "{:02d}{:02d}{:02d}".format(
                ou.fakultet, ou.institutt, ou.avdeling),
        })
    except AttributeError:
        pass

    return data


OrganizationalUnit = api.model('OrganizationalUnit', {
    'href': fields.href('.ou'),
    'id': fields.base.Integer(
        description='OU entity ID'),
    'contact': fields.base.List(
        fields.base.Nested(models.EntityContactInfo),
        description='Contact information'),
    'names': fields.base.List(
        fields.base.Nested(models.EntityNameWithLanguage),
        description='Names'),
    'contexts': fields.base.List(
        fields.Constant(ctype='Spread'),
        description='Visible in these contexts'),
    'stedkode': fields.base.String(),
    'fakultet': fields.base.Integer(),
    'institutt': fields.base.Integer(),
    'avdeling': fields.base.Integer(),
})


@api.route('/<string:id>', endpoint='ou')
@api.doc(params={'id': 'OU ID'})
class OrganizationalUnitResource(Resource):
    """Resource for organizational units."""
    @auth.require()
    @api.marshal_with(OrganizationalUnit)
    def get(self, id):
        """Get organizational unit information."""
        ou = find_ou(id)
        return format_ou(ou)
