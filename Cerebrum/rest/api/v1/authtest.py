from flask.ext.restful import Resource
from Cerebrum.rest.api import auth


class AuthTest(Resource):
    @auth.require()
    def get(self):
        return {
            'user': auth.user,
        }
