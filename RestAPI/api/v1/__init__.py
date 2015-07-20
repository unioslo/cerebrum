from flask import Blueprint
from flask.ext.restful import Api
from flask_restful_swagger import swagger

__version__ = '1'

blueprint = Blueprint('api_v1', __name__)
api = swagger.docs(Api(blueprint),
                   apiVersion=__version__,
                   resourcePath='/',
                   produces=["application/json", "text/html"],
                   api_spec_url='/spec',
                   description='Cerebrum REST API')

from . import routes
