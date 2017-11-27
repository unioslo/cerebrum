# -*- coding: utf-8 -*-
#
# Copyright 2016-2017 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
""" Account API. """

from flask import make_response, request
from flask_restplus import Namespace, Resource, abort

from Cerebrum.rest.api import db, auth, fields, utils
from Cerebrum.rest.api.v1 import group
from Cerebrum.rest.api.v1 import models
from Cerebrum.rest.api.v1 import emailaddress

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.modules.pwcheck.checker import (check_password,
                                              PasswordNotGoodEnough)

api = Namespace('accounts', description='Account operations')


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
    'href': fields.href('.account'),
    'name': fields.base.String(
        description='Account name'),
    'id': fields.base.Integer(
        default=None,
        description='Entity ID'),
    'owner': fields.base.Nested(
        models.EntityOwner,
        description='Entity owner'),
    'created_at': fields.DateTime(
        dt_format='iso8601',
        description='Account creation timestamp'),
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

PosixAccount = api.model('PosixAccount', {
    'href': fields.href('.posixaccount'),
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

AccountQuarantineList = api.model('AccountQuarantineList', {
    'locked': fields.base.Boolean(
        description='Is this account locked?'),
    'quarantines': fields.base.List(
        fields.base.Nested(models.EntityQuarantine),
        description='List of quarantines'),
    })

AccountEmailAddress = api.model('AccountEmailAddress', {
    'primary': fields.base.String(
        description='Primary email address for this account'),
    'addresses': fields.base.List(
        fields.base.Nested(emailaddress.EmailAddress),
        description='All addresses targeting this account'),
})

AccountListItem = api.model('AccountListItem', {
    'href': fields.href('.account'),
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

PasswordPayload = api.model('PasswordPayload', {
    'password': fields.base.String(
        description='Password',
        required=True),
})

PasswordChangePayload = api.model('PasswordChangePayload', {
    'password': fields.base.String(
        description='Password, leave empty to generate one'),
})

PasswordChanged = api.model('PasswordChanged', {
    'password': fields.base.String(
        description='New password')
})

PasswordVerification = api.model('PasswordVerification', {
    'verified': fields.base.Boolean(
        description='Did the password match?')
})


@api.route('/<string:name>', endpoint='account')
@api.doc(params={'name': 'account name'})
class AccountResource(Resource):
    """Resource for a single account."""

    @api.marshal_with(Account)
    @api.response(404, 'Not Found')
    @auth.require()
    def get(self, name):
        """Get account information."""
        ac = find_account(name)
        try:
            primary_email = ac.get_primary_mailaddress()
        except Errors.NotFoundError:
            primary_email = None
        return {
            'name': ac.account_name,
            'id': ac.entity_id,
            'owner': {
                'id': ac.owner_id,
                'type': ac.owner_type,
            },
            'created_at': ac.created_at,
            'expire_date': ac.expire_date,
            'contexts': [row['spread'] for row in ac.get_spread()],
            'primary_email': primary_email,
            'active': not (ac.is_expired() or ac.is_deleted()),
        }


@api.route('/<string:name>/posix', endpoint="posixaccount")
@api.doc(params={'name': 'account name'})
class PosixAccountResource(Resource):
    """Resource for a single POSIX account."""
    @api.marshal_with(PosixAccount)
    @auth.require()
    def get(self, name):
        """Get POSIX account information."""
        ac = find_account(name)

        return {
            'name': ac.account_name,
            'id': ac.entity_id,
            'posix': hasattr(ac, 'posix_uid'),
            'posix_uid': getattr(ac, 'posix_uid', None),
            'posix_shell': getattr(ac, 'shell', None),
            'gecos': getattr(ac, 'gecos', None),
            'default_file_group': (
                group.GroupResource._get(getattr(ac, 'gid_id'),
                                         idtype='entity_id')
                if hasattr(ac, 'gid_id') else None)
        }


@api.route('/<string:name>/quarantines', endpoint='account-quarantines')
@api.doc(params={'name': 'account name'})
class AccountQuarantineListResource(Resource):
    """Quarantines for a single account."""

    account_quarantines_filter = api.parser()
    account_quarantines_filter.add_argument(
        'context', type=str,
        help='Consider locked status based on context.')

    @api.marshal_with(AccountQuarantineList)
    @api.doc(parser=account_quarantines_filter)
    @auth.require()
    def get(self, name):
        """Get account quarantines."""
        args = self.account_quarantines_filter.parse_args()

        spreads = None
        if args.context:
            try:
                spreads = [int(db.const.Spread(args.context))]
            except Errors.NotFoundError:
                abort(404, message=u'Unknown context {!r}'.format(
                    args.context))

        ac = find_account(name)

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


@api.route('/<string:name>/emailaddresses', endpoint='account-emailaddresses')
@api.doc(params={'name': 'account name'})
class AccountEmailAddressResource(Resource):
    """Resource for the email addresses of a single account."""

    @api.marshal_with(AccountEmailAddress)
    @auth.require()
    def get(self, name):
        """Get the email addresses for an account."""
        ac = find_account(name)
        addresses = emailaddress.list_email_addresses(
            ac.get_primary_mailaddress())
        return {
            'primary': ac.get_primary_mailaddress(),
            'addresses': addresses,
        }


@api.route('/', endpoint='accounts')
class AccountListResource(Resource):
    """Resource for list of accounts."""

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

    @api.marshal_with(AccountList)
    @api.doc(parser=account_search_filter)
    @auth.require()
    def get(self):
        """List accounts."""
        args = self.account_search_filter.parse_args()
        filters = {key: value for (key, value) in args.items()
                   if value is not None}

        if 'owner_type' in filters:
            try:
                owner_type = db.const.EntityType(filters['owner_type'])
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


@api.route('/<string:name>/groups')
@api.doc(params={'name': 'account name'})
class AccountGroupListResource(Resource):
    """Resource for account group memberships."""

    account_groups_filter = api.parser()
    account_groups_filter.add_argument(
        'indirect_memberships', type=utils.str_to_bool,
        dest='indirect_members',
        help='If true, include indirect group memberships.')
    account_groups_filter.add_argument(
        'filter_expired', type=utils.str_to_bool,
        help='If false, include expired groups.')
    account_groups_filter.add_argument(
        'expired_only', type=utils.str_to_bool,
        help='If true, only include expired groups.')

    @api.marshal_with(group.GroupListItem, as_list=True, envelope='groups')
    @api.doc(parser=account_groups_filter)
    @auth.require()
    def get(self, name):
        """List groups an account is a member of."""
        ac = find_account(name)
        args = self.account_groups_filter.parse_args()
        filters = {key: value for (key, value) in args.items()
                   if value is not None}
        filters['member_id'] = ac.entity_id

        gr = Factory.get('Group')(db.connection)

        groups = list()
        for row in gr.search(**filters):
            group = dict(row)
            group.update({
                'id': utils._db_decode(group['name']),
                'name': utils._db_decode(group['name']),
                'description': utils._db_decode(group['description'])
            })
            groups.append(group)
        return groups


@api.route('/<string:name>/contacts')
@api.doc(params={'name': 'account name'})
class AccountContactInfoListResource(Resource):
    """Resource for account contact information."""

    @api.marshal_with(models.EntityContactInfoList)
    @auth.require()
    def get(self, name):
        """Lists contact information for an account."""
        ac = find_account(name)
        contacts = ac.get_contact_info()
        return {'contacts': contacts}


@api.route('/<string:name>/affiliations')
@api.doc(params={'name': 'account name'})
class AccountAffiliationListResource(Resource):
    """Resource for account affiliations."""

    @api.marshal_with(AccountAffiliationList)
    @auth.require()
    def get(self, name):
        """List affiliations for an account."""
        ac = find_account(name)

        affiliations = list()

        for aff in ac.get_account_types():
            aff = dict(aff)
            aff['ou'] = {'id': aff.pop('ou_id', None), }
            affiliations.append(aff)

        return {'affiliations': affiliations}


@api.route('/<string:name>/homes')
@api.doc(params={'name': 'account name'})
class AccountHomeListResource(Resource):
    """Resource for account home directories."""

    @api.marshal_with(AccountHomeList)
    @auth.require()
    def get(self, name):
        """List home directories for an account."""
        ac = find_account(name)

        homes = list()

        # Home directories
        for home in ac.get_homes():
            if home['home'] or home['disk_id']:
                home['home'] = ac.resolve_homedir(
                    disk_id=home['disk_id'],
                    home=home['home'])
            homes.append(home)

        return {'homes': homes}


@api.route('/<string:name>/password')
@api.doc(params={'name': 'account name'})
class AccountPasswordResource(Resource):
    """Resource for account password change."""

    @db.autocommit
    @auth.require()
    @api.expect(PasswordChangePayload)
    @api.response(200, 'Password changed', PasswordChanged)
    @api.response(400, 'Invalid password')
    def post(self, name):
        """Change the password for this account."""
        ac = find_account(name)
        data = request.json
        plaintext = data.get('password', None)
        plaintext_unicode = None  # used for utf-8 conversion
        if plaintext is None:
            plaintext = ac.make_passwd(ac.account_name)
        if isinstance(plaintext, str):
            # plaintext can be either latin1 (ISO-8859-1) or UTF-8 str
            # depending on the publisher and the weather...
            # The following hack ensures that we end up with a latin1 string
            # in order to please set_password.
            # Hopefully Cerebrum will switch to unicode in the near future
            try:
                plaintext_unicode = plaintext.decode('utf-8')
            except:  # probably latin1
                plaintext_unicode = plaintext.decode('iso-8859-1')
            try:
                plaintext = plaintext_unicode.encode('iso-8859-1')
            except UnicodeEncodeError:
                abort(400, 'Bad password: Contains illegal characters')
        elif isinstance(plaintext, unicode):
            # in case it came from ac.make_passwd...
            try:
                plaintext_unicode = plaintext
                plaintext = plaintext.encode('ISO-8859-1')
            except UnicodeEncodeError:
                abort(400, 'Bad password: Contains illegal characters')
        try:
            check_password(plaintext,
                           account=ac,
                           structured=False)
        except PasswordNotGoodEnough as err:
            abort(400, 'Bad password: {}'.format(err))
        ac.set_password(plaintext)
        # Remove "weak password" quarantine
        for q in (db.const.quarantine_autopassord,
                  db.const.quarantine_svakt_passord):
            ac.delete_entity_quarantine(q)
        ac.write_db()
        return {'password': plaintext_unicode.encode('utf-8')}


@api.route('/<string:name>/password/verify')
@api.doc(params={'name': 'account name'})
class AccountPasswordVerifierResource(Resource):
    """Resource for account password verification."""

    @auth.require()
    @api.expect(PasswordPayload)
    @api.response(200, 'Password verification', PasswordVerification)
    @api.response(400, 'Password missing or contains unsupported characters')
    def post(self, name):
        """Verify the password for this account."""
        ac = find_account(name)
        data = request.json
        plaintext = data.get('password', None)
        if plaintext is None:
            abort(400, 'No password specified')
        if isinstance(plaintext, str):
            # plaintext can be either latin1 (ISO-8859-1) or UTF-8 str
            # depending on the publisher and the weather...
            # The following hack ensures that we end up with a latin1 string
            # in order to please set_password.
            # Hopefully Cerebrum will switch to unicode in the near future
            try:
                plaintext = plaintext.decode('utf-8')
            except:  # probably latin1
                plaintext = plaintext.decode('iso-8859-1')
            try:
                # and back to latin1 again...
                plaintext = plaintext.encode('iso-8859-1')
            except UnicodeEncodeError:
                abort(400, 'Bad password: Contains illegal characters')
        elif isinstance(plaintext, unicode):
            try:
                plaintext = plaintext.encode('ISO-8859-1')
            except UnicodeEncodeError:
                abort(400, 'Bad password: Contains illegal characters')
        verified = bool(ac.verify_auth(plaintext))
        return {'verified': verified}


@api.route('/<string:name>/password/check')
@api.doc(params={'name': 'account name'})
class AccountPasswordCheckerResource(Resource):
    """Resource for account password checking."""

    @auth.require()
    @api.expect(PasswordPayload)
    @api.response(200, 'Password check result')
    @api.response(400, 'Password missing or contains unsupported characters')
    def post(self, name):
        """Check if a password is valid according to rules."""
        ac = find_account(name)
        data = request.json
        plaintext = data.get('password', None)
        if plaintext is None:
            abort(400, 'No password specified')
        if isinstance(plaintext, str):
            # plaintext can be either latin1 (ISO-8859-1) or UTF-8 str
            # depending on the publisher and the weather...
            # The following hack ensures that we end up with a latin1 string
            # in order to please set_password.
            # Hopefully Cerebrum will switch to unicode in the near future
            try:
                plaintext = plaintext.decode('utf-8')
            except:  # probably latin1
                plaintext = plaintext.decode('iso-8859-1')
            try:
                plaintext = plaintext.encode('iso-8859-1')
            except UnicodeEncodeError:
                abort(400, 'Bad password: Contains illegal characters')
        elif isinstance(plaintext, unicode):
            try:
                plaintext = plaintext.encode('ISO-8859-1')
            except UnicodeEncodeError:
                abort(400, 'Bad password: Contains illegal characters')
        return check_password(plaintext,
                              account=ac,
                              structured=True)


@api.route('/<string:name>/gpg/<string:tag>/<string:key_id>/latest', doc=False)
@api.doc(params={'name': 'account name',
                 'tag': 'GPG data tag',
                 'key_id': 'Public key fingerprint (40-bit)'})
class AccountGPGResource(Resource):
    """Resource for GPG data for accounts."""

    @auth.require()
    def get(self, name, tag, key_id):
        """Get latest GPG data for an account."""
        ac = find_account(name)
        gpg_data = ac.search_gpg_data(entity_id=ac.entity_id,
                                      tag=tag,
                                      recipient=key_id,
                                      latest=True)
        if not gpg_data:
            abort(404, "No GPG messages found")
        message = gpg_data[0].get('message')
        response = make_response(message)
        response.headers['Content-Type'] = 'text/plain'
        return response


@api.route('/<string:name>/traits', doc=False)
@api.doc(params={'name': 'account name'})
class AccountTraitResource(Resource):
    """Resource for account traits."""

    @auth.require()
    @api.marshal_with(models.EntityTrait, as_list=True, envelope='traits')
    def get(self, name):
        ac = find_account(name)
        traits = ac.get_traits()
        return traits.values()
