from flask import url_for
from flask.ext.restful import Resource, abort, marshal_with
from flask_restful_swagger import swagger

from Cerebrum.Utils import Factory
from Cerebrum import Errors

from Cerebrum.rest.api import db, auth, fields, utils
from Cerebrum.rest.api.v1 import models


def find_person(id):
    pe = Factory.get('Person')(db.connection)
    try:
        pe.find(id)
    except Errors.NotFoundError:
        abort(404, message=u"No such person with entity_id={}".format(id))
    return pe


@swagger.model
@swagger.nested(
    ou='OU')
class PersonAffiliation(object):
    resource_fields = {
        'affiliation': fields.Constant(ctype='PersonAffiliation'),
        'status': fields.Constant(ctype='PersonAffStatus'),
        'ou': fields.base.Nested(models.OU.resource_fields),
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
        'variant': fields.Constant(ctype='PersonName',
                                   attribute='name_variant'),
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
        'href': fields.base.String,
        'id': fields.base.String,
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
        'names': fields.base.List(
            fields.base.Nested(
                PersonName.resource_fields)),
        'contexts': fields.base.List(fields.Constant(ctype='Spread')),

    }

    swagger_metadata = {
        'id': {'description': 'Person entity ID', },
        'birth_date': {'description': 'Birth date', },
        'names': {'description': 'Names', },
        'contexts': {'description': 'Visible in these contexts', },
        'accounts': {'description': 'Accounts'},
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
        pe = find_person(id)

        data = {
            'id': pe.entity_id,
            'contexts': [row['spread'] for row in pe.get_spread()],
            'birth_date': pe.birth_date,
            'names': pe.get_all_names(),
        }

        return data


@swagger.model
@swagger.nested(
    affiliations='PersonAffiliation')
class PersonAffiliationList(object):
    """Data model for a single person"""
    resource_fields = {
        'affiliations': fields.base.List(
            fields.base.Nested(
                PersonAffiliation.resource_fields))
    }

    swagger_metadata = {
        'affiliations': {'description': 'Person affiliations', },
    }


class PersonAffiliationListResource(Resource):
    """Resource for person affiliations."""
    @swagger.operation(
        notes='Get person affiliations',
        nickname='get',
        responseClass=PersonAffiliationList,
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
    @marshal_with(PersonAffiliationList.resource_fields)
    def get(self, id):
        """Returns person affiliations.

        :param int id: The entity ID of the person

        :rtype: dict
        :return: person affiliations
        """
        pe = find_person(id)
        affiliations = list()

        for row in pe.get_affiliations():
            aff = dict(row)
            aff['ou'] = {'id': aff.pop('ou_id', None), }
            affiliations.append(aff)

        return {'affiliations': affiliations}


class PersonContactInfoListResource(Resource):
    """Resource for person contact information."""
    @swagger.operation(
        notes='Get person contact information',
        nickname='get',
        responseClass='EntityContactInfoList',
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
    @marshal_with(models.EntityContactInfoList.resource_fields)
    def get(self, id):
        """Returns person contact information.

        :param int id: The entity ID of the person

        :rtype: dict
        :return: contact information
        """
        pe = find_person(id)
        contacts = pe.get_contact_info()
        return {'contacts': contacts}


class PersonExternalIdListResource(Resource):
    """Resource for person external IDs."""
    @swagger.operation(
        notes='Get the external IDs of a person',
        nickname='get',
        responseClass='EntityContactInfoList',
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
    @marshal_with(models.EntityExternalIdList.resource_fields)
    def get(self, id):
        """Returns the external IDs of a person

        :param int id: The entity ID of the person

        :rtype: dict
        :return: external ids
        """
        pe = find_person(id)
        external_ids = pe.get_external_id(),
        return {'external_ids': external_ids}


@swagger.model
@swagger.nested(
    accounts='PersonAccount')
class PersonAccountList(object):
    resource_fields = {
        'accounts': fields.base.List(fields.base.Nested(
            PersonAccount.resource_fields)),
    }

    swagger_metadata = {
        'accounts': {'description': 'Accounts'},
    }


class PersonAccountListResource(Resource):
    """Resource for person accounts."""
    @swagger.operation(
        notes='Get the accounts of a person',
        nickname='get',
        responseClass='PersonAccountList',
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
    @marshal_with(PersonAccountList.resource_fields)
    def get(self, id):
        """Returns the accounts of a person.

        :param int id: The entity ID of the person

        :rtype: dict
        :return: accounts
        """
        pe = find_person(id)

        accounts = list()
        primary_account_id = pe.get_primary_account()
        for row in pe.get_accounts():
            account_name = utils.get_entity_name(row['account_id'])
            accounts.append({
                'href': url_for('.account', id=account_name, _external=True),
                'id': account_name,
                'primary': (row['account_id'] == primary_account_id),
            })

        return {'accounts': accounts}
