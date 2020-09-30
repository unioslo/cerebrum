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
Update employee reservation groups.

Reservation groups are legacy consent functionality, and is used to track
employee publication opt-outs from the HR system.
"""
import logging

from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)


class ReservationGroupUpdater(object):
    """ Update reservation groups.  """

    group_name = 'SAP-elektroniske-reservasjoner'

    def __init__(self, database):
        self.db = database

    @property
    def group(self):
        """ The Cerebrum.Group.Group reservation group object. """
        if not hasattr(self, '_group'):
            group = Factory.get('Group')(self.db)
            group.find_by_name(self.group_name)
            self._group = group
        return self._group

    def set(self, person_id, reserve):
        """
        Update reservation group.

        :type person_id: int
        :type reserve: bool
        """
        is_reserved = self.group.has_member(person_id)

        if reserve and not is_reserved:
            logger.debug('person_id=%r, not reserved -> reserved', person_id)
            self.group.add_member(person_id)
        elif not reserve and is_reserved:
            logger.debug('person_id=%r, reserved -> not reserved', person_id)
            self.group.remove_member(person_id)
