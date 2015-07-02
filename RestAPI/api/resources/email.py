from flask.ext.restful import Resource, abort, reqparse, marshal_with
from api import db, auth, fields
from flask_restful_swagger import swagger

from Cerebrum import Errors
from Cerebrum.modules import Email

@swagger.model
class EmailAddressResourceFields(object):

    def __init__(self):
        pass

    email_address_fields = {
        'address_id': fields.base.Integer,
        'local_part': fields.base.String,
        'domain_id': fields.base.Integer,
        'primary_address': fields.base.String
    }

    resource_fields = {
        'address_id': fields.base.Integer,
        'address': fields.base.String,
        'address_target_id': fields.base.Integer,
        'all_addresses': fields.base.Nested(email_address_fields),
    }


class EmailAddressResource(Resource):
    def __init__(self):
        super(EmailAddressResource, self).__init__()
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('address', type=str)
        self.args = self.reqparse.parse_args()
        self.email_target = Email.EmailTarget(db.connection)
        self.email_address = Email.EmailAddress(db.connection)

    @swagger.operation(
        notes='get email-address info',
        nickname='get',
        responseClass=EmailAddressResourceFields,
        parameters=[
            {
                'name': 'email_address',
                'description': 'The requested email-address',
                'required': True,
                'allowMultiple': False,
                'dataType': 'string',
                'paramType': 'path'
            },
        ]
    )
    @auth.require()
    @marshal_with(EmailAddressResourceFields.resource_fields)
    def get(self, email_address):

        lookup = self.email_address.find_by_address
        identifier = email_address

        try:
            lookup(identifier)
        except Errors.NotFoundError:
            abort(404, message=u"No such email address {}".format(identifier))

        # Create and populate dict to be returned
        data = dict()
        data['address'] = self.email_address.get_address()
        data['address_id'] = self.email_address.entity_id
        data['address_target_id'] = self.email_address.get_target_id()
        data['email_addr_domain_id'] = self.email_address.email_addr_domain_id

        # Get all email-addresses for the target of this email-address
        data['all_addresses'] = {}
        all_addresses = self.email_address.list_target_addresses(self.email_address.get_target_id())

        # Populate all addresses field
        for address in all_addresses:
            primary_address = 'false'
            if address['address_id'] == self.email_address.entity_id:
                primary_address = 'true'
            data['all_addresses'] = [{'address_id': address['address_id'],
                                               'local_part': address['local_part'],
                                               'domain_id': address['domain_id'],
                                               'primary_address': primary_address}]
        return data
