from flask_restful import Resource, abort, marshal_with
from flask_restful_swagger import swagger

from Cerebrum.rest.api import db, auth, fields
from Cerebrum.rest.api.v1 import models

from Cerebrum.Utils import Factory
from Cerebrum import Errors


def find_ou(ou_id):
    ou = Factory.get('OU')(db.connection)
    try:
        ou.find(ou_id)
    except Errors.NotFoundError:
        abort(404, message=u"No such OU with entity_id={}".format(ou_id))
    return ou


def format_ou(ou):
    if isinstance(ou, (int, long)):
        ou = find_ou(ou)

    data = {
        'id': ou.entity_id,
        'contexts': [row['spread'] for row in ou.get_spread()],
        'contact': ou.get_contact_info(),
        'names': ou.search_name_with_language(entity_id=ou.entity_id),
    }

    # Extend with data from the stedkode mixin if available
    try:
        data.update({
            'landkode': ou.landkode,
            'fakultet': ou.fakultet,
            'institutt': ou.institutt,
            'avdeling': ou.avdeling,
            'institusjon': ou.institusjon,
            'stedkode': "{:02d}{:02d}{:02d}".format(
                ou.fakultet, ou.institutt, ou.avdeling),
        })
    except AttributeError:
        pass

    return data


@swagger.model
class OrganizationalUnit(object):
    resource_fields = {
        'href': fields.base.Url(endpoint='.ou', absolute=True),
        'id': fields.base.Integer,
        'contact': fields.base.List(fields.base.Nested(
            models.EntityContactInfo.resource_fields)),
        'names': fields.base.List(fields.base.Nested(
            models.EntityNameWithLanguage.resource_fields)),
        'contexts': fields.base.List(fields.Constant(ctype='Spread')),
        'stedkode': fields.base.String,
        'fakultet': fields.base.Integer,
        'institutt': fields.base.Integer,
        'avdeling': fields.base.Integer,
    }

    swagger_metadata = {}


class OrganizationalUnitResource(Resource):
    """Resource for organizational units."""
    @swagger.operation(
        notes='Get organizational unit information',
        nickname='get',
        responseClass='OrganizationalUnit',
        parameters=[
            {
                'name': 'id',
                'description': 'The entity ID of the organizational unit',
                'required': True,
                'allowMultiple': False,
                'dataType': 'int',
                'paramType': 'path'
            },
        ]
    )
    @auth.require()
    @marshal_with(OrganizationalUnit.resource_fields)
    def get(self, id):
        """Returns organizational unit information based on the \
            OrganizationalUnit model.

        :param int entity_id: The entity ID of the organizational unit

        :rtype: dict
        :return: information about the organizational unit
        """
        ou = find_ou(id)
        data = format_ou(ou)
        return data
