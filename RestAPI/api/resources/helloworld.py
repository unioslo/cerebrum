from flask import request
from flask.ext.restful import Resource


class HelloWorld(Resource):
    def get(self):
        return {
            'hello': 'world',
            'headers': request.headers.items(),
        }
