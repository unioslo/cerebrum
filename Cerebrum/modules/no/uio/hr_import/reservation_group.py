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
Update employee reservation groups.

Reservation groups are legacy consent functionality, and is used to track
employee publication opt-outs from the HR system.
"""
import logging

from Cerebrum.group.template import GroupTemplate

logger = logging.getLogger(__name__)


DFO_RESERVATION_GROUP = GroupTemplate(
    group_name='DFO-elektroniske-reservasjoner',
    group_description='Employees reserved from publication',
    group_type='internal-group',
    group_visibility='A',
    conflict=GroupTemplate.CONFLICT_UPDATE,
)


class ReservationGroupUpdater(object):
    """ Update reservation groups.  """

    def __init__(self, database):
        self.db = database

    def _get_group(self):
        """ The Cerebrum.Group.Group reservation group object. """
        return DFO_RESERVATION_GROUP(self.db)

    def set(self, person_id, reserve):
        """
        Update reservation group.

        :type person_id: int
        :type reserve: bool
        """
        group = self._get_group()
        is_reserved = group.has_member(person_id)

        if reserve and not is_reserved:
            logger.info('person_id=%r, not reserved -> reserved', person_id)
            group.add_member(person_id)
        elif not reserve and is_reserved:
            logger.info('person_id=%r, reserved -> not reserved', person_id)
            group.remove_member(person_id)
