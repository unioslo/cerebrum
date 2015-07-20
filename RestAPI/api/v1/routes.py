from . import api
from authtest import AuthTest
from account import AccountListResource, AccountResource, AccountEmailAddressResource
from person import PersonResource
from emailaddress import EmailAddressResource
from ou import OrganizationalUnitResource

api.add_resource(AuthTest, '/auth-test')

api.add_resource(
    AccountListResource,
    '/accounts',
    endpoint='accounts')

api.add_resource(
    AccountResource,
    '/accounts/<string:id>',
    endpoint='account')

api.add_resource(
    AccountEmailAddressResource,
    '/accounts/<string:id>/emailaddresses',
    endpoint='accountemailaddresses')

api.add_resource(
    PersonResource,
    '/persons/<int:id>',
    endpoint='person')

api.add_resource(
    EmailAddressResource,
    '/emailaddresses/<string:address>',
    endpoint='emailaddress')

api.add_resource(
    OrganizationalUnitResource,
    '/ous/<int:id>',
    endpoint='ou')
