from flask.ext.restful import Resource, abort, marshal_with
from api import db, auth, fields
from flask_restful_swagger import swagger

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


def get_email_domain(domain_id):
    """Looks up a email domain by ID and builds a dictionary suitable for marshalling.

    :param int: Email domain entity ID
    :rtype: dict
    :return: Email domain information
    """
    ed = Email.EmailDomain(db.connection)
    ed.find(domain_id)
    return {
        'id': ed.entity_id,
        'name': ed.email_domain_name,
        'description': ed.email_domain_description,
    }


def get_email_target(target_id):
    """Looks up a email target by ID and builds a dictionary suitable for marshalling.

    :param int: Email target entity ID
    :rtype: dict
    :return: Email target information
    """
    et = Email.EmailTarget(db.connection)
    et.find(target_id)
    return {
        'id': et.entity_id,
        'type': et.get_target_type(),
        'entity': {
            'id': et.get_target_entity_id(),
            'type': et.get_target_entity_type(),
        },
    }


def get_email_address(ea):
    """Takes an email address by id/address/object and builds a dictionary
    suitable for marshalling.

    :param int/str/Email.EmailAddress: Email address
    :rtype: dict
    :return: Email address information
    """
    if not isinstance(ea, Email.EmailAddress):
        ea = find_email_address(ea)
    return {
        'address': ea.get_address(),
        'local_part': ea.get_localpart(),
        'id': ea.entity_id,
        'target': get_email_target(ea.get_target_id()),
        'domain': get_email_domain(ea.get_domain_id()),
    }


@swagger.model
class EmailDomain(object):
    """Data model for an email domain."""
    resource_fields = {
        'id': fields.base.Integer,
        'name': fields.base.String,
        'description': fields.base.String,
    }

    swagger_metadata = {
        'id': {'description': 'Domain entity ID'},
        'name': {'description': 'Domain name'},
        'description': {'description': 'Domain description'},
    }


@swagger.model
class EmailTargetEntity(object):
    """Data model for the targeted entity of an email target."""
    resource_fields = {
        'id': fields.base.Integer,
        'type': fields.Constant(ctype='EntityType'),
        'href': fields.UrlFromEntityType(absolute=True),
    }

    swagger_metadata = {
        'id': {'description': 'Entity ID being targeted'},
        'type': {'description': 'Type of entity being targeted'},
        'href': {'description': 'URL to the resource being targeted'},
    }


@swagger.model
@swagger.nested(
    entity='EmailTargetEntity')
class EmailTarget(object):
    """Data model for an email target."""
    resource_fields = {
        'id': fields.base.Integer,
        'type': fields.Constant(ctype='EmailTarget'),
        'entity': fields.base.Nested(EmailTargetEntity.resource_fields),
    }

    swagger_metadata = {
        'id': {'description': 'Email target entity ID'},
        'type': {'description': 'Email target type'},
        'entity': {'description': 'Entity being targeted'},
    }


@swagger.model
@swagger.nested(
    domain='EmailDomain',
    target='EmailTarget')
class EmailAddress(object):
    """Data model for a single email address."""
    resource_fields = {
        'address': fields.base.String,
        'local_part': fields.base.String,
        'id': fields.base.Integer,
        'domain': fields.base.Nested(EmailDomain.resource_fields),
        'target': fields.base.Nested(EmailTarget.resource_fields),
        'href': fields.UrlFromEntityType(endpoint='.emailaddress'),
    }

    swagger_metadata = {
        'address': {'description': 'Fully qualified domain address (FQDA)'},
        'local_part': {'description': 'The local part of the email address'},
        'id': {'description': 'Email address entity ID'},
        'domain': {'description': 'Email domain'},
        'target': {'description': 'Email target'},
        'href': {'description': 'URL to this resource'},
    }


class EmailAddressResource(Resource):
    """Resource for a single email address."""
    @swagger.operation(
        notes='Get email address information',
        nickname='get',
        responseClass=EmailAddress,
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
    @marshal_with(EmailAddress.resource_fields)
    def get(self, address):
        """Returns email address information for a single address based on the EmailAddress model.

        :param str address: The email address
        :return: Information about the email address
        """
        return get_email_address(address)
