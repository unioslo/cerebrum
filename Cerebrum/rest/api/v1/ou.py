from flask_restplus import Namespace, Resource, abort

from Cerebrum.rest.api import db, auth, fields
from Cerebrum.rest.api.v1 import models

from Cerebrum.Utils import Factory
from Cerebrum import Errors

api = Namespace('ous', description='Organizational unit operations')


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


OrganizationalUnit = api.model('OrganizationalUnit', {
    'href': fields.base.Url(
        endpoint='.ou',
        absolute=True,
        description='URL to this resource'),
    'id': fields.base.Integer(
        description='OU entity ID'),
    'contact': fields.base.List(
        fields.base.Nested(models.EntityContactInfo),
        description='Contact information'),
    'names': fields.base.List(
        fields.base.Nested(models.EntityNameWithLanguage),
        description='Names'),
    'contexts': fields.base.List(
        fields.Constant(ctype='Spread'),
        description='Visible in these contexts'),
    'stedkode': fields.base.String(),
    'fakultet': fields.base.Integer(),
    'institutt': fields.base.Integer(),
    'avdeling': fields.base.Integer(),
})


@api.route('/<string:id>', endpoint='ou')
class OrganizationalUnitResource(Resource):
    """Resource for organizational units."""
    @auth.require()
    @api.marshal_with(OrganizationalUnit)
    @api.doc(params={'id': 'OU ID'})
    def get(self, id):
        """Get organizational unit information."""
        ou = find_ou(id)
        return format_ou(ou)
