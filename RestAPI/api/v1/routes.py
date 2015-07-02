from . import api

from api.resources.helloworld import HelloWorld
from api.resources.authtest import AuthTest
from api.resources.account import Account
from api.resources.email import EmailAddressResource

api.add_resource(HelloWorld, '/')
api.add_resource(AuthTest, '/auth-test')
api.add_resource(Account, '/account')
api.add_resource(EmailAddressResource, '/email')