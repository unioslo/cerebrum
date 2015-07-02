from flask.ext.restful.fields import *
from api import db

from Cerebrum.Utils import Factory


class EntityType(Raw):
    def format(self, code):
        co = Factory.get('Constants')(db.connection)
        return str(co.EntityType(code))


class DateTimeString(Raw):
    def format(self, mxdatetime):
        return mxdatetime.pydatetime().isoformat('T')


class CallMethod(Raw):
    def format(self, function):
        return str(function())
