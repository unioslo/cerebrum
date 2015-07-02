from flask.ext.restful import Resource, abort, reqparse, marshal_with
from api import db, auth, fields

# from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules import Email

class EmailAddressResource(Resource):
    def __init__(self):
        super(EmailAddressResource, self).__init__()
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('address', type=str)
        self.args = self.reqparse.parse_args()
        self.email_target = Email.EmailTarget(db.connection)
        self.email_address = Email.EmailAddress(db.connection)

    @auth.require()
    @marshal_with(fields.email_fields)
    def get(self):
        if self.args.address:
            lookup = self.email_address.find_by_address
            identifier = self.args.address
        else:
            abort(404, message=u"Missing identifier")
        try:
            lookup(identifier)
        except Errors.NotFoundError:
            abort(404, message=u"No such email address {}".format(identifier))

        # Create and populate dict to be returned as JSON
        returned_data = dict()
        returned_data['address'] = self.email_address.get_address()
        returned_data['address_id'] = self.email_address.entity_id
        returned_data['address_target_id'] = self.email_address.get_target_id()
        returned_data['email_addr_domain_id'] = self.email_address.email_addr_domain_id

        # Get all email-addresses for the target of this email-address
        returned_data['all_addresses'] = {}
        all_addresses = self.email_address.list_target_addresses(self.email_address.get_target_id())

        # Populate all addresses field
        for address in all_addresses:
            primary_address = 'false'
            if address['address_id'] == self.email_address.entity_id:
                primary_address = 'true'
            returned_data['all_addresses'] = [{'address_id': address['address_id'],
                                               'local_part': address['local_part'],
                                               'domain_id': address['domain_id'],
                                               'primary_address': primary_address}]
        return returned_data
