# -*- coding: utf-8 -*-
from flask_restplus import Namespace, Resource, abort
from Cerebrum.rest.api import db, auth, fields

from Cerebrum import Errors
from Cerebrum.modules import Email

api = Namespace('emailaddresses', description='Email address operations')


def find_email_address(address):
    """Looks up an email address.

    :param int/str address: Email address entity ID or FQDA
    :rtype Email.EmailAddress:
    :return: the email address object
    """
    ea = Email.EmailAddress(db.connection)
    lookup = ea.find_by_address
    if isinstance(address, (int, long)):
        lookup = ea.find
    try:
        lookup(address)
    except (Errors.NotFoundError, ValueError):
        abort(404, message=u"No such email address {}".format(address))
    return ea


def list_email_addresses(ea):
    if not isinstance(ea, Email.EmailAddress):
        ea = find_email_address(ea)
    et = Email.EmailTarget(db.connection)
    et.find(ea.email_addr_target_id)

    return map(lambda (lp, dom, _a_id): {'value': '{}@{}'.format(lp, dom),
                                         'type': et.get_target_type()},
               et.get_addresses())


EmailAddress = api.model('EmailAddress', {
    'value': fields.base.String(
        description='The email address'),
    'type': fields.Constant(
        ctype='EmailTarget',
        description="Email address type, i.e. 'forward', 'target'")
})

EmailAddresses = api.model('EmailAddresses', {
    'addresses': fields.base.List(
        fields.base.Nested(EmailAddress),
        description='List of addresses'),
})


@api.route('/<string:address>', endpoint='emailaddresses')
@api.doc(params={'address': 'Email address'})
class EmailAddressesResource(Resource):
    """Resource for listing email addresses."""
    @api.marshal_list_with(EmailAddress)
    @auth.require()
    def get(self, address):
        """Get email address information."""
        return {'addresses': list_email_addresses(address)}
