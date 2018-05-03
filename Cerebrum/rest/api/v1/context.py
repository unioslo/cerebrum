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

from __future__ import unicode_literals

from flask_restplus import Namespace, Resource, abort

from Cerebrum.rest.api import db, auth, fields, validator

from Cerebrum import Errors
from Cerebrum.Entity import EntitySpread

api = Namespace('contexts', description='Context operations')


# Model for data from EntitySpread.list_spreads()
Context = api.model('Context', {
    'context': fields.base.String(
        attribute='spread',
        description='Context name'),
    'description': fields.base.String(
        description='Context description'),
    'entity_type': fields.Constant(
        ctype='EntityType',
        attribute='entity_type',
        description=''),
})


@api.route('/', endpoint='contexts')
class ContextListResource(Resource):
    """Resource for contexts."""

    context_search_filter = api.parser()
    context_search_filter.add_argument(
        'entity_types',
        type=validator.String(),
        action='append',
        help='Filter by entity type(s)')

    @api.marshal_list_with(Context)
    @api.doc(parser=context_search_filter)
    @auth.require()
    def get(self):
        """List contexts"""
        args = self.context_search_filter.parse_args()
        filters = {key: value for (key, value) in args.items() if
                   value is not None}

        entity_types = None

        if 'entity_types' in filters:
            etypes = []
            for etype in filters['entity_types']:
                try:
                    entity_type = db.const.EntityType(etype)
                    int(entity_type)
                    etypes.append(entity_type)
                except Errors.NotFoundError:
                    abort(404, message='Unknown entity type for '
                          'entity_types={}'.format(etype))
            entity_types = etypes or None

        es = EntitySpread(db.connection)
        contexts = es.list_spreads(entity_types=entity_types)
        return contexts
