from flask_restplus import Namespace, Resource, abort, reqparse

from Cerebrum.rest.api import db, auth, fields, utils

from Cerebrum import Errors
from Cerebrum.Utils import Factory

api = Namespace('groups', description='Group operations')
co = Factory.get('Constants')(db.connection)


def find_group(identifier):
    idtype = 'entity_id' if (isinstance(identifier, (int, long) or
                             identifier.isdigit())) else 'name'
    try:
        try:
            group = utils.get_group(identifier=identifier,
                                    idtype=idtype,
                                    grtype='PosixGroup')
        except utils.EntityLookupError:
            group = utils.get_group(identifier=identifier, idtype=idtype)
    except utils.EntityLookupError as e:
        abort(404, message=str(e))
    return group


GroupModerator = api.model('GroupModerator', {
    'href': fields.UrlFromEntityType(
        description='URL to resource'),
    'id': fields.base.String(
        attribute='owner_id',
        description='Entity ID'),
    'type': fields.Constant(
        ctype='EntityType',
        description='Entity type'),
    'operation_name': fields.base.String(
        description='Authorization name'),
})


Group = api.model('Group', {
    'href': fields.base.Url(
        endpoint='.group',
        absolute=True,
        description='URL to this resource'),
    'id': fields.base.Integer(
        description='Group entity ID'),
    'create_date': fields.DateTime(
        dt_format='iso8601',
        description='Creation date'),
    'name': fields.base.String(
        description='Group name'),
    'description': fields.base.String(
        description='Group description'),
    'contexts': fields.base.List(
        fields.Constant(ctype='Spread'),
        description='Visible in these contexts'),
    'moderators': fields.base.List(
        fields.base.Nested(GroupModerator),
        description='Group moderators'),
    'members': fields.base.Url(
        endpoint='.groupmembers',
        absolute=True,
        description='URL to the resource containing group members'),
})


@api.route('/<string:id>', endpoint='group')
@api.doc(params={'id': 'Group name or ID'})
class GroupResource(Resource):
    """Resource for a single group."""
    # @swagger.operation(
    #     notes='Get group information',
    #     nickname='get',
    #     responseClass='Group',
    #     parameters=[
    #         {
    #             'name': 'id',
    #             'description': 'Group name or ID',
    #             'required': True,
    #             'allowMultiple': False,
    #             'dataType': 'string',
    #             'paramType': 'path'
    #         },
    #     ]
    # )
    @auth.require()
    @api.marshal_with(Group)
    def get(self, id):
        """Returns group information for a single group based on the Group model.

        :param str id: The group name or ID
        :return: Information about the group
        """
        gr = find_group(id)

        return {
            'name': gr.group_name,
            'id': gr.entity_id,
            'create_date': gr.create_date,
            'expire_date': gr.expire_date,
            'contexts': [row['spread'] for row in gr.get_spread()],
            'moderators': utils.get_auth_owners(entity=gr,
                                                target_type='group'),
        }


PosixGroup = api.model('PosixGroup', {
    'href': fields.base.Url(
        endpoint='.posixgroup',
        absolute=True,
        description='URL to this resource'),
    'id': fields.base.Integer(
        description='Group entity ID'),
    'posix': fields.base.Boolean(
        description='Is this a POSIX group?'),
    'posix_gid': fields.base.Integer(
        default=None,
        description='Group POSIX GID'),
})


@api.route('/<string:id>/posix', endpoint='posixgroup')
@api.doc(params={'id': 'Group name or ID'})
class PosixGroupResource(Resource):
    """Resource for the POSIX information of a group."""
    # @swagger.operation(
    #     notes='Get POSIX group information',
    #     nickname='get',
    #     responseClass='PosixGroup',
    #     parameters=[
    #         {'name': 'id',
    #          'description': 'Group name or ID',
    #          'required': True,
    #          'allowMultiple': False,
    #          'dataType': 'string',
    #          'paramType': 'path'}])
    @auth.require()
    @api.marshal_with(PosixGroup)
    def get(self, id):
        """Returns POSIX group information for a single group based on the \
            PosixGroup model."""
        gr = find_group(id)

        return {
            'id': gr.entity_id,
            'posix': hasattr(gr, 'posix_gid'),
            'posix_gid': getattr(gr, 'posix_gid', None)
        }


GroupListItem = api.model('GroupListItem', {
    'href': fields.base.Url(
        endpoint='.group',
        absolute=True,
        description='URL to this resource'),
    'name': fields.base.String(
        description='Group name'),
    'id': fields.base.Integer(
        default=None,
        attribute='group_id',
        description='Group entity ID'),
    'description': fields.base.String(
        description='Group description'),
    'create_date': fields.DateTime(
        dt_format='iso8601',
        description='Creation date'),
    'expire_date': fields.DateTime(
        dt_format='iso8601',
        description='Expiration date'),
})

GroupList = api.model('GroupList', {
    'groups': fields.base.List(
        fields.base.Nested(GroupListItem),
        description='List of groups'),
})


@api.route('/', endpoint='groups')
class GroupListResource(Resource):
    """Resource for list of groups."""
    # @swagger.operation(
    #     notes='Get a list of groups',
    #     nickname='get',
    #     responseClass='GroupList',
    #     parameters=[
    #         {
    #             'name': 'name',
    #             'description': 'Filter by name. Accepts * and ? as wildcards.',
    #             'required': False,
    #             'allowMultiple': False,
    #             'dataType': 'str',
    #             'paramType': 'query'
    #         },
    #         {
    #             'name': 'description',
    #             'description': 'Filter by description. Accepts * and ? as \
    #                 wildcards.',
    #             'required': False,
    #             'allowMultiple': False,
    #             'dataType': 'str',
    #             'paramType': 'query'
    #         },
    #         {
    #             'name': 'context',
    #             'description': 'Filter by context. Accepts * and ? as \
    #                 wildcards.',
    #             'required': False,
    #             'allowMultiple': False,
    #             'dataType': 'str',
    #             'paramType': 'query'
    #         },
    #         {
    #             'name': 'member_id',
    #             'description': 'Filter by memberships. Only groups that have member_id as a \
    #                 member will be returned. If member_id is a sequence, the \
    #                 group is returned if any of the IDs are a member of it.',
    #             'required': False,
    #             'allowMultiple': True,
    #             'dataType': 'int',
    #             'paramType': 'query'
    #         },
    #         {
    #             'name': 'indirect_members',
    #             'description': 'If true, alter the behavior of the member_id filter to also \
    #                 include groups where member_id is an indirect member.',
    #             'required': False,
    #             'allowMultiple': False,
    #             'dataType': 'bool',
    #             'paramType': 'query'
    #         },
    #         {
    #             'name': 'filter_expired',
    #             'description': 'If false, include expired groups.',
    #             'required': False,
    #             'allowMultiple': False,
    #             'defaultValue': True,
    #             'dataType': 'bool',
    #             'paramType': 'query'
    #         },
    #         {
    #             'name': 'expired_only',
    #             'description': 'If true, only include expired groups.',
    #             'required': False,
    #             'allowMultiple': False,
    #             'dataType': 'bool',
    #             'paramType': 'query'
    #         },
    #         {
    #             'name': 'creator_id',
    #             'description': 'Filter by creator entity ID.',
    #             'required': False,
    #             'allowMultiple': False,
    #             'dataType': 'int',
    #             'paramType': 'query'
    #         },
    #     ],
    # )
    @auth.require()
    @api.marshal_with(GroupList)
    def get(self):
        """Returns a list of groups based on the GroupList model.

        :param str id: the group name or entity ID

        :rtype: list
        :return: a list of groups
        """
        parser = reqparse.RequestParser()
        parser.add_argument('name', type=str)
        parser.add_argument('description', type=str)
        parser.add_argument('context', type=str, dest='spread')
        parser.add_argument('member_id', type=int, action='append')
        parser.add_argument('indirect_members', type=bool)
        parser.add_argument('filter_expired', type=bool)
        parser.add_argument('expired_only', type=bool)
        parser.add_argument('creator_id', type=int)
        args = parser.parse_args()
        filters = {key: value for (key, value) in args.items() if
                   value is not None}

        gr = Factory.get('Group')(db.connection)

        groups = list()
        for row in gr.search(**filters):
            group = dict(row)
            group.update({
                'id': group['name'],
            })
            groups.append(group)
        return {'groups': groups}


GroupMember = api.model('GroupMember', {
    'href': fields.UrlFromEntityType(
        absolute=True,
        type_field='member_type',
        description='URL to this resource'),
    'id': fields.base.Integer(
        attribute='member_id',
        description='Member entity ID'),
    'type': fields.Constant(
        ctype='EntityType',
        attribute='member_type',
        description='Member entity type'),
    'name': fields.base.String(
        attribute='member_name',
        description='Member name'),
})

GroupMemberList = api.model('GroupMemberList', {
    'members': fields.base.List(
        fields.base.Nested(GroupMember),
        description='List of group members'),
})


@api.route('/<string:id>/members', endpoint='groupmembers')
@api.doc(params={'id': 'Group name or ID'})
class GroupMemberListResource(Resource):
    """Resource for list of members of groups."""
    # @swagger.operation(
    #     notes='Get a list of members of a group',
    #     nickname='get',
    #     responseClass='GroupMemberList',
    #     parameters=[
    #         {
    #             'name': 'id',
    #             'description': 'Group name or ID',
    #             'required': True,
    #             'allowMultiple': False,
    #             'dataType': 'string',
    #             'paramType': 'path'
    #         },
    #         {
    #             'name': 'type',
    #             'description': 'Filter by entity type.',
    #             'required': False,
    #             'allowMultiple': False,
    #             'dataType': 'str',
    #             'paramType': 'query'
    #         },
    #         {
    #             'name': 'context',
    #             'description': 'Filter by context. Accepts * and ? as \
    #                 wildcards.',
    #             'required': False,
    #             'allowMultiple': False,
    #             'dataType': 'str',
    #             'paramType': 'query'
    #         },
    #         {
    #             'name': 'filter_expired',
    #             'description': 'If false, include members that are expired.',
    #             'required': False,
    #             'allowMultiple': False,
    #             'defaultValue': True,
    #             'dataType': 'bool',
    #             'paramType': 'query'
    #         },
    #     ],
    # )
    @auth.require()
    @api.marshal_with(GroupMemberList)
    def get(self, id):
        """Returns a list of groups based on the GroupList model.

        :param str id: the group name or entity ID

        :rtype: list
        :return: a list of groups
        """
        parser = reqparse.RequestParser()
        parser.add_argument('type', type=str, dest='member_type')
        parser.add_argument('context', type=str, dest='member_spread')
        parser.add_argument('filter_expired',
                            type=bool,
                            dest='member_filter_expired')
        args = parser.parse_args()
        filters = {key: value for (key, value) in args.items() if
                   value is not None}

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
                abort(404, message=u'Unknown context for context={}'.format(
                    filters['member_spread']))

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
