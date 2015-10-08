#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2013-2015 University of Oslo, Norway
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
"""Utility class for maintainig event to target system relations"""
# TODO: Make ChangeType go away. We should have EventTypes

from Cerebrum.Utils import Factory
from Cerebrum.Errors import *

class EventToTargetUtils(object):
    """Utility class for maintainig event to target system relations.
    
    This table will typically be consulted under population of events
    in the EventLog, in order to create an unique event for relevant
    target systems"""
    def __init__(self, db):
        self.db = db
        self.co = Factory.get('Constants')(self.db)

    def populate(self, target_system, event_type):
        """Populate event_to_target with new entries.

        @type target_system: int or str
        @param target_system: The code(_str) for the target system

        @type event_type: int or str
        @param event_type: The code(_str) for the event/change type
        """
        v = {'ts': int(self.co.TargetSystem(target_system)),
                'et': int(self.co.ChangeType(*event_type.split(':')))}
        # (target_system, event_type) has an UNIQUE constraint.
        # Calling this method with the same pair of values will
        # result in an exception.
        try:
            self.db.execute("""
                INSERT INTO
                [:table schema=cerebrum name=event_to_target]
                (target_system, event_type)
                VALUES (:ts, :et)""", v)
        except self.db.IntegrityError:
            # TODO: Should we really pass silently?
            pass

    def delete(self, target_system=None, event_type=None):
        """Remove event to target system bindings

        @type target_system: int or str
        @param target_system: The code(_str) for the target system

        @type event_type: int or str
        @param event_type: The code(_str) for the event/change type
        """
        if not target_system and not event_type:
            raise CerebrumError('Must specify target_system and/or event_type')
        selector = []
        if target_system:
            selector.append('target_system = %d' % \
                            int(self.co.TargetSystem(target_system)))
        if event_type:
            selector.append('event_type = %d' % \
                    int(self.co.ChangeType(*event_type.split(':'))))
        try:
            self.db.execute("""
                DELETE FROM
                [:table schema=cerebrum name=event_to_target]
                WHERE %s""" % ' AND '.join(selector))
        except self.db.IntegrityError:
            # TODO: Should we really pass silently?
            pass


