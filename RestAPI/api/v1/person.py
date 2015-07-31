from flask.ext.restful import Resource, abort, marshal_with
from api import db, auth, fields, utils
from flask_restful_swagger import swagger

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors


@swagger.model
@swagger.nested(
    ou='OU')
class PersonAffiliation(object):
    resource_fields = {
        'affiliation': fields.Constant(ctype='PersonAffiliation'),
        'status': fields.Constant(ctype='PersonAffStatus'),
        'ou': fields.base.Nested(fields.OU.resource_fields),
        'create_date': fields.DateTime(dt_format='iso8601'),
        'last_date': fields.DateTime(dt_format='iso8601'),
        'deleted_date': fields.DateTime(dt_format='iso8601'),
        'source_system': fields.Constant(ctype='AuthoritativeSystem'),
    }

    swagger_metadata = {
        'affiliation': {'description': 'Affiliation type'},
        'status': {'description': 'Affiliation status'},
        'ou': {'description': 'Organizational unit'},
        'create_date': {'description': 'Creation date'},
        'last_date': {'description': 'Last seen in source system'},
        'deleted_date': {'description': 'Deletion date'},
        'source_system': {'description': 'Source system'},
    }


@swagger.model
class PersonName(object):
    resource_fields = {
        'source_system': fields.Constant(ctype='AuthoritativeSystem'),
        'variant': fields.Constant(ctype='PersonName', attribute='name_variant'),
        'name': fields.base.String,
    }

    swagger_metadata = {
        'source_system': {'description': 'Source system'},
        'variant': {'description': 'Name variant'},
        'name': {'description': 'Name'},
    }


@swagger.model
class PersonAccount(object):
    resource_fields = {
        'href': fields.UrlFromEntityType(absolute=True),
        'id': fields.base.Integer(attribute='account_id'),
        'name': fields.base.String,
        'type': fields.Constant(ctype='EntityType'),
        'primary': fields.base.Boolean,
    }


@swagger.model
@swagger.nested(
    affiliations='PersonAffiliation',
    names='PersonName',
    external_ids='EntityExternalId',
    contact='EntityContactInfo',
    accounts='PersonAccount')
class Person(object):
    """Data model for a single person"""
    resource_fields = {
        'href': fields.base.Url('.person', absolute=True),
        'id': fields.base.Integer(default=None),
        'birth_date': fields.DateTime(dt_format='iso8601'),
        'names': fields.base.List(fields.base.Nested(PersonName.resource_fields)),
        'accounts': fields.base.List(fields.base.Nested(PersonAccount.resource_fields)),
        'contexts': fields.base.List(fields.Constant(ctype='Spread')),
        'affiliations': fields.base.List(fields.base.Nested(PersonAffiliation.resource_fields)),
        'contact': fields.base.List(fields.base.Nested(fields.EntityContactInfo.resource_fields)),
        'external_ids': fields.base.List(fields.base.Nested(
            fields.EntityExternalId.resource_fields)),
    }

    swagger_metadata = {
        'id': {'description': 'Person entity ID', },
        'birth_date': {'description': 'Birth date', },
        'names': {'description': 'Names', },
        'contexts': {'description': 'Visible in these contexts', },
        'primary_account': {'description': 'Primary account', },
        'affiliations': {'description': 'Person affiliations', },
        'contact': {'description': 'Contact information', },
        'external_ids': {'description': 'External IDs', },
    }


class PersonResource(Resource):
    """Resource for a single person."""
    @swagger.operation(
        notes='Get person information',
        nickname='get',
        responseClass=Person,
        parameters=[
            {
                'name': 'id',
                'description': 'The entity ID of the person',
                'required': True,
                'allowMultiple': False,
                'dataType': 'int',
                'paramType': 'path'
            },
        ]
    )
    @auth.require()
    @marshal_with(Person.resource_fields)
    def get(self, id):
        """Returns person information based on the model in Person.

        :param int id: The entity ID of the person

        :rtype: dict
        :return: information about the person
        """
        pe = Factory.get('Person')(db.connection)
        try:
            pe.find(id)
        except Errors.NotFoundError:
            abort(404, message=u"No such person with entity_id={}".format(id))

        co = Factory.get('Constants')(db.connection)

        data = {
            'id': pe.entity_id,
            'contexts': [row['spread'] for row in pe.get_spread()],
            'birth_date': pe.birth_date,
            'contact': pe.get_contact_info(),
            'names': pe.get_all_names(),
            'external_ids': pe.get_external_id(),
        }

        # Accounts
        primary_account_id = pe.get_primary_account()
        for row in pe.get_accounts():
            account_name = utils.get_entity_name(row['account_id'])
            data.setdefault('accounts', []).append({
                'account_id': row['account_id'],
                'id': account_name,
                'type': co.entity_account,
                'name': account_name,
                'primary': (row['account_id'] == primary_account_id),
            })

        # Affiliations
        for row in pe.get_affiliations():
            aff = dict(row)
            aff['ou'] = {'id': aff.pop('ou_id', None), }
            data.setdefault('affiliations', []).append(aff)

        return data
