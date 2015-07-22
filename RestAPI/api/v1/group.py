from flask.ext.restful import Resource, abort, marshal_with, reqparse
from flask.ext.restful_swagger import swagger
from api import db, auth, fields, utils

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory

co = Factory.get('Constants')(db.connection)


def find_group(identifier):
    idtype = 'entity_id' if identifier.isdigit() else 'name'
    try:
        try:
            group = utils.get_group(identifier=identifier, idtype=idtype, grtype='PosixGroup')
        except utils.EntityLookupError:
            group = utils.get_group(identifier=identifier, idtype=idtype)
    except utils.EntityLookupError as e:
        abort(404, message=str(e))
    return group


@swagger.model
class GroupModerator(object):
    """Data model for group moderators."""
    resource_fields = {
        'href': fields.UrlFromEntityType(),
        'id': fields.base.String(attribute='owner_id'),
        'type': fields.Constant(ctype='EntityType'),
        'operation_name': fields.base.String,
    }

    swagger_metadata = {
        'id': {'description': 'Moderator entity ID'},
        'type': {'description': 'Moderator entity type'},
        'operation_name': {'description': 'Authorization name'},
    }


@swagger.model
@swagger.nested(
    moderators='GroupModerator')
class Group(object):
    """Data model for a single group."""
    resource_fields = {
        'href': fields.base.Url('.group', absolute=True),
        'id': fields.base.Integer,
        'name': fields.base.String,
        'description': fields.base.String,
        'systems': fields.base.List(fields.Constant(ctype='Spread')),
        'moderators': fields.base.List(fields.base.Nested(GroupModerator.resource_fields)),
        'posix': fields.base.Boolean,
        'posix_gid': fields.base.Integer,
        'members': fields.base.Url('.groupmembers', absolute=True),
    }

    swagger_metadata = {
        'href': {'description': 'URL to this resource'},
        'id': {'description': 'Group entity ID'},
        'name': {'description': 'Group name'},
        'description': {'description': 'Group description'},
        'systems': {'description': 'Visible to these systems'},
        'moderators': {'description': 'Group moderators'},
        'posix': {'description': 'Is this a POSIX group?'},
        'posix_gid': {'description': 'POSIX GID'},
        'members': {'description': 'URL to the resource containing group members'},
    }


class GroupResource(Resource):
    """Resource for a single group."""
    @swagger.operation(
        notes='Get group information',
        nickname='get',
        responseClass='Group',
        parameters=[
            {
                'name': 'id',
                'description': 'Group name or ID',
                'required': True,
                'allowMultiple': False,
                'dataType': 'string',
                'paramType': 'path'
            },
        ]
    )
    @auth.require()
    @marshal_with(Group.resource_fields)
    def get(self, id):
        """Returns group information for a single group based on the Group model.

        :param str id: The group name or ID
        :return: Information about the group
        """
        gr = find_group(id)

        data = {
            'name': gr.group_name,
            'id': gr.entity_id,
            'create_date': gr.create_date,
            'expire_date': gr.expire_date,
            'creator_id': gr.creator_id,
            'systems': [row['spread'] for row in gr.get_spread()],
            'moderators': utils.get_auth_owners(entity=gr, target_type='group'),
        }

        # POSIX
        is_posix = hasattr(gr, 'posix_uid')
        data['posix'] = is_posix
        if is_posix:
            data['posix_gid'] = getattr(gr, 'posix_gid', None)

        return data


@swagger.model
class GroupListItem(object):
    """Data model for an account in a list."""
    resource_fields = {
        'href': fields.base.Url('.group', absolute=True),
        'name': fields.base.String,
        'id': fields.base.Integer(default=None, attribute='group_id'),
        'description': fields.base.String,
        'creator_id': fields.base.Integer,
        'create_date': fields.DateTime(dt_format='iso8601'),
        'expire_date': fields.DateTime(dt_format='iso8601'),
        'visibility': fields.Constant(ctype='GroupVisibility'),
    }

    swagger_metadata = {
        'href': {'description': 'URL to this resource'},
        'name': {'description': 'Group name'},
        'id': {'description': 'Group entity ID'},
        'description': {'description': 'Group description'},
        'creator_id': {'description': 'Creator entity ID'},
        'create_date': {'description': 'Creation date'},
        'expire_date': {'description': 'Expiration date'},
        'visibility': {'description': 'Group visibility'},
    }


@swagger.model
@swagger.nested(
    groups='GroupListItem')
class GroupList(object):
    """Data model for a list of groups"""
    resource_fields = {
        'groups': fields.base.List(fields.base.Nested(GroupListItem.resource_fields)),
    }

    swagger_metadata = {
        'groups': {'description': 'List of groups'},
    }


class GroupListResource(Resource):
    """Resource for list of groups."""
    @swagger.operation(
        notes='Get a list of groups',
        nickname='get',
        responseClass='GroupList',
        parameters=[
            {
                'name': 'name',
                'description': 'Filter by name. Accepts * and ? as wildcards.',
                'required': False,
                'allowMultiple': False,
                'dataType': 'str',
                'paramType': 'query'
            },
            {
                'name': 'description',
                'description': 'Filter by description. Accepts * and ? as wildcards.',
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
                'name': 'member_id',
                'description': 'Filter by memberships. Only groups that have member_id as a \
                    member will be returned. If member_id is a sequence, the group is returned \
                    if any of the IDs are a member of it.',
                'required': False,
                'allowMultiple': True,
                'dataType': 'int',
                'paramType': 'query'
            },
            {
                'name': 'indirect_members',
                'description': 'If true, alter the behavior of the member_id filter to also \
                    include groups where member_id is an indirect member.',
                'required': False,
                'allowMultiple': False,
                'dataType': 'bool',
                'paramType': 'query'
            },
            {
                'name': 'filter_expired',
                'description': 'If false, include expired groups.',
                'required': False,
                'allowMultiple': False,
                'defaultValue': True,
                'dataType': 'bool',
                'paramType': 'query'
            },
            {
                'name': 'expired_only',
                'description': 'If true, only include expired groups.',
                'required': False,
                'allowMultiple': False,
                'dataType': 'bool',
                'paramType': 'query'
            },
            {
                'name': 'creator_id',
                'description': 'Filter by creator entity ID.',
                'required': False,
                'allowMultiple': False,
                'dataType': 'int',
                'paramType': 'query'
            },
        ],
    )
    @auth.require()
    @marshal_with(GroupList.resource_fields)
    def get(self):
        """Returns a list of groups based on the GroupList model.

        :param str id: the group name or entity ID

        :rtype: list
        :return: a list of groups
        """
        parser = reqparse.RequestParser()
        parser.add_argument('name', type=str)
        parser.add_argument('description', type=str)
        parser.add_argument('system', type=str, dest='spread')
        parser.add_argument('member_id', type=int, action='append')
        parser.add_argument('indirect_members', type=bool)
        parser.add_argument('filter_expired', type=bool)
        parser.add_argument('expired_only', type=bool)
        parser.add_argument('creator_id', type=int)
        args = parser.parse_args()
        filters = {key: value for (key, value) in args.items() if value is not None}

        gr = Factory.get('Group')(db.connection)

        groups = list()
        for row in gr.search(**filters):
            group = dict(row)
            group.update({
                'id': group['name'],
            })
            groups.append(group)
        return {'groups': groups}


@swagger.model
class GroupMember(object):
    """Data model for group members."""
    resource_fields = {
        'href': fields.UrlFromEntityType(absolute=True, type_field='member_type'),
        'id': fields.base.Integer(attribute='member_id'),
        'type': fields.Constant(ctype='EntityType', attribute='member_type'),
        'name': fields.base.String(attribute='member_name'),
    }

    swagger_metadata = {
        'href': {'description': 'URL to this resource'},
        'id': {'description': 'Member entity ID'},
        'type': {'description': 'Member entity type'},
        'name': {'description': 'Member name'},
    }


@swagger.model
@swagger.nested(
    members='GroupMember')
class GroupMemberList(object):
    """Data model for a list of groups"""
    resource_fields = {
        'members': fields.base.List(fields.base.Nested(GroupMember.resource_fields)),
    }

    swagger_metadata = {
        'members': {'description': 'List of group members'},
    }


class GroupMemberListResource(Resource):
    """Resource for list of members of groups."""
    @swagger.operation(
        notes='Get a list of members of a group',
        nickname='get',
        responseClass='GroupMemberList',
        parameters=[
            {
                'name': 'id',
                'description': 'Group name or ID',
                'required': True,
                'allowMultiple': False,
                'dataType': 'string',
                'paramType': 'path'
            },
            {
                'name': 'type',
                'description': 'Filter by entity type.',
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
                'name': 'filter_expired',
                'description': 'If false, include members that are expired.',
                'required': False,
                'allowMultiple': False,
                'defaultValue': True,
                'dataType': 'bool',
                'paramType': 'query'
            },
        ],
    )
    @auth.require()
    @marshal_with(GroupMemberList.resource_fields)
    def get(self, id):
        """Returns a list of groups based on the GroupList model.

        :param str id: the group name or entity ID

        :rtype: list
        :return: a list of groups
        """
        parser = reqparse.RequestParser()
        parser.add_argument('type', type=str, dest='member_type')
        parser.add_argument('system', type=str, dest='member_spread')
        parser.add_argument('filter_expired', type=bool, dest='member_filter_expired')
        args = parser.parse_args()
        filters = {key: value for (key, value) in args.items() if value is not None}

        if 'member_type' in filters:
            try:
                member_type = co.EntityType(filters['member_type'])
                filters['member_type'] = int(member_type)
            except Errors.NotFoundError:
                abort(404, message=u'Unknown entity type for type={}'.format(
                    filters['member_type']))

        if 'member_spread' in filters:
            try:
                member_spread = co.Spread(filters['member_spread'])
                filters['member_spread'] = int(member_spread)
            except Errors.NotFoundError:
                abort(404, message=u'Unknown system for system={}'.format(filters['member_spread']))

        gr = find_group(id)

        filters['group_id'] = gr.entity_id
        filters['include_member_entity_name'] = True

        members = list()
        for row in gr.search_members(**filters):
            member = dict(row)
            member.update({
                'id': row['member_name'],
            })
            members.append(member)
        return {'members': members}
