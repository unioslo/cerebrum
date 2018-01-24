# -*- coding: utf-8 -*-
from flask_restplus import fields as base
from werkzeug.routing import BuildError

from Cerebrum.rest.api import db


# FIXME: We should not need the constant type for this to work.
# Something like co.map_const() without fetching everything from the db
# TBD: Maybe this is a bad idea, but it seems convenient.
class Constant(base.String):
    """Gets the string representation of a Cerebrum constant by code."""

    def __init__(self, ctype=None, transform=None, **kwargs):
        """
        :param str ctype:
            The constant type, e.g. 'EntityType'.
        :param callable transform:
            A callable that takes the constant strval, and returns a mapped
            value.
        """
        super(Constant, self).__init__(**kwargs)
        self._ctype = ctype
        self.transform = transform

    @property
    def ctype(self):
        return getattr(db.const, self._ctype)

    def format(self, code):
        strval = str(self.ctype(code)) if code else None
        if strval is not None and callable(self.transform):
            return self.transform(strval)
        return strval

    def output(self, key, data):
        code = base.get_value(key if self.attribute is None
                              else self.attribute, data)
        return self.format(code)


class DateTime(base.DateTime):
    """Converts an mx.DateTime to a Python datetime object if needed."""
    def format(self, dt):
        value = dt.pydatetime() if hasattr(dt, 'pydatetime') else dt
        if value is None:
            return None
        return super(DateTime, self).format(value)


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
