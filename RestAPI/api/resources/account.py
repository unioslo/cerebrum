from flask.ext.restful import Resource, abort, reqparse, marshal_with
from api import db, auth, fields
from flask_restful_swagger import swagger

from Cerebrum.Utils import Factory
from Cerebrum import Errors


@swagger.model
class AccountResourceFields(object):

    def __init__(self):
        pass

    resource_fields = {
        'account_name': fields.base.String,
        'entity_id': fields.base.Integer(default=None),
        'owner_id': fields.base.Integer(default=None),
        'owner_type': fields.EntityType,
        'create_date': fields.DateTimeString,
        'expire_date': fields.DateTimeString,
        'creator_id': fields.base.Integer(default=None),
        'spreads': fields.SpreadGet(attribute='get_spread'),
        'primary_email': fields.Call(attribute='get_primary_mailaddress'),
    }

    swagger_metadata = {
        'account_name': {
            'description': 'The name of the returned account',
        }
    }

class Account(Resource):
    def __init__(self):
        super(Account, self).__init__()
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('name', type=str)
        self.reqparse.add_argument('entity_id', type=int)
        self.args = self.reqparse.parse_args()
        self.ac = Factory.get('Account')(db.connection)

    @swagger.operation(
        notes='get account info',
        nickname='get',
        responseClass=AccountResourceFields,
        parameters=[
            {
                'name': 'lookup',
                'description': 'The value-type to use when looking up an Cerebrum-account. Valid values are: \
                                name, entity_id',
                'required': True,
                'allowMultiple': False,
                'dataType': 'string',
                'paramType': 'path'
            },
            {
                'name': 'identifier',
                'description': "Account name or entity ID for account (depending on the lookup value-type)",
                'required': True,
                'allowMultiple': False,
                'dataType': 'string',
                'paramType': 'path'
            }
        ]
    )
    @auth.require()
    @marshal_with(AccountResourceFields.resource_fields)
    def get(self, lookup, identifier):
        if lookup not in ['name', 'entity_id']:
            abort(404, message=u"Invalid lookup value type {}".format(identifier))

        if lookup == 'name':
            lookup = self.ac.find_by_name
        else:  # entity_id
            lookup = self.ac.find
            try:
                identifier = int(identifier)
            except ValueError:
                abort(404, message=u"Invalid entity_id {}".format(identifier))

        try:
            lookup(identifier)
        except Errors.NotFoundError:
            abort(404, message=u"No such account {}".format(identifier))

        return self.ac
