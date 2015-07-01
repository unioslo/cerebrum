from flask import Blueprint
from flask.ext.restful import Api

blueprint = Blueprint('api_v1', __name__)
api = Api(blueprint)

from . import routes
