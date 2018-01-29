# -*- coding: utf-8 -*-
from flask_restplus import Namespace, Resource, abort
from Cerebrum.rest.api import db, auth, fields

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
        'entity_types', type=str, action='append',
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
                    abort(404, message=u'Unknown entity type for '
                          'entity_types={}'.format(etype))
            entity_types = etypes or None

        es = EntitySpread(db.connection)
        contexts = es.list_spreads(entity_types=entity_types)
        return contexts
