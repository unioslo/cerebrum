from flask.ext.restful import Resource, abort, marshal_with, reqparse
from flask.ext.restful_swagger import swagger
from api import db, auth, fields, utils

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory

from Cerebrum.modules import Email
import emailaddress

import ou

co = Factory.get('Constants')(db.connection)


def find_account(identifier):
    idtype = 'entity_id' if identifier.isdigit() else 'name'
    try:
        try:
            account = utils.get_account(identifier=identifier, idtype=idtype, actype='PosixUser')
        except utils.EntityLookupError:
            account = utils.get_account(identifier=identifier, idtype=idtype)
    except utils.EntityLookupError as e:
        abort(404, message=str(e))
    return account


@swagger.model
@swagger.nested(
    ou='OU')
class AccountAffiliation(object):
    resource_fields = {
        'affiliation': fields.Constant(ctype='PersonAffiliation'),
        'priority': fields.base.Integer,
        'ou': fields.base.Nested(fields.OU.resource_fields),
    }

    swagger_metadata = {
        'affiliation': {'description': 'Affiliation name'},
        'priority': {'description': 'Affiliation priority'},
        'ou': {'description': 'Organizational unit'},
    }


@swagger.model
class AccountHome(object):
    resource_fields = {
        'homedir_id': fields.base.Integer,
        'home': fields.base.String,
        'system': fields.Constant(ctype='Spread', attribute='spread'),
        'status': fields.Constant(ctype='AccountHomeStatus'),
        'disk_id': fields.base.Integer,
    }

    swagger_metadata = {
        'homedir_id': {'description': 'Home directory entity ID'},
        'home': {'description': 'Home directory path'},
        'system': {'description': ''},
        'status': {'description': 'Home status'},
        'disk_id': {'description': 'Disk entity ID'},
    }


@swagger.model
@swagger.nested(
    owner='EntityOwner',
    affiliations='AccountAffiliation',
    homes='AccountHome',
    contact='fields.EntityContactInfo')
class Account(object):
    """Data model for a single account."""

    resource_fields = {
        'href': fields.base.Url('.account', absolute=True),
        'name': fields.base.String,
        'id': fields.base.Integer(default=None),
        'owner': fields.base.Nested(fields.EntityOwner.resource_fields),
        'create_date': fields.DateTime(dt_format='iso8601'),
        'expire_date': fields.DateTime(dt_format='iso8601'),
        'creator_id': fields.base.Integer(default=None),
        'systems': fields.base.List(fields.Constant(ctype='Spread')),
        'primary_email': fields.base.String,
        'affiliations': fields.base.List(fields.base.Nested(AccountAffiliation.resource_fields)),
        'posix': fields.base.Boolean,
        'posix_uid': fields.base.Integer(default=None),
        'posix_shell': fields.Constant(ctype='PosixShell'),
        'deleted': fields.base.Boolean,
        'quarantine_status': fields.base.String,
        'homes': fields.base.List(fields.base.Nested(AccountHome.resource_fields)),
        'contact': fields.base.List(fields.base.Nested(fields.EntityContactInfo.resource_fields)),
    }

    swagger_metadata = {
        'href': {'description': 'URL to this resource'},
        'name': {'description': 'Account name', },
        'id': {'description': 'Entity ID', },
        'owner': {'description': 'Entity owner'},
        'create_date': {'description': 'Date of account creation', },
        'expire_date': {'description': 'Expiration date', },
        'creator_id': {'description': 'Account creator entity ID', },
        'systems': {'description': 'Visible to these systems', },
        'primary_email': {'description': 'Primary email address', },
        'affiliations': {'description': 'Account affiliations', },
        'posix': {'description': 'Is this a POSIX account?', },
        'posix_uid': {'description': 'POSIX UID', },
        'posix_shell': {'description': 'POSIX shell', },
        'deleted': {'description': 'Is this account deleted?', },
        'quarantine_status': {'description': 'Quarantine status', },
        'homes': {'description': 'Home directories'},
        'contact': {'description': 'Contact information'},
    }


class AccountResource(Resource):
    """Resource for a single account."""
    @swagger.operation(
        notes='Get account information',
        nickname='get',
        responseClass='Account',
        parameters=[
            {
                'name': 'id',
                'description': 'Account name or ID',
                'required': True,
                'allowMultiple': False,
                'dataType': 'string',
                'paramType': 'path'
            },
        ]
    )
    @auth.require()
    @marshal_with(Account.resource_fields)
    def get(self, id):
        """Returns account information for a single account based on the Account model.

        :param str name_or_id: The account name or account ID
        :return: Information about the account
        """
        ac = find_account(id)

        data = {
            'name': ac.account_name,
            'id': ac.entity_id,
            'owner': {
                'id': ac.owner_id,
                'type': ac.owner_type,
            },
            'create_date': ac.create_date,
            'expire_date': ac.expire_date,
            'creator_id': ac.creator_id,
            'systems': [row['spread'] for row in ac.get_spread()],
            'primary_email': ac.get_primary_mailaddress(),
            'deleted': ac.is_deleted(),
            'contact': ac.get_contact_info(),
        }

        # Affiliations
        for aff in ac.get_account_types():
            aff = dict(aff)
            aff['ou'] = {'id': aff.pop('ou_id', None), }
            data.setdefault('affiliations', []).append(aff)

        # POSIX
        is_posix = hasattr(ac, 'posix_uid')
        data['posix'] = is_posix
        if is_posix:
            #group = self._get_group(account.gid_id, idtype='id', grtype='PosixGroup')
            data.update({
                'posix_uid': ac.posix_uid,
                #'dfg_posix_gid': group.posix_gid,
                #'dfg_name': group.group_name,
                #'gecos': ac.gecos,
                'posix_shell': ac.shell,
            })

        # Home directories
        for home in ac.get_homes():
            if home['home'] or home['disk_id']:
                home['home'] = ac.resolve_homedir(disk_id=home['disk_id'], home=home['home'])
            data.setdefault('homes', []).append(home)

        # Quarantine status
        quarantined = None
        from mx import DateTime
        now = DateTime.now()
        for q in ac.get_entity_quarantine():
            if q['start_date'] <= now:
                if (q['end_date'] is not None and q['end_date'] < now):
                    quarantined = 'expired'
                elif (q['disable_until'] is not None and q['disable_until'] > now):
                    quarantined = 'disabled'
                else:
                    quarantined = 'active'
                    break
            else:
                quarantined = 'pending'
        if quarantined:
            data['quarantine_status'] = quarantined

        return data


@swagger.model
@swagger.nested(
    addresses='EmailAddress')
class AccountEmailAddress(object):
    resource_fields = {
        'primary': fields.base.String,
        'addresses': fields.base.Nested(emailaddress.EmailAddress.resource_fields),
    }

    swagger_metadata = {
        'primary': {'description': 'Primary email address for this account'},
        'addresses': {'description': 'All addresses targeting this account'},
    }


class AccountEmailAddressResource(Resource):
    """Resource for the email addresses of a single account."""
    @swagger.operation(
        notes='Get the email addresses of an account',
        nickname='get',
        responseClass=AccountEmailAddress,
        parameters=[
            {
                'name': 'id',
                'description': 'Account name or ID',
                'required': True,
                'allowMultiple': False,
                'dataType': 'string',
                'paramType': 'path'
            },
        ]
    )
    @auth.require()
    @marshal_with(AccountEmailAddress.resource_fields)
    def get(self, id):
        """Returns the email addresses for a single account based on the EmailAddress model.

        :param str id: The account name or account ID
        :return: Information about the email addresses
        """
        ac = find_account(id)

        ea = Email.EmailAddress(db.connection)
        et = Email.EmailTarget(db.connection)
        et.find_by_target_entity(ac.entity_id)
        target_addresses = ea.list_target_addresses(et.entity_id)
        addresses = [emailaddress.get_email_address(a['address_id']) for a in target_addresses]
        return {
            'primary': ac.get_primary_mailaddress(),
            'addresses': addresses,
        }


@swagger.model
@swagger.nested(
    owner='EntityOwner')
class AccountListItem(object):
    """Data model for an account in a list."""
    resource_fields = {
        'href': fields.base.Url('.account', absolute=True),
        'name': fields.base.String,
        'id': fields.base.Integer(default=None, attribute='account_id'),
        'owner': fields.base.Nested(fields.EntityOwner.resource_fields),
        'expire_date': fields.DateTime(dt_format='iso8601'),
        'np_type': fields.Constant(ctype='Account'),
    }

    swagger_metadata = {
        'href': {'description': 'Account URI'},
        'name': {'description': 'Account name'},
        'id': {'description': 'Account entity ID'},
        'owner': {'description': 'Account owner'},
        'expire_date': {'description': 'Expiration date'},
        'np_type': {'description': 'Non-personal account type, null if personal'},
    }


@swagger.model
@swagger.nested(
    accounts='AccountListItem')
class AccountList(object):
    """Data model for a list of accounts"""
    resource_fields = {
        'accounts': fields.base.List(fields.base.Nested(AccountListItem.resource_fields)),
    }

    swagger_metadata = {
        'accounts': {'description': 'List of accounts'},
    }


class AccountListResource(Resource):
    """Resource for list of accounts."""
    @swagger.operation(
        notes='Get a list of accounts',
        nickname='get',
        responseClass=AccountList.__name__,
        parameters=[
            {
                'name': 'name',
                'description': 'Filter by account name. Accepts * and ? as wildcards.',
                'required': False,
                'allowMultiple': False,
                'dataType': 'str',
                'paramType': 'query'
            },
            {
                'name': 'system',
                'description': 'Filter by system. Accepts * and ? as wildcards.',
                'required': False,
                'allowMultiple': False,
                'dataType': 'str',
                'paramType': 'query'
            },
            {
                'name': 'owner_id',
                'description': 'Filter by owner entity ID.',
                'required': False,
                'allowMultiple': False,
                'dataType': 'int',
                'paramType': 'query'
            },
            {
                'name': 'owner_type',
                'description': 'Filter by owner entity type.',
                'required': False,
                'allowMultiple': False,
                'dataType': 'str',
                'paramType': 'query'
            },
        ],
    )
    @auth.require()
    @marshal_with(AccountList.resource_fields)
    def get(self):
        """Returns a list of accounts based on the model in AccountListResourceFields.

        :param str name_or_id: the account name or account ID

        :rtype: list
        :return: a list of accounts
        """
        parser = reqparse.RequestParser()
        parser.add_argument('name', type=str)
        parser.add_argument('system', type=str, dest='spread')
        parser.add_argument('owner_id', type=int)
        parser.add_argument('owner_type', type=str)
        parser.add_argument('expire_start', type=str)
        parser.add_argument('expire_stop', type=str)
        args = parser.parse_args()
        filters = {key: value for (key, value) in args.items() if value is not None}

        if 'owner_type' in filters:
            try:
                owner_type = co.EntityType(filters['owner_type'])
                filters['owner_type'] = int(owner_type)
            except Errors.NotFoundError:
                abort(404, message=u'Unknown entity type for owner_type={}'.format(
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
