from flask import Blueprint
from flask.ext.restful import Api
from flask_restful_swagger import swagger

blueprint = Blueprint('api_v1', __name__)
api = swagger.docs(Api(blueprint), apiVersion='1.0',
                   basePath='http://localhost:5000',
                   resourcePath='/',
                   produces=["application/json", "text/html"],
                   api_spec_url='/spec',
                   description='Cerebrum Rest-API')

from . import routes
