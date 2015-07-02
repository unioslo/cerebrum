from flask.ext.restful import marshal
from flask.ext.restful import fields as base
from api import db

from Cerebrum.Utils import Factory

co = Factory.get('Constants')(db.connection)


class Constant(base.String):
    def __init__(self, ctype=None):
        super(Constant, self).__init__()
        self.ctype = getattr(co, ctype)

    def format(self, code):
        return str(self.ctype(code))


class Spreads(base.Raw):
    def format(self, function):
        return [str(co.Spread(row['spread'])) for row in function()]


class MXDateTime(base.DateTime):
    def format(self, mxdatetime, **kwargs):
        return super(MXDateTime, self).format(value=mxdatetime.pydatetime(), **kwargs)


class SpreadList(base.Raw):
    def format(self, function):
        return marshal(function(), spread_fields)


class Call(base.Raw):
    def format(self, function):
        return str(function())

spread_fields = {
    'spread': base.String,
    'spread_code': base.Integer,
    'description': base.String,
    'entity_type_str': base.String(attribute='entity_type'),
    'entity_type': base.Integer(attribute='entity_type_code'),
}
