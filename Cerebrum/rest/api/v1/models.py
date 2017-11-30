# -*- coding: utf-8 -*-
""" API models. """

from Cerebrum.rest.api import db, fields

from . import api

# Model for data from entity.get_contact_info()
EntityContactInfo = api.model('EntityContactInfo', {
    'value': fields.base.String(
        attribute='contact_value',
        description='Value'),
    'alias': fields.base.String(
        attribute='contact_alias',
        description='Alias'),
    'preference': fields.base.Integer(
        attribute='contact_pref',
        description='Preference/priority, 1 = highest'),
    'type': fields.Constant(
        ctype='ContactInfo',
        attribute='contact_type',
        description='Type'),
    'entity_id': fields.base.Integer(
        description='Entity ID'),
    'description': fields.base.String(
        description='Description'),
    'source_system': fields.Constant(
        ctype='AuthoritativeSystem',
        description='Source system'),
    'last_modified': fields.DateTime(dt_format='iso8601',
                                     description='Last modified timestamp'),
})

EntityContactInfoList = api.model('EntityContactInfoList', {
    'contacts': fields.base.List(
        fields.base.Nested(EntityContactInfo),
        description='Contact information'),
})


EntityOwner = api.model('EntityOwner', {
    'id': fields.base.Integer(
        default=None,
        description='Entity ID'),
    'type': fields.Constant(
        ctype='EntityType',
        description='Entity type'),
    'href': fields.UrlFromEntityType(
        description='URL to resource'),
})


class ExternalIdType(object):
    """ External ID type translation. """

    _map = {
        'NO_BIRTHNO': 'norwegianNationalId',
        'PASSNR': 'passportNumber',
        'NO_SAPNO': 'employeeNumber',
        'SSN': 'socialSecurityNumber',
        'NO_STUDNO': 'studentNumber',
    }

    _rev_map = dict((v, k) for k, v in _map.iteritems())

    @classmethod
    def serialize(cls, strval):
        return cls._map.get(strval, strval)

    @classmethod
    def unserialize(cls, input_):
        return db.const.EntityExternalId(cls._rev_map[input_])

    @classmethod
    def valid_types(cls):
        return cls._rev_map.keys()


# Model for data from entity.get_external_id()
EntityExternalId = api.model('EntityExternalId', {
    'external_id': fields.base.String(
        description='External ID'),
    'id_type': fields.Constant(
        ctype='EntityExternalId',
        transform=ExternalIdType.serialize,
        description='External ID type'),
    'source_system': fields.Constant(
        ctype='AuthoritativeSystem',
        description='Source system'),
})


# Model for data from entity.get_entity_quarantines()
EntityQuarantine = api.model('EntityQuarantine', {
    'type': fields.Constant(
        ctype='Quarantine',
        description='Type of quarantine'),
    'comment': fields.base.String(
        description='Reason of quarantine'),
    'start': fields.DateTime(
        dt_format='iso8601',
        description='Quarantine start date'),
    'end': fields.DateTime(
        dt_format='iso8601',
        description='Quarantine end date'),
    'disable_until': fields.DateTime(
        dt_format='iso8601',
        description='Quarantine disabled until'),
    'active': fields.base.Boolean(
        description='Quarantine currently active'),
})


EntityTrait = api.model('EntityTrait', {
    'trait': fields.Constant(
        ctype='EntityTrait',
        attribute='code',
        description='Trait type'),
    'string': fields.base.String(
        attribute='strval',
        description='Trait string value'),
    'number': fields.base.Integer(
        attribute='numval',
        description='Trait number value'),
    'date': fields.DateTime(
        description='Trait date value'),
})


# Model for data from entity.search_name_with_language()
EntityNameWithLanguage = api.model('EntityNameWithLanguage', {
    'variant': fields.Constant(
        ctype='EntityNameCode',
        attribute='name_variant',
        description='Name variant'),
    'language': fields.Constant(
        ctype='LanguageCode',
        attribute='name_language',
        description='Language'),
    'name': fields.base.String(
        description='Name'),
})


EntityConsent = api.model('EntityConsent', {
    'name': fields.base.String(
        description='Consent name'),
    'description': fields.base.String(
        description='Consent description'),
    'type': fields.base.String(
        description='Consent type'),
    'set_at': fields.DateTime(
        dt_format='iso8601',
        description='Consent set at'),
    'expires': fields.DateTime(
        dt_format='iso8601',
        description='Consent expires at'),
})


# Model for referencing OUs by ID
OU = api.model('OU', {
    'href': fields.href(
        '.ou', description='OU resource URL'),
    'id': fields.base.Integer(
        description='OU entity ID'),
})
