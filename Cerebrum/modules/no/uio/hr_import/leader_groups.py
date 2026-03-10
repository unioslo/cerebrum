# -*- coding: utf-8 -*-
#
# Copyright 2020-2026 University of Oslo, Norway
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
Manager group module.

This module defines the Cerebrum groups for managers, ``adm-leder-<ou>``.
These groups mirror manager roles from the hr system.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum.Utils import Factory
from Cerebrum.group.template import GroupTypeTemplate
from Cerebrum.modules.automatic_group import template_helpers

logger = logging.getLogger(__name__)


class ManagerGroups(template_helpers.AutomaticGroupCache):
    """ Manager group template, rules, and cache. """

    template = GroupTypeTemplate(
        # TODO: Fix this - it should probably have it's own type, or a more
        # generic type:
        group_type="affiliation-group",
        # TODO: Fix this - it should probably be "A":
        group_visibility="I",
        conflict=GroupTypeTemplate.CONFLICT_UPDATE,
    )

    prefix = "adm-leder-"
    description_fmt = "Administrerende leder ved {}"
    required_spreads = frozenset(("group@ldap", "AD_group", "NIS_ng@uio"))


class ManagerSupergroups(ManagerGroups):
    """ Manager supergroup template, rules, and cache. """

    prefix = "meta-adm-leder-"
    description_fmt = "Administrerende ledere ved {} og underenheter"


def get_manager_group(db, identifier):
    return ManagerGroups.assert_group(db, identifier)


def _get_group_by_id(db, group_id):
    gr = Factory.get('Group')(db)
    gr.find(group_id)
    return gr


def update_memberships(db, entity_id, current_memberships, wanted_memberships):
    """Make sure entity 'entity_id' is member of groups 'wanted_membeships'

    This method differentiates the current and wanted memberships of an entity
    and makes the necessary updates to the entity's memberships.

    :type db: Cerebrum.database.Database
    :param entity_id: entity to add
    :type current_memberships: set
    :type wanted_memberships: set
    """
    to_add = set(wanted_memberships) - set(current_memberships)
    to_remove = set(current_memberships) - set(wanted_memberships)
    for group_id in to_add:
        gr = _get_group_by_id(db, group_id)
        # If we blindly trust the current_memberships input, we may run into
        # problems.  Often, the search for current memberships will *omit
        # expired groups*, and the wanted_memberships *includes* expired
        # groups.
        if not gr.has_member(entity_id):
            gr.add_member(entity_id)
    for group_id in to_remove:
        gr = _get_group_by_id(db, group_id)
        if gr.has_member(entity_id):
            gr.remove_member(entity_id)


class ManagerGroupSync(object):
    """ Update manager groups.  """

    def __init__(self, db):
        self.db = db
        self.const = Factory.get('Constants')(self.db)

    def _fetch_group_ids(self, ou_objects):
        """
        Convert a collection of OU objects into a set of manager group ids

        :type: ou_objects: list[Cerebrum.OU.OU]
        :param list ou_objects: List of OUs where the person is a manager
        """
        for ou in ou_objects:
            stedkode = ou.get_stedkode()
            # TODO: This group may not exist, e.g. if it's quarantined...
            #       We should probably use the same criterias as the
            #       manager_groups module.
            mgr_group = ManagerGroups.assert_group(self.db, stedkode)
            yield mgr_group.entity_id

    def sync(self, person_id, ou_objects):
        """
        Ensure that person_id is a manager at the given org units.

        :param person_id:
            entity id of the person to sync

        :param ou_objects:
            a sequence of Cerebrum.OU.OU objects with each location where this
            person is a manager (if any).
        """
        require_memberships = set(self._fetch_group_ids(ou_objects))
        logger.debug("manager groups for person_id=%r: %r",
                     person_id, require_memberships)

        current_memberships = ManagerGroups.list_groups(
            self.db,
            include_expired=True,
            member_id=int(person_id),
        )
        if require_memberships == current_memberships:
            return

        logger.info(
            "manager group changes for person_id=%r: add=%r, remove=%r",
            person_id, require_memberships - current_memberships,
            current_memberships - require_memberships)

        update_memberships(self.db,
                           person_id,
                           current_memberships,
                           require_memberships)
