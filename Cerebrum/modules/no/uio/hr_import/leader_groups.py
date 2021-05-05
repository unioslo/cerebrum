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
Leader group module.

This module defines the Cerebrum leader groups, ``adm-leder-<ou>``.  These
groups mirror manager roles from the hr system.
"""
import logging

import cereconf

from Cerebrum.Utils import Factory

from Cerebrum.modules.automatic_group.structure import (
    get_automatic_group,
    update_memberships,
)

logger = logging.getLogger(__name__)

LEADER_GROUP_PREFIX = 'adm-leder-'


def get_leader_group(db, identifier):
    return get_automatic_group(db, identifier, LEADER_GROUP_PREFIX)


class LeaderGroupUpdater(object):
    """
    Update leader groups from affs.
    """

    def __init__(self, db, source_system):
        self.db = db
        self.const = Factory.get('Constants')(self.db)
        self.source_system = source_system

    def _get_current_groups(self, person_id):
        gr = Factory.get('Group')(self.db)

        return (r['group_id'] for r in
                gr.search(member_id=person_id,
                          name=LEADER_GROUP_PREFIX + '*',
                          group_type=self.const.group_type_affiliation,
                          filter_expired=True,
                          fetchall=False))

    def get_leader_group_ids(self, hr_ous):
        """Convert a set of OU's into a set of leader group ids

        :param hr_ous: Cerebrum OU-objects of OUs where the person is a leader
        """
        leader_group_ids = set()
        for hr_ou in hr_ous:
            stedkode = hr_ou.get_stedkode()
            leader_group_id = get_leader_group(self.db, stedkode).entity_id
            leader_group_ids.add(leader_group_id)
        return leader_group_ids

    def sync(self, person_id, hr_ous):
        require_memberships = self.get_leader_group_ids(hr_ous)
        current_memberships = set(self._get_current_groups(person_id))

        if require_memberships == current_memberships:
            return

        logger.info('Updating person_id=%r leader groups (add=%r, remove=%r)',
                    person_id,
                    require_memberships - current_memberships,
                    current_memberships - require_memberships)

        update_memberships(Factory.get('Group')(self.db),
                           person_id,
                           current_memberships,
                           require_memberships)
