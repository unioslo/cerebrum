# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
Utils for defining and creating (internal) Cerebrum groups.

Certain modules in Cerebrum depend on specific internal groups to exist.  The
GroupTemplate can be used to define these groups on a module level, without any
db-interaction.  The GroupTemplate will then fetch/verify/create the group on
demand.

Notable issues
--------------
If changelog is in use, and no cl_init has been issued, groups cannot
be created.  Use py:meth:`GroupTemplate.require` for these scripts.

Example
-------

::

    foo_group = GroupTemplate(
        group_name='foo',
        group_description='Group of foo',
        group_type='internal-group',
        group_visibility='A',
        conflict=GroupTemplate.CONFLICT_ERROR,
    )

    def add_to_foo(db, entity_id):
        # fetch or create group:
        group = foo_group(db)

        if not group.has_member(entity_id):
            group.add_member(entity_id)
"""
import logging
import cereconf

from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils import reprutils

logger = logging.getLogger(__name__)


def _get_group_by_name(db, group_name):
    gr = Factory.get('Group')(db)
    gr.find_by_name(group_name)
    return gr


def _get_account_by_name(db, account_name):
    ac = Factory.get('Account')(db)
    ac.find_by_name(account_name)
    return ac


def _get_default_creator_id(db):
    return _get_account_by_name(db, cereconf.INITIAL_ACCOUNTNAME).entity_id


def _get_group_type(const, group_type):
    return const.get_constant(Constants._GroupTypeCode, group_type)


def _get_group_visibility(const, group_visibility):
    return const.get_constant(Constants._GroupVisibilityCode, group_visibility)


class GroupTemplate(reprutils.ReprFieldMixin):
    """
    Template for a group that should exist in Cerebrum.

    """
    repr_module = False
    repr_id = False
    repr_fields = ('group_name',)

    # Conflict resolution for groups with differing attributes:
    #
    # Raise an error if group exists with different attributes
    CONFLICT_ERROR = 'error'
    #
    # Update attributes if group exists
    CONFLICT_UPDATE = 'update'
    #
    # Ignore and use group if exists with different attributes
    CONFLICT_IGNORE = 'ignore'

    def __init__(self, group_name, group_description,
                 group_type='internal-group',
                 group_visibility='A',
                 conflict=CONFLICT_UPDATE):
        self.group_name = group_name
        self.group_description = group_description
        self.group_type = group_type
        self.group_visibility = group_visibility
        if conflict not in (self.CONFLICT_ERROR, self.CONFLICT_UPDATE,
                            self.CONFLICT_IGNORE):
            raise ValueError('invalid conflict resolution: ' + repr(conflict))
        self.conflict_resolution = conflict

    def _create(self, db):
        group = Factory.get('Group')(db)
        group.populate(
            name=self.group_name,
            description=self.group_description,
            group_type=_get_group_type(group.const, self.group_type),
            visibility=_get_group_visibility(group.const,
                                             self.group_visibility),
            creator_id=_get_default_creator_id(db),
        )
        group.write_db()
        logger.info("created group: %s (%d)",
                    group.group_name, group.entity_id)
        return group

    def _update(self, group):
        wants = {
            'description': self.group_description,
            'group_type': _get_group_type(group.const, self.group_type),
            'expire_date': None,
            'visibility': _get_group_visibility(group.const,
                                                self.group_visibility),
        }

        update = {}
        for k, v in wants.items():
            if getattr(group, k) != v:
                update[k] = v

        if not update:
            return

        if self.conflict_resolution == self.CONFLICT_UPDATE:
            for k, v in update.items():
                setattr(group, k, v)
            group.write_db()
            logger.info('updated group: %s (%d) - %r',
                        group.group_name, group.entity_id, tuple(update))
        elif self.conflict_resolution == self.CONFLICT_ERROR:
            raise ValueError('incompatible group %s (%d) - %r differs'
                             % (group.group_name, group.entity_id,
                                tuple(update)))
        elif self.conflict_resolution == self.CONFLICT_IGNORE:
            logger.warning('group needs update: %s (%d) - %r',
                           group.group_name, group.entity_id,
                           tuple(update))
        else:
            raise RuntimeError('invalid conflict resolution: '
                               + repr(self.conflict_resolution))

    def require(self, db):
        """ Require group to exist. """
        return _get_group_by_name(db, self.group_name)

    def __call__(self, db):
        """ Get or create the group defined by this template. """
        try:
            group = _get_group_by_name(db, self.group_name)
            logger.info('found group: %s (%d)',
                        group.group_name, group.entity_id)
        except Errors.NotFoundError:
            group = self._create(db)
        else:
            self._update(group)
        return group
