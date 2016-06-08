from flask_restplus import Namespace, Resource, abort

from Cerebrum.rest.api import db, auth, fields, utils
from Cerebrum.rest.api.v1 import group
from Cerebrum.rest.api.v1 import models
from Cerebrum.rest.api.v1 import emailaddress

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.QuarantineHandler import QuarantineHandler

api = Namespace('accounts', description='Account operations')
co = Factory.get('Constants')(db.connection)


def find_account(identifier):
    idtype = 'entity_id' if identifier.isdigit() else 'name'
    try:
        try:
            account = utils.get_account(identifier=identifier,
                                        idtype=idtype,
                                        actype='PosixUser')
        except utils.EntityLookupError:
            account = utils.get_account(identifier=identifier,
                                        idtype=idtype)
    except utils.EntityLookupError as e:
        abort(404, message=str(e))
    return account


AccountAffiliation = api.model('AccountAffiliation', {
    'affiliation': fields.Constant(
        ctype='PersonAffiliation',
        description='Affiliation name'),
    'priority': fields.base.Integer(
        description='Affiliation priority'),
    'ou': fields.base.Nested(
        models.OU,
        description='Organizational unit'),
})

AccountAffiliationList = api.model('AccountAffiliationList', {
    'affiliations': fields.base.List(
        fields.base.Nested(
            AccountAffiliation),
        description='Account affiliations'),
})


Account = api.model('Account', {
    'href': fields.base.Url(
        endpoint='.account',
        absolute=True,
        description='URL to this resource'),
    'name': fields.base.String(
        description='Account name'),
    'id': fields.base.Integer(
        default=None,
        description='Entity ID'),
    'owner': fields.base.Nested(
        models.EntityOwner,
        description='Entity owner'),
    'create_date': fields.DateTime(
        dt_format='iso8601',
        description='Account creation date'),
    'expire_date': fields.DateTime(
        dt_format='iso8601',
        description='Expiration date'),
    'contexts': fields.base.List(
        fields.Constant(ctype='Spread'),
        description='Visible in these contexts'),
    'primary_email': fields.base.String(
        description='Primary email address'),
    'active': fields.base.Boolean(
        description='Is this account active, i.e. not deleted or expired?'),
})


@api.route('/<string:id>', endpoint='account')
class AccountResource(Resource):
    """Resource for a single account."""
    @api.marshal_with(Account)
    @api.doc(params={'id': 'Account name or ID'})
    @api.response(404, 'Not Found')
    @auth.require()
    def get(self, id):
        """Get account information."""
        ac = find_account(id)
        return {
            'name': ac.account_name,
            'id': ac.entity_id,
            'owner': {
                'id': ac.owner_id,
                'type': ac.owner_type,
            },
            'create_date': ac.create_date,
            'expire_date': ac.expire_date,
            'contexts': [row['spread'] for row in ac.get_spread()],
            'primary_email': ac.get_primary_mailaddress(),
            'active': not (ac.is_expired() or ac.is_deleted()),
        }


PosixAccount = api.model('PosixAccount', {
    'href': fields.base.Url(
        endpoint='.posixaccount',
        absolute=True,
        description='URL to this resource'),
    'name': fields.base.String(
        description='Account name'),
    'id': fields.base.Integer(
        default=None,
        description='Entity ID'),
    'posix': fields.base.Boolean(
        description='Is this a POSIX account?'),
    'posix_uid': fields.base.Integer(
        default=None,
        description='POSIX UID'),
    'posix_shell': fields.Constant(
        ctype='PosixShell',
        description='POSIX shell'),
    'default_file_group': fields.base.Nested(
        group.Group,
        allow_null=True,
        description='Default file group')
})


@api.route('/<string:id>/posix', endpoint="posixaccount")
class PosixAccountResource(Resource):
    """Resource for a single POSIX account."""
    @api.marshal_with(PosixAccount)
    @api.doc(params={'id': 'Account name or ID'})
    @auth.require()
    def get(self, id):
        """Get POSIX account information."""
        ac = find_account(id)

        return {
            'name': ac.account_name,
            'id': ac.entity_id,
            'posix': hasattr(ac, 'posix_uid'),
            'posix_uid': getattr(ac, 'posix_uid', None),
            'posix_shell': getattr(ac, 'shell', None),
            'gecos': getattr(ac, 'gecos', None),
            'default_file_group': (
                group.GroupResource.get(
                    group.GroupResource(), getattr(ac, 'gid_id', None)) if
                hasattr(ac, 'gid_id') else None),
        }


AccountQuarantineList = api.model('AccountQuarantineList', {
    'locked': fields.base.Boolean(
        description='Is this account locked?'),
    'quarantines': fields.base.List(
        fields.base.Nested(models.EntityQuarantine),
        description='List of quarantines'),
    })


account_quarantines_filter = api.parser()
account_quarantines_filter.add_argument(
    'context', type=str,
    help='Consider locked status based on context.')


@api.route('/<string:id>/quarantines', endpoint='account-quarantines')
@api.doc(params={'id': 'Account name or ID'})
class AccountQuarantineListResource(Resource):
    """Quarantines for a single account."""
    @api.marshal_with(AccountQuarantineList)
    @api.doc(parser=account_quarantines_filter)
    @auth.require()
    def get(self, id):
        """Get account quarantines."""
        args = account_quarantines_filter.parse_args()

        spreads = None
        if args.context:
            try:
                spreads = [int(co.Spread(args.context))]
            except Errors.NotFoundError:
                abort(404, message=u'Unknown context {!r}'.format(
                    args.context))

        ac = find_account(id)

        qh = QuarantineHandler.check_entity_quarantines(
            db=db.connection,
            entity_id=ac.entity_id,
            spreads=spreads)
        locked = qh.is_locked()

        quarantines = []
        for q in ac.get_entity_quarantine(only_active=True):
            quarantines.append({
                'type': q['quarantine_type'],
                # 'description': q['description'],
                'end': q['end_date'],
                'start': q['start_date'],
                # 'disable_until': q['disable_until'],
            })

        return {
            'locked': locked,
            'quarantines': quarantines
        }


AccountEmailAddress = api.model('AccountEmailAddress', {
    'primary': fields.base.String(
        description='Primary email address for this account'),
    'addresses': fields.base.List(
        fields.base.Nested(emailaddress.EmailAddress),
        description='All addresses targeting this account'),
})


@api.route('/<string:id>/emailaddresses', endpoint='account-emailaddresses')
class AccountEmailAddressResource(Resource):
    """Resource for the email addresses of a single account."""
    @api.marshal_with(AccountEmailAddress)
    @api.doc(params={'id': 'Account name or ID'})
    @auth.require()
    def get(self, id):
        """Get the email addresses for an account."""
        ac = find_account(id)
        addresses = emailaddress.list_email_addresses(
            ac.get_primary_mailaddress())
        return {
            'primary': ac.get_primary_mailaddress(),
            'addresses': addresses,
        }


AccountListItem = api.model('AccountListItem', {
    'href': fields.base.Url(
        endpoint='.account',
        absolute=True,
        description='URL to this resource'),
    'name': fields.base.String(
        description='Account name'),
    'id': fields.base.Integer(
        default=None,
        attribute='account_id',
        description='Account entity ID'),
    'owner': fields.base.Nested(
        models.EntityOwner,
        description='Account owner'),
    'expire_date': fields.DateTime(
        dt_format='iso8601',
        description='Expiration date'),
    'np_type': fields.Constant(
        ctype='Account',
        description='Non-personal account type (null if personal)'),
})


AccountList = api.model('AccountList', {
    'accounts': fields.base.List(
        fields.base.Nested(AccountListItem),
        description='List of accounts'),
})


account_search_filter = api.parser()
account_search_filter.add_argument(
    'name', type=str,
    help='Filter by account name. Accepts * and ? as wildcards.')
account_search_filter.add_argument(
    'context', type=str, dest='spread',
    help='Filter by context. Accepts * and ? as wildcards.')
account_search_filter.add_argument(
    'owner_id', type=int,
    help='Filter by owner entity ID.')
account_search_filter.add_argument(
    'owner_type', type=str,
    help='Filter by owner entity type.')
account_search_filter.add_argument(
    'expire_start', type=str,
    help='Filter by expiration start date.')
account_search_filter.add_argument(
    'expire_stop', type=str,
    help='Filter by expiration end date.')


@api.route('/', endpoint='accounts')
class AccountListResource(Resource):
    """Resource for list of accounts."""
    @api.marshal_with(AccountList)
    @api.doc(parser=account_search_filter)
    @auth.require()
    def get(self):
        """List accounts."""
        args = account_search_filter.parse_args()
        filters = {key: value for (key, value) in args.items()
                   if value is not None}

        if 'owner_type' in filters:
            try:
                owner_type = co.EntityType(filters['owner_type'])
                filters['owner_type'] = int(owner_type)
            except Errors.NotFoundError:
                abort(404,
                      message=u'Unknown entity type for owner_type={}'.format(
                          filters['owner_type']))

        ac = Factory.get('Account')(db.connection)

        accounts = list()
        for row in ac.search(**filters):
            account = dict(row)
            account.update({
                'id': account['name'],
                'owner': {
                    'id': account['owner_id'],
                    'type': account['owner_type'],
                }
            })
            accounts.append(account)
        return {'accounts': accounts}


account_groups_filter = api.parser()
account_groups_filter.add_argument(
    'indirect_memberships', type=bool, dest='indirect_members',
    help='If true, include indirect group memberships.')
account_groups_filter.add_argument(
    'filter_expired', type=bool,
    help='If false, include expired groups.')
account_groups_filter.add_argument(
    'expired_only', type=bool,
    help='If true, only include expired groups.')


@api.route('/<string:id>/groups')
class AccountGroupListResource(Resource):
    """Resource for account group memberships."""
    @api.marshal_with(group.GroupList)
    @api.doc(params={'id': 'Account name or ID'})
    @auth.require()
    def get(self, id):
        """List groups an account is a member of."""
        ac = find_account(id)
        args = account_groups_filter.parse_args()
        filters = {key: value for (key, value) in args.items()
                   if value is not None}
        filters['member_id'] = ac.entity_id

        gr = Factory.get('Group')(db.connection)

        groups = list()
        for row in gr.search(**filters):
            group = dict(row)
            group.update({
                'id': group['name'],
            })
            groups.append(group)
        return {'groups': groups}


@api.route('/<string:id>/contacts')
class AccountContactInfoListResource(Resource):
    """Resource for account contact information."""
    @api.marshal_with(models.EntityContactInfoList)
    @api.doc(params={'id': 'Account name or ID'})
    @auth.require()
    def get(self, id):
        """Lists contact information for an account."""
        ac = find_account(id)
        contacts = ac.get_contact_info()
        return {'contacts': contacts}


@api.route('/<string:id>/affiliations')
class AccountAffiliationListResource(Resource):
    """Resource for account affiliations."""
    @api.marshal_with(AccountAffiliationList)
    @api.doc(params={'id': 'Account name or ID'})
    @auth.require()
    def get(self, id):
        """List affiliations for an account."""
        ac = find_account(id)

        affiliations = list()

        for aff in ac.get_account_types():
            aff = dict(aff)
            aff['ou'] = {'id': aff.pop('ou_id', None), }
            affiliations.append(aff)

        return {'affiliations': affiliations}


AccountHome = api.model('AccountHome', {
    'homedir_id': fields.base.Integer(
        description='Home directory entity ID'),
    'home': fields.base.String(
        description='Home directory path'),
    'context': fields.Constant(
        ctype='Spread',
        attribute='spread',
        description='Context'),
    'status': fields.Constant(
        ctype='AccountHomeStatus',
        description='Home status'),
    'disk_id': fields.base.Integer(
        description='Disk entity ID'),
})


AccountHomeList = api.model('AccountHomeList', {
    'homes': fields.base.List(
        fields.base.Nested(AccountHome),
        description='Home directories'),
})


@api.route('/<string:id>/homes')
class AccountHomeListResource(Resource):
    """Resource for account home directories."""
    @api.marshal_with(AccountHomeList)
    @api.doc(params={'id': 'Account name or ID'})
    @auth.require()
    def get(self, id):
        """List home directories for an account."""
        ac = find_account(id)

        homes = list()

        # Home directories
        for home in ac.get_homes():
            if home['home'] or home['disk_id']:
                home['home'] = ac.resolve_homedir(
                    disk_id=home['disk_id'],
                    home=home['home'])
            homes.append(home)

        return {'homes': homes}
