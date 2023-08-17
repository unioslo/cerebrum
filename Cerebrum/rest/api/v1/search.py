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
""" Generic search API. """

from __future__ import unicode_literals

from flask_restx import Namespace, Resource, abort
from flask_restx import fields as base_fields

from Cerebrum.Constants import ConstantsBase
from Cerebrum.Entity import EntityExternalId
from Cerebrum.Utils import Factory
from Cerebrum import Errors

from Cerebrum.rest.api import db, auth, validator
from Cerebrum.rest.api import fields as crb_fields
from Cerebrum.rest.api.v1 import models

api = Namespace('search', description='Search operations')

PersonResult = api.model(
    "PersonResult",
    {
        "id": base_fields.Integer(),
        "href": crb_fields.href(endpoint=".person"),
    },
)

def stedkode_string_validator(value):
    if not value.isdigit() or len(value) != 6:
        raise ValueError
    return value


@api.route("/persons/affiliations", endpoint="search-persons-affiliations")
class AffSearchResource(Resource):
    """
    Resource for affiliation ID searches

    TODO: Deprecate this endpoint when the /persons/ endpoint has been
    implemented and has filtering on affiliation
    """

    search_filter = api.parser()
    search_filter.add_argument(
        "affiliation",
        type=validator.String(),
        action="store",
        required=False,
        help="Filter by affiliation or status, e.g ANSATT or ANSATT/tekadm",
    )
    search_filter.add_argument(
        "location",
        type=stedkode_string_validator,
        action="store",
        required=False,
        help="Filter by location using six-digit stedkode, e.g 373022",
    )

    @auth.require()
    @api.doc(expect=[search_filter])
    @api.marshal_with(PersonResult, as_list=True, envelope="persons")
    def get(self):
        args = self.search_filter.parse_args()
        search_filters = {
            key: value for (key, value) in args.items() if value is not None
        }
        filters = {}
        pe = Factory.get("Person")(db.connection)
        if search_filters.get("affiliation"):
            cb = ConstantsBase()
            try:
                aff, status = cb.get_affiliation(search_filters["affiliation"])
                filters["affiliation"] = aff
                if status:
                    filters["status"] = status
            except Errors.NotFoundError:
                abort(
                    400,
                    "Invalid affiliation: {aff}".format(aff=search_filters["affiliation"]),
                )
        if search_filters.get("location"):
            ou = Factory.get("OU")(db.connection)
            try:
                ou.find_sko(search_filters["location"])
                filters["ou_id"] = ou.entity_id
            except Errors.NotFoundError:
                abort(
                    400,
                    "Invalid stedkode {sko}".format(sko=search_filters["location"])
                )
        return [{"id": i["person_id"]} for i in pe.list_affiliations(**filters)]


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
        transform=models.ExternalIdType.serialize,
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
        type=validator.String(),
        action='append',
        help='Filter by one or more source systems.')
    extid_search_filter.add_argument(
        'id_type',
        type=validator.String(),
        action='append',
        help='Filter by one or more ID types.')
    extid_search_filter.add_argument(
        'external_id',
        type=validator.String(),
        required=True,
        help='Filter by external ID.')

    @auth.require()
    @api.doc(expect=[extid_search_filter])
    @api.marshal_with(ExternalIdItem, as_list=True, envelope='external_ids')
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
                          message='Unknown source_system={}'.format(entry))
            filters['source_system'] = source_systems

        if 'id_type' in filters:
            id_types = []
            if not isinstance(filters['id_type'], list):
                filters['id_type'] = [filters['id_type']]
            for entry in filters['id_type']:
                try:
                    if entry not in models.ExternalIdType.valid_types():
                        raise Errors.NotFoundError
                    code = int(models.ExternalIdType.unserialize(entry))
                    id_types.append(code)
                except Errors.NotFoundError:
                    abort(404,
                          message='Unknown id_type={}'.format(entry))
            filters['id_type'] = id_types

        strip_wildcards = {ord(c): '' for c in '*?%_'}
        if 'external_id' in filters:
            filters['external_id'] = filters['external_id'].translate(
                strip_wildcards)

        results = list()
        for row in eei.search_external_ids(**filters):
            entry = dict(row)
            # id for the href builder, won't be shown in output
            entry['id'] = entry['entity_id']
            results.append(entry)
        return results
