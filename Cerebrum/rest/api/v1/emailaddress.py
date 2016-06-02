from flask_restful import Resource, abort, marshal_with
from flask_restful_swagger import swagger
from Cerebrum.rest.api import db, auth, fields

from Cerebrum import Errors
from Cerebrum.modules import Email


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


@swagger.model
class EmailAddress(object):
    """Data model for a single email address."""
    resource_fields = {
        'value': fields.base.String,
        'type': fields.Constant(ctype='EmailTarget')
    }
    swagger_metadata = {
        'value': {'description': 'The email address'},
        'type': {'description':
                 "Email address type, i.e. 'forward', 'target'"}
    }


@swagger.nested(addresses='EmailAddress')
@swagger.model
class EmailAddresses(object):
    """Data model for a set of email addresses."""
    resource_fields = {
        'addresses': fields.base.List(
            fields.base.Nested(
                EmailAddress.resource_fields)),
    }
    swagger_metadata = {
        'addresses': {'description': 'List of addresses'}
    }


class EmailAddressesResource(Resource):
    """Resource for listing email addresses."""
    @swagger.operation(
        notes='Get email address information',
        nickname='get',
        responseClass=EmailAddresses,
        parameters=[
            {
                'name': 'address',
                'description': 'The email address',
                'required': True,
                'allowMultiple': False,
                'dataType': 'string',
                'paramType': 'path'
            },
        ]
    )
    @auth.require()
    @marshal_with(EmailAddresses.resource_fields)
    def get(self, address):
        """Returns email address information for a single address based on the
        EmailAddresses model.

        :param str address: The email address
        :return: Information about the email address
        """
        r = list_email_addresses(address)
        return {'addresses': r}
