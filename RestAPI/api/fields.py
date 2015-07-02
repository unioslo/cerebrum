from flask.ext.restful import marshal
from flask.ext.restful import fields as base
from api import db

from Cerebrum.Utils import Factory

co = Factory.get('Constants')(db.connection)


class EntityType(base.Raw):
    def format(self, code):
        return str(co.EntityType(code))


class SpreadGet(base.Raw):
    def format(self, function):
        return [str(co.Spread(row['spread'])) for row in function()]


class SpreadList(base.Raw):
    def format(self, function):
        return marshal(function(), spread_fields)


class DateTimeString(base.Raw):
    def format(self, mxdatetime):
        return mxdatetime.pydatetime().isoformat('T')


class Call(base.Raw):
    def format(self, function):
        return str(function())


account_fields = {
    'account_name': base.String,
    'entity_id': base.Integer(default=None),
    'owner_id': base.Integer(default=None),
    'owner_type': EntityType,
    'create_date': DateTimeString,
    'expire_date': DateTimeString,
    'creator_id': base.Integer(default=None),
    'spreads': SpreadGet(attribute='get_spread'),
    'primary_email': Call(attribute='get_primary_mailaddress'),
}

spread_fields = {
    'spread': base.String,
    'spread_code': base.Integer,
    'description': base.String,
    'entity_type_str': base.String(attribute='entity_type'),
    'entity_type': base.Integer(attribute='entity_type_code'),
}
