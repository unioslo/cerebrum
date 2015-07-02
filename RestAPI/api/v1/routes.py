from . import api
from authtest import AuthTest
from account import AccountResource
from emailaddress import EmailAddressResource

api.add_resource(AuthTest, '/auth-test')
api.add_resource(AccountResource, '/account/<string:lookup>/<string:identifier>')
api.add_resource(EmailAddressResource, '/email/<string:email_address>')
