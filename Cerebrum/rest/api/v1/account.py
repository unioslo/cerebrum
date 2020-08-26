# -*- coding: utf-8 -*-
#
# Copyright 2016-2018 University of Oslo, Norway
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

from __future__ import unicode_literals

from flask import make_response
from flask_restplus import Namespace, Resource, abort
from six import text_type

import mx.DateTime

from Cerebrum.rest.api import db, auth, fields, utils, validator
from Cerebrum.rest.api.v1 import group
from Cerebrum.rest.api.v1 import models
from Cerebrum.rest.api.v1 import emailaddress

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils import date
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.modules.gpg.data import GpgData
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
        abort(404, message=e)
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

password_parser = api.parser()
password_parser.add_argument(
    'password',
    type=validator.String(),
    required=True,
    location=['form', 'json'],
    help='Password',
)

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
        owner_name = utils.get_entity_name(
            utils.get_entity(ac.owner_id, idtype='entity_id'))
        return {
            'name': ac.account_name,
            'id': ac.entity_id,
            'owner': {
                'id': ac.owner_id,
                'type': ac.owner_type,
                'name': owner_name,
                'href': utils.href_from_entity_type(entity_type=ac.owner_type,
                                                    entity_id=ac.owner_id,
                                                    entity_name=owner_name),
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


def _in_range(date, start=None, end=None):
    if start and date < start:
        return False
    if end and end < date:
        return False
    return True


def _format_quarantine(q):
    """ Format a quarantine db_row for models.EntityQuarantine. """

    def _tz_aware(dt):
        if dt is None:
            return None
        return date.mx2datetime(dt)

    return {
        'type': q['quarantine_type'],
        'start': _tz_aware(q['start_date']),
        'end': _tz_aware(q['end_date']),
        'disable_until': _tz_aware(q['disable_until']),
        'comment': q['description'] or None,
        'active': _in_range(
            mx.DateTime.now(),
            start=(q['disable_until'] or q['start_date']),
            end=q['end_date']),
    }


@api.route('/<string:name>/quarantines', endpoint='account-quarantines')
@api.doc(params={'name': 'account name'})
class AccountQuarantineListResource(Resource):
    """Quarantines for a single account."""

    account_quarantines_filter = api.parser()
    account_quarantines_filter.add_argument(
        'context',
        type=validator.String(),
        location=['form', 'json'],
        help='Consider locked status based on context.')

    @api.marshal_with(AccountQuarantineList)
    @api.doc(expect=[account_quarantines_filter])
    @auth.require()
    def get(self, name):
        """Get account quarantines."""
        args = self.account_quarantines_filter.parse_args()

        spreads = None
        if args.context:
            try:
                spreads = [int(db.const.Spread(args.context))]
            except Errors.NotFoundError:
                abort(404, message='Unknown context {!r}'.format(
                    args.context))

        ac = find_account(name)

        qh = QuarantineHandler.check_entity_quarantines(
            db=db.connection,
            entity_id=ac.entity_id,
            spreads=spreads)
        locked = qh.is_locked()

        # TODO: Replace with list of hrefs to quarantines resource?
        quarantines = []
        for q in ac.get_entity_quarantine(only_active=True):
            quarantines.append(_format_quarantine(q))

        return {
            'locked': locked,
            'quarantines': quarantines
        }


@api.route('/<string:name>/quarantines/<string:quarantine>',
           endpoint='account-quarantines-items')
@api.doc(params={'name': 'account name',
                 'quarantine': 'quarantine type'},)
class AccountQuarantineItemResource(Resource):
    """Quarantine for a single account."""

    def get_qtype(self, value):
        # TODO: If not str/bytes, constants will try to look up the constant
        # using 'code = value'
        c = db.const.Quarantine(bytes(value))
        try:
            int(c)
        except Errors.NotFoundError:
            # TODO: Or should this be 404 as well?
            #       doesn't make sense to have 404 on this when using PUT
            abort(400, message="quarantine type does not exist")
        return c

    # GET /<account>/quarantines/<quarantine>
    #
    @api.marshal_with(models.EntityQuarantine)
    @api.response(400, 'invalid quarantine type')
    @api.response(404, 'account or quarantine not found')
    @auth.require()
    def get(self, name, quarantine):
        """Get account quarantines."""
        ac = find_account(name)
        qtype = self.get_qtype(quarantine)

        q = ac.get_entity_quarantine(
            qtype,
            only_active=False,
            ignore_disable_until=False,
            filter_disable_until=False)

        if len(q) == 0:
            abort(404, message="quarantine not set")
        elif len(q) == 1:
            q = q[0]
        else:
            raise Exception("more than one quarantine of a given type?")

        return _format_quarantine(q)

    # PUT /<account>/quarantines/<quarantine>
    #
    quarantine_parser = api.parser()
    quarantine_parser.add_argument(
        'start',
        type=lambda v, k, s: date.parse(v),
        required=True,
        nullable=False,
        location=['form', 'json'],
        help='when the quarantine should take effect (ISO8601 datetime)')
    quarantine_parser.add_argument(
        'end',
        type=lambda v, k, s: date.parse(v),
        nullable=True,
        location=['form', 'json'],
        help='if/when the quarantine should end (ISO8601 datetime)')
    quarantine_parser.add_argument(
        'disable_until',
        type=lambda v, k, s: date.parse(v),
        nullable=True,
        location=['form', 'json'],
        help='if/when the quarantine should really start (ISO8601 datetime)')
    quarantine_parser.add_argument(
        'comment',
        nullable=True,
        location=['form', 'json'],
        help='{error_msg}')

    @api.expect(quarantine_parser)
    @api.response(200, 'quarantine updated')
    @api.response(201, 'quarantine added')
    @api.response(400, 'invalid quarantine type')
    @api.response(404, 'account not found')
    @api.marshal_with(models.EntityQuarantine)
    @db.autocommit
    @auth.require()
    def put(self, name, quarantine):
        """ Add quarantine on account.

        Note that all datetime inputs are stripped of time info, and turned
        into dates (in local time). E.g.

        - 2017-01-01T00+08 -> 2016-12-31T17+01 -> 2016-12-31

        """
        ac = find_account(name)
        qtype = self.get_qtype(quarantine)
        args = self.quarantine_parser.parse_args()

        if args['end'] and args['end'] < args['start']:
            raise ValueError("end date before start date")

        is_update = bool(ac.get_entity_quarantine(
            qtype,
            only_active=False,
            ignore_disable_until=False,
            filter_disable_until=False))

        if is_update:
            # TODO: Implement an actual update?
            ac.delete_entity_quarantine(qtype)

        ac.add_entity_quarantine(
            qtype,
            auth.account.entity_id,
            description=args['comment'],
            start=args['start'],
            end=args['end'])

        if args['disable_until']:
            if not _in_range(args['disable_until'],
                             start=args['start'],
                             end=args['end']):
                raise ValueError("invalid disable_until date")
            ac.disable_entity_quarantine(qtype, args['disable_until'])

        return (
            _format_quarantine(
                ac.get_entity_quarantine(
                    qtype,
                    only_active=False,
                    ignore_disable_until=False,
                    filter_disable_until=False)[0]),
            200 if is_update else 201)

    # DELETE /<account>/quarantines/<quarantine>
    #
    @api.response(204, 'quarantine removed')
    @api.response(400, 'invalid quarantine type')
    @api.response(404, 'account or quarantine not found')
    @db.autocommit
    @auth.require()
    def delete(self, name, quarantine):
        """ Remove quarantine from account. """
        ac = find_account(name)
        qtype = self.get_qtype(quarantine)

        if not ac.get_entity_quarantine(
                qtype,
                only_active=False,
                ignore_disable_until=False,
                filter_disable_until=False):
            abort(404, message='quarantine not found')

        ac.delete_entity_quarantine(qtype)
        return None, 204


@api.route('/<string:name>/emailaddresses', endpoint='account-emailaddresses')
@api.doc(params={'name': 'account name'})
class AccountEmailAddressResource(Resource):
    """Resource for the email addresses of a single account."""

    @api.marshal_with(AccountEmailAddress)
    @auth.require()
    def get(self, name):
        """Get the email addresses for an account."""
        ac = find_account(name)
        primary = None
        addresses = []
        try:
            primary = ac.get_primary_mailaddress()
        except Errors.NotFoundError:
            pass
        if primary:
            addresses = emailaddress.list_email_addresses(primary)

        return {
            'primary': primary,
            'addresses': addresses,
        }


@api.route('/', endpoint='accounts')
class AccountListResource(Resource):
    """Resource for list of accounts."""

    account_search_filter = api.parser()
    account_search_filter.add_argument(
        'name',
        type=validator.String(),
        help='Filter by account name. Accepts * and ? as wildcards.')
    account_search_filter.add_argument(
        'context',
        type=validator.String(),
        dest='spread',
        help='Filter by context. Accepts * and ? as wildcards.')
    account_search_filter.add_argument(
        'owner_id',
        type=int,
        help='Filter by owner entity ID.')
    account_search_filter.add_argument(
        'owner_type',
        type=validator.String(),
        help='Filter by owner entity type.')
    account_search_filter.add_argument(
        'expire_start',
        type=validator.String(),
        help='Filter by expiration start date.')
    account_search_filter.add_argument(
        'expire_stop',
        type=validator.String(),
        help='Filter by expiration end date.')

    @api.marshal_with(AccountList)
    @api.doc(expect=[account_search_filter])
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
                      message='Unknown entity type for owner_type={}'.format(
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
        'indirect_memberships',
        type=utils.str_to_bool,
        dest='indirect_members',
        help='If true, include indirect group memberships.')
    account_groups_filter.add_argument(
        'filter_expired',
        type=utils.str_to_bool,
        help='If false, include expired groups.')
    account_groups_filter.add_argument(
        'expired_only',
        type=utils.str_to_bool,
        help='If true, only include expired groups.')

    @api.marshal_with(group.GroupListItem, as_list=True, envelope='groups')
    @api.doc(expect=[account_groups_filter])
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
                'id': group['name'],
                'name': group['name'],
                'description': group['description']
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


@api.route('/<string:name>/password', endpoint='account-password')
@api.doc(params={'name': 'account name'})
class AccountPasswordResource(Resource):
    """Resource for account password change."""

    new_password_parser = api.parser()
    new_password_parser.add_argument(
        'password',
        type=validator.String(),
        required=False,
        location=['form', 'json'],
        help='Password, leave empty to generate one',
    )

    @db.autocommit
    @auth.require()
    @api.expect(new_password_parser)
    @api.response(200, 'Password changed', PasswordChanged)
    @api.response(400, 'Invalid password')
    def post(self, name):
        """Change the password for this account."""
        ac = find_account(name)
        data = self.new_password_parser.parse_args()
        password = data.get('password', None)
        if password is None:
            password = ac.make_passwd(ac.account_name)
        assert isinstance(password, text_type)
        try:
            check_password(password, account=ac, structured=False)
        except PasswordNotGoodEnough as e:
            abort(400, 'Bad password: {}'.format(e))
        ac.set_password(password)
        # Remove "weak password" quarantine
        for q in (db.const.quarantine_autopassord,
                  db.const.quarantine_svakt_passord):
            ac.delete_entity_quarantine(q)
        ac.write_db()
        return {'password': password}


@api.route('/<string:name>/password/verify',
           endpoint='account-password-verify')
@api.doc(params={'name': 'account name'})
class AccountPasswordVerifierResource(Resource):
    """Resource for account password verification."""

    @auth.require()
    @api.expect(password_parser)
    @api.response(200, 'Password verification', PasswordVerification)
    @api.response(400, 'Password missing or contains unsupported characters')
    def post(self, name):
        """Verify the password for this account."""
        ac = find_account(name)
        args = password_parser.parse_args()
        password = args['password']
        assert isinstance(password, text_type)
        verified = bool(ac.verify_auth(password))
        return {'verified': verified}


@api.route('/<string:name>/password/check',
           endpoint='account-password-check')
@api.doc(params={'name': 'account name'})
class AccountPasswordCheckerResource(Resource):
    """Resource for account password checking."""

    @auth.require()
    @api.expect(password_parser)
    @api.response(200, 'Password check result')
    @api.response(400, 'Password missing or contains unsupported characters')
    def post(self, name):
        """Check if a password is valid according to rules."""
        ac = find_account(name)
        args = password_parser.parse_args()
        password = args['password']
        assert isinstance(password, text_type)
        return check_password(password, account=ac, structured=True)


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
        gpg_db = GpgData(db.connection)
        gpg_data = gpg_db.get_messages_for_recipient(entity_id=ac.entity_id,
                                                     tag=tag,
                                                     recipient=key_id,
                                                     latest=True)
        if not gpg_data:
            abort(404, "No GPG messages found")
        message = gpg_data[0]['message']
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
