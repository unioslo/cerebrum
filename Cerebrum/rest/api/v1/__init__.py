from flask import Blueprint
from flask_restful import Api
from flask_restful.representations.json import output_json
from flask_restful_swagger import swagger

__version__ = '1'

blueprint = Blueprint('api_v1', __name__)
api = swagger.docs(Api(blueprint),
                   apiVersion=__version__,
                   resourcePath='/',
                   produces=["application/json", "text/html"],
                   api_spec_url='/spec',
                   description='Cerebrum REST API')


@api.representation('application/json; charset=utf-8')
def output_json_with_charset(data, code, headers=None):
    return output_json(data, code, headers)

from . import routes
