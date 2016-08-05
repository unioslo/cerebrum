# coding: utf-8
""" Person API. """

from flask import url_for
from flask_restplus import Namespace, Resource, abort

from Cerebrum.Utils import Factory
from Cerebrum import Errors

from Cerebrum.rest.api import db, auth, fields, utils
from Cerebrum.rest.api.v1 import models

api = Namespace('persons', description='Person operations')


def find_person(id):
    pe = Factory.get('Person')(db.connection)
    try:
        pe.find(id)
    except Errors.NotFoundError:
        abort(404, message=u"No such person with entity_id={}".format(id))
    return pe


PersonAffiliation = api.model('PersonAffiliation', {
    'affiliation': fields.Constant(
        ctype='PersonAffiliation',
        description='Affiliation type'),
    'status': fields.Constant(
        ctype='PersonAffStatus',
        description='Affiliation status'),
    'ou': fields.base.Nested(
        models.OU,
        description='Organizational unit'),
    'create_date': fields.DateTime(
        dt_format='iso8601',
        description='Creation date'),
    'last_date': fields.DateTime(
        dt_format='iso8601',
        description='Last seen in source system'),
    'deleted_date': fields.DateTime(
        dt_format='iso8601',
        description='Deletion date'),
    'source_system': fields.Constant(
        ctype='AuthoritativeSystem',
        description='Source system'),
})

PersonName = api.model('PersonName', {
    'source_system': fields.Constant(
        ctype='AuthoritativeSystem',
        description='Source system'),
    'variant': fields.Constant(
        ctype='PersonName',
        attribute='name_variant',
        description='Name variant'),
    'name': fields.base.String(
        description='Name value'),
})

PersonAccount = api.model('PersonAccount', {
    'href': fields.base.String(
        description='URL to this resource'),
    'id': fields.base.String(
        description='Account ID'),
    'primary': fields.base.Boolean(
        description='Is this a primary account?'),
})

Person = api.model('Person', {
    'href': fields.href('.person'),
    'id': fields.base.Integer(
        default=None,
        description='Person entity ID'),
    'birth_date': fields.DateTime(
        dt_format='iso8601',
        description='Birth date'),
    'names': fields.base.List(
        fields.base.Nested(PersonName),
        description='Names'),
    'contexts': fields.base.List(
        fields.Constant(ctype='Spread'),
        description='Visible in these contexts'),
})

PersonAffiliationList = api.model('PersonAffiliationList', {
    'affiliations': fields.base.List(
        fields.base.Nested(PersonAffiliation),
        description='List of person affiliations')
})

PersonAccountList = api.model('PersonAccountList', {
    'accounts': fields.base.List(
        fields.base.Nested(PersonAccount),
        description='List of accounts'),
})


@api.route('/<int:id>', endpoint='person')
class PersonResource(Resource):
    """Resource for a single person."""
    @auth.require()
    @api.marshal_with(Person)
    @api.doc(params={'id': 'Person entity ID'})
    def get(self, id):
        """Get person information"""
        pe = find_person(id)
        return {
            'id': pe.entity_id,
            'contexts': [row['spread'] for row in pe.get_spread()],
            'birth_date': pe.birth_date,
            'names': pe.get_all_names(),
        }


@api.route('/<int:id>/affiliations', endpoint='person-affiliations')
class PersonAffiliationListResource(Resource):
    """Resource for person affiliations."""
    @auth.require()
    @api.marshal_with(PersonAffiliationList)
    @api.doc(params={'id': 'Person entity ID'})
    def get(self, id):
        """List person affiliations."""
        pe = find_person(id)
        affiliations = list()

        for row in pe.get_affiliations():
            aff = dict(row)
            aff['ou'] = {'id': aff.pop('ou_id', None), }
            affiliations.append(aff)

        return {'affiliations': affiliations}


@api.route('/<int:id>/contacts', endpoint='person-contacts')
class PersonContactInfoListResource(Resource):
    """Resource for person contact information."""
    @auth.require()
    @api.marshal_with(models.EntityContactInfoList)
    @api.doc(params={'id': 'Person entity ID'})
    def get(self, id):
        """Get person contact information."""
        pe = find_person(id)
        return {'contacts': pe.get_contact_info()}


@api.route('/<int:id>/external-ids', endpoint='person-externalids')
class PersonExternalIdListResource(Resource):
    """Resource for person external IDs."""
    @auth.require()
    @api.marshal_with(models.EntityExternalIdList)
    @api.doc(params={'id': 'Person entity ID'})
    def get(self, id):
        """Get external IDs of a person."""
        pe = find_person(id)
        return {'external_ids': pe.get_external_id()}


@api.route('/<int:id>/accounts', endpoint='person-accounts')
class PersonAccountListResource(Resource):
    """Resource for person accounts."""
    @auth.require()
    @api.marshal_with(PersonAccountList)
    @api.doc(params={'id': 'Person entity ID'})
    def get(self, id):
        """Get the accounts of a person."""
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
