# coding: utf-8
""" API models. """
from Cerebrum.rest.api import fields

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


# Model for data from entity.get_external_id()
EntityExternalId = api.model('EntityExternalId', {
    'id': fields.base.String(
        attribute='external_id',
        description='External ID'),
    'type': fields.Constant(
        ctype='EntityExternalId',
        attribute='id_type',
        description='ID type'),
    'source_system': fields.Constant(
        ctype='AuthoritativeSystem',
        description='Source system'),
})

EntityExternalIdList = api.model('EntityExternalIdList', {
    'external_ids': fields.base.List(
        fields.base.Nested(EntityExternalId),
        description='External IDs'),
})


# Model for data from entity.get_entity_quarantines()
EntityQuarantine = api.model('EntityQuarantine', {
    'type': fields.Constant(
        ctype='Quarantine',
        description='Type of quarantine'),
    # 'description': fields.base.String(
    #     description='Description of quarantine'),
    'start': fields.DateTime(
        dt_format='iso8601',
        description='Quarantine start date'),
    'end': fields.DateTime(
        dt_format='iso8601',
        description='Quarantine end date'),
    # 'disable_until': fields.DateTime(
    #     dt_format='iso8601',
    #     description='Quarantine disabled until'),
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

# Model for referencing OUs by ID
OU = api.model('OU', {
    'href': fields.href(
        '.ou', description='OU resource URL'),
    'id': fields.base.Integer(
        description='OU entity ID'),
})
