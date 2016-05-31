from flask.ext.restful_swagger import swagger
from Cerebrum.rest.api import fields


# Model for data from entity.get_contact_info()
@swagger.model
class EntityContactInfo(object):
    resource_fields = {
        'value': fields.base.String(attribute='contact_value'),
        'alias': fields.base.String(attribute='contact_alias'),
        'preference': fields.base.Integer(attribute='contact_pref'),
        'type': fields.Constant(ctype='ContactInfo', attribute='contact_type'),
        'entity_id': fields.base.Integer,
        'description': fields.base.String,
        'source_system': fields.Constant(ctype='AuthoritativeSystem'),
    }

    swagger_metadata = {
        'value': {'description': 'Value'},
        'alias': {'description': 'Alias'},
        'preference': {'description': 'Preference/priority, 1 = highest'},
        'type': {'description': 'Type'},
        'entity_id': {'description': 'Entity ID'},
        'description': {'description': 'Description'},
        'source_system': {'description': 'Source system'},
    }


@swagger.model
@swagger.nested(
    contacts='EntityContactInfo')
class EntityContactInfoList(object):
    resource_fields = {
        'contacts': fields.base.List(fields.base.Nested(
            EntityContactInfo.resource_fields)),
    }

    swagger_metadata = {
        'contacts': {'description': 'Contact information'},
    }


@swagger.model
class EntityOwner(object):
    """Data model for the owner of an entity."""
    resource_fields = {
        'id': fields.base.Integer(default=None),
        'type': fields.Constant(ctype='EntityType'),
        'href': fields.UrlFromEntityType(absolute=True),
    }

    swagger_metadata = {
        'id': {'description': 'Entity ID', },
        'type': {'description': 'Entity type', },
        'href': {'description': 'URL to resource', },
    }


# Model for data from entity.get_external_id()
@swagger.model
class EntityExternalId(object):
    """Data model for the external ID of an entity."""
    resource_fields = {
        'id': fields.base.String(attribute='external_id'),
        'type': fields.Constant(ctype='EntityExternalId', attribute='id_type'),
        'source_system': fields.Constant(ctype='AuthoritativeSystem'),
    }

    swagger_metadata = {
        'id': {'description': 'External ID'},
        'type': {'description': 'ID type'},
        'source_system': {'description': 'Source system'},
    }


@swagger.model
@swagger.nested(
    external_ids='EntityExternalId')
class EntityExternalIdList(object):
    resource_fields = {
        'external_ids': fields.base.List(fields.base.Nested(
            EntityExternalId.resource_fields)),
    }

    swagger_metadata = {
        'external_ids': {'description': 'External IDs'},
    }


# Model for data from entity.get_entity_quarantines()
@swagger.model
class EntityQuarantine(object):
    """Data model for a quarantine."""

    resource_fields = {
        'type': fields.Constant(ctype='Quarantine'),
        # 'description': fields.base.String,
        'start': fields.DateTime(dt_format='iso8601'),
        'end': fields.DateTime(dt_format='iso8601'),
        # 'disable_until': fields.DateTime(dt_format='iso8601'),
    }

    swagger_metadata = {
        'type': {'description': 'Type of quarantine'},
        # 'description': {'description': 'Description of quarantine', },
        'start': {'description': 'Quarantine start date', },
        'end': {'description': 'Quarantine end date', },
        # 'disable_until': {'description': 'Quarantine disabled until', },
    }


# Model for data from entity.search_name_with_language()
@swagger.model
class EntityNameWithLanguage(object):
    """Data model for the name of an entity."""
    resource_fields = {
        'variant': fields.Constant(ctype='EntityNameCode',
                                   attribute='name_variant'),
        'language': fields.Constant(ctype='LanguageCode',
                                    attribute='name_language'),
        'name': fields.base.String(),
    }

    swagger_metadata = {
        'variant': {'description': 'Name variant'},
        'language': {'description': 'Language'},
        'name': {'description': 'Name'},
    }


# Model for referencing OUs by ID
@swagger.model
class OU(object):
    """Data model for an OU reference."""
    resource_fields = {
        'href': fields.base.Url(endpoint='.ou', absolute=True),
        'id': fields.base.Integer,
    }

    swagger_metadata = {
        'href': {'description': 'OU resource URL'},
        'id': {'description': 'OU entity ID'},
    }
