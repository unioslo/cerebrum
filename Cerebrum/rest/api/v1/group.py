#!/usr/bin/env python
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
""" RESTful Cerebrum group API. """

from __future__ import unicode_literals

from flask_restplus import Namespace, Resource, abort, reqparse
from flask_restplus import fields as base_fields
from werkzeug.exceptions import NotFound
from six import text_type

from Cerebrum.rest.api import db, auth, utils
from Cerebrum.rest.api import fields as crb_fields
from Cerebrum.rest.api import validator
from Cerebrum import Errors
from Cerebrum.Utils import Factory

api = Namespace('groups', description='Group operations')


def find_group(identifier, idtype='name'):
    if idtype == 'name' and isinstance(identifier, unicode):
        identifier = identifier
    try:
        try:
            group = utils.get_group(identifier=identifier,
                                    idtype=idtype,
                                    grtype='PosixGroup')
        except utils.EntityLookupError:
            group = utils.get_group(identifier=identifier, idtype=idtype)
    except utils.EntityLookupError as e:
        raise NotFound(text_type(e))
    return group


def find_entity(entity_id):
    try:
        entity = utils.get_entity(identifier=entity_id, idtype='entity_id')
    except utils.EntityLookupError as e:
        raise NotFound(text_type(e))
    return entity


class GroupVisibility(object):
    """ Group visibility translation. """

    _map = {
        'A': 'all',
        'I': 'internal',
        'N': 'none',
    }

    _rev_map = dict((v, k) for k, v in _map.iteritems())

    @classmethod
    def serialize(cls, strval):
        return cls._map[strval]

    @classmethod
    def unserialize(cls, input_):
        return db.const.GroupVisibility(cls._rev_map[input_.lower()])


class GroupAuthRoles(object):
    """ Group auth roles translation. """

    # ugh, opsets are ugly
    # to prevent clients from granting superuser rights, we need to
    # limit the valid opsets to a hard-coded list of names here.
    _map = {
        # 'Group-admin': 'admin',
        'Group-owner': 'owner',
    }

    _rev_map = dict((v, k) for k, v in _map.iteritems())

    @classmethod
    def serialize(cls, strval):
        return cls._map[strval]

    @classmethod
    def unserialize(cls, input_):
        return cls._rev_map[input_.lower()]

    @classmethod
    def valid_roles(cls):
        return cls._rev_map.keys()


_group_fields = {
    'id': base_fields.Integer(description='group id'),
    'name': base_fields.String(description='group name'),
    'visibility': crb_fields.Constant(ctype='GroupVisibility',
                                      transform=GroupVisibility.serialize,
                                      description='group visibility'),
    'description': base_fields.String(description='group description'),
    'created_at': crb_fields.DateTime(dt_format='iso8601',
                                      description='creation timestamp'),
    'expire_date': crb_fields.DateTime(dt_format='iso8601',
                                       description='expire date'),
}


Group = api.model('Group', {
    'href': crb_fields.href('.group'),
    'id': _group_fields['id'],
    'name': _group_fields['name'],

    'visibility': _group_fields['visibility'],
    'description': _group_fields['description'],
    'created_at': _group_fields['created_at'],
    'expire_date': _group_fields['expire_date'],

    'contexts': base_fields.List(
        crb_fields.Constant(ctype='Spread'),
        description='Visible in these contexts'),
    'moderators': crb_fields.href(
        '.group-moderators',
        description='URL to the resource containing group moderators'),
    'members': crb_fields.href(
        '.group-members-list',
        description='URL to the resource containing group members'),
})


PosixGroup = api.model('PosixGroup', {
    'href': crb_fields.href('.posixgroup'),
    'id': _group_fields['id'],
    'posix': base_fields.Boolean(
        description='Is this a POSIX group?'),
    'posix_gid': base_fields.Integer(
        default=None,
        description='Group POSIX GID'),
})


GroupListItem = api.model('GroupListItem', {
    'href': crb_fields.href('.group'),
    'id': base_fields.Integer(
        default=None,
        attribute='group_id',
        description='group id'),
    'name': _group_fields['name'],

    'visibility': _group_fields['visibility'],
    'description': _group_fields['description'],
    'created_at': _group_fields['created_at'],
    'expire_date': _group_fields['expire_date'],
})


GroupMember = api.model('GroupMember', {
    'href': crb_fields.UrlFromEntityType(
        type_field='member_type',
        description='path to member resource'),
    'id': base_fields.Integer(
        attribute='member_id',
        description='member id'),
    'type': crb_fields.Constant(
        ctype='EntityType',
        attribute='member_type',
        description='member type'),
    'name': base_fields.String(
        attribute='member_name',
        description='member name'),
})


GroupModerator = api.model('GroupModerator', {
    'href': crb_fields.UrlFromEntityType(
        description='url to moderator resource'),
    'id': base_fields.String(
        description='moderator id'),
    'type': crb_fields.Constant(
        ctype='EntityType',
        description='moderator type'),
    'name': base_fields.String(
        description='moderator name'),
    'roles': base_fields.List(
        base_fields.String,
        description='moderator roles')
})


@api.route('/<string:name>', endpoint='group')
@api.doc(params={'name': 'group name'})
class GroupResource(Resource):
    """ Resource for a single group. """

    @staticmethod
    def group_info(group):
        return {
            'name': group.group_name,
            'id': group.entity_id,
            'created_at': group.created_at,
            'expire_date': group.expire_date,
            'visibility': group.visibility,
            'description': group.description,
            'contexts': [row['spread'] for row in group.get_spread()],
        }

    @staticmethod
    def visibility_type(vis):
        lut = {
            'all': db.const.GroupVisibility('A'),
            'internal': db.const.GroupVisibility('I'),
            'none': db.const.GroupVisibility('N')
        }
        return lut[vis.lower()]

    # Either this or import undecorated other places
    @staticmethod
    def _get(name, idtype='name'):
        """ Undecorated get(). """
        group = find_group(name, idtype)
        return GroupResource.group_info(group)

    # GET /<group>
    #
    @auth.require()
    @api.response(200, 'Group found', Group)
    @api.response(404, 'Group not found')
    @api.marshal_with(Group)
    def get(self, name):
        """ Get group information. """
        return self._get(name)

    # PUT /<group>
    #
    new_group_parser = reqparse.RequestParser()
    new_group_parser.add_argument(
        'visibility',
        choices=GroupVisibility._rev_map.keys(),
        required=True,
        location='form',
        case_sensitive=False,
        nullable=False,
        help='{error_msg}',
    )
    new_group_parser.add_argument(
        'description',
        type=validator.String(min_len=0, max_len=512),
        location='form',
        nullable=True,
        help='{error_msg}',
    )

    @db.autocommit
    @auth.require()
    @api.expect(new_group_parser)
    @api.response(200, 'Group updated', Group)
    @api.response(201, 'Group created', Group)
    @api.response(400, 'Illegal group name')
    @api.marshal_with(Group)
    def put(self, name):
        """ Create or update group. """
        args = self.new_group_parser.parse_args()
        args['visibility'] = GroupVisibility.unserialize(args['visibility'])
        result_code = 200
        try:
            # find and update all attributes
            group = utils.get_group(name, 'name', 'Group')
            changes = False
            if group.visibility != args['visibility']:
                group.visibility = args['visibility']
                changes = True
            if group.description != args['description']:
                group.description = args['description']
                changes = True
            if changes:
                group.write_db()
        except utils.EntityLookupError:
            # create group
            group = Factory.get('Group')(db.connection)
            bad_name = group.illegal_name(name)
            if bad_name:
                abort(400, message="Illegal group name: {!s}".format(bad_name))
            group.new(auth.account.entity_id,
                      args['visibility'],
                      name,
                      args['description'])
            result_code = 201
        return self.group_info(group), result_code

    # TODO: Do we want PATCH?
    #
    #   # PATCH /<group>
    #   #
    #   update_group_parser = new_group_parser.copy()
    #
    #   @db.autocommit
    #   @auth.require()
    #   @api.expect(update_group_parser)
    #   @api.response(200, 'group updated', Group)
    #   @api.response(404, 'group not found')
    #   @api.marshal_with(Group)
    #   def patch(self, name):
    #       """ Alter group attributes. """
    #       args = self.update_group_parser.parse_args()
    #       group = find_group(name)
    #
    #       changes = False
    #       if group.description != args['description']:
    #           group.description = args['description']
    #           changes = True
    #       if group.visibility != args['visibility']:
    #           group.visibility = args['visibility']
    #           changes = True
    #       if changes:
    #           group.write_db()
    #
    #       return self.group_info(group)

    # DELETE /<group>
    #
    @db.autocommit
    @auth.require()
    @api.response(204, 'group deleted')
    @api.response(404, 'group not found')
    def delete(self, name):
        """ Delete group. """
        # TODO: Find out if any user has group as dfg?
        #       If so, 409 CONFLICT?
        group = find_group(name)
        group.delete()
        return '', 204


@api.route('/<string:name>/moderators/', endpoint='group-moderators')
@api.doc(params={'name': 'group name', })
class GroupModeratorListResource(Resource):
    """ Moderator resource for a single group. """

    # GET /<group>/moderators
    #
    @auth.require()
    @api.response(200, "group found")
    @api.response(404, "group not found")
    @api.marshal_with(GroupModerator, as_list=True, envelope='moderators')
    def get(self, name):
        """ Get moderators for this group. """
        group = find_group(name)
        return utils.get_auth_roles(group, 'group',
                                    role_map=GroupAuthRoles._map)


@api.route('/<string:name>/moderators/<string:role>/<int:moderator_id>',
           endpoint='group-moderator')
@api.doc(params={
    'name': 'group name',
    'role': 'role to modify ({!s})'.format(
        ','.join(GroupAuthRoles.valid_roles())),
    'moderator_id': 'id of the moderator'})
class GroupModeratorResource(Resource):
    """ Alter group moderator. """

    def get_opset(self, role):
        try:
            return utils.get_opset(GroupAuthRoles.unserialize(role))
        except (Errors.NotFoundError, KeyError):
            pass
        abort(400, 'invalid role', roles=GroupAuthRoles.valid_roles())

    @db.autocommit
    @auth.require()
    @api.response(204, "moderator added")
    @api.response(400, 'invalid role')
    @api.response(404, 'group or moderator not found')
    def put(self, name, role, moderator_id):
        """ Add a group moderator. """
        mod = find_entity(moderator_id)
        opset = self.get_opset(role)
        group = find_group(name)
        utils.grant_auth(mod, opset, group)

    @db.autocommit
    @auth.require()
    @api.response(204, "moderator removed")
    @api.response(400, 'invalid opset')
    @api.response(404, 'group or moderator not found')
    def delete(self, name, role, moderator_id):
        """ Remove a group moderator. """
        mod = find_entity(moderator_id)
        opset = self.get_opset(role)
        group = find_group(name)
        utils.revoke_auth(mod, opset, group)


@api.route('/<string:name>/contexts/<string:context>',
           endpoint='group-contexts')
@api.doc(params={'name': 'group name', 'context': 'group context'})
class GroupContextResource(Resource):
    """ Context resource for a single group. """

    def get_spread(self, value):
        # TODO: If not str/bytes, constants will try to look up the constant
        # using 'code = value'
        c = db.const.Spread(bytes(value))
        try:
            int(c)
        except Errors.NotFoundError:
            abort(400, message="context does not exist")
        if c.entity_type != db.const.entity_group:
            abort(400, message="context does not apply to group")
        return c

    # GET /<group>/contexts/<context>
    #
    @auth.require()
    @api.response(204, 'context found on group')
    @api.response(400, 'invalid context')
    @api.response(404, 'group or context not found')
    def get(self, name, context):
        """ Check if group has context. """
        gr = find_group(name)
        spread = self.get_spread(context)
        if not gr.has_spread(spread):
            abort(404, "No such context on group")

    # PUT /<group>/contexts/<context>
    #
    @db.autocommit
    @auth.require()
    @api.response(204, 'context added')
    @api.response(400, 'invalid context')
    @api.response(404, 'group not found')
    def put(self, name, context):
        """ Add context on group. """
        gr = find_group(name)
        spread = self.get_spread(context)
        if not gr.has_spread(spread):
            gr.add_spread(spread)

    # DELETE /<group>/contexts/<context>
    #
    @db.autocommit
    @auth.require()
    @api.response(204, 'context removed')
    @api.response(400, 'invalid context')
    @api.response(404, 'group not found')
    def delete(self, name, context):
        """ Remove context from group. """
        gr = find_group(name)
        spread = self.get_spread(context)
        if gr.has_spread(spread):
            gr.delete_spread(spread)


@api.route('/<string:name>/members/', endpoint='group-members-list')
class GroupMemberListResource(Resource):
    """Resource for list of members of groups."""

    # GET /<group>/members/
    #
    group_member_filter = api.parser()
    group_member_filter.add_argument(
        'type',
        type=text_type,
        dest='member_type',
        help='Filter by entity type.')
    group_member_filter.add_argument(
        'context',
        type=text_type,
        dest='member_spread',
        help='Filter by context. Accepts * and ? as wildcards.')
    group_member_filter.add_argument(
        'filter_expired',
        type=bool,
        dest='member_filter_expired',
        help='If false, include members that are expired.')

    @auth.require()
    @api.marshal_with(GroupMember, as_list=True, envelope='members')
    @api.doc(parser=group_member_filter)
    @api.doc(params={'name': 'group name'})
    def get(self, name):
        """List members of a group."""
        args = self.group_member_filter.parse_args()
        filters = {key: value for (key, value) in args.items() if
                   value is not None}

        if 'member_type' in filters:
            try:
                member_type = db.const.EntityType(filters['member_type'])
                filters['member_type'] = int(member_type)
            except Errors.NotFoundError:
                abort(404, message='Unknown entity type for type={}'.format(
                    filters['member_type']))

        if 'member_spread' in filters:
            try:
                member_spread = db.const.Spread(filters['member_spread'])
                filters['member_spread'] = int(member_spread)
            except Errors.NotFoundError:
                abort(404, message='Unknown context for context={}'.format(
                    filters['member_spread']))

        gr = find_group(name)

        filters['group_id'] = gr.entity_id
        filters['include_member_entity_name'] = True

        members = list()
        for row in gr.search_members(**filters):
            member = dict(row)
            member.update({
                'id': row['member_name'],
            })
            members.append(member)
        return members


@api.route('/<string:name>/members/<int:member_id>',
           endpoint='group-members')
@api.doc(params={'name': 'group name', 'member_id': 'member id'})
class GroupMemberResource(Resource):
    """ Context resource for a single group. """

    # GET /<group>/members/<member>
    #
    @auth.require()
    @api.response(200, 'member found in group', GroupMember)
    @api.response(404, 'group or member not found')
    @api.marshal_with(GroupMember)
    def get(self, name, member_id):
        """ Check if member exists in group. """
        group = find_group(name)
        member = find_entity(member_id)
        if not group.has_member(member.entity_id):
            abort(404, "No such member in group")
        return {
            'member_type': member.entity_type,
            # id for the href builder, won't be shown in output
            'id': utils.get_entity_name(member) or member.entity_id,
            'member_id': member.entity_id,
            'member_name': utils.get_entity_name(member),
        }

    # PUT /<group>/members/<member>
    #
    @db.autocommit
    @auth.require()
    @api.response(200, 'member added', GroupMember)
    @api.response(404, 'group or member not found')
    @api.marshal_with(GroupMember)
    def put(self, name, member_id):
        """ Add member to group. """
        group = find_group(name)
        member = find_entity(member_id)
        if not group.has_member(member.entity_id):
            group.add_member(member.entity_id)
        return {
            'member_type': member.entity_type,
            # id for the href builder, won't be shown in output
            'id': utils.get_entity_name(member) or member.entity_id,
            'member_id': member.entity_id,
            'member_name': utils.get_entity_name(member),
        }

    # DELETE /<group>/members/<member>
    #
    @db.autocommit
    @auth.require()
    @api.response(204, 'member removed')
    @api.response(404, 'group or member not found')
    def delete(self, name, member_id):
        """ Remove member from group. """
        group = find_group(name)
        member = find_entity(member_id)
        if group.has_member(member.entity_id):
            group.remove_member(member.entity_id)
        return '', 204


@api.route('/<string:name>/posix', endpoint='posixgroup')
class PosixGroupResource(Resource):
    """Resource for the POSIX information of a group."""

    # GET /<group>/posix
    #
    @auth.require()
    @api.response(200, 'posix data', PosixGroup)
    @api.response(404, 'group not found')
    @api.marshal_with(PosixGroup)
    @api.doc(params={'name': 'group name'})
    def get(self, name):
        """Get POSIX group information."""
        gr = find_group(name)
        return {
            'name': name,
            'id': gr.entity_id,
            'posix': hasattr(gr, 'posix_gid'),
            'posix_gid': getattr(gr, 'posix_gid', None)
        }


@api.route('/', endpoint='group-list')
class GroupListResource(Resource):
    """Resource for list of groups."""

    # GET /
    #
    group_search_filter = api.parser()
    group_search_filter.add_argument(
        'name',
        type=text_type,
        help='Filter by name. Accepts * and ? as wildcards.')
    group_search_filter.add_argument(
        'description',
        type=text_type,
        help='Filter by description. Accepts * and ? as wildcards.')
    group_search_filter.add_argument(
        'context',
        type=text_type,
        dest='spread',
        help='Filter by context. Accepts * and ? as wildcards.')
    group_search_filter.add_argument(
        'member_id',
        type=int,
        action='append',
        help='Filter by memberships. Only groups that have member_id as a '
             'member will be returned. If member_id is a sequence, the group '
             'is returned if any of the IDs are a member of it.')
    group_search_filter.add_argument(
        'indirect_members',
        type=bool,
        help='If true, alter the behavior of the member_id filter to also '
             'include groups where member_id is an indirect member.')
    group_search_filter.add_argument(
        'filter_expired',
        type=bool,
        help='If false, include expired groups.')
    group_search_filter.add_argument(
        'expired_only',
        type=bool,
        help='If true, only include expired groups.')
    group_search_filter.add_argument(
        'creator_id',
        type=int,
        help='Filter by creator entity ID.')

    @auth.require()
    @api.marshal_with(GroupListItem, as_list=True, envelope='groups')
    @api.doc(parser=group_search_filter)
    def get(self):
        """List groups."""
        args = self.group_search_filter.parse_args()
        filters = {key: value for (key, value) in args.items() if
                   value is not None}

        gr = Factory.get('Group')(db.connection)

        groups = list()
        for row in gr.search(**filters):
            group = dict(row)
            group.update({
                'id': group['name'],
                'name': group['name'],
            })
            groups.append(group)
        return groups
