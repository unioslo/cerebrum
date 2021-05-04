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

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)


class ReservationGroupUpdater(object):
    """ Update reservation groups.  """

    group_name = 'DFO-elektroniske-reservasjoner'

    def __init__(self, database):
        self.db = database

    def _get_reservation_group(self):
        """ Get or create the group used to store reservations

        @rtype:  Group
        @return: The owner Group object that was found/created.
        """
        gr = Factory.get('Group')(self.db)
        try:
            gr.find_by_name(self.group_name)
            return gr
        except Errors.NotFoundError:
            # Group does not exist, must create it
            pass
        logger.info('Creating reservation group %r', self.group_name)
        co = Factory.get('Constants')(self.db)
        ac = Factory.get('Account')(self.db)
        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        gr.populate(
            creator_id=ac.entity_id,
            visibility=co.group_visibility_all,
            name=self.group_name,
            description="Employees reserved from publication",
            group_type=co.group_type_internal)
        gr.write_db()
        return gr

    @property
    def group(self):
        """ The Cerebrum.Group.Group reservation group object. """
        if not hasattr(self, '_group'):
            self._group = self._get_reservation_group()
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
