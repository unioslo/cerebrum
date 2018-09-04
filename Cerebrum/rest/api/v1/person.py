#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2018 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
""" Person API. """

from __future__ import unicode_literals

from flask import url_for
from flask_restplus import Namespace, Resource, abort
from six import text_type

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
    'href': fields.href('.account'),
    'id': fields.base.String(
        description='Account ID'),
    'name': fields.base.String(
        description='Account name'),
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
    'created_at': fields.DateTime(
        dt_format='iso8601',
        description='Creation timestamp'),
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


class AddressType(object):
    """ Address type translation. """

    _map = {
        'POST': 'postalAddress',
        'OTHER_POST': 'otherPostalAddress',
        'PRIVPOST': 'privatePostalAddress',
        'STREET': 'visitingAddress',
        'OTHER_STREET': 'otherVisitingAddress'
    }

    _rev_map = dict((v, k) for k, v in _map.iteritems())

    @classmethod
    def serialize(cls, strval):
        return cls._map[strval]

    @classmethod
    def unserialize(cls, input_):
        return db.const.Address(cls._rev_map[input_.lower()])


PersonAddress = api.model('PersonAddress', {
    'source_system': fields.Constant(
        ctype='AuthoritativeSystem',
        description='Source system'),
    'address_type': fields.Constant(
        ctype='Address',
        description='Address type',
        transform=AddressType.serialize
    ),
    'address_text': fields.base.String(
        default=None,
        description='Address text'
    ),
    'p_o_box': fields.base.String(
        default=None,
        description='Postal box'
    ),
    'postal_number': fields.base.String(
        default=None,
        description='Postal number'
    ),
    'city': fields.base.String(
        default=None,
        description='City'
    ),
    'country': fields.base.String(
        default=None,
        description='Country'
    ),

})


@api.route('/<int:id>', endpoint='person')
@api.doc(params={'id': 'Person entity ID'})
class PersonResource(Resource):
    """Resource for a single person."""
    @auth.require()
    @api.marshal_with(Person)
    def get(self, id):
        """Get person information"""
        pe = find_person(id)

        name_keys = [PersonName.get(k).attribute or k for k in PersonName]

        # Filter out appropriate fields from db_row objects
        names = [filter(lambda (k, _): k in name_keys, e.items()) for
                 e in pe.get_all_names()]
        names = [dict(n) for n in names]

        return {
            'id': pe.entity_id,
            'contexts': [row['spread'] for row in pe.get_spread()],
            'birth_date': pe.birth_date,
            'created_at': pe.created_at,
            'names': names
        }


@api.route('/<int:id>/affiliations', endpoint='person-affiliations')
@api.doc(params={'id': 'Person entity ID'})
class PersonAffiliationListResource(Resource):
    """Resource for person affiliations."""

    person_affiliations_filter = api.parser()
    person_affiliations_filter.add_argument(
        'include_deleted', type=utils.str_to_bool, dest='include_deleted',
        help='If true, deleted affiliations are included.')

    @auth.require()
    @api.marshal_with(PersonAffiliationList)
    @api.doc(parser=person_affiliations_filter)
    def get(self, id):
        """List person affiliations."""
        args = self.person_affiliations_filter.parse_args()
        filters = {key: value for (key, value) in args.items()
                   if value is not None}

        pe = find_person(id)
        affiliations = list()

        for row in pe.get_affiliations(**filters):
            aff = dict(row)
            aff['ou'] = {'id': aff.pop('ou_id', None), }
            affiliations.append(aff)

        return {'affiliations': affiliations}


@api.route('/<int:id>/contacts', endpoint='person-contacts')
@api.doc(params={'id': 'Person entity ID'})
class PersonContactInfoListResource(Resource):
    """Resource for person contact information."""
    @auth.require()
    @api.marshal_with(models.EntityContactInfoList)
    def get(self, id):
        """Get person contact information."""
        pe = find_person(id)
        return {'contacts': pe.get_contact_info()}


@api.route('/<int:id>/external-ids', endpoint='person-externalids')
@api.doc(params={'id': 'Person entity ID'})
class PersonExternalIdListResource(Resource):
    """Resource for person external IDs."""
    @auth.require()
    @api.marshal_with(models.EntityExternalId,
                      as_list=True, envelope='external_ids')
    def get(self, id):
        """Get external IDs of a person."""
        pe = find_person(id)
        return pe.get_external_id()


@api.route('/<int:id>/accounts', endpoint='person-accounts')
@api.doc(params={'id': 'Person entity ID'})
class PersonAccountListResource(Resource):
    """Resource for person accounts."""
    @auth.require()
    @api.marshal_with(PersonAccountList)
    def get(self, id):
        """Get the accounts of a person."""
        pe = find_person(id)

        accounts = list()
        primary_account_id = pe.get_primary_account()
        for row in pe.get_accounts():
            account_name = utils.get_entity_name(row['account_id'])
            accounts.append({
                'href': url_for('.account', name=account_name),
                # TODO: Make the 'id' field contain the actual ID!
                'id': account_name,
                # 'id': row['account_id'],
                'name': account_name,
                'primary': (row['account_id'] == primary_account_id),
            })

        return {'accounts': accounts}


@api.route('/<int:id>/consents', endpoint='person-consents')
@api.doc(params={'id': 'Person entity ID'})
class PersonConsentListResource(Resource):
    """Resource for person consents."""
    @auth.require()
    @api.marshal_with(models.EntityConsent, as_list=True, envelope='consents')
    def get(self, id):
        """Get the consents of a person."""
        pe = find_person(id)
        consents = []
        # Hack to represent publication reservation
        if hasattr(pe, 'has_e_reservation') and pe.has_e_reservation():
            consents.append({
                'name': 'publication',
                'description': 'Hide from public catalogs?',
                'type': 'opt-out',
                'set_at': None,
                'expires': None,
            })
        if not hasattr(pe, 'list_consents'):
            return consents
        for c in pe.list_consents(entity_id=pe.entity_id):
            consent = db.const.EntityConsent(c['consent_code'])
            consent_type = db.const.ConsentType(consent.consent_type)
            consents.append({
                'name': text_type(consent),
                'description': consent.description,
                'type': text_type(consent_type),
                'set_at': c.time_set,
                'expires': c.expiry,
            })
        return consents


@api.route('/<int:id>/addresses', endpoint='person-addresses')
@api.doc(params={'id': 'Person entity ID'})
class PersonAddressListResource(Resource):
    """Resource for person addresses."""
    @auth.require()
    @api.marshal_list_with(PersonAddress, envelope='addresses')
    def get(self, id):
        """Get the addresses of a person."""
        pe = find_person(id)
        addrs = map(dict, pe.get_entity_address())
        data = []
        for addr in addrs:
            del addr['entity_id']
            data.append(addr)
        return data
