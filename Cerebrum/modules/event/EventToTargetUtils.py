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
from functools import partial
# TODO: Make ChangeType go away. We should have EventTypes
from Cerebrum.Errors import CerebrumError
from Cerebrum.Errors import NotFoundError
from Cerebrum.Utils import Factory
from Cerebrum.Utils import argument_to_sql


class EventToTargetUtils(object):
    u"""Utility class for maintainig event to target system relations.

    This table will typically be consulted under population of events
    in the EventLog, in order to create an unique event for relevant
    target systems.
    """

    def __init__(self, db):
        self.db = db
        self.co = Factory.get('Constants')(self.db)
        self.clconst = Factory.get('CLConstants')(self.db)

        self._event_type_to_code = partial(self.__get_const,
                                           self.clconst.ChangeType)
        self._target_system_to_code = partial(self.__get_const,
                                              self.co.TargetSystem)

    def __get_const(self, const_type, value):
        u""" A human2constant that accepts Constants as input.

        :raises CerebrumError:
            If the constant doesn't exist.
        """
        if isinstance(value, const_type):
            const = value
        else:
            const = self.co.human2constant(value, const_type=const_type)
        if const is None:
            raise CerebrumError('No {!r} code {!r}'.format(const_type,
                                                           value))
        return const

    def get_mappings(self, target_systems=None, event_types=None):
        u""" Gets current event-to-target mappings.

        :type target_system:
            NoneType, int, str, TargetSystem, list
        :param target_system:
            Filter by a single target system constant, or a list of target
            system constants. A `None` value returns all target systems
            (default).

        :type event_types:
            NoneType, int, str, TargetSystem, list
        :param event_types:
            Filter by a single event (change type) constant, or a list of event
            constants. A `None` value returns all events (default).

        :returns list:
            Returns a list of db_rows. Columns:
              (target_system, event_type)
        """
        filters = set()
        args = dict()

        if target_systems:
            filters.add(
                argument_to_sql(target_systems, 'target_system', args,
                                lambda x: int(self._target_system_to_code(x))))
        if event_types:
            filters.add(
                argument_to_sql(event_types, 'event_type', args,
                                lambda x: int(self._event_type_to_code(x))))

        sql = """SELECT target_system, event_type
        FROM [:table schema=cerebrum name=event_to_target]"""
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        return self.db.query(sql, args)

    def populate(self, target_system, event_type):
        """Populate event_to_target with new entries.

        @type target_system: int or str
        @param target_system: The code(_str) for the target system

        @type event_type: int or str
        @param event_type: The code(_str) for the event/change type
        """
        v = {'ts': int(self._target_system_to_code(target_system)),
             'et': int(self._event_type_to_code(event_type))}
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
        u""" Removes event-to-target mappings.

        :type target_system:
            NoneType, int, str, TargetSystem, list
        :param target_system:
            Delete mappings that matches a given target system, or list of
            target systems. A `None` value will match all target systems
            (default).

        :type event_type:
            NoneType, int, str, TargetSystem, list
        :param event_types:
            Delete mappings that matches a given change type, or list of
            change types. A `None` value will match all change types
            (default).
        """
        filters = set()
        args = dict()

        if target_system:
            filters.add(
                argument_to_sql(target_system, 'target_system', args,
                                lambda x: int(self._target_system_to_code(x))))
        if event_type:
            filters.add(
                argument_to_sql(event_type, 'event_type', args,
                                lambda x: int(self._event_type_to_code(x))))

        sql = """DELETE FROM [:table schema=cerebrum name=event_to_target]"""
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        try:
            self.db.execute(sql, args)
        except self.db.IntegrityError:
            # TODO: Should we really pass silently?
            pass

    def update_target_system(self, target_system, event_types):
        u""" Update event types for a given target system.

        :type target_system:
            int, str, TargetSystem
        :param target_system:
            The target system to update.

        :type event_types:
            list
        :param event_types:
            A new, complete list of event (change type) constants that the
            `target system` should map to.

        :return tuple:
            Returns a tuple with two sets. The first set contains event types
            that have been added, the second contains event types that have
            been removed.
        """
        target_system = self._target_system_to_code(target_system)
        event_types = [self._event_type_to_code(t) for t in event_types]
        added = set()
        removed = set()

        current = [self.clconst.ChangeType(x['event_type']) for x in
                   self.get_mappings(target_systems=target_system)]

        for ct in event_types:
            if ct not in current:
                self.populate(int(target_system), int(ct))
                added.add(ct)

        for ct in current:
            if ct not in event_types:
                self.delete(target_system=int(target_system),
                            event_type=int(ct))
                removed.add(ct)
        return (added, removed)
