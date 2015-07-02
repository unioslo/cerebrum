from flask.ext.restful import Resource, abort, marshal_with
from api import db, auth, fields
from flask_restful_swagger import swagger

from Cerebrum.Utils import Factory
from Cerebrum import Errors


class NotFound(Exception):
    pass


@swagger.model
class AccountResourceFields(object):
    """Data model for accounts"""

    account_types_fields = {
        'affiliation': fields.Constant(ctype='PersonAffiliation'),
        'priority': fields.base.Integer,
        'ou_id': fields.base.Integer,
    }

    resource_fields = {
        'account_name': fields.base.String,
        'entity_id': fields.base.Integer(default=None),
        'owner_id': fields.base.Integer(default=None),
        'owner_type': fields.Constant(ctype='EntityType'),
        'create_date': fields.MXDateTime(dt_format='iso8601'),
        'expire_date': fields.MXDateTime(dt_format='iso8601'),
        'creator_id': fields.base.Integer(default=None),
        'spreads': fields.base.List(fields.base.String),
        'primary_email': fields.base.String,
        'affiliations': fields.base.List(fields.base.Nested(account_types_fields)),
        'posix': fields.base.Boolean(),
        'posix_uid': fields.base.Integer(default=None),
        'posix_shell': fields.Constant(ctype='PosixShell'),
        'deleted': fields.base.Boolean(),
    }

    swagger_metadata = {
        'account_name': {'description': 'Account name', },
        'entity_id': {'description': 'Entity ID', },
        'owner_id': {'description': 'Owner entity ID', },
        'owner_type': {'description': 'Type of owner', },
        'create_date': {'description': 'Date of account creation', },
        'expire_date': {'description': 'Expiration date', },
        'creator_id': {'description': 'Account creator entity ID', },
        'spreads': {'description': '', },
        'primary_email': {'description': 'Primary email address', },
        'affiliations': {'description': 'Account affiliations', },
        'posix': {'description': 'Is this a POSIX account?', },
        'posix_uid': {'description': 'POSIX UID', },
        'posix_shell': {'description': 'POSIX shell', },
        'deleted': {'description': 'Is this account deleted?', },
    }


class AccountResource(Resource):
    """
    Resource for accounts in Cerebrum.
    """
    def __init__(self):
        super(AccountResource, self).__init__()
        self.ac = Factory.get('Account')(db.connection)
        self.co = Factory.get('Constants')(db.connection)

    def _get_account(self, identifier, idtype=None, actype='Account'):
        if actype == 'Account':
            account = Factory.get('Account')(db.connection)
        elif actype == 'PosixUser':
            account = Factory.get('PosixUser')(db.connection)

        try:
            if idtype == 'name':
                account.find_by_name(identifier, self.co.account_namespace)
            elif idtype == 'entity_id':
                if isinstance(identifier, str) and not identifier.isdigit():
                    raise NotFound(u"entity_id must be a number")
                account.find(identifier)
            elif idtype == 'uid':
                if isinstance(identifier, str) and not identifier.isdigit():
                    raise NotFound(u"uid must be a number")
                if actype != 'PosixUser':
                    account = Factory.get('PosixUser')(db.connection)
                    account.clear()
                account.find_by_uid(id)
            else:
                raise NotFound(u"Invalid identifier type {}".format(idtype))
        except Errors.NotFoundError:
            raise NotFound(u"No such {} with {}={}".format(actype, idtype, identifier))
        return account

    @swagger.operation(
        notes='get account information',
        nickname='get',
        responseClass=AccountResourceFields,
        parameters=[
            {
                'name': 'idtype',
                'description': 'The identifier type to use when looking up an account. \
                                Valid values are: name, entity_id, uid',
                'required': True,
                'allowMultiple': False,
                'dataType': 'string',
                'paramType': 'path'
            },
            {
                'name': 'identifier',
                'description': 'Account name, entity ID or POSIX UID for account, \
                               depending on the chosen identifier type.',
                'required': True,
                'allowMultiple': False,
                'dataType': 'string',
                'paramType': 'path'
            }
        ]
    )
    @auth.require()
    @marshal_with(AccountResourceFields.resource_fields)
    def get(self, idtype, identifier):
        """Returns account information based on the model in AccountResourceFields.

        :param str idtype: identifier type: 'name', 'entity_id' or 'uid'
        :param str identifier: the name, entity_id or uid

        :rtype: dict
        :return: information about the account
        """

        is_posix = False
        try:
            ac = self._get_account(idtype=idtype, identifier=identifier, actype="PosixUser")
            is_posix = True
        except NotFound:
            try:
                ac = self._get_account(idtype=idtype, identifier=identifier)
            except NotFound as e:
                abort(404, message=str(e))

        data = {
            'account_name': ac.account_name,
            'entity_id': ac.entity_id,
            'owner_id': ac.owner_id,
            'owner_type': ac.owner_type,
            'create_date': ac.create_date,
            'expire_date': ac.expire_date,
            'creator_id': ac.creator_id,
            'spreads': [str(self.co.Spread(row['spread'])) for row in ac.get_spread()],
            'primary_email': ac.get_primary_mailaddress(),
            'affiliations': ac.get_account_types(),
            'posix': is_posix,
            'deleted': ac.is_deleted(),
        }

        if is_posix:
            #group = self._get_group(account.gid_id, idtype='id', grtype='PosixGroup')
            data.update({
                'posix_uid': ac.posix_uid,
                #'dfg_posix_gid': group.posix_gid,
                #'dfg_name': group.group_name,
                #'gecos': ac.gecos,
                'posix_shell': ac.shell,
            })

        # missing fields:
        # home dir + status
        # disk quota?
        # quarantines / quarantine status

        return data
