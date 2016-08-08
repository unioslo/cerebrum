from flask_restplus import fields as base
from werkzeug.routing import BuildError

from Cerebrum.rest.api import db
from Cerebrum.Utils import Factory

co = Factory.get('Constants')(db.connection)


# FIXME: We should not need the constant type for this to work.
# Something like co.map_const() without fetching everything from the db
# TBD: Maybe this is a bad idea, but it seems convenient.
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


# FIXME: This is horrible and we want entity names in the URIs when applicable.
class UrlFromEntityType(base.Url):
    """Attempts to build a self-referencing URL from the 'id' and 'type'
    fields in a model."""
    def __init__(self, endpoint=None, absolute=False, scheme=None,
                 ctype='EntityType', type_field='type', **kwargs):
        super(UrlFromEntityType, self).__init__(
            endpoint=endpoint, absolute=absolute, scheme=scheme, **kwargs)
        self.type_field = type_field
        self.ctype = ctype

    def output(self, key, obj):
        if not obj:
            return None
        try:
            if not self.endpoint:
                self.endpoint = '.' + Constant(ctype=self.ctype).format(
                    code=obj[self.type_field])
            return super(UrlFromEntityType, self).output(key, obj)
        except BuildError:
            return None


def href(endpoint, description="URL to this resource"):
    """ Create a reference to another API resource. """
    return base.Url(
        endpoint=endpoint,
        absolute=False,
        description=description)
