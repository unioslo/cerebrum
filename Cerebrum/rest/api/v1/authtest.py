from flask_restful import Resource
from Cerebrum.rest.api import auth


class AuthTest(Resource):
    @auth.require()
    def get(self):
        return {
            'user': auth.user,
        }
