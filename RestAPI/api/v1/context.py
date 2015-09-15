from flask.ext.restful import Resource, abort, marshal_with, reqparse
from flask.ext.restful_swagger import swagger
from api import db, auth, fields, utils

import cereconf
from Cerebrum import Errors
from Cerebrum.Entity import EntitySpread
from Cerebrum.Utils import Factory

co = Factory.get('Constants')(db.connection)


# Model for data from EntitySpread.list_spreads()
@swagger.model
class Context(object):
    resource_fields = {
        'context': fields.base.String(attribute='spread'),
        #'spread_code': base.Integer,
        'description': fields.base.String,
        'entity_type': fields.Constant(ctype='EntityType', attribute='entity_type'),
    }


@swagger.model
class ContextList(object):
    resource_fields = {
        'contexts': fields.base.Nested(Context.resource_fields),
    }


class ContextListResource(Resource):
    """Resource for contexts."""
    @swagger.operation(
        notes='Get a list of contexts',
        nickname='get',
        responseClass='Context',
        parameters=[
            {
                'name': 'entity_types',
                'description': 'Filter by entity type(s).',
                'required': False,
                'allowMultiple': True,
                'dataType': 'str',
                'paramType': 'query'
            },
        ],
    )
    @auth.require()
    @marshal_with(ContextList.resource_fields)
    def get(self):
        """Returns the groups this account is a member of.

        :rtype: list
        :return: a list of contexts
        """

        parser = reqparse.RequestParser()
        parser.add_argument('entity_types', type=str, action='append')
        args = parser.parse_args()
        filters = {key: value for (key, value) in args.items() if value is not None}

        entity_types = None

        if 'entity_types' in filters:
            etypes = []
            for etype in filters['entity_types']:
                try:
                    entity_type = co.EntityType(etype)
                    int(entity_type)
                    etypes.append(entity_type)
                except Errors.NotFoundError:
                    abort(404, message=u'Unknown entity type for entity_types={}'.format(
                        etype))
            entity_types = etypes or None

        es = EntitySpread(db.connection)
        contexts = es.list_spreads(entity_types=entity_types)
        return {'contexts': contexts}
