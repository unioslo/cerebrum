from flask import Blueprint
from flask_restplus import Api

__version__ = '1.0'

blueprint = Blueprint('api_v1', __name__)
api = Api(blueprint,
          version=__version__,
          title='Cerebrum REST API',
          description='Cerebrum is an user administration system.',
          contact='cerebrum-kontakt@usit.uio.no')

from Cerebrum.rest.api.v1.account import api as account_ns
from Cerebrum.rest.api.v1.group import api as group_ns
from Cerebrum.rest.api.v1.emailaddress import api as emailaddress_ns
from Cerebrum.rest.api.v1.context import api as context_ns
from Cerebrum.rest.api.v1.ou import api as ou_ns
from Cerebrum.rest.api.v1.person import api as person_ns

api.add_namespace(account_ns)
api.add_namespace(group_ns)
api.add_namespace(emailaddress_ns)
api.add_namespace(context_ns)
api.add_namespace(ou_ns)
api.add_namespace(person_ns)
