#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016 University of Oslo, Norway
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
from __future__ import unicode_literals
""" Generic search API. """

from flask import url_for
from flask_restplus import Namespace, Resource, abort
from flask_restplus import fields as base_fields

from Cerebrum.Utils import Factory
from Cerebrum.Entity import EntityExternalId
from Cerebrum import Errors

from Cerebrum.rest.api import db, auth, utils
from Cerebrum.rest.api import fields as crb_fields
from Cerebrum.rest.api.v1 import models

api = Namespace('search', description='Search operations')


class ExternalIdType(object):
    """ External ID type translation. """

    _map = {
        'NO_BIRTHNO': 'norwegianNationalId',
        'PASSNR': 'passportNumber',
        'NO_SAPNO': 'employeeNumber',
        'SSN': 'socialSecurityNumber',
        'NO_STUDNO': 'studentNumber',
    }

    _rev_map = dict((v, k) for k, v in _map.iteritems())

    @classmethod
    def serialize(cls, strval):
        return cls._map.get(strval, strval)

    @classmethod
    def unserialize(cls, input_):
        return db.const.EntityExternalId(cls._rev_map[input_])


ExternalIdItem = api.model('ExternalIdItem', {
    'href': crb_fields.href(
        endpoint='.person'),
    'person_id': base_fields.Integer(
        description='Person ID',
        attribute='entity_id'),
    'source_system': crb_fields.Constant(
        ctype='AuthoritativeSystem',
        description='Source system'),
    'id_type': crb_fields.Constant(
        ctype='EntityExternalId',
        transform=ExternalIdType.serialize,
        attribute='id_type',
        description='External ID type'),
    'external_id': base_fields.String(
        description='External ID value')
})


@api.route('/persons/external-ids', endpoint='search-persons-external-ids')
class ExternalIdResource(Resource):
    """Resource for external ID searches."""

    # GET /
    #
    extid_search_filter = api.parser()
    extid_search_filter.add_argument(
        'source_system',
        type=str,
        action='append',
        help='Filter by one or more source systems.')
    extid_search_filter.add_argument(
        'id_type',
        type=str,
        action='append',
        help='Filter by one or more ID types.')
    extid_search_filter.add_argument(
        'external_id',
        type=str,
        help='Filter by external ID. Accepts * and ? as wildcards.')

    @auth.require()
    @api.doc(parser=extid_search_filter)
    @api.marshal_with(ExternalIdItem, as_list=True)
    def get(self):
        """Get external IDs"""
        args = self.extid_search_filter.parse_args()
        filters = {key: value for (key, value) in args.items() if
                   value is not None}
        filters['entity_type'] = db.const.entity_person
        eei = EntityExternalId(db.connection)

        if 'source_system' in filters:
            source_systems = []
            if not isinstance(filters['source_system'], list):
                filters['source_system'] = [filters['source_system']]
            for entry in filters['source_system']:
                try:
                    code = int(db.const.AuthoritativeSystem(entry))
                    source_systems.append(code)
                except Errors.NotFoundError:
                    abort(404,
                          message=u'Unknown source system for source_system={}'.format(
                              entry))
            filters['source_system'] = source_systems

        if 'id_type' in filters:
            id_types = []
            if not isinstance(filters['id_type'], list):
                filters['id_type'] = [filters['id_type']]
            for entry in filters['id_type']:
                try:
                    code = int(ExternalIdType.unserialize(entry))
                    id_types.append(code)
                except Errors.NotFoundError:
                    abort(404,
                          message=u'Unknown external ID type for id_type={}'.format(
                              entry))
            filters['id_type'] = id_types

        results = list()
        for row in eei.search_external_ids(**filters):
            entry = dict(row)
            # id for the href builder, won't be shown in output
            entry['id'] = entry['entity_id']
            results.append(entry)
        return results
