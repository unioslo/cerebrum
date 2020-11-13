# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
"""
Group tree utilities.

Group trees
-----------
Group trees are collections of groups where:

1. All the groups are of a given group type (``Group.group_type``)

   All groups of this group type are considered members of a given tree.  No
   other groups should be assigned the given ``group_type``.

2. Any one group in the hierarchy can only be a member of *one parent group* of
   the same type.

   This ensures that the groups form an actual tree structure.  However, groups
   in the hierarchy can be members of groups outside of the hierarhcy (other
   types).

   .. todo::
      This is an important step if the hierarchy ever needs to be re-organized.
      We may omit this requirement if there is a "full sync" of the hierarchy
      somewhere.

3. All group memberships within the hierarhcy are automatically maintained.

   Groups outside of the hierarchy (other group_types) cannot be members of
   groups within the hierarchy (this is the opposite of #2).  Other member
   types are updated by the hierarhcy sync class in this module
   (or a subclass).
"""
import datetime

import six

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory


def _get_account_by_name(db, account_name):
    ac = Factory.get('Account')(db)
    ac.find_by_name(account_name)
    return ac


def _get_default_visibility(db):
    co = Factory.get('Constants')(db)
    return co.group_visibility_all


def _date(date_or_mxdatetime):
    if date_or_mxdatetime is None:
        return None
    if isinstance(date_or_mxdatetime, datetime.date):
        return date_or_mxdatetime
    return date_or_mxdatetime.pydate()


class ExpireDateCallback(object):
    """
    Set a hard coded group expire_date.
    """

    def __init__(self, expire_date):
        self.expire_date = expire_date

    def __call__(self, group_obj):
        expire_date = _date(group_obj.expire_date)
        if expire_date != self.expire_date:
            group_obj.expire_date = self.expire_date
            return True
        return False


class ExpireThresholdCallback(object):
    """
    Push back an expire date.
    """

    def __init__(self, delta, threshold):
        self.delta = delta
        self.threshold = threshold

    def __call__(self, group_obj, _today=None):
        today = _today or datetime.date.today()
        expire_date = _date(group_obj.expire_date)
        if not expire_date or today + self.threshold < expire_date:
            group_obj.expire_date = expire_date + self.delta
            return True
        return False


class DescriptionCallback(object):
    """
    Set or update group description.
    """

    def __init__(self, description, update=False):
        self.description = description
        self.update_desc = update

    def __call__(self, group_obj):
        if self.update_desc:
            if group_obj.description != self.description:
                group_obj.description = self.description
                return True
        else:
            if not group_obj.description:
                group_obj.description = self.description
                return True
        return False


class GroupTypeCallback(object):
    """
    Update group group_type.
    """

    def __init__(self, group_type):
        self.group_type = group_type

    def __call__(self, group_obj):
        if group_obj.group_type != self.group_type:
            group_obj.group_type = self.group_type
            return True
        return False


# TODO: A spread callback? Default spreads callback?


def assert_group(db,
                 group_name,
                 default_group_type,
                 default_group_visibility,
                 creator_id,
                 callbacks):
    """
    Get or create a group with name `group_name`.

    If the group does not exist, it is created with the given defaults (type,
    visibility, creator_id)

    An optional set of callbacks can be used to update the given group.
    """
    group_obj = Factory.get('Group')(db)
    try:
        group_obj.find_by_name(group_name)
    except Errors.NotFoundError:
        group_obj.populate(
            name=group_name,
            group_type=default_group_type,
            visibility=default_group_visibility,
            creator_id=creator_id,
        )
        group_obj.write_db()

    if any(callback(group_obj) for callback in callbacks):
        group_obj.write_db()

    return group_obj


def get_group(db, group_name):
    group_obj = Factory.get('Group')(db)
    group_obj.find_by_name(group_name)
    return group_obj


class GroupFactory(object):
    """
    Wrap assert_group with defaults.
    """

    def __init__(self, db, group_type, visibility):
        self.db = db
        self.group_type = group_type
        self.visibility = visibility

    @property
    def creator_id(self):
        return _get_account_by_name(
            self.db,
            cereconf.INITIAL_ACCOUNTNAME,
        ).entity_id

    # TODO: abstractprop?
    @property
    def callbacks(self):
        return []

    def __call__(self, group_name):
        return assert_group(
            group_name=group_name,
            default_group_type=self.group_type,
            default_group_visibility=self.visibility,
            creator_id=self.creator_id,
        )


def get_tree_memberships(db, member_id, member_type, group_type):
    gr = Factory.get('Group')(db)
    return set(row['group_id']
               for row in gr.search_members(
                   member_id=member_id,
                   member_type=member_type,
                   group_type=group_type,
                   indirect_members=False,
                   member_filter_expired=False))

#
# Translating roles
#
# Takes some sort of input (e.g. aff + ou, role name + role hierarhcy
# definitions), and generates membership group, and all group "parents"
#


class GroupNameFormatter(object):
    """
    Utility for formatting ou tree group names.

    >>> get_name = GroupNameFormatter('prefix', 'leaf', separator='-')

    >>> get_name('foo', 'bar', leaf=True)
    'leaf-foo-bar'
    >>> get_name('foo', 'bar', leaf=False)
    'prefix-foo-bar'

    >>> [get_name(n, leaf=(not i))
    ...  for i, n in enumerate(['foo', 'bar', 'baz'])]
    ['leaf-foo', 'prefix-bar', 'prefix-baz']
    """

    separator = '-'

    def __init__(self, prefix, leaf_prefix=None, separator=separator):
        self.prefix = prefix
        if leaf_prefix:
            self.leaf_prefix = leaf_prefix
        else:
            self.leaf_prefix = prefix
        self.separator = separator

    def _validate(self, part):
        if self.separator in part:
            raise ValueError()
        return part

    def _normalize(self, part):
        return part.lower()

    def __call__(self, parts, leaf=False):
        prefix = self.leaf_prefix if leaf else self.prefix

        return self.separator.join(
            (prefix,) + (self._validate(self._normalize(part)) for
                         part in parts))


class AffiliationGroupTranslator(object):
    """
    Find and format group names for a given ou.

    E.g. an employee group tree:

    ::

        aff_group_names = GroupNameFormatter(prefix='meta-ansatt',
                                             leaf_prefix='ansatt',
                                             separator='-')
        employee_groups = AffiliationGroupTranslator(
            db,
            ou_perspective=co.perspective_sap,
            name_formatter=aff_group_names)


        # get groups for affiliation ``ANSATT@352100``
        ou.find(ou_id)
        group_tree = tuple(aff_groups(ou))
    """

    def __init__(self, db, ou_perspective, name_formatter,
                 leaf_group=True):
        self.db = db
        self.perspective = ou_perspective
        self.formatter = name_formatter

    def _get_ou(self, ou_id):
        """ Get an OU object from its ou_id. """
        ou = Factory.get('OU')(self.db)
        ou.find(ou_id)
        return ou

    def _iter_ous(self, ou_id):
        """ Iterate over all ous from a given ou to to a root ou. """
        next_id = ou_id
        while next_id:
            ou = self._get_ou(next_id)
            next_id = ou.get_parent(self.perspective)
            yield ou

    def format_group_name(self, ou, is_leaf=False):
        """ Format a group name for a given ou. """
        ou_identifier = ou.get_stedkode()
        return self.formatter((ou_identifier,), is_leaf=is_leaf)

    def _generate_names(self, ou):
        # Yield an extra leaf group (ansatt-<sko>) in addition to groups for
        # the tree structure (meta-ansatt-<sko>)
        if self.leaf_group:
            yield self.format_group_name(ou, is_leaf=True)

        for ou in self._iter_ous(ou):
            yield self.format_group_name(ou, is_leaf=False)

    def __call__(self, ou):
        """ Get a collection of groups from an OU. """
        return tuple(self._generate_names(ou))


# Building the tree from a path
#     Whenever a *leaf* group from a *path* needs to be updated, we start off
#     by asserting that the *path* exists as expected within the tree:
#
#     1. Ensure that each of the groups exists:
#     2. Ensure that each group is only a member of its parent group:


class GroupTreeParams(object):
    """ Settings for a group tree.  """

    tree_name = 'employee affiliation groups'

    # TODO: abstractprop
    group_type = 'group_type_manual'

    # TODO: abstractprop
    # TODO: Do we even want this to be customizeable?
    #       What is the use-case for visibility?
    visibility = 'ALL'

    # TODO: abstractprop
    # TODO: perspective
    # TODO: This really belongs to the translation
    perspective = 'SAP'

    # TODO: abstractprop
    # TODO: creator
    creator_name = cereconf.INITIAL_ACCOUNTNAME

    def __init__(self):
        pass


class GroupTreeBuilder(object):

    def __init__(self, db, params):
        self.db = db
        self._params = params

    @property
    def _co(self):
        return Factory.get('Constants')(self.db)

    @property
    def group_type(self):
        const = self._co.GroupType(self._params.group_type)
        int(const)
        return const

    @property
    def visibility(self):
        const = self._co.GroupVisibility(self._params.visibility)
        int(const)
        return const

    @property
    def creator(self):
        return _get_account_by_name(self.db, self._params.creator_name)

    @property
    def description(self):
        return "Part of group tree '%s'".format(six.text_type(self.group_type))

    def assert_group(self, group_name):

        callbacks = [
            DescriptionCallback(self.description),
        ]

        group = assert_group(
            self.db,
            group_name=group_name,
            default_group_type=self.group_type,
            callbacks=callbacks,
            creator_id=self.creator.entity_id,
            visibility=self.visibility,
        )

        return group

    def assert_path(self, group_names):

        # TODO: This could *probably* be done *much* more efficient

        name_cache = {}
        id_cache = {}

        # Create and cache all groups
        for group_name in group_names:
            group = self.assert_group(group_name)
            name_cache[group.group_name] = group
            id_cache[group.entity_id] = group

        # Identify wanted parent group memberships
        parent_ids = {}
        prev = None
        for group_name in reversed(group_names):
            parent_ids[group_name] = prev
            prev = name_cache[group_name].entity_id

        # update tree memberships for each group
        for group_name in group_names:
            group = group_names[group_name]
            parent_id = parent_ids[group_name]
            to_add = set((parent_id,) if parent_id else ())
            to_remove = set()

            # identify invalid parent group memberships
            for group_id in get_tree_memberships(group.entity_id,
                                                 group.entity_type,
                                                 self.group_type):
                if group_id == parent_id:
                    # correct parent already exists
                    to_add.remove(group_id)
                else:
                    # incorrect parent, must be removed
                    to_remove.add(group_id)

            # update parent memberships
            for parent_id in to_remove:
                id_cache[parent_id].remove_member(group.entity_id)
            for parent_id in to_add:
                id_cache[parent_id].add_member(group.entity_id)

        return tuple(name_cache[name] for name in group_names)


#
# Updating roles
#
#    1. Translate role into path
#    2. Ensure the tree structure itself is in sync with the *path*
#    3. Ensure that the *leaf* group is up to date with a given set of members.
#

def update_tree_memberships(account, builder, paths):

    account_memberships = set()
    for path in paths:
        # each "path" is a list of group names in a subtree
        leaf = builder.assert_path(path)[0]
        account_memberships.add(leaf.entity_id)

    current_memberships = get_tree_memberships(account.entity_id,
                                               account.entity_type,
                                               builder.group_type)

    for group_id in (current_memberships - account_memberships):
        group = get_group(group_id)
        group.remove_member(account.entity_id)

    for group_id in (account_memberships - current_memberships):
        group = get_group(group_id)
        group.add_member(account.entity_id)
