from flask.ext.restful import fields as base
from flask.ext.restful_swagger import swagger
from werkzeug.routing import BuildError
from api import db

from Cerebrum.Utils import Factory

co = Factory.get('Constants')(db.connection)


class Constant(base.String):
    """Gets the string representation of a Cerebrum constant by code."""
    def __init__(self, ctype=None, **kwargs):
        super(Constant, self).__init__(**kwargs)
        self.ctype = getattr(co, ctype)

    def format(self, code):
        return str(self.ctype(code)) if code else None

    def output(self, key, data):
        code = base.get_value(key if self.attribute is None else self.attribute, data)
        return self.format(code)


class DateTime(base.DateTime):
    """Converts an mx.DateTime to a Python datetime object if needed."""
    def format(self, dt, **kwargs):
        value = dt.pydatetime() if hasattr(dt, 'pydatetime') else dt
        return super(DateTime, self).format(value=value, **kwargs)


class UrlFromEntityType(base.Url):
    """Attempts to build a self-referencing URL from the 'id' and 'type' fields in a model."""
    def __init__(self, endpoint=None, absolute=False, scheme=None,
                 ctype='EntityType', type_field='type'):
        super(UrlFromEntityType, self).__init__(
            endpoint=endpoint, absolute=absolute, scheme=scheme)
        self.type_field = type_field
        self.ctype = ctype

    def output(self, key, obj):
        if not obj:
            return None
        try:
            if not self.endpoint:
                self.endpoint = '.' + Constant(ctype=self.ctype).format(code=obj[self.type_field])
            return super(UrlFromEntityType, self).output(key, obj)
        except BuildError:
            return None


# Model for data from entity.get_contact_info()
@swagger.model
class EntityContactInfo(object):
    resource_fields = {
        'value': base.String(attribute='contact_value'),
        'alias': base.String(attribute='contact_alias'),
        'preference': base.Integer(attribute='contact_pref'),
        'type': Constant(ctype='ContactInfo', attribute='contact_type'),
        'entity_id': base.Integer,
        'description': base.String,
        'source_system': Constant(ctype='AuthoritativeSystem'),
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
        'contacts': base.List(base.Nested(EntityContactInfo.resource_fields)),
    }

    swagger_metadata = {
        'contacts': {'description': 'Contact information'},
    }


@swagger.model
class EntityOwner(object):
    """Data model for the owner of an entity."""
    resource_fields = {
        'id': base.Integer(default=None),
        'type': Constant(ctype='EntityType'),
        'href': UrlFromEntityType(absolute=True),
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
        'id': base.String(attribute='external_id'),
        'type': Constant(ctype='EntityExternalId', attribute='id_type'),
        'source_system': Constant(ctype='AuthoritativeSystem'),
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
        'external_ids': base.List(base.Nested(EntityExternalId.resource_fields)),
    }

    swagger_metadata = {
        'external_ids': {'description': 'External IDs'},
    }


# Model for data from entity.search_name_with_language()
@swagger.model
class EntityNameWithLanguage(object):
    """Data model for the name of an entity."""
    resource_fields = {
        'variant': Constant(ctype='EntityNameCode', attribute='name_variant'),
        'language': Constant(ctype='LanguageCode', attribute='name_language'),
        'name': base.String(),
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
        'href': base.Url(endpoint='.ou', absolute=True),
        'id': base.Integer,
    }

    swagger_metadata = {
        'href': {'description': 'OU resource URL'},
        'id': {'description': 'OU entity ID'},
    }
